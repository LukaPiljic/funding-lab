"""Day 3 Step 5: download the last 365 days of funding history (Binance, Hyperliquid).

Floats are fine here: this is statistics, not accounting. Day 7 turns rates back into
Decimal with Decimal(str(r)) when it builds Nautilus FundingRateUpdate objects.

Output contract (Days 5, 7 and 9 read these files):
    data/{venue}_{coin}.parquet, e.g. data/binance_btc.parquet, data/hyperliquid_eth.parquet
    index: UTC DatetimeIndex "ts" (raw exchange time, may carry a few ms of jitter)
    columns: rate (per funding period), apr (simple annualisation), plus
             mark_price (Binance) or premium (Hyperliquid)

Run:  python -m funding_lab.fetch            # BTC and ETH, 365 days
      python -m funding_lab.fetch --coins BTC --days 30
"""

import argparse
import time
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

DAY_MS = 24 * 3600 * 1000

BINANCE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
BINANCE_PAGE = 1000
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"
HYPERLIQUID_PAGE = 500

BINANCE_PERIODS_PER_YEAR = 3 * 365      # 8-hour funding
HYPERLIQUID_PERIODS_PER_YEAR = 24 * 365  # hourly funding

PAUSE_S = 0.2  # be polite to rate limits


def default_start_ms(days: int = 365, now_ms: Optional[int] = None) -> int:
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    return now_ms - days * DAY_MS


def _check_page(page, venue: str) -> list:
    """Every page must be a list of rows. Error responses come back as a dict
    (Binance: {"code": ..., "msg": ...}); `rows += dict` would silently add its keys."""
    if not isinstance(page, list):
        raise RuntimeError(f"{venue} returned an error instead of rows: {page!r}")
    return page


def _paginate(fetch_page: Callable[[int], list], start_ms: int, time_key: str,
              page_size: int, end_ms: Optional[int], pause_s: float) -> list:
    """Page forward in time: ask for rows from start_ms, then from last_time + 1.

    Stops on a short page, an empty page, a page that doesn't move forward,
    or once we are past end_ms.
    """
    rows: List[dict] = []
    while True:
        page = fetch_page(start_ms)
        if not page:
            break
        rows += page
        last = int(page[-1][time_key])
        if len(page) < page_size or last < start_ms:
            break
        if end_ms is not None and last >= end_ms:
            break
        start_ms = last + 1
        if pause_s:
            time.sleep(pause_s)
    return rows


def _get_json(response: requests.Response):
    response.raise_for_status()
    return response.json()


def fetch_binance_rows(symbol: str = "BTCUSDT", start_ms: Optional[int] = None,
                       end_ms: Optional[int] = None, session=None,
                       pause_s: float = PAUSE_S) -> list:
    """Raw Binance funding rows (dicts with fundingTime, fundingRate, markPrice)."""
    http = session or requests
    start_ms = default_start_ms() if start_ms is None else start_ms

    def page(since: int) -> list:
        params = {"symbol": symbol, "startTime": since, "limit": BINANCE_PAGE}
        if end_ms is not None:
            params["endTime"] = end_ms
        return _check_page(_get_json(http.get(BINANCE_URL, params=params, timeout=10)), "Binance")

    return _paginate(page, start_ms, "fundingTime", BINANCE_PAGE, end_ms, pause_s)


def fetch_hyperliquid_rows(coin: str = "BTC", start_ms: Optional[int] = None,
                           end_ms: Optional[int] = None, session=None,
                           pause_s: float = PAUSE_S) -> list:
    """Raw Hyperliquid funding rows (dicts with time, fundingRate, premium)."""
    http = session or requests
    start_ms = default_start_ms() if start_ms is None else start_ms

    def page(since: int) -> list:
        body = {"type": "fundingHistory", "coin": coin, "startTime": since}
        if end_ms is not None:
            body["endTime"] = end_ms
        return _check_page(_get_json(http.post(HYPERLIQUID_URL, json=body, timeout=10)), "Hyperliquid")

    return _paginate(page, start_ms, "time", HYPERLIQUID_PAGE, end_ms, pause_s)


def _frame(rows: list, time_key: str, extra: dict, periods_per_year: int) -> pd.DataFrame:
    """Rows -> DataFrame indexed by UTC time with rate, apr and the extra columns."""
    columns = ["rate", "apr", *extra.values()]
    if not rows:
        return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], tz="UTC", name="ts"))
    df = pd.DataFrame(rows).drop_duplicates(time_key)
    df["ts"] = pd.to_datetime(df[time_key].astype("int64"), unit="ms", utc=True)
    df["rate"] = df["fundingRate"].astype(float)
    df["apr"] = df["rate"] * periods_per_year
    for raw, clean in extra.items():
        # Binance leaves markPrice empty ("") on some old rows.
        df[clean] = pd.to_numeric(df[raw], errors="coerce") if raw in df else float("nan")
    return df.set_index("ts").sort_index()[columns]


def binance_frame(rows: list) -> pd.DataFrame:
    return _frame(rows, "fundingTime", {"markPrice": "mark_price"}, BINANCE_PERIODS_PER_YEAR)


def hyperliquid_frame(rows: list) -> pd.DataFrame:
    return _frame(rows, "time", {"premium": "premium"}, HYPERLIQUID_PERIODS_PER_YEAR)


def binance_funding(symbol: str = "BTCUSDT", start_ms: Optional[int] = None, **kwargs) -> pd.DataFrame:
    return binance_frame(fetch_binance_rows(symbol, start_ms, **kwargs))


def hyperliquid_funding(coin: str = "BTC", start_ms: Optional[int] = None, **kwargs) -> pd.DataFrame:
    return hyperliquid_frame(fetch_hyperliquid_rows(coin, start_ms, **kwargs))


def data_path(venue: str, coin: str, data_dir: Path = DATA_DIR) -> Path:
    return Path(data_dir) / f"{venue}_{coin.lower()}.parquet"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Download funding history to data/*.parquet")
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH"])
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--out", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    start = default_start_ms(args.days)
    with requests.Session() as session:
        for coin in args.coins:
            coin = coin.upper()
            frames = {
                "binance": binance_funding(f"{coin}USDT", start, session=session),
                "hyperliquid": hyperliquid_funding(coin, start, session=session),
            }
            for venue, df in frames.items():
                path = data_path(venue, coin, args.out)
                df.to_parquet(path)
                span = f"{df.index[0]:%Y-%m-%d %H:%M} -> {df.index[-1]:%Y-%m-%d %H:%M}" if len(df) else "empty"
                print(f"{venue:12s} {coin:4s} {len(df):6d} rows  {span}  -> {path}")


if __name__ == "__main__":
    main()
