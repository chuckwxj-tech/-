from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SpliceMetadata:
    first_etf_date: pd.Timestamp
    proxy_observations: int
    total_observations: int
    proxy_share: float
    tracking_error_60d: float


def build_strict_total_return(
    close: pd.Series,
    split_ratios: Mapping[pd.Timestamp | str, float] | None = None,
    cash_dividends: pd.Series | None = None,
) -> pd.Series:
    """Build a total-return index from raw closes and explicit corporate actions."""
    prices = _prepare_positive_series(close, "close")
    splits = {
        pd.Timestamp(date).normalize(): float(ratio)
        for date, ratio in (split_ratios or {}).items()
    }
    if any(ratio <= 0 for ratio in splits.values()):
        raise ValueError("split ratios must be positive")

    dividends = pd.Series(0.0, index=prices.index)
    if cash_dividends is not None:
        prepared_dividends = _prepare_numeric_series(cash_dividends, "cash_dividends")
        dividends = prepared_dividends.reindex(prices.index, fill_value=0.0)

    result = pd.Series(1.0, index=prices.index, dtype=float)
    for position in range(1, len(prices)):
        date = prices.index[position]
        gross_return = (
            prices.iloc[position] * splits.get(date, 1.0) + dividends.iloc[position]
        ) / prices.iloc[position - 1]
        result.iloc[position] = result.iloc[position - 1] * gross_return
    return result


def build_cash_total_return(
    hundred_unit_income: pd.Series,
    trading_dates: Sequence[pd.Timestamp | str],
) -> pd.Series:
    """Compound official income quoted per 100 ETF units, each priced near CNY 100."""
    income = _prepare_numeric_series(hundred_unit_income, "hundred_unit_income")
    dates = pd.DatetimeIndex(pd.to_datetime(trading_dates)).normalize().sort_values().unique()
    if dates.empty:
        raise ValueError("trading_dates must not be empty")

    result = pd.Series(1.0, index=dates, dtype=float)
    for position in range(1, len(dates)):
        previous_date = dates[position - 1]
        current_date = dates[position]
        period_income = income[(income.index > previous_date) & (income.index <= current_date)]
        gross_return = float((1.0 + period_income / 10_000.0).prod())
        result.iloc[position] = result.iloc[position - 1] * gross_return
    return result


def splice_index_to_etf(
    index_level: pd.Series,
    etf_total_return: pd.Series,
) -> tuple[pd.Series, SpliceMetadata]:
    """Use an official index before ETF listing and strict ETF total return afterwards."""
    index_series = _prepare_positive_series(index_level, "index_level")
    etf_series = _prepare_positive_series(etf_total_return, "etf_total_return")
    first_etf_date = etf_series.index[0]
    if first_etf_date not in index_series.index:
        raise ValueError("index level must contain the first ETF date")

    index_normalized = index_series / index_series.iloc[0]
    combined = index_normalized[index_normalized.index <= first_etf_date].copy()
    listing_level = float(combined.loc[first_etf_date])
    etf_after_listing = etf_series[etf_series.index >= first_etf_date]
    etf_normalized = etf_after_listing / etf_after_listing.iloc[0] * listing_level
    combined = pd.concat(
        [combined[combined.index < first_etf_date], etf_normalized]
    ).sort_index()

    common_returns = pd.concat(
        [
            index_series.pct_change().rename("index"),
            etf_series.pct_change().rename("etf"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    tracking_window = common_returns.head(60)
    if len(tracking_window) < 2:
        tracking_error = math.nan
    else:
        tracking_error = float(
            (tracking_window["etf"] - tracking_window["index"]).std(ddof=1)
            * math.sqrt(252)
        )

    proxy_observations = int((combined.index < first_etf_date).sum())
    total_observations = len(combined)
    metadata = SpliceMetadata(
        first_etf_date=first_etf_date,
        proxy_observations=proxy_observations,
        total_observations=total_observations,
        proxy_share=proxy_observations / total_observations,
        tracking_error_60d=tracking_error,
    )
    return combined, metadata


def _prepare_positive_series(series: pd.Series, name: str) -> pd.Series:
    prepared = _prepare_numeric_series(series, name)
    if prepared.empty:
        raise ValueError(f"{name} must not be empty")
    if prepared.isna().any() or (prepared <= 0).any():
        raise ValueError(f"{name} must contain positive values")
    return prepared


def _prepare_numeric_series(series: pd.Series, name: str) -> pd.Series:
    prepared = pd.Series(series).copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).normalize()
    prepared = pd.to_numeric(prepared, errors="coerce").sort_index()
    if prepared.index.has_duplicates:
        raise ValueError(f"{name} contains duplicate dates")
    if prepared.isna().any():
        raise ValueError(f"{name} contains missing or non-numeric values")
    return prepared.astype(float)
