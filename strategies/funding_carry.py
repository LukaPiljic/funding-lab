"""Day 7 Step 3: funding carry strategy (NautilusTrader 2.x).

TODO
- Config: instrument_id, bar_type, trade_size, enter_apr, exit_apr
- Enter: short when funding annualises above enter_apr
- Exit: close when it falls below exit_apr
- Track funding PnL yourself (FundingRateUpdate is reference data, not a payment)
"""
