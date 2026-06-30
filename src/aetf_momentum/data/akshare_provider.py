from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from aetf_momentum.data.cache import ParquetCache
from aetf_momentum.data.schema import (
    normalize_symbol,
    standardize_ohlcv_frame,
    validate_ohlcv_frame,
)


class AKShareProvider:
    """AKShare-backed ETF data provider with parquet caching."""

    def __init__(self, ak_client: Any | None = None, cache: ParquetCache | None = None) -> None:
        self._ak_client = ak_client
        self.cache = cache or ParquetCache()

    @property
    def ak_client(self) -> Any:
        if self._ak_client is None:
            import akshare as ak

            self._ak_client = ak
        return self._ak_client

    def get_etf_spot(self) -> pd.DataFrame:
        return self.ak_client.fund_etf_spot_em().copy()

    def get_etf_history(
        self,
        symbol: str,
        start: str | date | pd.Timestamp,
        end: str | date | pd.Timestamp,
        adjust: str = "qfq",
        refresh: bool = False,
    ) -> pd.DataFrame:
        normalized_symbol = normalize_symbol(symbol)
        if not refresh:
            cached = self.cache.read_raw(normalized_symbol)
            if cached is not None:
                return cached

        raw = self.ak_client.fund_etf_hist_em(
            symbol=normalized_symbol,
            period="daily",
            start_date=_format_akshare_date(start),
            end_date=_format_akshare_date(end),
            adjust=adjust,
        )
        if raw.empty:
            raise ValueError(f"AKShare returned empty history for {normalized_symbol}")

        frame = standardize_ohlcv_frame(raw, symbol=normalized_symbol)
        self.cache.write_raw(normalized_symbol, frame)
        return frame

    def get_panel(
        self,
        symbols: list[str],
        start: str | date | pd.Timestamp,
        end: str | date | pd.Timestamp,
        adjust: str = "qfq",
        refresh: bool = False,
    ) -> pd.DataFrame:
        start_key = _format_iso_date(start)
        end_key = _format_iso_date(end)
        normalized_symbols = [normalize_symbol(symbol) for symbol in symbols]

        if not refresh:
            cached = self.cache.read_panel(normalized_symbols, start_key, end_key, adjust)
            if cached is not None:
                return cached

        frames = [
            self.get_etf_history(symbol, start_key, end_key, adjust, refresh=refresh)
            for symbol in normalized_symbols
        ]
        panel = (
            pd.concat(frames, ignore_index=True)
            .sort_values(["symbol", "date"])
            .reset_index(drop=True)
        )
        validate_ohlcv_frame(panel)
        self.cache.write_panel(normalized_symbols, start_key, end_key, adjust, panel)
        return panel


def _format_akshare_date(value: str | date | pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def _format_iso_date(value: str | date | pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")
