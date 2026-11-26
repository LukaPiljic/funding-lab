"""Day 3: test the funding statistics on small synthetic series."""
import pandas as pd
import pytest

from funding_lab.analysis import (
    BASELINE,
    analyse,
    rolling_apr,
    spread,
    summary,
    to_8h_blocks,
)
from funding_lab.fetch import binance_frame, data_path, hyperliquid_frame

HOUR_MS = 3600 * 1000


def frame(rates, freq, periods_per_year, start="2026-01-01 08:00", jitter_ms=0):
    idx = pd.date_range(start, periods=len(rates), freq=freq, tz="UTC") + pd.Timedelta(milliseconds=jitter_ms)
    df = pd.DataFrame({"rate": rates}, index=idx)
    df["apr"] = df["rate"] * periods_per_year
    return df


def test_summary_counts_baseline_with_isclose():
    # 0.1 * 0.001 is 0.00010000000000000002 in floats: == would miss it, isclose doesn't
    df = frame([0.0001, 0.1 * 0.001, -0.0002, 0.0005], "8h", 1095)
    s = summary(df, BASELINE["binance"])
    assert s["periods"] == 4
    assert s["pct_baseline"] == pytest.approx(0.5)
    assert s["pct_positive"] == pytest.approx(0.75)
    assert s["max_apr"] == pytest.approx(0.0005 * 1095)
    assert s["min_apr"] == pytest.approx(-0.0002 * 1095)
    assert s["mean_apr"] == pytest.approx(0.000125 * 1095)  # (1 + 1 - 2 + 5) / 4 bp


def test_8h_blocks_sum_hourly_rates_on_binance_clock():
    # HL prints at 01:00..16:00 (with ms jitter) -> blocks ending 08:00 and 16:00
    hourly = frame([0.0000125] * 8 + [0.00005] * 8, "1h", 8760, start="2026-01-01 01:00", jitter_ms=41)
    blocks = to_8h_blocks(hourly)
    assert list(blocks.index) == [pd.Timestamp("2026-01-01 08:00", tz="UTC"),
                                  pd.Timestamp("2026-01-01 16:00", tz="UTC")]
    assert blocks["rate"].iloc[0] == pytest.approx(0.0001)  # baseline 8h block
    assert blocks["rate"].iloc[1] == pytest.approx(0.0004)
    assert blocks["apr"].iloc[0] == pytest.approx(0.1095)


def test_8h_blocks_drop_partial_blocks():
    hourly = frame([0.0000125] * 11, "1h", 8760, start="2026-01-01 01:00")  # 01:00..11:00
    blocks = to_8h_blocks(hourly)
    assert len(blocks) == 1  # 09:00-11:00 is only 3 hours


def test_spread_aligns_despite_jitter_and_sign():
    bn = frame([0.0001, 0.0002], "8h", 1095, jitter_ms=3)
    hl = frame([0.0003, 0.0001], "8h", 1095)  # already 8h blocks
    sp = spread(hl, bn)
    assert len(sp) == 2
    assert sp["spread_apr"].iloc[0] == pytest.approx((0.0003 - 0.0001) * 1095)  # HL - Binance
    assert sp["spread_apr"].iloc[1] < 0


def test_rolling_apr_is_time_based():
    s = frame([0.0, 0.0003, 0.0003], "8h", 1095)["apr"]
    r = rolling_apr(s, "16h")  # window (t-16h, t] covers the last two prints
    assert r.iloc[-1] == pytest.approx(0.0003 * 1095)


def test_analyse_end_to_end(tmp_path):
    start = pd.Timestamp("2026-01-01", tz="UTC").value // 10**6
    bn_rows = [{"fundingTime": start + i * 8 * HOUR_MS, "fundingRate": "0.0001", "markPrice": "1"}
               for i in range(1, 30)]
    hl_rows = [{"time": start + i * HOUR_MS, "fundingRate": "0.0000125", "premium": "0"}
               for i in range(1, 30 * 8)]
    binance_frame(bn_rows).to_parquet(data_path("binance", "BTC", tmp_path))
    hyperliquid_frame(hl_rows).to_parquet(data_path("hyperliquid", "BTC", tmp_path))

    result = analyse("BTC", data_dir=tmp_path, charts_dir=tmp_path)
    table = result["table"]
    assert table.loc["binance", "pct_baseline"] == pytest.approx(1.0)
    assert table.loc["hyperliquid", "pct_baseline"] == pytest.approx(1.0)
    assert table.loc["hyperliquid_8h", "pct_baseline"] == pytest.approx(1.0)
    assert result["spread"]["spread_apr"].abs().max() == pytest.approx(0.0, abs=1e-12)
    assert (tmp_path / "funding_apr_btc.png").exists()
    assert (tmp_path / "spread_btc.png").exists()
