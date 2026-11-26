"""Day 3 Step 6 (+ optional hour): first look at the funding data.

Run after fetch.py:  python -m funding_lab.analysis            # BTC and ETH
                     python -m funding_lab.analysis --coins BTC

Prints a summary table per venue and saves charts to charts/.

Day 9 TODO: how often the spread exceeded round-trip fees; simple carry backtest in pandas.
"""

import argparse
from pathlib import Path
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")  # no display needed, we only save PNGs
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from funding_lab.fetch import BINANCE_PERIODS_PER_YEAR, DATA_DIR, data_path  # noqa: E402

CHARTS_DIR = Path(__file__).resolve().parents[1] / "charts"

# Rate per funding period when the premium is inside the clamp band.
BASELINE = {
    "binance": 0.0001,         # 0.01% per 8h
    "hyperliquid": 0.0000125,  # 0.01% / 8 per hour
}
VENUES = ("binance", "hyperliquid")


def load(venue: str, coin: str = "BTC", data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_parquet(data_path(venue, coin, data_dir))


def summary(df: pd.DataFrame, baseline: float) -> dict:
    """Mean APR, share positive, share at baseline (np.isclose, never == on floats), max, min."""
    rate = df["rate"].to_numpy()
    return {
        "periods": len(df),
        "mean_apr": df["apr"].mean(),
        "pct_positive": (rate > 0).mean(),
        "pct_baseline": np.isclose(rate, baseline, rtol=0, atol=1e-12).mean(),
        "max_apr": df["apr"].max(),
        "min_apr": df["apr"].min(),
    }


def summary_table(frames: Dict[str, pd.DataFrame], baselines: Dict[str, float] = BASELINE) -> pd.DataFrame:
    return pd.DataFrame({name: summary(df, baselines[name]) for name, df in frames.items()}).T


def to_8h_blocks(hourly: pd.DataFrame) -> pd.DataFrame:
    """Sum Hyperliquid's hourly rates into Binance-style 8h blocks.

    A Binance print at 08:00 covers 00:00-08:00; a Hyperliquid print at t covers the hour
    before t. So floor away the ms jitter, then bin (00:00, 08:00] labelled 08:00.
    Only full blocks (8 hourly prints) are kept. A block's baseline is 0.0001, like Binance.
    """
    rate = hourly["rate"].copy()
    rate.index = rate.index.floor("h")
    grouped = rate.resample("8h", closed="right", label="right", origin="epoch")
    blocks = pd.DataFrame({"rate": grouped.sum(), "n": grouped.count()})
    blocks = blocks[blocks["n"] == 8].drop(columns="n")
    blocks["apr"] = blocks["rate"] * BINANCE_PERIODS_PER_YEAR
    blocks.index.name = "ts"
    return blocks


def on_hour(df: pd.DataFrame) -> pd.DataFrame:
    """Floor timestamps to the hour so the two venues line up when joined."""
    out = df.copy()
    out.index = out.index.floor("h")
    return out


def spread(hl_8h: pd.DataFrame, binance: pd.DataFrame) -> pd.DataFrame:
    """Hyperliquid minus Binance, per matching 8h block (APR).

    Positive spread -> HL pays more: short HL perp, long Binance perp to collect it.
    """
    joined = pd.merge(on_hour(hl_8h)[["apr"]], on_hour(binance)[["apr"]], how="inner",
                      left_index=True, right_index=True, suffixes=("_hl", "_bn"))
    joined["spread_apr"] = joined["apr_hl"] - joined["apr_bn"]
    return joined


def rolling_apr(series: pd.Series, window: str = "7D") -> pd.Series:
    return series.sort_index().rolling(window).mean()


def plot_apr(frames: Dict[str, pd.DataFrame], coin: str, path: Path) -> Path:
    """Raw APR per venue (Hyperliquid in 8h blocks so both are on the same clock) + 7-day mean."""
    fig, ax = plt.subplots(figsize=(11, 4.5))
    colors = {"binance": "#d4a017", "hyperliquid": "#2a9d8f"}
    for name, df in frames.items():
        ax.plot(df.index, df["apr"] * 100, color=colors[name], alpha=0.25, lw=0.7)
        ax.plot(df.index, rolling_apr(df["apr"]) * 100, color=colors[name], lw=1.8,
                label=f"{name} (7-day mean)")
    ax.axhline(10.95, color="grey", ls="--", lw=0.8, label="baseline 10.95%")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title(f"{coin} perp funding, APR (faint: per 8h block, bold: 7-day mean)")
    ax.set_ylabel("APR, %")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    return _save(fig, path)


def plot_spread(sp: pd.DataFrame, coin: str, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(sp.index, sp["spread_apr"] * 100, color="#6c757d", alpha=0.3, lw=0.7)
    ax.plot(sp.index, rolling_apr(sp["spread_apr"]) * 100, color="#c0392b", lw=1.8, label="7-day mean")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title(f"{coin} funding spread: Hyperliquid - Binance, 8h blocks (positive: short HL, long Binance)")
    ax.set_ylabel("spread APR, %")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    return _save(fig, path)


def _save(fig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def analyse(coin: str = "BTC", data_dir: Path = DATA_DIR, charts_dir: Optional[Path] = CHARTS_DIR) -> dict:
    raw = {venue: load(venue, coin, data_dir) for venue in VENUES}
    hl_8h = to_8h_blocks(raw["hyperliquid"])
    table = summary_table(raw)
    table_8h = summary_table({"hyperliquid_8h": hl_8h}, {"hyperliquid_8h": BASELINE["binance"]})
    sp = spread(hl_8h, raw["binance"])

    if charts_dir is not None:
        lower = coin.lower()
        plot_apr({"binance": raw["binance"], "hyperliquid": hl_8h}, coin, Path(charts_dir) / f"funding_apr_{lower}.png")
        plot_spread(sp, coin, Path(charts_dir) / f"spread_{lower}.png")

    return {"table": pd.concat([table, table_8h]), "spread": sp}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Summarise funding data and save charts")
    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH"])
    args = parser.parse_args(argv)

    for coin in (c.upper() for c in args.coins):
        result = analyse(coin)
        table = result["table"].copy()
        for col in ("mean_apr", "pct_positive", "pct_baseline", "max_apr", "min_apr"):
            table[col] = table[col].map(_pct)
        table["periods"] = table["periods"].astype(int)
        sp = result["spread"]["spread_apr"]
        print(f"\n=== {coin} ===")
        print(table.to_string())
        print(f"spread HL - Binance: mean {_pct(sp.mean())}, HL higher in {_pct((sp > 0).mean())} "
              f"of {len(sp)} blocks, |spread| > 10% APR in {_pct((sp.abs() > 0.10).mean())}")


if __name__ == "__main__":
    main()
