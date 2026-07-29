from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

from aetf_momentum.research.v8_grid import (
    RebalanceConfig,
    RiskCashResult,
    simulate_risk_cash,
)

TRADING_DAYS_PER_YEAR = 252


def run_parameter_grid(
    samples: Mapping[str, pd.DataFrame],
    execution_validity: Mapping[str, pd.Series],
    risk_symbols: tuple[str, ...],
    cash_symbol: str,
    internal_risk_weights: tuple[float, ...],
    risk_weights: tuple[int, ...],
    thresholds_pp: tuple[int, ...],
    initial_capital: float,
) -> tuple[pd.DataFrame, dict[tuple[str, int, int, str], RiskCashResult]]:
    rows: list[dict[str, object]] = []
    results: dict[tuple[str, int, int, str], RiskCashResult] = {}
    strategies = {
        "dynamic_a": "aggregate",
        "dynamic_b": "aggregate_or_internal",
        "static": "static",
    }
    for sample_name, levels in samples.items():
        for risk_weight in risk_weights:
            for threshold_pp in thresholds_pp:
                for strategy, trigger_mode in strategies.items():
                    config = RebalanceConfig(
                        risk_symbols=risk_symbols,
                        cash_symbol=cash_symbol,
                        internal_risk_weights=internal_risk_weights,
                        risk_target=risk_weight / 100.0,
                        threshold_pp=float(threshold_pp),
                        trigger_mode=trigger_mode,
                        initial_capital=initial_capital,
                    )
                    result = simulate_risk_cash(
                        levels,
                        config,
                        valid_execution=execution_validity[sample_name],
                    )
                    key = (sample_name, risk_weight, threshold_pp, strategy)
                    results[key] = result
                    row = {
                        "sample": sample_name,
                        "risk_weight_pct": risk_weight,
                        "cash_weight_pct": 100 - risk_weight,
                        "threshold_pp": threshold_pp,
                        "strategy": strategy,
                    }
                    row.update(summarize_result(result, initial_capital))
                    rows.append(row)
    return pd.DataFrame(rows), results


def summarize_result(
    result: RiskCashResult,
    initial_capital: float,
) -> dict[str, float | int | str | None]:
    daily = result.daily
    equity = pd.to_numeric(daily["total_equity"], errors="coerce")
    daily_returns = equity.pct_change().dropna()
    observations = len(daily)
    years = max((observations - 1) / TRADING_DAYS_PER_YEAR, 1 / TRADING_DAYS_PER_YEAR)
    final_equity = float(equity.iloc[-1])
    cagr = (
        (final_equity / initial_capital) ** (1 / years) - 1
        if final_equity > 0 and observations > 1
        else math.nan
    )
    volatility = (
        float(daily_returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
        if len(daily_returns) > 1
        else math.nan
    )
    drawdown = equity / equity.cummax() - 1.0
    trough_position = int(drawdown.to_numpy().argmin())
    max_drawdown = float(drawdown.iloc[trough_position])
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else math.nan
    max_underwater_days = _max_consecutive_true(drawdown < 0)
    underwater_share = float((drawdown < 0).mean())
    annual_cost_bps = result.total_cost / initial_capital / years * 10_000.0
    annual_triggers = result.trigger_count / years
    worst_three_year_return, worst_three_year_end = _worst_window_return(
        equity,
        daily["date"],
        TRADING_DAYS_PER_YEAR * 3,
    )
    return {
        "start": str(pd.Timestamp(daily["date"].iloc[0]).date()),
        "end": str(pd.Timestamp(daily["date"].iloc[-1]).date()),
        "observations": observations,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "annualized_volatility": volatility,
        "calmar": calmar,
        "underwater_share": underwater_share,
        "longest_underwater_days": max_underwater_days,
        "annual_triggers": annual_triggers,
        "annual_cost_bps": annual_cost_bps,
        "trigger_count": result.trigger_count,
        "total_cost": result.total_cost,
        "final_equity": final_equity,
        "end_risk_weight": float(daily["risk_weight"].iloc[-1]),
        "mdd_trough_date": str(pd.Timestamp(daily["date"].iloc[trough_position]).date()),
        "mdd_trough_balance": float(equity.iloc[trough_position]),
        "worst_three_year_return": worst_three_year_return,
        "worst_three_year_end": worst_three_year_end,
    }


def build_tradeoff_table(grid: pd.DataFrame) -> pd.DataFrame:
    dynamic = grid[grid["strategy"] == "dynamic_a"].copy()
    rows: list[dict[str, object]] = []
    for (sample, threshold), group in dynamic.groupby(["sample", "threshold_pp"]):
        ordered = group.sort_values("risk_weight_pct").reset_index(drop=True)
        for position in range(1, len(ordered)):
            low = ordered.iloc[position - 1]
            high = ordered.iloc[position]
            mdd_reduction_pp = (
                abs(float(high["max_drawdown"])) - abs(float(low["max_drawdown"]))
            ) * 100
            cagr_cost_pp = (float(high["cagr"]) - float(low["cagr"])) * 100
            ratio = (
                cagr_cost_pp / mdd_reduction_pp
                if mdd_reduction_pp > 1e-12
                else math.nan
            )
            rows.append(
                {
                    "sample": sample,
                    "threshold_pp": threshold,
                    "lower_risk_weight_pct": int(low["risk_weight_pct"]),
                    "higher_risk_weight_pct": int(high["risk_weight_pct"]),
                    "mdd_reduction_pp": mdd_reduction_pp,
                    "cagr_cost_pp": cagr_cost_pp,
                    "cagr_cost_per_1pp_mdd": ratio,
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["kink_flag"] = False
    for (_, _), indexes in result.groupby(["sample", "threshold_pp"]).groups.items():
        group_indexes = list(indexes)
        for position in range(1, len(group_indexes) - 1):
            previous_value = result.loc[
                group_indexes[position - 1], "cagr_cost_per_1pp_mdd"
            ]
            current_value = result.loc[
                group_indexes[position], "cagr_cost_per_1pp_mdd"
            ]
            next_value = result.loc[group_indexes[position + 1], "cagr_cost_per_1pp_mdd"]
            if (
                pd.notna(previous_value)
                and pd.notna(current_value)
                and pd.notna(next_value)
                and current_value < 0.75 * min(previous_value, next_value)
            ):
                result.loc[group_indexes[position], "kink_flag"] = True
    return result


def build_mechanism_table(grid: pd.DataFrame) -> pd.DataFrame:
    keys = ["sample", "risk_weight_pct", "cash_weight_pct", "threshold_pp"]
    dynamic = grid[grid["strategy"] == "dynamic_a"].set_index(keys)
    static = grid[grid["strategy"] == "static"].set_index(keys)
    result = dynamic[
        ["cagr", "max_drawdown", "annual_triggers", "annual_cost_bps"]
    ].join(
        static[["cagr", "max_drawdown", "end_risk_weight"]],
        lsuffix="_dynamic",
        rsuffix="_static",
    )
    result["cagr_delta_dynamic_minus_static"] = (
        result["cagr_dynamic"] - result["cagr_static"]
    )
    result["mdd_delta_dynamic_minus_static"] = (
        result["max_drawdown_dynamic"] - result["max_drawdown_static"]
    )
    result["static_end_risk_weight_drift"] = (
        result["end_risk_weight"] - result.index.get_level_values("risk_weight_pct") / 100
    )
    return result.reset_index()


def build_trigger_ab_table(grid: pd.DataFrame) -> pd.DataFrame:
    keys = ["sample", "risk_weight_pct", "cash_weight_pct", "threshold_pp"]
    aggregate = grid[grid["strategy"] == "dynamic_a"].set_index(keys)
    internal = grid[grid["strategy"] == "dynamic_b"].set_index(keys)
    columns = ["cagr", "max_drawdown", "annual_triggers", "annual_cost_bps"]
    result = aggregate[columns].join(
        internal[columns],
        lsuffix="_aggregate",
        rsuffix="_aggregate_or_internal",
    )
    for column in columns:
        result[f"{column}_delta_b_minus_a"] = (
            result[f"{column}_aggregate_or_internal"]
            - result[f"{column}_aggregate"]
        )
    return result.reset_index()


def _max_consecutive_true(values: pd.Series) -> int:
    longest = 0
    current = 0
    for value in values:
        if bool(value):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _worst_window_return(
    equity: pd.Series,
    dates: pd.Series,
    window: int,
) -> tuple[float, str | None]:
    if len(equity) <= window:
        return math.nan, None
    window_returns = equity / equity.shift(window) - 1.0
    end_position = int(window_returns.to_numpy()[window:].argmin()) + window
    return (
        float(window_returns.iloc[end_position]),
        str(pd.Timestamp(dates.iloc[end_position]).date()),
    )
