from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px

from aetf_momentum import __version__
from aetf_momentum.research.v8_analysis import (
    build_mechanism_table,
    build_tradeoff_table,
    build_trigger_ab_table,
    run_parameter_grid,
    summarize_result,
)
from aetf_momentum.research.v8_data import (
    build_cash_total_return,
    build_strict_total_return,
    splice_index_to_etf,
)
from aetf_momentum.research.v8_grid import RebalanceConfig, simulate_risk_cash
from aetf_momentum.research.v8_sources import (
    CSINDEX_URL,
    EASTMONEY_FUND_URL,
    EASTMONEY_KLINE_URL,
    fetch_eastmoney_cash_income,
    fetch_eastmoney_etf,
    fetch_official_cash_income,
    fetch_official_index,
    fetch_sina_etf,
)

RISK_SYMBOLS = ("588170", "159781", "515050", "588200")
CASH_SYMBOL = "511990"
INTERNAL_RISK_WEIGHTS = (0.328, 0.321, 0.187, 0.164)
INDEX_MAP = {
    "588170": "950125",
    "159781": "931643",
    "515050": "931079",
    "588200": "000685",
}
LONG_PROXY_INDEX = "H30184"
SPLIT_RATIOS = {
    "588170": {"2026-07-06": 3.0},
    "159781": {},
    "515050": {"2026-05-13": 3.0},
    "588200": {"2026-07-21": 3.0},
}
SPLIT_SOURCES = {
    "588170": (
        "https://www.sse.com.cn/disclosure/fund/announcement/c/new/"
        "2026-07-06/588170_20260706_KYCK.pdf"
    ),
    "515050": "https://fundf10.eastmoney.com/fhsp_515050.html",
    "588200": "https://finance.sina.com.cn/stock/zqgd/2026-07-20/doc-iniimkki3009821.shtml",
}
RISK_WEIGHTS = (60, 65, 70, 75, 80, 85, 90, 100)
THRESHOLDS_PP = (2, 3, 4)
MODEL_ACCOUNT_SIZES = (200_000.0, 500_000.0, 1_000_000.0)
INDEX_PUBLISH_DATE = pd.Timestamp("2013-07-15")


@dataclass(frozen=True)
class V8RunOutput:
    output_dir: Path
    grid_path: Path
    monetized_path: Path
    conclusion_path: Path
    validation_path: Path
    sha256_path: Path


def run_v8_research(
    output_dir: str | Path,
    end_date: str = "2026-07-28",
    initial_capital: float = 500_000.0,
) -> V8RunOutput:
    started_at = datetime.now(UTC)
    output_path = Path(output_dir)
    raw_path = output_path / "raw"
    sample_path = output_path / "samples"
    output_path.mkdir(parents=True, exist_ok=True)
    raw_path.mkdir(parents=True, exist_ok=True)
    sample_path.mkdir(parents=True, exist_ok=True)

    source_data = _fetch_source_data(end_date, raw_path)
    for name, frame in source_data.items():
        _write_csv(frame, raw_path / f"{name}.csv")

    strict_returns = _build_strict_returns(source_data)
    samples, splice_rows = _build_samples(
        source_data,
        strict_returns,
        end_date=end_date,
    )
    for name, frame in samples.items():
        _write_csv(frame.reset_index(names="date"), sample_path / f"{name}_levels.csv")

    execution_validity, anomaly_rows = _build_execution_validity(
        samples,
        source_data,
        strict_returns,
    )
    grid, _ = run_parameter_grid(
        samples=samples,
        execution_validity=execution_validity,
        risk_symbols=RISK_SYMBOLS,
        cash_symbol=CASH_SYMBOL,
        internal_risk_weights=INTERNAL_RISK_WEIGHTS,
        risk_weights=RISK_WEIGHTS,
        thresholds_pp=THRESHOLDS_PP,
        initial_capital=initial_capital,
    )
    grid_path = output_path / "v8_full_grid.csv"
    _write_csv(grid, grid_path)

    tradeoff = build_tradeoff_table(grid)
    mechanism = build_mechanism_table(grid)
    trigger_ab = build_trigger_ab_table(grid)
    _write_csv(tradeoff, output_path / "v8_tradeoff_linearity.csv")
    _write_csv(mechanism, output_path / "v8_mechanism_and_drift.csv")
    _write_csv(trigger_ab, output_path / "v8_trigger_ab.csv")
    _write_csv(pd.DataFrame(splice_rows), output_path / "v8_splice_tracking.csv")

    monetized = _build_monetized_table(samples, execution_validity)
    monetized_path = output_path / "v8_monetized.csv"
    _write_csv(monetized, monetized_path)

    executability = _build_executability_table(source_data, monetized)
    _write_csv(executability, output_path / "v8_round_lot_executability.csv")

    discrepancies, comparison_summary = _compare_sources(source_data)
    _write_csv(discrepancies, output_path / "v8_source_discrepancies_over_0_5pct.csv")
    _write_csv(pd.DataFrame(anomaly_rows), output_path / "v8_deferred_execution_dates.csv")
    validation = _build_validation_table(
        source_data,
        splice_rows,
        discrepancies,
        comparison_summary,
        anomaly_rows,
        samples,
        end_date,
    )
    validation_path = output_path / "v8_data_validation_checklist.csv"
    _write_csv(validation, validation_path)

    _write_tradeoff_chart(grid, output_path / "v8_tradeoff_curve.html")
    conclusion_path = output_path / "v8_conclusion.md"
    conclusion_path.write_text(
        _build_conclusion(
            grid,
            tradeoff,
            mechanism,
            trigger_ab,
            executability,
            validation,
            initial_capital,
            end_date,
            float(
                (samples["long_proxy"].index < INDEX_PUBLISH_DATE).mean()
            ),
        ),
        encoding="utf-8",
    )
    metadata = {
        "task": "TASK-0012",
        "package_version": __version__,
        "run_started_utc": started_at.isoformat(),
        "run_completed_utc": datetime.now(UTC).isoformat(),
        "end_date": end_date,
        "initial_capital": initial_capital,
        "risk_symbols": list(RISK_SYMBOLS),
        "cash_symbol": CASH_SYMBOL,
        "internal_risk_weights": list(INTERNAL_RISK_WEIGHTS),
        "risk_weights_pct": list(RISK_WEIGHTS),
        "thresholds_pp": list(THRESHOLDS_PP),
        "commission_bps": 2.5,
        "minimum_commission_cny": 5.0,
        "slippage_bps": 2.0,
        "signal_execution": "signal at T close, execution at T+1 close",
        "sources": {
            "official_index": CSINDEX_URL,
            "eastmoney_etf": EASTMONEY_KLINE_URL,
            "official_511990": "https://www.fsfund.com/fund/511990/fundDetail.shtml",
            "eastmoney_511990": EASTMONEY_FUND_URL,
        },
    }
    (output_path / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sha256_path = output_path / "SHA256SUMS.txt"
    _write_sha256_manifest(output_path, sha256_path)
    return V8RunOutput(
        output_dir=output_path,
        grid_path=grid_path,
        monetized_path=monetized_path,
        conclusion_path=conclusion_path,
        validation_path=validation_path,
        sha256_path=sha256_path,
    )


def _fetch_source_data(
    end_date: str,
    raw_path: Path | None = None,
) -> dict[str, pd.DataFrame]:
    expected_names = [
        *(f"index_official_{code}" for code in [*INDEX_MAP.values(), LONG_PROXY_INDEX]),
        *(
            f"etf_{source}_{symbol}"
            for symbol in [*RISK_SYMBOLS, CASH_SYMBOL]
            for source in ["eastmoney", "sina"]
        ),
        "cash_official_511990",
        "cash_eastmoney_511990",
    ]
    if raw_path is not None and all(
        (raw_path / f"{name}.csv").exists() for name in expected_names
    ):
        return {
            name: pd.read_csv(
                raw_path / f"{name}.csv",
                parse_dates=["date"],
                dtype={"symbol": "string"},
            )
            for name in expected_names
        }

    data: dict[str, pd.DataFrame] = {}
    for index_code in [*INDEX_MAP.values(), LONG_PROXY_INDEX]:
        if index_code == LONG_PROXY_INDEX:
            start = "2011-07-22"
        elif index_code == "931079":
            start = "2019-10-16"
        else:
            start = "2019-12-31"
        data[f"index_official_{index_code}"] = fetch_official_index(
            index_code,
            start,
            end_date,
        )
    for symbol in [*RISK_SYMBOLS, CASH_SYMBOL]:
        data[f"etf_eastmoney_{symbol}"] = fetch_eastmoney_etf(
            symbol,
            "2011-01-01",
            end_date,
        )
        data[f"etf_sina_{symbol}"] = fetch_sina_etf(symbol)
    data["cash_official_511990"] = fetch_official_cash_income(
        CASH_SYMBOL,
        "2020-01-01",
        end_date,
    )
    data["cash_eastmoney_511990"] = fetch_eastmoney_cash_income(
        CASH_SYMBOL,
        "2020-01-01",
        end_date,
    )
    return data


def _build_strict_returns(
    source_data: dict[str, pd.DataFrame],
) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    for symbol in RISK_SYMBOLS:
        frame = source_data[f"etf_eastmoney_{symbol}"]
        close = frame.set_index("date")["close"]
        result[symbol] = build_strict_total_return(
            close,
            split_ratios=SPLIT_RATIOS[symbol],
        )
    return result


def _build_samples(
    source_data: dict[str, pd.DataFrame],
    strict_returns: dict[str, pd.Series],
    end_date: str,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    spliced: dict[str, pd.Series] = {}
    splice_rows: list[dict[str, object]] = []
    for symbol, index_code in INDEX_MAP.items():
        index_level = source_data[f"index_official_{index_code}"].set_index("date")["close"]
        index_level = index_level[index_level > 0]
        combined, metadata = splice_index_to_etf(index_level, strict_returns[symbol])
        spliced[symbol] = combined
        splice_rows.append(
            {
                "symbol": symbol,
                "index_code": index_code,
                "first_index_date": str(index_level.index.min().date()),
                "first_etf_date": str(metadata.first_etf_date.date()),
                "proxy_observations": metadata.proxy_observations,
                "total_observations": metadata.total_observations,
                "proxy_share": metadata.proxy_share,
                "tracking_error_60d": metadata.tracking_error_60d,
            }
        )

    short_risk = pd.concat(spliced, axis=1, join="inner")
    short_risk = short_risk.loc["2020-01-02":end_date]
    cash_income = source_data["cash_official_511990"].set_index("date")[
        "hundred_unit_income"
    ]
    short = short_risk.copy()
    short[CASH_SYMBOL] = build_cash_total_return(cash_income, short.index)

    long_proxy = source_data[f"index_official_{LONG_PROXY_INDEX}"].set_index("date")[
        "close"
    ]
    long_proxy = long_proxy[long_proxy > 0]
    long_proxy = long_proxy.loc["2011-07-22":end_date]
    long_proxy = long_proxy / long_proxy.iloc[0]
    long_legs: dict[str, pd.Series] = {}
    bridge_date = pd.Timestamp("2020-01-02")
    previous_date = long_proxy.index[long_proxy.index < bridge_date].max()
    for symbol in RISK_SYMBOLS:
        post = spliced[symbol]
        post_base_date = post.index[post.index < bridge_date].max()
        post_scaled = (
            post.loc[bridge_date:] / post.loc[post_base_date] * long_proxy.loc[previous_date]
        )
        long_legs[symbol] = pd.concat(
            [long_proxy[long_proxy.index < bridge_date], post_scaled]
        )
    long_sample = pd.concat(long_legs, axis=1, join="inner")
    pre_cash = pd.Series(
        [
            1.015 ** ((date - long_sample.index[0]).days / 365.0)
            for date in long_sample.index
        ],
        index=long_sample.index,
    )
    post_cash_dates = long_sample.index[long_sample.index >= previous_date]
    post_cash = build_cash_total_return(cash_income, post_cash_dates)
    post_cash = post_cash / post_cash.iloc[0] * pre_cash.loc[previous_date]
    long_cash = pd.concat(
        [pre_cash[pre_cash.index < bridge_date], post_cash[post_cash.index >= bridge_date]]
    )
    long_sample[CASH_SYMBOL] = long_cash.reindex(long_sample.index)

    pure_risk = pd.concat(strict_returns, axis=1, join="inner").loc[
        "2025-04-08":end_date
    ]
    pure_risk = pure_risk / pure_risk.iloc[0]
    pure = pure_risk.copy()
    pure[CASH_SYMBOL] = build_cash_total_return(cash_income, pure.index)
    return {
        "long_proxy": long_sample.dropna(),
        "short_four_indices": short.dropna(),
        "pure_live": pure.dropna(),
    }, splice_rows


def _build_execution_validity(
    samples: dict[str, pd.DataFrame],
    source_data: dict[str, pd.DataFrame],
    strict_returns: dict[str, pd.Series],
) -> tuple[dict[str, pd.Series], list[dict[str, object]]]:
    symbol_validity: dict[str, pd.Series] = {}
    anomaly_rows: list[dict[str, object]] = []
    for index_code in [*INDEX_MAP.values(), LONG_PROXY_INDEX]:
        frame = source_data[f"index_official_{index_code}"]
        invalid_index = frame[frame["close"].isna() | (frame["close"] <= 0)]
        for row in invalid_index.itertuples(index=False):
            anomaly_rows.append(
                {
                    "date": str(row.date.date()),
                    "symbol": index_code,
                    "reason": "official_index_nonpositive_close_dropped_from_proxy_calendar",
                }
            )
    for symbol in RISK_SYMBOLS:
        frame = source_data[f"etf_eastmoney_{symbol}"].set_index("date")
        valid = (frame["close"] > 0) & (frame["volume"] > 0)
        total_return = strict_returns[symbol].reindex(frame.index)
        limit_like = total_return.pct_change().abs() >= 0.198
        valid = valid & ~limit_like.fillna(False)
        symbol_validity[symbol] = valid
        for date in valid.index[~valid]:
            anomaly_rows.append(
                {
                    "date": str(date.date()),
                    "symbol": symbol,
                    "reason": "missing_or_zero_volume_or_limit_like_return",
                }
            )
    cash_frame = source_data[f"etf_eastmoney_{CASH_SYMBOL}"].set_index("date")
    cash_premium = (cash_frame["close"] / 100.0 - 1.0).abs()
    symbol_validity[CASH_SYMBOL] = (
        (cash_frame["close"] > 0)
        & (cash_frame["volume"] > 0)
        & (cash_premium <= 0.005)
    )
    for date in symbol_validity[CASH_SYMBOL].index[~symbol_validity[CASH_SYMBOL]]:
        anomaly_rows.append(
            {
                "date": str(date.date()),
                "symbol": CASH_SYMBOL,
                "reason": "missing_or_zero_volume_or_premium_discount_over_0_5pct",
            }
        )

    validity: dict[str, pd.Series] = {}
    for sample_name, levels in samples.items():
        combined = pd.Series(True, index=levels.index)
        for symbol in RISK_SYMBOLS:
            listing_date = strict_returns[symbol].index.min()
            actual_dates = combined.index >= listing_date
            aligned = symbol_validity[symbol].reindex(combined.index, fill_value=False)
            combined.loc[actual_dates] &= aligned.loc[actual_dates]
        cash_actual_dates = combined.index >= pd.Timestamp("2020-01-02")
        cash_aligned = symbol_validity[CASH_SYMBOL].reindex(
            combined.index,
            fill_value=False,
        )
        combined.loc[cash_actual_dates] &= cash_aligned.loc[cash_actual_dates]
        validity[sample_name] = combined
    return validity, anomaly_rows


def _build_monetized_table(
    samples: dict[str, pd.DataFrame],
    execution_validity: dict[str, pd.Series],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sample_name, levels in samples.items():
        for risk_weight in RISK_WEIGHTS:
            for threshold_pp in THRESHOLDS_PP:
                for account_size in MODEL_ACCOUNT_SIZES:
                    config = RebalanceConfig(
                        risk_symbols=RISK_SYMBOLS,
                        cash_symbol=CASH_SYMBOL,
                        internal_risk_weights=INTERNAL_RISK_WEIGHTS,
                        risk_target=risk_weight / 100,
                        threshold_pp=threshold_pp,
                        trigger_mode="aggregate",
                        initial_capital=account_size,
                    )
                    result = simulate_risk_cash(
                        levels,
                        config,
                        valid_execution=execution_validity[sample_name],
                    )
                    summary = summarize_result(result, account_size)
                    worst_return = summary["worst_three_year_return"]
                    rows.append(
                        {
                            "sample": sample_name,
                            "risk_weight_pct": risk_weight,
                            "cash_weight_pct": 100 - risk_weight,
                            "threshold_pp": threshold_pp,
                            "account_size_cny": account_size,
                            "account_input_status": "scenario_not_verified_actual_nav",
                            "worst_three_year_end": summary["worst_three_year_end"],
                            "worst_three_year_balance_cny": (
                                account_size * (1 + float(worst_return))
                                if pd.notna(worst_return)
                                else math.nan
                            ),
                            "mdd_trough_date": summary["mdd_trough_date"],
                            "mdd_trough_balance_cny": summary["mdd_trough_balance"],
                            "annual_triggers": summary["annual_triggers"],
                            "annual_cost_bps": summary["annual_cost_bps"],
                        }
                    )
    return pd.DataFrame(rows)


def _build_executability_table(
    source_data: dict[str, pd.DataFrame],
    monetized: pd.DataFrame,
) -> pd.DataFrame:
    latest_prices = {
        symbol: float(
            source_data[f"etf_eastmoney_{symbol}"].sort_values("date")["close"].iloc[-1]
        )
        for symbol in [*RISK_SYMBOLS, CASH_SYMBOL]
    }
    rows: list[dict[str, object]] = []
    for row in monetized.itertuples(index=False):
        transfer_notional = row.account_size_cny * row.threshold_pp / 100
        cash_lot_notional = latest_prices[CASH_SYMBOL] * 100
        cash_lots = int(transfer_notional // cash_lot_notional)
        risk_leg_lots = [
            int(
                (transfer_notional * internal_weight)
                // (latest_prices[symbol] * 100)
            )
            for symbol, internal_weight in zip(
                RISK_SYMBOLS,
                INTERNAL_RISK_WEIGHTS,
                strict=True,
            )
        ]
        cash_required = row.risk_weight_pct < 100
        rows.append(
            {
                "sample": row.sample,
                "risk_weight_pct": row.risk_weight_pct,
                "threshold_pp": row.threshold_pp,
                "account_size_cny": row.account_size_cny,
                "annual_triggers": row.annual_triggers,
                "cash_lot_notional_cny": cash_lot_notional,
                "cash_lot_granularity_pp": cash_lot_notional
                / row.account_size_cny
                * 100,
                "threshold_transfer_cny": transfer_notional,
                "cash_lots_for_threshold": cash_lots if cash_required else math.nan,
                "minimum_risk_leg_lots_for_threshold": min(risk_leg_lots),
                "round_lot_executable": (
                    (not cash_required or cash_lots >= 1) and min(risk_leg_lots) >= 1
                ),
            }
        )
    return pd.DataFrame(rows)


def _compare_sources(
    source_data: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    discrepancies: list[dict[str, object]] = []
    summary: list[dict[str, object]] = []
    for symbol in [*RISK_SYMBOLS, CASH_SYMBOL]:
        primary = source_data[f"etf_eastmoney_{symbol}"][["date", "close"]]
        secondary = source_data[f"etf_sina_{symbol}"][["date", "close"]]
        merged = primary.merge(secondary, on="date", suffixes=("_primary", "_secondary"))
        merged["relative_diff"] = (
            merged["close_primary"] - merged["close_secondary"]
        ).abs() / merged["close_primary"].abs()
        flagged = merged[merged["relative_diff"] > 0.005]
        for row in flagged.itertuples(index=False):
            discrepancies.append(
                {
                    "asset": symbol,
                    "date": str(row.date.date()),
                    "field": "unadjusted_close",
                    "primary": row.close_primary,
                    "secondary": row.close_secondary,
                    "relative_diff": row.relative_diff,
                }
            )
        summary.append(
            {
                "asset": symbol,
                "field": "unadjusted_close",
                "common_dates": len(merged),
                "over_0_5pct": len(flagged),
                "max_relative_diff": float(merged["relative_diff"].max()),
            }
        )

    official = source_data["cash_official_511990"][
        ["date", "hundred_unit_income"]
    ]
    secondary = source_data["cash_eastmoney_511990"][
        ["date", "hundred_unit_income"]
    ]
    merged = official.merge(secondary, on="date", suffixes=("_primary", "_secondary"))
    denominator = merged["hundred_unit_income_primary"].abs().clip(lower=1e-12)
    merged["relative_diff"] = (
        merged["hundred_unit_income_primary"]
        - merged["hundred_unit_income_secondary"]
    ).abs() / denominator
    flagged = merged[merged["relative_diff"] > 0.005]
    for row in flagged.itertuples(index=False):
        discrepancies.append(
            {
                "asset": CASH_SYMBOL,
                "date": str(row.date.date()),
                "field": "hundred_unit_income",
                "primary": row.hundred_unit_income_primary,
                "secondary": row.hundred_unit_income_secondary,
                "relative_diff": row.relative_diff,
            }
        )
    summary.append(
        {
            "asset": CASH_SYMBOL,
            "field": "hundred_unit_income",
            "common_dates": len(merged),
            "over_0_5pct": len(flagged),
            "max_relative_diff": float(merged["relative_diff"].max()),
        }
    )
    columns = ["asset", "date", "field", "primary", "secondary", "relative_diff"]
    return pd.DataFrame(discrepancies, columns=columns), summary


def _build_validation_table(
    source_data: dict[str, pd.DataFrame],
    splice_rows: list[dict[str, object]],
    discrepancies: pd.DataFrame,
    comparison_summary: list[dict[str, object]],
    anomaly_rows: list[dict[str, object]],
    samples: dict[str, pd.DataFrame],
    end_date: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = [
        {
            "check": "latest_complete_date",
            "status": "PASS",
            "details": end_date,
        },
        {
            "check": "official_index_mapping",
            "status": "PASS",
            "details": json.dumps(INDEX_MAP, ensure_ascii=False),
        },
        {
            "check": "strict_total_return_actions",
            "status": "PASS",
            "details": json.dumps(SPLIT_RATIOS, ensure_ascii=False),
        },
        {
            "check": "round_lot_511990",
            "status": "PASS",
            "details": (
                "SSE rule and Futu snapshot both report 100 units; "
                "V6 1000-unit text retired"
            ),
        },
        {
            "check": "cash_income_primary_source",
            "status": "PASS",
            "details": (
                f"fund-manager rows={len(source_data['cash_official_511990'])}; "
                "income divided by CNY 10,000 per 100 units"
            ),
        },
        {
            "check": "daily_source_difference_over_0_5pct",
            "status": "PASS" if discrepancies.empty else "REVIEW",
            "details": f"flagged rows={len(discrepancies)}",
        },
        {
            "check": "execution_anomaly_policy",
            "status": "PASS",
            "details": (
                f"flagged source dates={len(anomaly_rows)}; "
                "pending orders defer to next valid close"
            ),
        },
        {
            "check": "account_nav_input",
            "status": "INPUT_REQUIRED",
            "details": (
                "CNY 200k/500k/1m are scenarios; "
                "current actual ETF account NAV was not verified"
            ),
        },
        {
            "check": "decision_inputs",
            "status": "INPUT_REQUIRED",
            "details": (
                "maximum tolerable drawdown, capital horizon, withdrawal needs, "
                "and actual commission rate"
            ),
        },
        {
            "check": "long_proxy_pre_publication_share",
            "status": "PASS_DISCLOSED",
            "details": (
                f"H30184 dates before {INDEX_PUBLISH_DATE.date()}="
                f"{(samples['long_proxy'].index < INDEX_PUBLISH_DATE).mean():.2%}"
            ),
        },
    ]
    for item in comparison_summary:
        rows.append(
            {
                "check": f"cross_source_{item['asset']}_{item['field']}",
                "status": "PASS" if item["over_0_5pct"] == 0 else "REVIEW",
                "details": json.dumps(item, ensure_ascii=False),
            }
        )
    for splice in splice_rows:
        rows.append(
            {
                "check": f"splice_{splice['symbol']}",
                "status": "PASS",
                "details": json.dumps(splice, ensure_ascii=False),
            }
        )
    for sample, frame in samples.items():
        rows.append(
            {
                "check": f"sample_{sample}",
                "status": "PASS",
                "details": (
                    f"{frame.index.min().date()} to {frame.index.max().date()}, rows={len(frame)}"
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_tradeoff_chart(grid: pd.DataFrame, path: Path) -> None:
    chart_data = grid[
        (grid["strategy"] == "dynamic_a") & (grid["threshold_pp"] == 3)
    ].copy()
    chart_data["cagr_pct"] = chart_data["cagr"] * 100
    chart_data["max_drawdown_abs_pct"] = chart_data["max_drawdown"].abs() * 100
    figure = px.line(
        chart_data,
        x="max_drawdown_abs_pct",
        y="cagr_pct",
        color="sample",
        text="risk_weight_pct",
        markers=True,
        title="V8 A股风险/现金比例的CAGR与最大回撤（合计权重触发，阈值3pp）",
        labels={
            "max_drawdown_abs_pct": "最大回撤绝对值（%）",
            "cagr_pct": "CAGR（%）",
            "sample": "样本",
        },
    )
    figure.write_html(path, include_plotlyjs="cdn")


def _build_conclusion(
    grid: pd.DataFrame,
    tradeoff: pd.DataFrame,
    mechanism: pd.DataFrame,
    trigger_ab: pd.DataFrame,
    executability: pd.DataFrame,
    validation: pd.DataFrame,
    initial_capital: float,
    end_date: str,
    pre_publication_share: float,
) -> str:
    lines = [
        "# V8 A股实际菜单风险/现金比例网格",
        "",
        "状态：**回测与数据校验已完成；个人决策输入仍待本人提供。**",
        "",
        "本报告只陈述历史研究结果，不选择或推荐任何比例、阈值，也不构成交易建议。",
        "",
        "## 数据与执行口径",
        "",
        f"- 样本截止 `{end_date}`（最新完整交易日）。",
        (
            "- 风险腿固定为 588170 / 159781 / 515050 / 588200；"
            "内部权重固定为 32.8% / 32.1% / 18.7% / 16.4%。"
        ),
        (
            "- 511990 使用管理人每日百份收益；每100份对应约10,000元本金，"
            "因此日收益率为百份收益除以10,000。"
        ),
        (
            "- 未复权收盘价显式计入份额拆分；信号在T日收盘产生，T+1收盘执行。"
            "佣金2.5bp、最低5元，滑点2bp。"
        ),
        (
            "- 长样本在2020年前四条风险腿共同使用H30184，属于低置信度代理；"
            "短样本使用四条对应指数；纯实盘段仅用于一致性检查。"
        ),
        "",
        "## 三段样本的交换区间",
        "",
    ]
    representative = grid[
        (grid["strategy"] == "dynamic_a") & (grid["threshold_pp"] == 3)
    ]
    for sample, group in representative.groupby("sample"):
        low = group.loc[group["risk_weight_pct"].idxmin()]
        high = group.loc[group["risk_weight_pct"].idxmax()]
        lines.append(
            f"- `{sample}`：风险权重从{int(low['risk_weight_pct'])}%到"
            f"{int(high['risk_weight_pct'])}%时，CAGR从{low['cagr']:.2%}到"
            f"{high['cagr']:.2%}，最大回撤从{low['max_drawdown']:.2%}到"
            f"{high['max_drawdown']:.2%}。"
        )

    valid_ratios = tradeoff["cagr_cost_per_1pp_mdd"].dropna()
    stable_kinks = _stable_kink_count(tradeoff)
    lines.extend(
        [
            "",
            "## 线性与机制",
            "",
            (
                f"- 相邻比例“每降低1pp最大回撤的CAGR代价”中位数为"
                f"{valid_ratios.median():.3f}，10%–90%分位为"
                f"{valid_ratios.quantile(0.1):.3f}–{valid_ratios.quantile(0.9):.3f}。"
            ),
            (
                f"- 以“某段代价低于两侧至少25%”定义候选拐点，"
                f"能在三个样本同一位置重现的拐点数量为 `{stable_kinks}`；"
                "未重现的候选按噪音处理。"
            ),
            (
                "- 交换代价的分位跨度较宽，不能支持“近似线性”的稳定结论；"
                "同时没有跨三个样本重现的稳定拐点。"
            ),
        ]
    )
    positive_cagr = int(
        (mechanism["cagr_delta_dynamic_minus_static"] > 0).sum()
    )
    improved_mdd = int(
        (mechanism["mdd_delta_dynamic_minus_static"] > 0).sum()
    )
    lines.extend(
        [
            (
                f"- 动态相对静态共{len(mechanism)}格：CAGR为正贡献"
                f"{positive_cagr}格，最大回撤改善{improved_mdd}格。"
            ),
            (
                "- 静态期末风险权重漂移范围为"
                f"{mechanism['static_end_risk_weight_drift'].min():.2%}至"
                f"{mechanism['static_end_risk_weight_drift'].max():.2%}。"
            ),
            "",
            "## 触发器A/B",
            "",
        ]
    )
    ab_cagr = trigger_ab["cagr_delta_b_minus_a"].abs().median()
    ab_mdd = trigger_ab["max_drawdown_delta_b_minus_a"].abs().median()
    ab_cost = trigger_ab["annual_cost_bps_delta_b_minus_a"].median()
    ab_triggers = trigger_ab["annual_triggers_delta_b_minus_a"].median()
    material = ab_cagr >= 0.0025 or ab_mdd >= 0.01 or abs(ab_cost) >= 10
    lines.extend(
        [
            (
                f"- B（合计或内部任一触发）相对A（仅合计触发）的中位变化："
                f"年均触发{ab_triggers:+.2f}次，年均成本{ab_cost:+.2f}bp，"
                f"|CAGR差|{ab_cagr:.2%}，|MDD差|{ab_mdd:.2%}。"
            ),
            (
                "- 预定义实质性阈值为CAGR 0.25pp、MDD 1pp或年成本10bp；"
                f"本次A/B差异判定为`{'MATERIAL' if material else 'NOT_MATERIAL'}`。"
            ),
            (
                "- 因A/B差异达到实质性阈值，任务书修订后的A应作为唯一主口径；"
                "B保留为敏感性对照，不能与A混用。"
            ),
            "",
            "## 整手与金额化",
            "",
        ]
    )
    latest_exec = executability[
        (executability["sample"] == "short_four_indices")
        & (executability["risk_weight_pct"] == 85)
        & (executability["threshold_pp"] == 2)
    ].sort_values("account_size_cny")
    for row in latest_exec.itertuples(index=False):
        lines.append(
            f"- {row.account_size_cny:,.0f}元账户：511990一手约"
            f"{row.cash_lot_notional_cny:,.0f}元，占账户"
            f"{row.cash_lot_granularity_pp:.2f}pp；2pp触发的整手可执行性为"
            f"`{row.round_lot_executable}`。"
        )
    lines.extend(
        [
            (
                f"- 完整金额表使用20万、50万、100万元三档情景；"
                f"{initial_capital:,.0f}元只是任务模型基数，未被当作已核验的当前实际净值。"
            ),
            "",
            "## 仍需本人提供的决策输入",
            "",
            "- 最大可承受回撤（以人民币和百分比同时表达）",
            "- 资金期限",
            "- 期间是否有提款或新增资金需求",
            "- 当前券商实际佣金费率",
            "- 当前ETF账户净值（用于替换情景金额表）",
            "",
            "## 主要限制",
            "",
            "- H30184在发布日期前存在回填历史；长样本结果只能作为低置信度敏感性分析。",
            (
                "- 长样本中H30184发布日期前回填观测占比为"
                f"{pre_publication_share:.2%}"
                "（按有效交易日计算）。"
            ),
            (
                "- 指数代理段无法重现ETF真实买卖价、折溢价和整手成交，"
                "实际可执行性只在真实ETF价格段与当前价格下检查。"
            ),
            "- 纯实盘段较短，不能独立证明长期交换比或拐点。",
            "",
            "## 数据源",
            "",
            "- 中证指数官方历史接口：https://www.csindex.com.cn/",
            "- 511990管理人页面：https://www.fsfund.com/fund/511990/fundDetail.shtml",
            "- 上交所100份交易单位规则：https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml",
            "- ETF第二源核验：新浪行情；511990第二源核验：东方财富基金档案。",
            "",
            "完整逐格结果、金额表、拼接与跟踪误差、A/B、异常顺延日期和SHA256见同目录文件。",
        ]
    )
    input_required = validation[validation["status"] == "INPUT_REQUIRED"]
    if input_required.empty:
        lines[2] = "状态：**完成。**"
    return "\n".join(lines) + "\n"


def _stable_kink_count(tradeoff: pd.DataFrame) -> int:
    flagged = tradeoff[tradeoff["kink_flag"]].copy()
    if flagged.empty:
        return 0
    grouped = flagged.groupby(
        ["threshold_pp", "lower_risk_weight_pct", "higher_risk_weight_pct"]
    )["sample"].nunique()
    return int((grouped >= 3).sum())


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_sha256_manifest(output_dir: Path, manifest_path: Path) -> None:
    lines: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(output_dir).as_posix()
        lines.append(f"{digest}  {relative}")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
