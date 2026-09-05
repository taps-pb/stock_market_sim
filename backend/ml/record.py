"""Record causal features, future prices, and next-tick executable quotes."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import SEED_COMPANIES, SIM_VERSION, Config
from app.engine.simulation import SimEngine
from .features import HISTORY, observable_row, oracle_row


def build_dataset(seeds: list[int], ticks: int, horizon: int = 20) -> pd.DataFrame:
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("provide distinct seeds")
    if horizon < 1 or ticks < HISTORY + horizon:
        raise ValueError("ticks must cover feature history and a positive forecast horizon")
    rows = []
    for seed in seeds:
        eng = SimEngine(Config(seed=seed), SEED_COMPANIES)
        prices = {s: [] for s in eng.symbols}
        quotes = {s: [] for s in eng.symbols}
        seed_rows = []
        for _ in range(ticks):
            eng.step()
            for s in eng.symbols:
                prices[s].append(eng.last[s])
                depth = eng.books[s].depth(8)
                bp, bq = depth["bids"][0] if depth["bids"] else (np.nan, 0)
                ap, aq = depth["asks"][0] if depth["asks"] else (np.nan, 0)
                quotes[s].append((bp, bq, ap, aq))
                if eng.tick < HISTORY or eng.tick + horizon > ticks:
                    continue
                obs = observable_row(np.array(prices[s][-HISTORY:]), depth,
                                     eng.books[s].spread(), eng.flow[s], eng.companies[s].public_fair())
                seed_rows.append({"seed": seed, "symbol": s, "tick": eng.tick,
                                  "horizon": horizon, "sim_version": SIM_VERSION,
                                  "price": eng.last[s], "bid": bp, "ask": ap,
                                  **obs, **oracle_row(eng, s)})
        for row in seed_rows:
            s, index = row["symbol"], row["tick"] - 1
            future = prices[s][index + horizon]
            row.update(future_price=future, target_return=future / row["price"] - 1,
                       y=int(future > row["price"]),
                       entry_ask=quotes[s][index + 1][2], entry_ask_qty=quotes[s][index + 1][3],
                       exit_bid=quotes[s][index + horizon][0], exit_bid_qty=quotes[s][index + horizon][1])
        rows.extend(seed_rows)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--ticks", type=int, default=3000)
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--out", default="ml/data/dataset.csv")
    a = ap.parse_args()
    df = build_dataset(list(range(1, a.seeds + 1)), a.ticks, a.horizon)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df):,} rows; {a.horizon}-tick price targets; {a.seeds} seeds", flush=True)


if __name__ == "__main__":
    main()
