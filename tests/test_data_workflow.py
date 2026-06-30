from __future__ import annotations

import pandas as pd

from aetf_momentum.data.cache import ParquetCache
from aetf_momentum.data.workflow import load_universe_symbols, update_data_cache


class FakeProvider:
    def __init__(self, cache: ParquetCache) -> None:
        self.cache = cache
        self.calls: list[dict[str, object]] = []

    def get_panel(self, symbols, start, end, adjust, refresh=False):
        self.calls.append(
            {
                "symbols": symbols,
                "start": start,
                "end": end,
                "adjust": adjust,
                "refresh": refresh,
            }
        )
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
                "symbol": ["510300", "510500"],
                "open": [1.0, 2.0],
                "high": [1.1, 2.1],
                "low": [0.9, 1.9],
                "close": [1.0, 2.0],
                "volume": [1000, 2000],
                "amount": [1000.0, 4000.0],
            }
        )


def test_load_universe_symbols_reads_enabled_etfs(tmp_path) -> None:
    universe_path = tmp_path / "universe.yaml"
    universe_path.write_text(
        """
universe:
  - symbol: SH510300
    name: enabled
  - symbol: 510500
    enabled: false
  - symbol: 159915.SZ
    name: enabled too
""".strip(),
        encoding="utf-8",
    )

    assert load_universe_symbols(universe_path) == ["510300", "159915"]


def test_update_data_cache_writes_panel_and_quality_report(tmp_path) -> None:
    universe_path = tmp_path / "universe.yaml"
    universe_path.write_text(
        """
universe:
  - symbol: 510300
  - symbol: 510500
""".strip(),
        encoding="utf-8",
    )
    provider = FakeProvider(ParquetCache(tmp_path / "cache"))

    result = update_data_cache(
        universe_path=universe_path,
        start="2024-01-01",
        end="2024-01-31",
        adjust="qfq",
        artifacts_dir=tmp_path / "artifacts",
        provider=provider,
        refresh=True,
    )

    assert provider.calls[0]["symbols"] == ["510300", "510500"]
    assert provider.calls[0]["refresh"] is True
    assert result.panel_path.exists()
    assert result.quality_report_path.exists()
    assert "510300" in result.quality_report_path.read_text(encoding="utf-8")
