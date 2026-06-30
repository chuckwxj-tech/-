from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from aetf_momentum.data.calendar import find_missing_sessions
from aetf_momentum.data.schema import (
    REQUIRED_COLUMNS,
    normalize_symbol,
    standardize_ohlcv_frame,
    validate_ohlcv_frame,
)


def test_symbol_normalization_accepts_common_formats() -> None:
    assert normalize_symbol("510300") == "510300"
    assert normalize_symbol("SH510300") == "510300"
    assert normalize_symbol("510300.SH") == "510300"
    assert normalize_symbol("sz159915") == "159915"


def test_symbol_normalization_rejects_invalid_codes() -> None:
    with pytest.raises(ValueError, match="6 digit"):
        normalize_symbol("ETF510300A")


def test_standardize_akshare_frame_maps_fields_and_sorts_rows() -> None:
    raw = pd.DataFrame(
        {
            "日期": ["2024-01-03", "2024-01-02"],
            "开盘": [1.01, 1.00],
            "最高": [1.04, 1.02],
            "最低": [1.00, 0.99],
            "收盘": [1.03, 1.01],
            "成交量": [2000, 1000],
            "成交额": [2060.0, 1010.0],
        }
    )

    result = standardize_ohlcv_frame(raw, symbol="SH510300")

    assert list(result.columns) == REQUIRED_COLUMNS
    assert result["symbol"].tolist() == ["510300", "510300"]
    assert result["date"].dt.date.tolist() == [date(2024, 1, 2), date(2024, 1, 3)]
    assert result["close"].tolist() == [1.01, 1.03]


def test_validate_ohlcv_frame_rejects_empty_data() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_ohlcv_frame(pd.DataFrame(columns=REQUIRED_COLUMNS))


def test_validate_ohlcv_frame_rejects_duplicate_symbol_dates() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
            "symbol": ["510300", "510300"],
            "open": [1.0, 1.0],
            "high": [1.1, 1.1],
            "low": [0.9, 0.9],
            "close": [1.0, 1.0],
            "volume": [1000, 1000],
            "amount": [1000.0, 1000.0],
        }
    )

    with pytest.raises(ValueError, match="duplicate"):
        validate_ohlcv_frame(frame)


def test_validate_ohlcv_frame_rejects_missing_prices() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "symbol": ["510300"],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [None],
            "volume": [1000],
            "amount": [1000.0],
        }
    )

    with pytest.raises(ValueError, match="missing required values"):
        validate_ohlcv_frame(frame)


def test_find_missing_sessions_reports_calendar_gaps() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-04"]),
            "symbol": ["510300", "510300"],
        }
    )
    sessions = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])

    missing = find_missing_sessions(frame, sessions)

    assert missing == {"510300": [pd.Timestamp("2024-01-03")]}
