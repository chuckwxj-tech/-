from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aetf_momentum.backtest.costs import CostConfig
from aetf_momentum.data.schema import normalize_symbol


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.DataFrame
    trades: pd.DataFrame
    positions: pd.DataFrame


def run_backtest(
    panel: pd.DataFrame,
    target_weights: pd.DataFrame,
    costs: CostConfig,
    initial_cash: float = 1_000_000.0,
    cash_annual_yield: float = 0.0,
) -> BacktestResult:
    """Run a simple next-bar ETF allocation backtest using open execution prices."""
    prepared = panel.copy()
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    prepared["symbol"] = prepared["symbol"].map(normalize_symbol)
    prepared = prepared.sort_values(["date", "symbol"])

    open_prices = prepared.pivot(index="date", columns="symbol", values="open").sort_index()
    close_prices = prepared.pivot(index="date", columns="symbol", values="close").sort_index()
    dates = list(close_prices.index)
    symbols = list(close_prices.columns)

    aligned_targets = target_weights.copy()
    aligned_targets.index = pd.to_datetime(aligned_targets.index).normalize()
    aligned_targets.columns = [normalize_symbol(column) for column in aligned_targets.columns]
    aligned_targets = aligned_targets.reindex(columns=symbols)

    cash = float(initial_cash)
    positions = pd.Series(0.0, index=symbols)
    equity_rows: list[dict[str, float | pd.Timestamp]] = []
    position_rows: list[dict[str, float | pd.Timestamp]] = []
    trade_rows: list[dict[str, float | str | pd.Timestamp]] = []

    for index, current_date in enumerate(dates):
        turnover_notional = 0.0
        if index > 0:
            cash = _accrue_cash(
                cash,
                previous_date=dates[index - 1],
                current_date=current_date,
                annual_yield=cash_annual_yield,
            )
            signal_date = dates[index - 1]
            if signal_date in aligned_targets.index:
                signal = aligned_targets.loc[signal_date]
                if not signal.isna().all():
                    turnover_notional = _rebalance_at_open(
                        current_date=current_date,
                        signal_date=signal_date,
                        signal=signal.fillna(0.0),
                        open_prices=open_prices.loc[current_date],
                        positions=positions,
                        cash_ref=[cash],
                        costs=costs,
                        trade_rows=trade_rows,
                    )
                    cash = float(trade_rows[-1]["cash_after"]) if turnover_notional else cash

        close = close_prices.loc[current_date]
        position_value = float((positions * close).fillna(0.0).sum())
        total_equity = cash + position_value
        equity_rows.append(
            {
                "date": current_date,
                "cash": cash,
                "position_value": position_value,
                "total_equity": total_equity,
                "turnover": turnover_notional / total_equity if total_equity else 0.0,
            }
        )

        position_row: dict[str, float | pd.Timestamp] = {"date": current_date}
        position_row.update({symbol: float(positions[symbol]) for symbol in symbols})
        position_rows.append(position_row)

    return BacktestResult(
        equity=pd.DataFrame(equity_rows),
        trades=pd.DataFrame(trade_rows),
        positions=pd.DataFrame(position_rows),
    )


def _accrue_cash(
    cash: float,
    previous_date: pd.Timestamp,
    current_date: pd.Timestamp,
    annual_yield: float,
) -> float:
    if cash <= 0 or annual_yield == 0:
        return cash
    elapsed_days = max((current_date - previous_date).days, 0)
    return cash * (1 + annual_yield) ** (elapsed_days / 365)


def _rebalance_at_open(
    current_date: pd.Timestamp,
    signal_date: pd.Timestamp,
    signal: pd.Series,
    open_prices: pd.Series,
    positions: pd.Series,
    cash_ref: list[float],
    costs: CostConfig,
    trade_rows: list[dict[str, float | str | pd.Timestamp]],
) -> float:
    cash = cash_ref[0]
    open_equity = cash + float((positions * open_prices).fillna(0.0).sum())
    turnover_notional = 0.0

    trade_intents: list[tuple[float, str, float, float]] = []
    for symbol, target_weight in signal.items():
        price = open_prices.get(symbol)
        if pd.isna(price) or price <= 0:
            continue

        current_value = float(positions[symbol] * price)
        target_value = float(open_equity * target_weight)
        delta_value = target_value - current_value
        if abs(delta_value) < 1e-9:
            continue

        shares = delta_value / float(price)
        trade_intents.append((delta_value, symbol, float(price), shares))

    for delta_value, symbol, price, shares in sorted(trade_intents):
        if delta_value > 0:
            delta_value = _cap_buy_notional(delta_value, cash, costs)
            if delta_value <= 1e-9:
                continue
            shares = delta_value / price

        fee = costs.trade_cost(delta_value)
        cash -= delta_value + fee
        positions[symbol] = float(positions[symbol] + shares)
        turnover_notional += abs(delta_value)

        trade_rows.append(
            {
                "date": current_date,
                "symbol": symbol,
                "side": "buy" if shares > 0 else "sell",
                "price": float(price),
                "shares": float(shares),
                "notional": float(delta_value),
                "fee": float(fee),
                "slippage": abs(delta_value) * costs.slippage_bps / 10_000,
                "reason": f"rebalance_from_{signal_date.date().isoformat()}",
                "cash_after": float(cash),
            }
        )

    cash_ref[0] = cash
    return turnover_notional


def _cap_buy_notional(desired_notional: float, available_cash: float, costs: CostConfig) -> float:
    if desired_notional <= 0 or available_cash <= 0:
        return 0.0
    if desired_notional + costs.trade_cost(desired_notional) <= available_cash:
        return desired_notional

    low = 0.0
    high = desired_notional
    for _ in range(40):
        midpoint = (low + high) / 2
        if midpoint + costs.trade_cost(midpoint) <= available_cash:
            low = midpoint
        else:
            high = midpoint
    return low
