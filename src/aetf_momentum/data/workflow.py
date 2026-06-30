from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from aetf_momentum.data.akshare_provider import AKShareProvider
from aetf_momentum.data.cache import ParquetCache
from aetf_momentum.data.schema import normalize_symbol, standardize_ohlcv_frame


@dataclass(frozen=True)
class DataUpdateResult:
    panel_path: Path
    quality_report_path: Path
    rows: int
    symbols: list[str]


def load_universe_symbols(universe_path: str | Path) -> list[str]:
    with Path(universe_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    rows = config.get("universe", [])
    symbols: list[str] = []
    for row in rows:
        if row.get("enabled", True):
            symbols.append(normalize_symbol(row["symbol"]))
    return symbols


def update_data_cache(
    universe_path: str | Path,
    start: str,
    end: str,
    adjust: str = "qfq",
    artifacts_dir: str | Path = "artifacts",
    cache_dir: str | Path = "cache",
    provider: Any | None = None,
    refresh: bool = False,
) -> DataUpdateResult:
    symbols = load_universe_symbols(universe_path)
    if not symbols:
        raise ValueError(f"No enabled ETF symbols found in {universe_path}")

    data_provider = provider or AKShareProvider(cache=ParquetCache(cache_dir))
    panel = data_provider.get_panel(symbols, start, end, adjust, refresh=refresh)
    panel = standardize_ohlcv_frame(panel)

    panel_path = data_provider.cache.write_panel(symbols, start, end, adjust, panel)
    artifacts_path = Path(artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    quality_report_path = artifacts_path / "data_quality.html"
    quality_report_path.write_text(
        _build_quality_report(panel, symbols, start, end, adjust),
        encoding="utf-8",
    )

    return DataUpdateResult(
        panel_path=panel_path,
        quality_report_path=quality_report_path,
        rows=len(panel),
        symbols=symbols,
    )


def _build_quality_report(
    panel: pd.DataFrame,
    requested_symbols: list[str],
    start: str,
    end: str,
    adjust: str,
) -> str:
    grouped = panel.groupby("symbol").agg(
        rows=("date", "count"),
        start=("date", "min"),
        end=("date", "max"),
        missing_close=("close", lambda values: int(values.isna().sum())),
    )
    rows = "\n".join(
        "<tr>"
        f"<td>{symbol}</td>"
        f"<td>{int(stats['rows'])}</td>"
        f"<td>{pd.Timestamp(stats['start']).date()}</td>"
        f"<td>{pd.Timestamp(stats['end']).date()}</td>"
        f"<td>{int(stats['missing_close'])}</td>"
        "</tr>"
        for symbol, stats in grouped.iterrows()
    )
    missing_symbols = sorted(set(requested_symbols).difference(set(grouped.index)))
    missing_text = ", ".join(missing_symbols) if missing_symbols else "None"
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>AETF Data Quality</title></head>
<body>
<h1>AETF Data Quality</h1>
<p>Range: {start} to {end}; adjust={adjust}</p>
<p>Missing symbols: {missing_text}</p>
<table>
<thead>
<tr><th>symbol</th><th>rows</th><th>start</th><th>end</th><th>missing close</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""
