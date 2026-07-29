from __future__ import annotations

import pandas as pd
import pytest

from aetf_momentum.research.v8_grid import (
    RebalanceConfig,
    calculate_trade_cost,
    simulate_risk_cash,
)


def test_trade_cost_applies_minimum_commission_before_slippage() -> None:
    assert calculate_trade_cost(1_000.0) == pytest.approx(5.20)
    assert calculate_trade_cost(100_000.0) == pytest.approx(45.0)
    assert calculate_trade_cost(0.0) == 0.0


def test_signal_at_close_executes_at_next_valid_close() -> None:
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    levels = pd.DataFrame(
        {"risk": [1.0, 2.0, 2.0], "cash": [1.0, 1.0, 1.0]},
        index=dates,
    )
    config = RebalanceConfig(
        risk_symbols=("risk",),
        cash_symbol="cash",
        internal_risk_weights=(1.0,),
        risk_target=0.5,
        threshold_pp=5.0,
        trigger_mode="aggregate",
        initial_capital=500_000.0,
    )

    result = simulate_risk_cash(levels, config)

    signal_row = result.daily.set_index("date").loc[pd.Timestamp("2026-01-05")]
    execution_row = result.daily.set_index("date").loc[pd.Timestamp("2026-01-06")]
    assert bool(signal_row["trigger_signal"])
    assert not bool(signal_row["executed"])
    assert bool(execution_row["executed"])
    assert execution_row["signal_date"] == pd.Timestamp("2026-01-05")
    assert execution_row["risk_weight"] == pytest.approx(0.5)


def test_internal_trigger_mode_is_distinct_from_aggregate_only() -> None:
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    levels = pd.DataFrame(
        {
            "risk_a": [1.0, 2.0, 2.0],
            "risk_b": [1.0, 0.5, 0.5],
            "cash": [1.0, 1.0, 1.0],
        },
        index=dates,
    )
    base = dict(
        risk_symbols=("risk_a", "risk_b"),
        cash_symbol="cash",
        internal_risk_weights=(0.5, 0.5),
        risk_target=0.8,
        threshold_pp=5.0,
        initial_capital=500_000.0,
    )

    aggregate = simulate_risk_cash(
        levels,
        RebalanceConfig(trigger_mode="aggregate", **base),
    )
    aggregate_or_internal = simulate_risk_cash(
        levels,
        RebalanceConfig(trigger_mode="aggregate_or_internal", **base),
    )

    assert aggregate.trigger_count == 0
    assert aggregate_or_internal.trigger_count == 1
    execution = aggregate_or_internal.daily.loc[
        aggregate_or_internal.daily["executed"]
    ].iloc[0]
    assert execution["trigger_reason"] == "internal"


def test_pending_trigger_is_deferred_until_execution_data_is_valid() -> None:
    dates = pd.to_datetime(
        ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    )
    levels = pd.DataFrame(
        {"risk": [1.0, 2.0, 2.0, 2.0], "cash": [1.0, 1.0, 1.0, 1.0]},
        index=dates,
    )
    valid_execution = pd.Series([True, True, False, True], index=dates)
    config = RebalanceConfig(
        risk_symbols=("risk",),
        cash_symbol="cash",
        internal_risk_weights=(1.0,),
        risk_target=0.5,
        threshold_pp=5.0,
        trigger_mode="aggregate",
        initial_capital=500_000.0,
    )

    result = simulate_risk_cash(levels, config, valid_execution=valid_execution)

    invalid_row = result.daily.set_index("date").loc[pd.Timestamp("2026-01-06")]
    execution_row = result.daily.set_index("date").loc[pd.Timestamp("2026-01-07")]
    assert not bool(invalid_row["executed"])
    assert bool(invalid_row["execution_deferred"])
    assert bool(execution_row["executed"])
    assert execution_row["signal_date"] == pd.Timestamp("2026-01-05")
