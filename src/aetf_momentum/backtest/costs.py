from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CostConfig:
    commission_bps: float = 2.5
    slippage_bps: float = 5.0
    min_fee: float = 0.0

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None) -> CostConfig:
        values = values or {}
        return cls(
            commission_bps=float(values.get("commission_bps", cls.commission_bps)),
            slippage_bps=float(values.get("slippage_bps", cls.slippage_bps)),
            min_fee=float(values.get("min_fee", cls.min_fee)),
        )

    def trade_cost(self, notional: float) -> float:
        variable_cost = abs(notional) * (self.commission_bps + self.slippage_bps) / 10_000
        if notional == 0:
            return 0.0
        return max(variable_cost, self.min_fee)
