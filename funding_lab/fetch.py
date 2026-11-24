"""Day 3 Step 5: download the last 365 days of BTC funding history.

TODO
- Binance:     GET  https://fapi.binance.com/fapi/v1/fundingRate  (paged, 1000 rows/call)
- Hyperliquid: POST https://api.hyperliquid.xyz/info  {"type": "fundingHistory", ...}  (paged, 500 rows/call)
- Save each venue to Parquet in data/
- Optional: add ETH
"""
