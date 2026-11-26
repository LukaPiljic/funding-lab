"""Day 3: test the fetchers offline with a fake HTTP session (no network)."""
import pandas as pd
import pytest

from funding_lab import fetch
from funding_lab.fetch import (
    binance_frame,
    data_path,
    fetch_binance_rows,
    fetch_hyperliquid_rows,
    hyperliquid_frame,
)

HOUR_MS = 3600 * 1000


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self.payload


class FakeSession:
    """Serves rows with time >= startTime, page_size at a time, and records each request."""

    def __init__(self, rows, time_key, page_size):
        self.rows, self.time_key, self.page_size = rows, time_key, page_size
        self.starts = []

    def _page(self, start):
        self.starts.append(start)
        hits = [r for r in self.rows if r[self.time_key] >= start]
        return FakeResponse(hits[: self.page_size])

    def get(self, url, params, timeout):
        return self._page(params["startTime"])

    def post(self, url, json, timeout):
        return self._page(json["startTime"])


def binance_rows(n, start=0):
    return [{"symbol": "BTCUSDT", "fundingTime": start + i * 8 * HOUR_MS + 3,
             "fundingRate": "0.00010000", "markPrice": "100000.0"} for i in range(n)]


def hl_rows(n, start=0):
    return [{"coin": "BTC", "time": start + i * HOUR_MS + 11,
             "fundingRate": "0.0000125", "premium": "0.0001"} for i in range(n)]


def test_binance_pages_forward_until_short_page():
    rows = binance_rows(2500)
    session = FakeSession(rows, "fundingTime", fetch.BINANCE_PAGE)
    got = fetch_binance_rows(start_ms=0, session=session, pause_s=0)
    assert len(got) == 2500
    # second request starts just after the last row of the first page
    assert session.starts == [0, rows[999]["fundingTime"] + 1, rows[1999]["fundingTime"] + 1]


def test_hyperliquid_pages_forward_and_stops_on_exact_multiple():
    rows = hl_rows(1000)  # exactly 2 full pages -> 3rd request is empty and ends the loop
    session = FakeSession(rows, "time", fetch.HYPERLIQUID_PAGE)
    got = fetch_hyperliquid_rows(start_ms=0, session=session, pause_s=0)
    assert len(got) == 1000
    assert len(session.starts) == 3


def test_error_dict_raises_instead_of_adding_keys():
    class ErrorSession:
        def get(self, url, params, timeout):
            return FakeResponse({"code": -1121, "msg": "Invalid symbol."})

    with pytest.raises(RuntimeError, match="error"):
        fetch_binance_rows("NOPE", start_ms=0, session=ErrorSession(), pause_s=0)


def test_http_error_raises():
    class Http429:
        def post(self, url, json, timeout):
            return FakeResponse([], status=429)

    with pytest.raises(RuntimeError, match="429"):
        fetch_hyperliquid_rows(start_ms=0, session=Http429(), pause_s=0)


def test_binance_frame_columns_and_apr():
    df = binance_frame(binance_rows(3))
    assert list(df.columns) == ["rate", "apr", "mark_price"]
    assert str(df.index.tz) == "UTC"
    assert df["rate"].iloc[0] == pytest.approx(0.0001)
    assert df["apr"].iloc[0] == pytest.approx(0.1095)  # x 1,095
    assert df["mark_price"].iloc[0] == 100_000


def test_hyperliquid_frame_drops_duplicates_and_annualises_hourly():
    rows = hl_rows(3)
    df = hyperliquid_frame(rows + rows[-1:])
    assert len(df) == 3
    assert df["apr"].iloc[0] == pytest.approx(0.1095)  # 0.00125% x 8,760
    assert df.index.is_monotonic_increasing


def test_empty_rows_give_empty_frame():
    df = binance_frame([])
    assert df.empty and list(df.columns) == ["rate", "apr", "mark_price"]


def test_data_path(tmp_path):
    assert data_path("binance", "BTC", tmp_path) == tmp_path / "binance_btc.parquet"


def test_frame_round_trips_through_parquet(tmp_path):
    df = hyperliquid_frame(hl_rows(5))
    path = tmp_path / "x.parquet"
    df.to_parquet(path)
    pd.testing.assert_frame_equal(pd.read_parquet(path), df)
