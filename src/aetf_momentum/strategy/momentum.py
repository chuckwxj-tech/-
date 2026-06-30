from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

RebalanceFreq = Literal["daily", "weekly", "biweekly", "monthly"]


@dataclass(frozen=True)
class MomentumConfig:
    lookbacks: list[int]
    weights: list[float]
    top_k: int = 3
    max_weight: float = 0.5
    rebalance_freq: RebalanceFreq = "weekly"
    volatility_adjusted: bool = True
    volatility_lookback: int = 60
    trend_ma: int | None = None

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> MomentumConfig:
        trend_ma = values.get("trend_ma")
        return cls(
            lookbacks=[int(value) for value in values["lookbacks"]],
            weights=[float(value) for value in values["weights"]],
            top_k=int(values.get("top_k", cls.top_k)),
            max_weight=float(values.get("max_weight", cls.max_weight)),
            rebalance_freq=values.get("rebalance_freq", cls.rebalance_freq),
            volatility_adjusted=bool(values.get("volatility_adjusted", cls.volatility_adjusted)),
            volatility_lookback=int(values.get("volatility_lookback", cls.volatility_lookback)),
            trend_ma=int(trend_ma) if trend_ma else None,
        )

    def __post_init__(self) -> None:
        if len(self.lookbacks) != len(self.weights):
            raise ValueError("Momentum lookbacks and weights must have the same length")
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if self.max_weight <= 0:
            raise ValueError("max_weight must be positive")


def build_momentum_scores(close: pd.DataFrame, config: MomentumConfig) -> pd.DataFrame:
    scores = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for lookback, weight in zip(config.lookbacks, config.weights, strict=True):
        scores = scores + close.pct_change(lookback) * weight

    if config.volatility_adjusted:
        daily_returns = close.pct_change()
        annualized_vol = daily_returns.rolling(config.volatility_lookback).std() * np.sqrt(252)
        scores = scores / annualized_vol.replace(0, np.nan)

    if config.trend_ma:
        trend_ok = close > close.rolling(config.trend_ma).mean()
        scores = scores.where(trend_ok)

    return scores.replace([np.inf, -np.inf], np.nan)


def build_momentum_targets(close: pd.DataFrame, config: MomentumConfig) -> pd.DataFrame:
    close = close.sort_index()
    scores = build_momentum_scores(close, config)
    targets = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    rebalance_dates = _rebalance_dates(close.index, config.rebalance_freq)

    for current_date in rebalance_dates:
        row = scores.loc[current_date].dropna().sort_values(ascending=False)
        if row.empty:
            continue
        selected = row.head(config.top_k).index
        weight = min(1.0 / len(selected), config.max_weight)
        targets.loc[current_date, :] = 0.0
        targets.loc[current_date, selected] = weight

    return targets


def _rebalance_dates(index: pd.DatetimeIndex, freq: RebalanceFreq) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(index)).sort_values()
    if freq == "daily":
        return dates
    if freq == "weekly":
        return dates.to_series().groupby(dates.to_period("W")).tail(1).index
    if freq == "biweekly":
        weeks = dates.to_series().groupby(dates.to_period("W")).tail(1)
        return weeks.iloc[1::2].index
    if freq == "monthly":
        return dates.to_series().groupby(dates.to_period("M")).tail(1).index
    raise ValueError(f"Unsupported rebalance frequency: {freq}")
