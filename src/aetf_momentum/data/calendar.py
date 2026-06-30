from __future__ import annotations

import pandas as pd


def find_missing_sessions(
    frame: pd.DataFrame, sessions: pd.DatetimeIndex | pd.Series | list[pd.Timestamp]
) -> dict[str, list[pd.Timestamp]]:
    """Return missing sessions per symbol within each symbol's observed date range."""
    if frame.empty:
        return {}

    session_index = pd.DatetimeIndex(pd.to_datetime(sessions)).normalize().sort_values()
    result: dict[str, list[pd.Timestamp]] = {}

    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"]).dt.normalize()

    for symbol, group in working.groupby("symbol"):
        observed = pd.DatetimeIndex(group["date"]).normalize().sort_values()
        if observed.empty:
            continue

        relevant = session_index[
            (session_index >= observed.min()) & (session_index <= observed.max())
        ]
        missing = relevant.difference(observed)
        if len(missing) > 0:
            result[str(symbol)] = list(missing)

    return result
