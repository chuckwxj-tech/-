from __future__ import annotations

import pandas as pd

from aetf_momentum.data.akshare_provider import AKShareProvider
from aetf_momentum.data.cache import ParquetCache


class FakeAKShare:
    def __init__(self) -> None:
        self.history_calls = 0

    def fund_etf_hist_em(self, **kwargs):
        self.history_calls += 1
        assert kwargs["symbol"] == "510300"
        assert kwargs["period"] == "daily"
        assert kwargs["start_date"] == "20240101"
        assert kwargs["end_date"] == "20240131"
        assert kwargs["adjust"] == "qfq"
        return pd.DataFrame(
            {
                "日期": ["2024-01-02"],
                "开盘": [1.0],
                "最高": [1.1],
                "最低": [0.9],
                "收盘": [1.0],
                "成交量": [1000],
                "成交额": [1000.0],
            }
        )

    def fund_etf_spot_em(self):
        return pd.DataFrame({"代码": ["510300"], "名称": ["example"]})


def test_get_etf_history_uses_akshare_and_writes_cache(tmp_path) -> None:
    fake = FakeAKShare()
    provider = AKShareProvider(ak_client=fake, cache=ParquetCache(tmp_path))

    result = provider.get_etf_history("SH510300", "2024-01-01", "2024-01-31", "qfq")

    assert fake.history_calls == 1
    assert result["symbol"].tolist() == ["510300"]
    assert provider.cache.read_raw("510300") is not None


def test_get_etf_history_uses_cache_when_refresh_is_false(tmp_path) -> None:
    fake = FakeAKShare()
    cache = ParquetCache(tmp_path)
    provider = AKShareProvider(ak_client=fake, cache=cache)

    provider.get_etf_history("510300", "2024-01-01", "2024-01-31", "qfq")
    provider.get_etf_history("510300", "2024-01-01", "2024-01-31", "qfq")

    assert fake.history_calls == 1


def test_get_panel_combines_symbols_and_uses_panel_cache(tmp_path) -> None:
    fake = FakeAKShare()
    provider = AKShareProvider(ak_client=fake, cache=ParquetCache(tmp_path))

    first = provider.get_panel(["510300"], "2024-01-01", "2024-01-31", "qfq")
    second = provider.get_panel(["510300"], "2024-01-01", "2024-01-31", "qfq")

    pd.testing.assert_frame_equal(first, second)
    assert fake.history_calls == 1
