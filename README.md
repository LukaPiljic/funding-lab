# funding-lab

> TODO (Day 9): what it is, in one sentence.

## How to run

> TODO (Day 9): three commands.

Setup notes:
- Core analysis: `pip install -r requirements.txt`
- Nautilus (Day 6+): needs Python 3.13 or newer and the 2.x pre-release:
  `uv venv --python 3.14 && source .venv/bin/activate && uv pip install --pre nautilus_trader`

## Findings

> TODO (Day 9): three findings, one sentence each, each with a number.

## Charts

> TODO (Day 9): one or two charts from `charts/`.

## Next steps

> TODO (Day 9)

## Layout

| Path | What | Day |
|------|------|-----|
| `funding_lab/position.py` | Position: PnL, margin, liquidation price | 1 |
| `funding_lab/funding.py` | Premium index, funding rate, payments, APR | 2 |
| `funding_lab/fetch.py` | Download funding history (Binance, Hyperliquid) | 3 |
| `funding_lab/analysis.py` | Funding statistics, spreads, charts | 3, 9 |
| `funding_lab/swap.py` | Interest rate swap cash flows and pricing | 4, 5 |
| `funding_lab/ou.py` | AR(1) / mean-reversion fit, fair implied APR | 5 |
| `strategies/` | Nautilus funding-carry strategy and backtest | 6, 7 |
| `funding_lab/orderbook.py` | L2 order book | 8 |
| `funding_lab/rolling.py` | Welford stats, rolling z-score | 8 |
| `tests/` | pytest | all |
| `days/` | Daily progress log | all |
