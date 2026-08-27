"""Generate a training dataset by running the sim headless across seeds.

Each row = one (symbol, tick) with observable + oracle features and a forward
label y = 1 if price H ticks later is higher. Run:

    python -m ml.record --seeds 10 --ticks 4000 --out ml/data/dataset.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import SEED_COMPANIES, Config
from app.engine.simulation import SimEngine

from .features import HISTORY, observable_row, oracle_row


def build_dataset(seeds: list[int], ticks: int) -> pd.DataFrame:
    cfg0 = Config()
    horizon = cfg0.candle_ticks
    warmup = max(HISTORY, cfg0.trend_window) + 1
    rows: list[dict] = []
    for seed in seeds:
        eng = SimEngine(Config(seed=seed), SEED_COMPANIES)
        prices = {s: [] for s in eng.symbols}
        for tick in range(ticks):
            eng.step()
            sent = eng._sentiment()
            for s in eng.symbols:
                prices[s].append(eng.last[s])
            if tick < warmup:
                continue
            for s in eng.symbols:
                parr = np.array(prices[s][-HISTORY:], dtype=float)
                obs = observable_row(parr, eng.books[s].depth(8), eng.books[s].spread(),
                                     eng.flow[s], eng.companies[s].public_fair(), sent)
                orc = oracle_row(eng, s)
                rows.append({"seed": seed, "symbol": s, "_idx": len(prices[s]) - 1, **obs, **orc})
        # forward labels from the full per-symbol series
        for r in rows:
            if r["seed"] != seed or "y" in r:
                continue
            ser = prices[r["symbol"]]
            j = r["_idx"] + horizon
            r["y"] = int(ser[j] > ser[r["_idx"]]) if j < len(ser) else np.nan
    df = pd.DataFrame(rows).drop(columns=["_idx"]).dropna(subset=["y"])
    df["y"] = df["y"].astype(int)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--ticks", type=int, default=4000)
    ap.add_argument("--out", default="ml/data/dataset.csv")
    a = ap.parse_args()
    df = build_dataset(list(range(1, a.seeds + 1)), a.ticks)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df):,} rows x {df.shape[1]} cols -> {a.out}")
    print(f"class balance (y=1 up): {df['y'].mean():.3f}   seeds={df['seed'].nunique()}")


if __name__ == "__main__":
    main()
