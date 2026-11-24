"""Day 5 (optional hour): mean reversion of funding.

TODO
- Fit AR(1) x_t = c + phi * x_{t-1} + noise on daily average funding (Day 3 data)
- Convert: a = -ln(phi) per day, b = c / (1 - phi), half-life = ln(2) / a
- Fair implied APR for 30 and 90 days; compare with Boros
"""
