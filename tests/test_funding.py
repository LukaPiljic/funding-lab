"""Day 2: test the funding functions against the Day 2 exercise answers."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from funding_lab.funding import (
    funding_rate,
    hyperliquid_hourly_rate,
    payment,
    premium_index,
    time_weighted_average,
    to_apr,
    to_apy,
)
from funding_lab.position import Side

INDEX = D(100_000)


# Step 2: premium index (index $100,000)
@pytest.mark.parametrize(
    "bid, ask, expected",
    [
        (D(100_150), D(100_200), D("0.0015")),   # +0.15%
        (D(99_700), D(99_800), D("-0.0020")),    # -0.20%
        (D(99_990), D(100_010), D(0)),           # index between impact prices
    ],
)
def test_premium_index(bid, ask, expected):
    assert premium_index(bid, ask, INDEX) == expected


def test_premium_index_rejects_bad_input():
    with pytest.raises(ValueError):
        premium_index(D(1), D(2), D(0))
    with pytest.raises(ValueError):
        premium_index(D(101), D(100), D(100))


# Step 4: clamp and full formula (I = 0.01%)
@pytest.mark.parametrize(
    "premium, expected",
    [
        (D("0.0003"), D("0.0001")),    # inside band -> F = I
        (D("0.0020"), D("0.0015")),    # clamped -> P - 0.05%
        (D("-0.0010"), D("-0.0005")),  # clamped -> P + 0.05%
        (D("0.0006"), D("0.0001")),    # edge of the band
        (D("0.0010"), D("0.0005")),
        (D("-0.0004"), D("0.0001")),   # lower edge of the band
    ],
)
def test_funding_rate(premium, expected):
    assert funding_rate(premium) == expected


# Step 5: paying funding (negative = you pay)
def test_payment_long_pays_positive_rate():
    assert payment(D("0.5"), INDEX, D("0.0001"), Side.LONG) == D(-5)


def test_payment_short_pays_negative_rate():
    assert payment(D(2), INDEX, D("-0.0005"), Side.SHORT) == D(-100)


def test_payment_counterparties_net_to_zero():
    rate = D("0.0003")
    assert payment(D(1), INDEX, rate, Side.LONG) + payment(D(1), INDEX, rate, Side.SHORT) == 0


def test_payment_self_test():
    # Long 1 BTC, mark $100,000, F = 0.02% -> pay $20
    assert payment(D(1), INDEX, D("0.0002"), Side.LONG) == D(-20)


def test_payment_rejects_bad_side():
    with pytest.raises(TypeError):
        payment(D(1), INDEX, D("0.0001"), "long")


# Step 6: Hyperliquid
def test_hyperliquid_exercise_1():
    oracle = D(10_000)
    p = premium_index(D(10_100), D(10_200), oracle)
    assert p == D("0.01")
    f8 = funding_rate(p)
    assert f8 == D("0.0095")
    hourly = hyperliquid_hourly_rate(f8)
    assert hourly == D("0.0011875")
    assert payment(D(2), oracle, hourly, Side.LONG) == D("-23.75")


def test_hyperliquid_calm_market():
    hourly = hyperliquid_hourly_rate(D("0.0001"))
    assert hourly == D("0.0000125")
    # $10,000 position: $0.125 per hour, $3 per day
    per_hour = payment(D(1), D(10_000), hourly, Side.LONG)
    assert per_hour == D("-0.125")
    assert per_hour * 24 == D(-3)


def test_hyperliquid_cap():
    assert hyperliquid_hourly_rate(D(1)) == D("0.04")
    assert hyperliquid_hourly_rate(D(-1)) == D("-0.04")


# Step 3 / 7: annualising
def test_to_apr_binance():
    assert to_apr(D("0.0001"), 8) == D("0.1095")


def test_to_apr_hyperliquid_vs_binance():
    hl = to_apr(D("0.000025"), 1)
    bn = to_apr(D("0.00015"), 8)
    assert hl == D("0.219")
    assert bn == D("0.16425")
    assert hl > bn


def test_to_apr_and_apy_hourly():
    assert to_apr(D("0.0001"), 1) == D("0.876")
    assert to_apy(D("0.0001"), 1) == pytest.approx(D("1.4012"), abs=D("0.0001"))  # ~140%


def test_to_apr_self_test():
    assert to_apr(D("0.00005"), 1) == D("0.438")


def test_to_apr_rejects_bad_interval():
    with pytest.raises(ValueError):
        to_apr(D("0.0001"), 0)


# Bonus: time-weighted average with gaps
def test_twa_equal_spacing_is_plain_mean():
    samples = [(0, D(1)), (5, D(2)), (10, D(3)), (15, D(4))]
    assert time_weighted_average(samples, end=20) == D("2.5")


def test_twa_weights_by_duration():
    # value 1 holds 10s, value 4 holds 5s -> (10 + 20) / 15 = 2
    assert time_weighted_average([(0, D(1)), (10, D(4))], end=15) == D(2)


def test_twa_last_sample_has_no_weight_without_end():
    assert time_weighted_average([(0, D(1)), (10, D(100))]) == D(1)


def test_twa_gap_is_excluded_with_max_gap():
    # Samples every 5s, then a 60s hole after t=10 (value 9 would be stale for 55s).
    samples = [(0, D(1)), (5, D(1)), (10, D(9)), (70, D(1))]
    without_cap = time_weighted_average(samples, end=75)
    with_cap = time_weighted_average(samples, end=75, max_gap=5)
    assert without_cap == D(10 + 9 * 60 + 5) / 75
    assert with_cap == D(1 * 5 + 1 * 5 + 9 * 5 + 1 * 5) / 20


def test_twa_unsorted_and_datetimes():
    t0 = datetime(2025, 11, 25, tzinfo=timezone.utc)
    samples = [(t0 + timedelta(seconds=10), D(4)), (t0, D(1))]
    assert time_weighted_average(samples, end=t0 + timedelta(seconds=15)) == D(2)


def test_twa_single_sample():
    assert time_weighted_average([(0, D("0.0003"))]) == D("0.0003")


def test_twa_rejects_empty():
    with pytest.raises(ValueError):
        time_weighted_average([])
