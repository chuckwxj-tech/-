from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from aetf_momentum.data.schema import normalize_symbol


class ParquetCache:
    """Small parquet cache for raw ETF files and combined panels."""

    def __init__(self, root: str | Path = "cache") -> None:
        self.root = Path(root)
        self.raw_dir = self.root / "raw"
        self.panel_dir = self.root / "panel"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.panel_dir.mkdir(parents=True, exist_ok=True)

    def raw_path(self, symbol: str) -> Path:
        return self.raw_dir / f"{normalize_symbol(symbol)}.parquet"

    def read_raw(self, symbol: str) -> pd.DataFrame | None:
        path = self.raw_path(symbol)
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def write_raw(self, symbol: str, frame: pd.DataFrame) -> Path:
        path = self.raw_path(symbol)
        frame.to_parquet(path, index=False)
        return path

    def panel_path(self, symbols: list[str], start: str, end: str, adjust: str) -> Path:
        payload = {
            "symbols": sorted(normalize_symbol(symbol) for symbol in symbols),
            "start": str(start),
            "end": str(end),
            "adjust": str(adjust),
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return self.panel_dir / f"etf_panel_{digest}.parquet"

    def read_panel(
        self, symbols: list[str], start: str, end: str, adjust: str
    ) -> pd.DataFrame | None:
        path = self.panel_path(symbols, start, end, adjust)
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def write_panel(
        self, symbols: list[str], start: str, end: str, adjust: str, frame: pd.DataFrame
    ) -> Path:
        path = self.panel_path(symbols, start, end, adjust)
        frame.to_parquet(path, index=False)
        return path
