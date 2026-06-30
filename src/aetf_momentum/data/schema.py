from __future__ import annotations

import re
from typing import Final

import pandas as pd

REQUIRED_COLUMNS: Final[list[str]] = [
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
]
OPTIONAL_COLUMNS: Final[list[str]] = ["adj_factor"]
PRICE_COLUMNS: Final[list[str]] = ["open", "high", "low", "close"]
NUMERIC_COLUMNS: Final[list[str]] = [*PRICE_COLUMNS, "volume", "amount", "adj_factor"]

_COLUMN_ALIASES: Final[dict[str, str]] = {
    "日期": "date",
    "date": "date",
    "交易日期": "date",
    "代码": "symbol",
    "symbol": "symbol",
    "证券代码": "symbol",
    "开盘": "open",
    "open": "open",
    "最高": "high",
    "high": "high",
    "最低": "low",
    "low": "low",
    "收盘": "close",
    "close": "close",
    "成交量": "volume",
    "volume": "volume",
    "成交额": "amount",
    "amount": "amount",
    "复权因子": "adj_factor",
    "adj_factor": "adj_factor",
}


def normalize_symbol(symbol: str) -> str:
    """Normalize common A-share ETF symbol formats to six digits."""
    raw = str(symbol).strip().upper()
    patterns = (
        r"^(\d{6})$",
        r"^(?:SH|SZ)(\d{6})$",
        r"^(\d{6})\.(?:SH|SZ)$",
    )
    for pattern in patterns:
        match = re.match(pattern, raw)
        if match:
            return match.group(1)

    raise ValueError(f"Expected a 6 digit ETF symbol, got {symbol!r}")


def standardize_ohlcv_frame(raw: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Map AKShare-style ETF history columns to the project OHLCV schema."""
    frame = raw.copy()
    frame = frame.rename(
        columns={column: _COLUMN_ALIASES.get(str(column), str(column)) for column in frame}
    )

    if symbol is not None:
        frame["symbol"] = normalize_symbol(symbol)
    elif "symbol" in frame.columns:
        frame["symbol"] = frame["symbol"].map(normalize_symbol)

    output_columns = [*REQUIRED_COLUMNS]
    if "adj_factor" in frame.columns:
        output_columns.append("adj_factor")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    result = frame.loc[:, output_columns].copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["symbol"] = result["symbol"].map(normalize_symbol)

    for column in NUMERIC_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result.sort_values(["symbol", "date"]).reset_index(drop=True)
    validate_ohlcv_frame(result)
    return result


def validate_ohlcv_frame(frame: pd.DataFrame) -> None:
    """Validate the normalized OHLCV schema."""
    if frame.empty:
        raise ValueError("OHLCV frame is empty")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    required_non_null = ["date", "symbol", *PRICE_COLUMNS, "volume", "amount"]
    if frame[required_non_null].isna().any().any():
        raise ValueError("OHLCV frame has missing required values")

    if frame.duplicated(["symbol", "date"]).any():
        raise ValueError("OHLCV frame has duplicate symbol/date rows")

    ordered = frame.sort_values(["symbol", "date"]).index.equals(frame.index)
    if not ordered:
        raise ValueError("OHLCV frame must be sorted by symbol and date")
