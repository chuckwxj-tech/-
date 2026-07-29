from __future__ import annotations

import hashlib
import json
import time
from datetime import date

import akshare as ak
import pandas as pd
import requests

CSINDEX_URL = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_FUND_URL = "https://api.fund.eastmoney.com/f10/lsjz"
FSFUND_BASE_URL = "https://api.fsfund.com/v2/webzk"
FSFUND_SIGNING_KEY = "CD364559FDA24D53B05F01E943ECDFCC"
DEFAULT_TIMEOUT = 60


def fetch_official_index(
    symbol: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    response = requests.get(
        CSINDEX_URL,
        params={
            "indexCode": symbol,
            "startDate": _compact_date(start),
            "endDate": _compact_date(end),
        },
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("code")) != "200" or not payload.get("data"):
        raise RuntimeError(f"official index request failed for {symbol}: {payload}")
    frame = pd.DataFrame(payload["data"])
    frame = frame.rename(
        columns={
            "tradeDate": "date",
            "indexCode": "symbol",
            "indexNameCnAll": "name",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
    for column in ["open", "high", "low", "close", "change", "changePct"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("date").reset_index(drop=True)


def fetch_eastmoney_etf(
    symbol: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    market = "1" if symbol.startswith(("5", "6")) else "0"
    response = requests.get(
        EASTMONEY_KLINE_URL,
        params={
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101",
            "fqt": "0",
            "beg": _compact_date(start),
            "end": _compact_date(end),
            "secid": f"{market}.{symbol}",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    rows = (payload.get("data") or {}).get("klines") or []
    if not rows:
        raise RuntimeError(f"Eastmoney ETF request returned no rows for {symbol}")
    frame = pd.DataFrame([row.split(",") for row in rows])
    frame.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude_pct",
        "change_pct",
        "change",
        "turnover_pct",
    ]
    frame.insert(1, "symbol", symbol)
    frame["date"] = pd.to_datetime(frame["date"])
    for column in frame.columns.difference(["date", "symbol"]):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("date").reset_index(drop=True)


def fetch_sina_etf(symbol: str) -> pd.DataFrame:
    market_symbol = ("sh" if symbol.startswith("5") else "sz") + symbol
    frame = ak.fund_etf_hist_sina(symbol=market_symbol).copy()
    if frame.empty:
        raise RuntimeError(f"Sina ETF request returned no rows for {symbol}")
    frame.insert(1, "symbol", symbol)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").reset_index(drop=True)


def fetch_official_cash_income(
    symbol: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    end_inclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()
    payload = _signed_fsfund_payload(
        {"fundCode": symbol, "startDate": start, "endDate": end_inclusive}
    )
    response = requests.post(
        f"{FSFUND_BASE_URL}/queryController/getFundNavList",
        data=json.dumps(payload, separators=(",", ":")),
        headers={
            "Content-Type": "application/json",
            "Origin": "https://www.fsfund.com",
            "Referer": f"https://www.fsfund.com/fund/{symbol}/fundDetail.shtml",
            "User-Agent": "Mozilla/5.0",
            "netNo": "web",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    response_payload = response.json()
    if response_payload.get("code") != "0000" or not response_payload.get("data"):
        raise RuntimeError(f"fund-manager cash request failed: {response_payload}")
    frame = pd.DataFrame(response_payload["data"])
    frame = frame.rename(
        columns={
            "fundCode": "symbol",
            "navDate": "date",
            "fundIncome": "hundred_unit_income",
            "yield": "seven_day_yield",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["hundred_unit_income"] = pd.to_numeric(
        frame["hundred_unit_income"], errors="coerce"
    )
    frame["seven_day_yield"] = pd.to_numeric(frame["seven_day_yield"], errors="coerce")
    return frame[
        ["date", "symbol", "hundred_unit_income", "seven_day_yield"]
    ].sort_values("date").reset_index(drop=True)


def fetch_eastmoney_cash_income(
    symbol: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{symbol}.html",
    }
    page_size = 200
    page = 1
    rows: list[dict[str, object]] = []
    total_count: int | None = None
    while total_count is None or len(rows) < total_count:
        response = requests.get(
            EASTMONEY_FUND_URL,
            params={
                "fundCode": symbol,
                "pageIndex": page,
                "pageSize": page_size,
                "startDate": start,
                "endDate": end,
                "_": round(time.time() * 1000),
            },
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("ErrCode") != 0:
            raise RuntimeError(f"Eastmoney cash request failed: {payload}")
        total_count = int(payload.get("TotalCount") or 0)
        page_rows = (payload.get("Data") or {}).get("LSJZList") or []
        rows.extend(page_rows)
        if not page_rows:
            break
        page += 1
    if not rows:
        raise RuntimeError(f"Eastmoney cash request returned no rows for {symbol}")
    frame = pd.DataFrame(rows)
    frame = frame.rename(
        columns={
            "FSRQ": "date",
            "DWJZ": "hundred_unit_income",
            "LJJZ": "seven_day_yield_pct",
        }
    )
    frame.insert(1, "symbol", symbol)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["hundred_unit_income"] = pd.to_numeric(
        frame["hundred_unit_income"], errors="coerce"
    )
    frame["seven_day_yield_pct"] = pd.to_numeric(
        frame["seven_day_yield_pct"], errors="coerce"
    )
    return frame[
        ["date", "symbol", "hundred_unit_income", "seven_day_yield_pct"]
    ].drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _signed_fsfund_payload(values: dict[str, object]) -> dict[str, str]:
    params = {
        key: str(value)
        for key, value in values.items()
        if value is not None and str(value) not in {"", "null"}
    }
    params["netNo"] = "web"
    params["timestamp"] = str(int(time.time() * 1000))
    sign_text = "".join(f"{key}={params[key]}&" for key in sorted(params))
    sign_text += f"key={FSFUND_SIGNING_KEY}"
    params["signature"] = hashlib.md5(sign_text.encode()).hexdigest()
    return params


def _compact_date(value: str | date) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")
