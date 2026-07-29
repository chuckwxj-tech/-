from __future__ import annotations

import pandas as pd
import pytest

from aetf_momentum.research.v8_data import (
    build_cash_total_return,
    build_strict_total_return,
    splice_index_to_etf,
)


def test_strict_total_return_handles_split_and_cash_dividend() -> None:
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    close = pd.Series([300.0, 102.0, 101.0], index=dates)
    dividends = pd.Series([0.0, 0.0, 2.0], index=dates)

    result = build_strict_total_return(
        close,
        split_ratios={pd.Timestamp("2026-01-05"): 3.0},
        cash_dividends=dividends,
    )

    assert result.tolist() == pytest.approx([1.0, 1.02, 1.03])


def test_cash_total_return_uses_hundred_units_at_100_yuan_each() -> None:
    income = pd.Series(
        [0.30, 0.60, 0.30],
        index=pd.to_datetime(["2026-01-02", "2026-01-04", "2026-01-05"]),
    )
    trading_dates = pd.to_datetime(["2026-01-02", "2026-01-05"])

    result = build_cash_total_return(income, trading_dates)

    expected = (1 + 0.60 / 10_000) * (1 + 0.30 / 10_000)
    assert result.tolist() == pytest.approx([1.0, expected])


def test_splice_uses_index_before_listing_and_etf_after_listing() -> None:
    dates = pd.to_datetime(
        ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
    )
    index_level = pd.Series([100.0, 110.0, 121.0, 133.1, 146.41], index=dates)
    etf_total_return = pd.Series([1.0, 1.05, 1.1025], index=dates[2:])

    result, metadata = splice_index_to_etf(index_level, etf_total_return)

    assert result.tolist() == pytest.approx([1.0, 1.1, 1.21, 1.2705, 1.334025])
    assert metadata.first_etf_date == pd.Timestamp("2026-01-06")
    assert metadata.proxy_observations == 2
    assert metadata.proxy_share == pytest.approx(2 / 5)
