from __future__ import annotations

import math

import pandas as pd
import pytest

from aetf_momentum.research.metrics import (
    add_cumulative_return,
    calculate_drawdown_series,
    calculate_performance_metrics,
)


def test_calculate_performance_metrics_p0_values() -> None:
    equity = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ),
            "total_equity": [100.0, 110.0, 105.0, 120.0],
            "turnover": [0.0, 0.1, 0.2, 0.3],
        }
    )
    daily_returns = pd.Series([0.10, -0.045454545454545414, 0.1428571428571428])

    metrics = calculate_performance_metrics(equity, initial_cash=100.0)

    assert metrics["cagr"] == pytest.approx((120 / 100) ** (252 / 4) - 1)
    assert metrics["annualized_return"] == pytest.approx(daily_returns.mean() * 252)
    assert metrics["annualized_volatility"] == pytest.approx(
        daily_returns.std(ddof=1) * math.sqrt(252)
    )
    assert metrics["max_drawdown"] == pytest.approx(-0.045454545454545414)
    assert metrics["max_drawdown_start"] == "2024-01-03"
    assert metrics["max_drawdown_trough"] == "2024-01-04"
    assert metrics["max_drawdown_recovery"] == "2024-01-05"
    assert metrics["sharpe"] == pytest.approx(
        metrics["annualized_return"] / metrics["annualized_volatility"]
    )
    assert metrics["calmar"] == pytest.approx(metrics["cagr"] / abs(metrics["max_drawdown"]))
    assert metrics["annualized_turnover"] == pytest.approx(equity["turnover"].mean() * 252)


def test_metrics_handle_short_or_flat_equity_without_crashing() -> None:
    single = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "total_equity": [100.0],
            "turnover": [0.0],
        }
    )
    flat = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "total_equity": [100.0, 100.0, 100.0],
            "turnover": [0.0, 0.0, 0.0],
        }
    )

    single_metrics = calculate_performance_metrics(single, initial_cash=100.0)
    flat_metrics = calculate_performance_metrics(flat, initial_cash=100.0)

    assert math.isnan(single_metrics["cagr"])
    assert math.isnan(single_metrics["annualized_volatility"])
    assert flat_metrics["max_drawdown"] == 0.0
    assert math.isnan(flat_metrics["sharpe"])
    assert math.isnan(flat_metrics["calmar"])


def test_add_cumulative_return_and_drawdown_series() -> None:
    equity = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "total_equity": [100.0, 90.0, 120.0],
            "turnover": [0.0, 0.1, 0.2],
        }
    )

    with_cum = add_cumulative_return(equity, initial_cash=100.0)
    drawdown = calculate_drawdown_series(equity)

    assert with_cum["cum_return"].tolist() == pytest.approx([0.0, -0.1, 0.2])
    assert drawdown.tolist() == pytest.approx([0.0, -0.1, 0.0])
