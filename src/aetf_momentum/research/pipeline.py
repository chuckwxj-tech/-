from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import yaml

from aetf_momentum.backtest.costs import CostConfig
from aetf_momentum.backtest.pandas_engine import BacktestResult, run_backtest
from aetf_momentum.data.schema import standardize_ohlcv_frame
from aetf_momentum.research.metrics import (
    add_cumulative_return,
    calculate_drawdown_series,
    calculate_performance_metrics,
)
from aetf_momentum.strategy.momentum import MomentumConfig, build_momentum_targets


@dataclass(frozen=True)
class FactorBacktestOutput:
    equity_path: Path
    trades_path: Path
    positions_path: Path
    summary_path: Path
    report_path: Path


def run_factor_backtest(
    panel_path: str | Path,
    strategy_path: str | Path | None,
    output_dir: str | Path,
    factor_name: str = "momentum",
    strategy_config: dict[str, Any] | None = None,
) -> FactorBacktestOutput:
    config = strategy_config or _load_yaml(strategy_path)
    if "momentum" not in config:
        raise ValueError("Only momentum-backed factor configs are supported")

    panel = _read_panel(panel_path)
    momentum_config = MomentumConfig.from_mapping(config["momentum"])
    cost_config = CostConfig.from_mapping(config.get("costs"))
    initial_cash = float(config.get("backtest", {}).get("initial_cash", 1_000_000))

    close = panel.pivot(index="date", columns="symbol", values="close").sort_index()
    targets = build_momentum_targets(close, momentum_config)
    result = run_backtest(panel, targets, cost_config, initial_cash=initial_cash)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    equity_path = output_path / "equity.csv"
    trades_path = output_path / "trades.csv"
    positions_path = output_path / "positions.csv"
    summary_path = output_path / "summary.json"
    report_path = output_path / "report.html"

    equity_with_cum = add_cumulative_return(result.equity, initial_cash)
    equity_with_cum.to_csv(equity_path, index=False)
    result.trades.to_csv(trades_path, index=False)
    result.positions.to_csv(positions_path, index=False)
    summary = _build_summary(result, factor_name, initial_cash)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_html_report(summary, equity_with_cum), encoding="utf-8")

    return FactorBacktestOutput(
        equity_path=equity_path,
        trades_path=trades_path,
        positions_path=positions_path,
        summary_path=summary_path,
        report_path=report_path,
    )


def _read_panel(panel_path: str | Path) -> pd.DataFrame:
    path = Path(panel_path)
    if path.suffix.lower() == ".parquet":
        raw = pd.read_parquet(path)
    else:
        raw = pd.read_csv(path)
    return standardize_ohlcv_frame(raw)


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return loaded


def _build_summary(
    result: BacktestResult,
    factor_name: str,
    initial_cash: float,
) -> dict[str, float | int | str]:
    final_equity = float(result.equity["total_equity"].iloc[-1])
    total_return = final_equity / initial_cash - 1
    summary = {
        "factor": factor_name,
        "start": str(pd.Timestamp(result.equity["date"].iloc[0]).date()),
        "end": str(pd.Timestamp(result.equity["date"].iloc[-1]).date()),
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "total_return": total_return,
        "trades": int(len(result.trades)),
    }
    summary.update(calculate_performance_metrics(result.equity, initial_cash))
    return summary


def _build_html_report(summary: dict[str, float | int | str], equity: pd.DataFrame) -> str:
    rows = "\n".join(
        f"<tr><th>{key}</th><td>{value}</td></tr>" for key, value in summary.items()
    )
    equity_chart = _equity_curve_chart(equity)
    drawdown_chart = _drawdown_curve_chart(equity)
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>AETF Momentum Backtest</title></head>
<body>
<h1>AETF Momentum Backtest</h1>
<table>{rows}</table>
<h2>Equity Curve</h2>
{equity_chart}
<h2>Drawdown Curve</h2>
{drawdown_chart}
</body>
</html>
"""


def _equity_curve_chart(equity: pd.DataFrame) -> str:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=equity["date"],
            y=equity["total_equity"],
            mode="lines",
            name="total_equity",
        )
    )
    figure.update_layout(title="Equity Curve", xaxis_title="Date", yaxis_title="Equity")
    return figure.to_html(full_html=False, include_plotlyjs="cdn")


def _drawdown_curve_chart(equity: pd.DataFrame) -> str:
    drawdown = calculate_drawdown_series(equity)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=equity["date"],
            y=drawdown,
            mode="lines",
            name="drawdown",
        )
    )
    figure.update_layout(title="Drawdown Curve", xaxis_title="Date", yaxis_title="Drawdown")
    return figure.to_html(full_html=False, include_plotlyjs=False)
