from __future__ import annotations

import json

import pandas as pd
from typer.testing import CliRunner

from aetf_momentum.app.cli import app
from aetf_momentum.backtest.costs import CostConfig
from aetf_momentum.backtest.pandas_engine import run_backtest
from aetf_momentum.research.pipeline import run_factor_backtest
from aetf_momentum.strategy.momentum import MomentumConfig, build_momentum_targets


def test_momentum_targets_execute_on_next_bar_only() -> None:
    panel = _sample_panel()
    close = panel.pivot(index="date", columns="symbol", values="close")
    targets = build_momentum_targets(
        close,
        MomentumConfig(
            lookbacks=[1],
            weights=[1.0],
            top_k=1,
            max_weight=1.0,
            rebalance_freq="daily",
            volatility_adjusted=False,
        ),
    )

    result = run_backtest(panel, targets, CostConfig(commission_bps=0, slippage_bps=0))

    assert not result.trades.empty
    assert result.trades["date"].min() == pd.Timestamp("2024-01-03")
    assert result.trades.iloc[0]["symbol"] == "510300"
    assert result.trades.iloc[0]["reason"] == "rebalance_from_2024-01-02"


def test_factor_backtest_pipeline_writes_artifacts(tmp_path) -> None:
    panel_path = tmp_path / "panel.csv"
    _sample_panel().to_csv(panel_path, index=False)

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        """
momentum:
  lookbacks: [1]
  weights: [1.0]
  top_k: 1
  max_weight: 1.0
  rebalance_freq: daily
  volatility_adjusted: false
costs:
  commission_bps: 0
  slippage_bps: 0
  min_fee: 0
backtest:
  initial_cash: 1000000
""".strip(),
        encoding="utf-8",
    )

    output = run_factor_backtest(panel_path, strategy_path, tmp_path / "artifacts")

    assert output.equity_path.exists()
    assert output.trades_path.exists()
    assert output.summary_path.exists()
    assert output.report_path.exists()

    summary = json.loads(output.summary_path.read_text(encoding="utf-8"))
    assert summary["factor"] == "momentum"
    assert summary["trades"] > 0
    assert "total_return" in summary


def test_cli_runs_selected_factor_backtest(tmp_path) -> None:
    panel_path = tmp_path / "panel.csv"
    _sample_panel().to_csv(panel_path, index=False)

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        """
momentum:
  lookbacks: [1]
  weights: [1.0]
  top_k: 1
  max_weight: 1.0
  rebalance_freq: daily
  volatility_adjusted: false
costs:
  commission_bps: 0
  slippage_bps: 0
  min_fee: 0
backtest:
  initial_cash: 1000000
""".strip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "run",
            "--strategy",
            str(strategy_path),
            "--panel",
            str(panel_path),
            "--output",
            str(tmp_path / "run"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "summary.json" in result.output
    assert (tmp_path / "run" / "summary.json").exists()


def test_cli_lists_factor_presets() -> None:
    result = CliRunner().invoke(app, ["factor", "list"])

    assert result.exit_code == 0, result.output
    assert "risk_adjusted_momentum" in result.output
    assert "short_momentum" in result.output
    assert "daily_momentum" in result.output


def test_cli_runs_factor_preset_without_strategy_yaml(tmp_path) -> None:
    panel_path = tmp_path / "panel.csv"
    _sample_panel().to_csv(panel_path, index=False)

    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "run",
            "--factor-preset",
            "daily_momentum",
            "--panel",
            str(panel_path),
            "--output",
            str(tmp_path / "preset-run"),
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads((tmp_path / "preset-run" / "summary.json").read_text(encoding="utf-8"))
    assert summary["factor"] == "daily_momentum"
    assert summary["trades"] > 0


def test_rebalance_sells_before_buys_to_avoid_negative_cash_log() -> None:
    rows = [
        ("2024-01-01", "100000", 100.0, 100.0),
        ("2024-01-01", "200000", 100.0, 100.0),
        ("2024-01-02", "100000", 90.0, 90.0),
        ("2024-01-02", "200000", 110.0, 110.0),
        ("2024-01-03", "100000", 120.0, 120.0),
        ("2024-01-03", "200000", 100.0, 100.0),
        ("2024-01-04", "100000", 100.0, 100.0),
        ("2024-01-04", "200000", 100.0, 100.0),
    ]
    panel = _panel_from_rows(rows)
    close = panel.pivot(index="date", columns="symbol", values="close")
    targets = build_momentum_targets(
        close,
        MomentumConfig(
            lookbacks=[1],
            weights=[1.0],
            top_k=1,
            max_weight=1.0,
            rebalance_freq="daily",
            volatility_adjusted=False,
        ),
    )

    result = run_backtest(panel, targets, CostConfig(commission_bps=0, slippage_bps=0))

    assert result.trades["cash_after"].min() >= 0


def test_buy_sizing_reserves_cash_for_costs() -> None:
    panel = _panel_from_rows(
        [
            ("2024-01-01", "100000", 100.0, 100.0),
            ("2024-01-01", "200000", 100.0, 100.0),
            ("2024-01-02", "100000", 110.0, 110.0),
            ("2024-01-02", "200000", 90.0, 90.0),
            ("2024-01-03", "100000", 100.0, 100.0),
            ("2024-01-03", "200000", 100.0, 100.0),
        ]
    )
    close = panel.pivot(index="date", columns="symbol", values="close")
    targets = build_momentum_targets(
        close,
        MomentumConfig(
            lookbacks=[1],
            weights=[1.0],
            top_k=1,
            max_weight=1.0,
            rebalance_freq="daily",
            volatility_adjusted=False,
        ),
    )

    result = run_backtest(
        panel,
        targets,
        CostConfig(commission_bps=100, slippage_bps=100, min_fee=0),
        initial_cash=1000,
    )

    assert result.trades["cash_after"].min() >= 0
    assert result.trades.iloc[0]["notional"] < 1000


def _sample_panel() -> pd.DataFrame:
    rows = [
        ("2024-01-01", "510300", 100.0, 100.0),
        ("2024-01-01", "510500", 100.0, 100.0),
        ("2024-01-02", "510300", 110.0, 110.0),
        ("2024-01-02", "510500", 90.0, 90.0),
        ("2024-01-03", "510300", 120.0, 121.0),
        ("2024-01-03", "510500", 95.0, 94.0),
        ("2024-01-04", "510300", 122.0, 123.0),
        ("2024-01-04", "510500", 90.0, 89.0),
    ]
    return _panel_from_rows(rows)


def _panel_from_rows(rows: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime([row[0] for row in rows]),
            "symbol": [row[1] for row in rows],
            "open": [row[2] for row in rows],
            "high": [row[2] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
            "volume": [1000 for _ in rows],
            "amount": [100000.0 for _ in rows],
        }
    )
