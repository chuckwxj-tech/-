from __future__ import annotations

import math
from typing import Any

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def add_cumulative_return(equity: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    result = equity.copy()
    result["cum_return"] = result["total_equity"] / initial_cash - 1
    return result


def calculate_drawdown_series(equity: pd.DataFrame) -> pd.Series:
    curve = pd.to_numeric(equity["total_equity"], errors="coerce")
    running_peak = curve.cummax()
    return curve / running_peak - 1


def calculate_performance_metrics(
    equity: pd.DataFrame,
    initial_cash: float,
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    prepared = equity.copy()
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    prepared = prepared.sort_values("date").reset_index(drop=True)

    total_equity = pd.to_numeric(prepared["total_equity"], errors="coerce")
    daily_returns = total_equity.pct_change().dropna()
    days = len(prepared)
    final_equity = float(total_equity.iloc[-1]) if days else math.nan

    cagr = _cagr(final_equity, initial_cash, days)
    annualized_return = _annualized_return(daily_returns)
    annualized_volatility = _annualized_volatility(daily_returns)
    drawdown = calculate_drawdown_series(prepared) if days else pd.Series(dtype=float)
    drawdown_metrics = _drawdown_metrics(prepared, drawdown)
    sharpe = _ratio(annualized_return - risk_free_rate, annualized_volatility)
    calmar = _ratio(cagr, abs(drawdown_metrics["max_drawdown"]))
    annualized_turnover = _annualized_turnover(prepared)

    return {
        "cagr": cagr,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "max_drawdown": drawdown_metrics["max_drawdown"],
        "max_drawdown_start": drawdown_metrics["max_drawdown_start"],
        "max_drawdown_trough": drawdown_metrics["max_drawdown_trough"],
        "max_drawdown_recovery": drawdown_metrics["max_drawdown_recovery"],
        "max_underwater_days": drawdown_metrics["max_underwater_days"],
        "sharpe": sharpe,
        "calmar": calmar,
        "annualized_turnover": annualized_turnover,
    }


def _cagr(final_equity: float, initial_cash: float, days: int) -> float:
    if days < 2 or initial_cash <= 0 or final_equity <= 0:
        return math.nan
    return (final_equity / initial_cash) ** (TRADING_DAYS_PER_YEAR / days) - 1


def _annualized_return(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return math.nan
    return float(daily_returns.mean() * TRADING_DAYS_PER_YEAR)


def _annualized_volatility(daily_returns: pd.Series) -> float:
    if len(daily_returns) < 2:
        return math.nan
    volatility = float(daily_returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
    return volatility if volatility > 0 else math.nan


def _ratio(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return math.nan
    return numerator / denominator


def _annualized_turnover(equity: pd.DataFrame) -> float:
    if "turnover" not in equity.columns or equity.empty:
        return 0.0
    turnover = pd.to_numeric(equity["turnover"], errors="coerce").fillna(0.0)
    return float(turnover.mean() * TRADING_DAYS_PER_YEAR)


def _drawdown_metrics(
    equity: pd.DataFrame,
    drawdown: pd.Series,
) -> dict[str, float | int | str | None]:
    if drawdown.empty:
        return {
            "max_drawdown": math.nan,
            "max_drawdown_start": None,
            "max_drawdown_trough": None,
            "max_drawdown_recovery": None,
            "max_underwater_days": 0,
        }

    trough_index = int(drawdown.idxmin())
    max_drawdown = float(drawdown.iloc[trough_index])
    if max_drawdown == 0:
        return {
            "max_drawdown": 0.0,
            "max_drawdown_start": None,
            "max_drawdown_trough": None,
            "max_drawdown_recovery": None,
            "max_underwater_days": 0,
        }

    peak_index = int(equity.loc[:trough_index, "total_equity"].idxmax())
    peak_value = float(equity.loc[peak_index, "total_equity"])
    recovery = equity.loc[trough_index + 1 :]
    recovered = recovery[recovery["total_equity"] >= peak_value]
    recovery_date = None
    if not recovered.empty:
        recovery_date = _iso_date(recovered.iloc[0]["date"])

    return {
        "max_drawdown": max_drawdown,
        "max_drawdown_start": _iso_date(equity.loc[peak_index, "date"]),
        "max_drawdown_trough": _iso_date(equity.loc[trough_index, "date"]),
        "max_drawdown_recovery": recovery_date,
        "max_underwater_days": _max_underwater_days(drawdown),
    }


def _max_underwater_days(drawdown: pd.Series) -> int:
    longest = 0
    current = 0
    for value in drawdown:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _iso_date(value: object) -> str:
    return str(pd.Timestamp(value).date())
