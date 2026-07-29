from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

TriggerMode = Literal["aggregate", "aggregate_or_internal", "static"]


@dataclass(frozen=True)
class RebalanceConfig:
    risk_symbols: tuple[str, ...]
    cash_symbol: str
    internal_risk_weights: tuple[float, ...]
    risk_target: float
    threshold_pp: float
    trigger_mode: TriggerMode
    initial_capital: float
    commission_bps: float = 2.5
    min_commission: float = 5.0
    slippage_bps: float = 2.0


@dataclass(frozen=True)
class RiskCashResult:
    daily: pd.DataFrame
    trigger_count: int
    total_cost: float


def calculate_trade_cost(
    notional: float,
    commission_bps: float = 2.5,
    min_commission: float = 5.0,
    slippage_bps: float = 2.0,
) -> float:
    absolute_notional = abs(float(notional))
    if absolute_notional == 0:
        return 0.0
    commission = max(absolute_notional * commission_bps / 10_000.0, min_commission)
    slippage = absolute_notional * slippage_bps / 10_000.0
    return commission + slippage


def simulate_risk_cash(
    levels: pd.DataFrame,
    config: RebalanceConfig,
    valid_execution: pd.Series | None = None,
) -> RiskCashResult:
    prepared = _prepare_levels(levels, config)
    targets = _target_weights(config)
    execution_valid = _prepare_execution_valid(valid_execution, prepared.index)
    gross_returns = (
        prepared.to_numpy(dtype=float)
        / np.vstack(
            [
                prepared.iloc[0].to_numpy(dtype=float),
                prepared.iloc[:-1].to_numpy(dtype=float),
            ]
        )
    )
    target_values = targets.to_numpy(dtype=float)
    values = target_values * config.initial_capital
    execution_values = execution_valid.to_numpy(dtype=bool)
    risk_count = len(config.risk_symbols)
    symbols = list(targets.index)

    pending_signal_date: pd.Timestamp | None = None
    pending_reason: str | None = None
    trigger_count = 0
    total_cost = 0.0
    rows: list[dict[str, object]] = []

    for position, date in enumerate(prepared.index):
        if position:
            values *= gross_returns[position]

        executed = False
        execution_deferred = False
        executed_signal_date: pd.Timestamp | None = None
        executed_reason: str | None = None
        trade_notional = 0.0
        cost = 0.0

        if pending_signal_date is not None:
            if execution_values[position]:
                executed_signal_date = pending_signal_date
                executed_reason = pending_reason
                values, trade_notional, cost = _rebalance_array(
                    values,
                    target_values,
                    config,
                )
                total_cost += cost
                pending_signal_date = None
                pending_reason = None
                executed = True
            else:
                execution_deferred = True

        total_equity = float(np.sum(values))
        weights = values / total_equity
        risk_weight = float(np.sum(weights[:risk_count]))
        trigger_signal = False
        row_reason = executed_reason

        if (
            config.trigger_mode != "static"
            and pending_signal_date is None
            and not executed
        ):
            row_reason = _trigger_reason_array(
                weights,
                target_values,
                config,
                risk_count,
            )
            if row_reason is not None:
                pending_signal_date = date
                pending_reason = row_reason
                trigger_count += 1
                trigger_signal = True

        row: dict[str, object] = {
            "date": date,
            "total_equity": total_equity,
            "risk_weight": risk_weight,
            "trigger_signal": trigger_signal,
            "executed": executed,
            "execution_deferred": execution_deferred,
            "signal_date": executed_signal_date,
            "trigger_reason": row_reason,
            "trade_notional": trade_notional,
            "cost": cost,
            "turnover": trade_notional / total_equity if total_equity else 0.0,
        }
        for symbol, weight in zip(symbols, weights, strict=True):
            row[f"weight_{symbol}"] = float(weight)
        rows.append(row)

    return RiskCashResult(
        daily=pd.DataFrame(rows),
        trigger_count=trigger_count,
        total_cost=total_cost,
    )


def _prepare_levels(levels: pd.DataFrame, config: RebalanceConfig) -> pd.DataFrame:
    required = [*config.risk_symbols, config.cash_symbol]
    if len(config.risk_symbols) != len(config.internal_risk_weights):
        raise ValueError("risk symbols and internal weights must have equal length")
    if not 0 <= config.risk_target <= 1:
        raise ValueError("risk_target must be between zero and one")
    if config.threshold_pp <= 0:
        raise ValueError("threshold_pp must be positive")
    if config.initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    if config.trigger_mode not in {"aggregate", "aggregate_or_internal", "static"}:
        raise ValueError(f"unsupported trigger mode: {config.trigger_mode}")
    if abs(sum(config.internal_risk_weights) - 1.0) > 1e-9:
        raise ValueError("internal risk weights must sum to one")

    prepared = levels.copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).normalize()
    prepared = prepared.sort_index()
    if prepared.index.has_duplicates:
        raise ValueError("levels contain duplicate dates")
    if prepared.empty:
        raise ValueError("levels must not be empty")
    missing_columns = sorted(set(required) - set(prepared.columns))
    if missing_columns:
        raise ValueError(f"levels missing required columns: {missing_columns}")
    prepared = prepared[required].apply(pd.to_numeric, errors="coerce")
    if prepared.isna().any().any() or (prepared <= 0).any().any():
        raise ValueError("levels must contain positive values")
    return prepared


def _target_weights(config: RebalanceConfig) -> pd.Series:
    risk_targets = {
        symbol: config.risk_target * internal_weight
        for symbol, internal_weight in zip(
            config.risk_symbols,
            config.internal_risk_weights,
            strict=True,
        )
    }
    risk_targets[config.cash_symbol] = 1.0 - config.risk_target
    return pd.Series(risk_targets, dtype=float)


def _prepare_execution_valid(
    valid_execution: pd.Series | None,
    dates: pd.DatetimeIndex,
) -> pd.Series:
    if valid_execution is None:
        return pd.Series(True, index=dates)
    prepared = pd.Series(valid_execution).copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).normalize()
    prepared = prepared.reindex(dates)
    return prepared.fillna(False).astype(bool)


def _rebalance_array(
    values: np.ndarray,
    targets: np.ndarray,
    config: RebalanceConfig,
) -> tuple[np.ndarray, float, float]:
    equity_before_cost = float(np.sum(values))
    target_values = targets * equity_before_cost
    notionals = target_values - values
    trade_notional = float(np.sum(np.abs(notionals)))
    cost = sum(
        calculate_trade_cost(
            notional,
            commission_bps=config.commission_bps,
            min_commission=config.min_commission,
            slippage_bps=config.slippage_bps,
        )
        for notional in notionals.tolist()
        if abs(notional) > 1e-9
    )
    equity_after_cost = equity_before_cost - cost
    if equity_after_cost <= 0:
        raise ValueError("transaction costs exhausted portfolio equity")
    return targets * equity_after_cost, trade_notional, cost


def _trigger_reason_array(
    weights: np.ndarray,
    targets: np.ndarray,
    config: RebalanceConfig,
    risk_count: int,
) -> str | None:
    threshold = config.threshold_pp / 100.0
    risk_weight = float(np.sum(weights[:risk_count]))
    if abs(risk_weight - config.risk_target) >= threshold:
        return "aggregate"
    if config.trigger_mode == "aggregate_or_internal":
        internal_deviation = np.abs(weights[:risk_count] - targets[:risk_count])
        if bool(np.any(internal_deviation >= threshold)):
            return "internal"
    return None
