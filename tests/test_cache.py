from __future__ import annotations

import pandas as pd

from aetf_momentum.data.cache import ParquetCache


def test_raw_cache_round_trips_symbol_data(tmp_path) -> None:
    cache = ParquetCache(tmp_path)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "symbol": ["510300"],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.0],
            "volume": [1000],
            "amount": [1000.0],
        }
    )

    cache.write_raw("SH510300", frame)
    result = cache.read_raw("510300")

    pd.testing.assert_frame_equal(result, frame)


def test_panel_cache_key_is_stable_for_symbol_order(tmp_path) -> None:
    cache = ParquetCache(tmp_path)

    first = cache.panel_path(["510300", "159915"], "2024-01-01", "2024-01-31", "qfq")
    second = cache.panel_path(["159915", "510300"], "2024-01-01", "2024-01-31", "qfq")

    assert first == second
    assert first.name.startswith("etf_panel_")
