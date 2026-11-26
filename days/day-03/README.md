# Day 3 — Thu 26 Nov: Funding rates II: trades, risks, real data

**Goal:** Explain the basis trade; download real funding history

## Repo deliverables

- [x] `funding_lab/fetch.py` — Binance + Hyperliquid, BTC + ETH, 365 days, paged, → Parquet
- [x] `funding_lab/analysis.py` — summary stats, HL → 8h blocks, rolling 7-day APR, HL − Binance spread
- [x] `data/` — `{binance,hyperliquid}_{btc,eth}.parquet` (gitignored, regenerate with `python -m funding_lab.fetch`)
- [x] `charts/` — `funding_apr_{btc,eth}.png`, `spread_{btc,eth}.png` (`python -m funding_lab.analysis`)
- [x] `tests/test_fetch.py`, `tests/test_analysis.py` (offline, fake HTTP session)

## Notes

### Step 1: why funding behaves as it does

- **Leverage demand** drives it: rallies → everyone wants leveraged longs → perp rich → funding up. Crashes → longs liquidated → funding falls, can go negative.
- **Positive bias**: the 0.01%/8h interest term means a small premium still gives F = 0.01%.
- **Mean reversion**: high funding attracts hedged carry traders (short perp + long spot); their shorting pushes the premium back down.
- **Spikes** come in leveraged rallies and liquidation cascades, then decay. Rising OI + high funding = crowded longs.

Exercise: +15% week with rising OI → strongly positive. Long-liquidation crash → falling, possibly negative. Sideways month → around 0.01%/8h.

### Step 2: basis trade (long 0.1 BTC spot at $100k, short 0.1 BTC perp at 5×)

Capital $10,000 spot + $2,000 margin = $12,000. ±20% move: spot ±$2,000, perp ∓$2,000 → $0.

1. 0.01%/8h for a year: $10,000 × 0.0001 = $1/period × 1,095 = **$1,095** → 1,095 / 12,000 ≈ **9.1%** on capital.
2. Fees 0.05% × 4 trades × $10,000 = **$20**.
3. 30% APR → $3,000 → **25%** on capital. −5% APR → −$500 → **−4.2%**.
4. **The trap**: short liquidated at $100,000 × (1 + 0.2 − 0.005) = **$119,500**. A 19.5% rally kills the short while the spot gain sits in another account. Fix = lower leverage or more margin, which costs return (capital efficiency vs safety).

### Step 3: cross-venue arbitrage

Short $10k Binance at 0.03%/8h → 0.03% × 1,095 = **32.85%** received. Long $10k HL at 0.00125%/h → × 8,760 = **10.95%** paid. Net **21.9% → $2,190/yr**.

Specific risks: two margin accounts (either leg can be liquidated), different settlement clocks (8h vs 1h), different index/oracle prices, the spread can flip. This venue gap is what Boros spread markets trade.

### Step 4: risk table

| Risk | Basis trade | Cross-venue arbitrage |
|------|-------------|-----------------------|
| Funding turns negative / spread flips | Yes: Feb–Apr 2026 Binance BTC averaged −0.8% to −2.2% APR | Yes: HL − Binance 7-day spread fell to −6.6% (Jan), −7.9% (Apr), −8.0% (May 2026) |
| One leg liquidated | Short perp in a rally (19.5% at 5×) | Either leg: the short in a rally, the long in a crash |
| Exchange failure / custody | Yes (exchange holds the perp, maybe the spot too) | Yes, on two venues (CEX + on-chain DEX/bridge risk) |
| Fees and slippage | Yes: 4 trades, ≈ $20 per $10k | Yes, and cost more if you rebalance margin between venues |
| Price gap between legs at exit | Spot vs perp (the basis) | Perp vs perp (Binance mark vs HL oracle) |

### Step 6: first look at the data (26 Nov 2025 → 26 Nov 2026)

Data is clean: Binance has 1,095 rows at exactly 8h steps, HL has 8,760 rows at 1h steps, no gaps. Timestamps carry a few ms of jitter, so they are floored to the hour before joining.

| BTC | periods | mean APR | % positive | % at baseline | max APR | min APR |
|-----|---------|----------|------------|---------------|---------|---------|
| Binance (8h) | 1,095 | 3.48% | 77.3% | 8.8% | 10.95% | −16.6% |
| Hyperliquid (1h) | 8,760 | 5.65% | 80.0% | 46.7% | 78.6% | −60.8% |
| Hyperliquid (8h blocks) | 1,094 | 5.65% | 81.5% | 26.5% | 29.5% | −42.3% |

| ETH | periods | mean APR | % positive | % at baseline | max APR | min APR |
|-----|---------|----------|------------|---------------|---------|---------|
| Binance (8h) | 1,095 | 2.33% | 72.2% | 5.2% | 10.95% | −40.0% |
| Hyperliquid (1h) | 8,760 | 6.03% | 82.6% | 50.7% | 73.1% | −67.2% |
| Hyperliquid (8h blocks) | 1,094 | 6.02% | 84.0% | 31.0% | 22.6% | −35.3% |

Spread HL − Binance (8h blocks): BTC mean **+2.17% APR**, HL higher in 71% of blocks, |spread| > 10% APR in 13%. ETH mean **+3.70%**, HL higher in 79%.

Observations:
1. **It was a quiet, bearish year.** BTC went from ≈ $87k to ≈ $60k. Binance BTC funding **never went above the 0.01% baseline** (max = 10.95% APR exactly) and averaged only 3.48% APR. Feb–Apr 2026 had negative monthly averages. A basis trade on Binance BTC earned 3.48% APR on notional, which is ≈ **2.9% on capital** at 5× (× 10k/12k). That compares with the textbook 9.1% from Step 2.
2. **Hyperliquid sits at the baseline far more often**: 47% of hours vs 9% of Binance periods. It pays more on average (5.65% vs 3.48%), but its hourly extremes are much wider (−61% to +79% APR). The HL − Binance spread was positive 71% of the time. That is the cross-venue trade: short HL, long Binance, ≈ +2.2% APR on notional before fees. Its capital base is two margin accounts, so the return on capital is lower still. That is thin, and the spread flips for weeks at a time.
3. **Spikes are short and mean-revert**: the worst HL hour (−61% APR on 6 Feb 2026) was a one-hour blip. Its 24h mean never left ±10.95%. The best (+79% on 21 Sep 2026) took 59 hours (≈ 2.5 days) for the 24h mean to get back inside ±10.95%. The 7-day means stay in −6.0%…+10.2% (Binance) and −6.8%…+12.9% (HL 8h blocks).

### Step 7: self-test

- **Basis trade**: long spot + short perp, same size. Price PnL cancels (Δ = +1 − 1 = 0); you keep funding (paid to shorts when positive).
- **Why the hedged short can be liquidated**: the legs live in different accounts. The spot gain doesn't top up the perp margin. At 5× with 0.5% MM, a ≈ **19.5%** rally does it.
- **Cross-venue arb**: short the perp where funding is high, long where it's low, and collect the difference. A specific risk is two margin accounts on different settlement clocks (8h vs 1h) with different oracle prices, and the spread can flip.
- **Why funding mean-reverts**: high funding pays hedged shorts to show up. Their selling compresses the premium. Liquidations also flush crowded positioning.
- **Share at baseline (my data, BTC)**: Binance **8.8%** of 8h periods. Hyperliquid **46.7%** of hours (26.5% of full 8h blocks).
