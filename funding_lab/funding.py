"""Day 2: funding rate formulas (Binance and Hyperliquid).

Everything is Decimal, like Position on Day 1, so money math doesn't drift.
Rates are plain fractions: 0.01% is Decimal("0.0001").
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional, Sequence, Tuple, Union

from funding_lab.position import Side

HOURS_PER_YEAR = Decimal(8760)  # 365 * 24
BINANCE_INTERVAL_HOURS = Decimal(8)
HYPERLIQUID_INTERVAL_HOURS = Decimal(1)
HYPERLIQUID_HOURLY_CAP = Decimal("0.04")  # 4% per hour

ZERO = Decimal(0)


def clamp(x: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    """Cut x to the range [lo, hi]."""
    if lo > hi:
        raise ValueError(f"lo ({lo}) must be <= hi ({hi})")
    return max(lo, min(x, hi))


def premium_index(impact_bid: Decimal, impact_ask: Decimal, index: Decimal) -> Decimal:
    """Binance premium index P.

    P = (max(0, ImpactBid - Index) - max(0, Index - ImpactAsk)) / Index

    Positive when even a decent-size sell fills above the index (perp is rich),
    negative when even a decent-size buy fills below it (perp is cheap),
    zero when the index sits between the two impact prices.
    """
    if index <= 0:
        raise ValueError(f"index must be positive, got {index}")
    if impact_bid > impact_ask:
        raise ValueError(f"impact_bid ({impact_bid}) must be <= impact_ask ({impact_ask})")
    return (max(ZERO, impact_bid - index) - max(ZERO, index - impact_ask)) / index


def funding_rate(
    avg_premium: Decimal,
    interest: Decimal = Decimal("0.0001"),
    band: Decimal = Decimal("0.0005"),) -> Decimal:
    """Funding rate per interval: F = P + clamp(I - P, -band, +band).

    With the defaults (I = 0.01%, band = 0.05%), any P in [-0.04%, +0.06%]
    gives exactly F = I = 0.01%. Outside that range, F = P -/+ 0.05%.
    """
    if band < 0:
        raise ValueError(f"band must be non-negative, got {band}")
    return avg_premium + clamp(interest - avg_premium, -band, band)


def payment(size: Decimal, price: Decimal, rate: Decimal, side: Side) -> Decimal:
    """Funding cash flow for one funding timestamp, from the position holder's view.

    size is in coins, price is the mark price (Binance) or oracle price (Hyperliquid).
    Returns a signed amount: negative = you pay, positive = you receive.
    Positive rate -> longs pay shorts; negative rate -> shorts pay longs.
    """
    if not isinstance(side, Side):
        raise TypeError("side must be Side.LONG or Side.SHORT")
    if size < 0:
        raise ValueError(f"size must be non-negative, got {size}")
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    amount = size * price * rate  # what a long pays when positive
    return -amount if side is Side.LONG else amount


def hyperliquid_hourly_rate(eight_hour_rate: Decimal, cap: Decimal = HYPERLIQUID_HOURLY_CAP) -> Decimal:
    """Hyperliquid computes an 8-hour rate but pays 1/8 of it every hour, capped at 4%/hour."""
    return clamp(eight_hour_rate / 8, -cap, cap)


def to_apr(rate: Decimal, interval_hours: Union[Decimal, int]) -> Decimal:
    """Simple annualisation: rate per period * periods per year.

    Binance (8h): x 1,095. Hyperliquid (1h): x 8,760.
    """
    interval_hours = Decimal(interval_hours)
    if interval_hours <= 0:
        raise ValueError(f"interval_hours must be positive, got {interval_hours}")
    return rate * (HOURS_PER_YEAR / interval_hours)


def to_apy(rate: Decimal, interval_hours: Union[Decimal, int]) -> Decimal:
    """Compounded annualisation: (1 + rate) ** periods_per_year - 1."""
    interval_hours = Decimal(interval_hours)
    if interval_hours <= 0:
        raise ValueError(f"interval_hours must be positive, got {interval_hours}")
    return (1 + rate) ** (HOURS_PER_YEAR / interval_hours) - 1


Timestamp = Union[int, float, Decimal, datetime]


def _seconds(delta) -> Decimal:
    """Turn a timestamp difference (number or timedelta) into Decimal seconds."""
    if isinstance(delta, timedelta):
        return Decimal(str(delta.total_seconds()))
    return Decimal(str(delta))


def time_weighted_average(
    samples: Iterable[Tuple[Timestamp, Decimal]],
    end: Optional[Timestamp] = None,
    max_gap: Optional[Union[int, float, Decimal, timedelta]] = None,
) -> Decimal:
    """Time-weighted average of (timestamp, value) premium samples.

    Each sample holds its value until the next sample (a step function).
    The last sample holds until `end` (defaults to the last timestamp, so it gets no weight).

    Gaps: if `max_gap` is given (e.g. 5 seconds for Binance-style sampling), a sample only
    counts for at most `max_gap` after its timestamp. Missing stretches beyond that are left out
    of the average instead of being filled with a stale value.

    Timestamps can be numbers (seconds) or datetimes; max_gap matches (seconds or timedelta).
    """
    points: Sequence[Tuple[Timestamp, Decimal]] = sorted(samples, key=lambda s: s[0])
    if not points:
        raise ValueError("need at least one sample")
    if end is not None and end < points[-1][0]:
        raise ValueError("end must not be before the last sample")

    cap = None if max_gap is None else _seconds(max_gap)
    if cap is not None and cap <= 0:
        raise ValueError(f"max_gap must be positive, got {max_gap}")

    boundaries = [t for t, _ in points[1:]] + [points[-1][0] if end is None else end]
    weighted_sum = ZERO
    total_weight = ZERO
    for (t, value), next_t in zip(points, boundaries):
        weight = _seconds(next_t - t)
        if cap is not None:
            weight = min(weight, cap)
        weighted_sum += weight * Decimal(value)
        total_weight += weight

    if total_weight == 0:
        # All samples at one instant (or a single sample): plain mean.
        return sum((Decimal(v) for _, v in points), ZERO) / len(points)
    return weighted_sum / total_weight
