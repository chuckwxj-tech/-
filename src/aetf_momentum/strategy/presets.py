from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FactorPreset:
    name: str
    description: str
    config: dict[str, Any]


_BASE_COSTS = {
    "commission_bps": 2.5,
    "slippage_bps": 5.0,
    "min_fee": 0.0,
}
_BASE_BACKTEST = {"initial_cash": 1_000_000, "cash_annual_yield": 0.015}

_PRESETS: dict[str, FactorPreset] = {
    "risk_adjusted_momentum": FactorPreset(
        name="risk_adjusted_momentum",
        description="Multi-horizon momentum divided by 60-day annualized volatility.",
        config={
            "momentum": {
                "lookbacks": [20, 60, 120, 240],
                "weights": [0.20, 0.40, 0.30, 0.10],
                "volatility_adjusted": True,
                "volatility_lookback": 60,
                "trend_ma": 120,
                "top_k": 3,
                "max_weight": 0.50,
                "rebalance_freq": "weekly",
            },
            "costs": _BASE_COSTS,
            "backtest": _BASE_BACKTEST,
        },
    ),
    "short_momentum": FactorPreset(
        name="short_momentum",
        description="Short-horizon 20/60-day momentum for faster rotation.",
        config={
            "momentum": {
                "lookbacks": [20, 60],
                "weights": [0.40, 0.60],
                "volatility_adjusted": False,
                "top_k": 3,
                "max_weight": 0.50,
                "rebalance_freq": "weekly",
            },
            "costs": _BASE_COSTS,
            "backtest": _BASE_BACKTEST,
        },
    ),
    "daily_momentum": FactorPreset(
        name="daily_momentum",
        description="One-day relative momentum for quick smoke tests and very fast rotation.",
        config={
            "momentum": {
                "lookbacks": [1],
                "weights": [1.0],
                "volatility_adjusted": False,
                "top_k": 1,
                "max_weight": 1.0,
                "rebalance_freq": "daily",
            },
            "costs": _BASE_COSTS,
            "backtest": _BASE_BACKTEST,
        },
    ),
    "long_momentum": FactorPreset(
        name="long_momentum",
        description="Slower 120/240-day momentum with weekly top-3 allocation.",
        config={
            "momentum": {
                "lookbacks": [120, 240],
                "weights": [0.60, 0.40],
                "volatility_adjusted": False,
                "trend_ma": 120,
                "top_k": 3,
                "max_weight": 0.50,
                "rebalance_freq": "weekly",
            },
            "costs": _BASE_COSTS,
            "backtest": _BASE_BACKTEST,
        },
    ),
}


def list_factor_presets() -> list[FactorPreset]:
    return list(_PRESETS.values())


def get_factor_preset_config(name: str) -> dict[str, Any]:
    try:
        return deepcopy(_PRESETS[name].config)
    except KeyError as exc:
        options = ", ".join(sorted(_PRESETS))
        raise ValueError(f"Unknown factor preset {name!r}. Available presets: {options}") from exc
