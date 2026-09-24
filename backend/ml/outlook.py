"""Train independent long-tick forecasts and evaluate a nontradable market index.

The recorded 20-tick dataset contains exact future prices. A row at t+h-20
contains the price at t+h, so longer labels need no new simulator rollout.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from math import ceil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.config import SEED_COMPANIES, SIM_VERSION
from .features import OBSERVABLE_COLS
from .train import INTERVAL_COVERAGE, SCHEMA_VERSION, forecast, train_eval

HORIZONS = (20, 60, 120)
BASE_PRICES = {symbol: float(price) for symbol, _, _, price, *_ in SEED_COMPANIES}


def relabel(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Retain issue-tick inputs; join exact target-tick prices and quotes."""
    if df.empty or df.horizon.nunique() != 1 or df.horizon.iloc[0] != 20 or horizon <= 20:
        raise ValueError("expected a 20-tick dataset and a longer horizon")
    delta = horizon - 20
    target = df[["seed", "symbol", "tick", "future_price", "exit_bid", "exit_bid_qty"]].copy()
    target["tick"] -= delta
    target = target.rename(columns={"future_price": "target_price", "exit_bid": "target_bid",
                                    "exit_bid_qty": "target_qty"})
    rows = df.merge(target, on=["seed", "symbol", "tick"], validate="one_to_one")
    rows["horizon"] = horizon
    rows["future_price"] = rows.pop("target_price")
    rows["target_return"] = rows.future_price / rows.price - 1
    rows["y"] = (rows.future_price > rows.price).astype(int)
    rows["exit_bid"] = rows.pop("target_bid")
    rows["exit_bid_qty"] = rows.pop("target_qty")
    return rows


def index_rows(df: pd.DataFrame, artifact: dict) -> pd.DataFrame:
    """One forecast/actual index point per complete market tick, using only issue inputs."""
    if set(df.symbol.unique()) != set(BASE_PRICES):
        raise ValueError("index requires exactly the six listed stocks")
    pred, lo, hi = forecast(artifact, df[OBSERVABLE_COLS].to_numpy())
    base = df.symbol.map(BASE_PRICES).to_numpy(dtype=float)
    price = df.price.to_numpy(dtype=float)
    future = df.future_price.to_numpy(dtype=float)
    ratios = df[["seed", "tick", "symbol"]].copy()
    ratios["now"] = price / base
    ratios["actual"] = future / base
    ratios["predicted"] = price * (1 + pred) / base
    ratios["lower"] = price * (1 + lo) / base
    ratios["upper"] = price * (1 + hi) / base
    grouped = ratios.groupby(["seed", "tick"], sort=True)
    complete = grouped.symbol.nunique() == len(BASE_PRICES)
    result = grouped[["now", "actual", "predicted", "lower", "upper"]].sum().loc[complete]
    return result * (100 / len(BASE_PRICES))


def calibrate_index(rows: pd.DataFrame, calibration_seeds: list[int], horizon: int) -> float:
    """Conformal index-point radius from thinned calibration markets only."""
    sample = rows[rows.index.get_level_values("seed").isin(calibration_seeds)]
    sample = sample[sample.index.get_level_values("tick") % horizon == 0]
    if sample.empty:
        raise ValueError("not enough index calibration history")
    scores = abs(sample.predicted - sample.actual)
    level = min(1, ceil((len(scores) + 1) * INTERVAL_COVERAGE) / len(scores))
    return float(np.quantile(scores, level, method="higher"))


def evaluate_index(rows: pd.DataFrame, test_seeds: list[int], pad: float) -> dict:
    sample = rows[rows.index.get_level_values("seed").isin(test_seeds)]
    if sample.empty:
        raise ValueError("no unseen index evaluation markets")
    return {"mae": float(np.mean(abs(sample.predicted - sample.actual))),
            "baseline_mae": float(np.mean(abs(sample.now - sample.actual))),
            "coverage": float(np.mean((sample.predicted - pad <= sample.actual)
                                      & (sample.actual <= sample.predicted + pad))),
            "n": len(sample)}


def train_outlook(df: pd.DataFrame, base: dict, base_sha256: str, max_iter: int = 120) -> dict:
    if (base.get("schema_version") != SCHEMA_VERSION or base.get("sim_version") != SIM_VERSION
            or base.get("cols") != OBSERVABLE_COLS or base.get("horizon") != 20
            or df.empty or df.horizon.nunique() != 1 or df.horizon.iloc[0] != 20
            or (df.sim_version != SIM_VERSION).any()):
        raise ValueError("incompatible 20-tick dataset or primary model")
    seeds = [base["train_seeds"], base["calibration_seeds"], base["test_seeds"]]
    if any(set(a) & set(b) for i, a in enumerate(seeds) for b in seeds[i + 1:]) or set(df.seed.unique()) != set().union(*map(set, seeds)):
        raise ValueError("model and dataset must share disjoint training/calibration/test seeds")
    models = {20: base}
    datasets = {20: df}
    for horizon in HORIZONS[1:]:
        datasets[horizon] = relabel(df, horizon)
        trained = train_eval(datasets[horizon], max_iter=max_iter)["artifact"]
        if [trained[k] for k in ("train_seeds", "calibration_seeds", "test_seeds")] != seeds:
            raise ValueError("long-horizon seed split differs from primary model")
        models[horizon] = trained
    index = {}
    for horizon in HORIZONS:
        rows = index_rows(datasets[horizon], models[horizon])
        pad = calibrate_index(rows, seeds[1], horizon)
        index[horizon] = {"pad": pad, "evaluation": evaluate_index(rows, seeds[2], pad)}
    return {"bundle_version": 1, "schema_version": SCHEMA_VERSION, "sim_version": SIM_VERSION,
            "cols": list(OBSERVABLE_COLS), "base_sha256": base_sha256,
            "base_prices": dict(BASE_PRICES), "models": {h: models[h] for h in HORIZONS[1:]},
            "index": index, "primary_evaluation": base["evaluation"],
            "seeds": {"train": seeds[0], "calibration": seeds[1], "test": seeds[2]}}


def report(bundle: dict) -> str:
    seeds = bundle["seeds"]
    lines = ["# Synthetic market outlook", "", "20 / 60 / 120 simulation ticks; ticks have no calendar-time mapping.",
             "The six-stock equal-weight normalized price index starts at 100 at tick 0 and is not tradable.",
             f"Stock models fit training seeds {seeds['train']}; stock and index intervals calibrate on seeds {seeds['calibration']}.",
             f"All reported errors and coverage use unseen seeds {seeds['test']}. Calls overlap in time.", "",
             "| Ticks | Stock MAE ($) | Stock baseline ($) | Stock coverage | Index MAE (points) | Index baseline (points) | Index coverage |",
             "|---:|---:|---:|---:|---:|---:|---:|"]
    for h in HORIZONS:
        stock = bundle["primary_evaluation"] if h == 20 else bundle["models"][h]["evaluation"]
        index = bundle["index"][h]["evaluation"]
        lines.append(f"| {h} | {stock['mae']:.3f} | {stock['baseline_mae']:.3f} | {stock['coverage']:.1%} | "
                     f"{index['mae']:.3f} | {index['baseline_mae']:.3f} | {index['coverage']:.1%} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="ml/data/dataset-v4.csv")
    parser.add_argument("--base", default="ml/model.pkl")
    parser.add_argument("--save", default="ml/outlook.pkl")
    parser.add_argument("--report", default="ml/outlook-report.md")
    parser.add_argument("--max-iter", type=int, default=120)
    args = parser.parse_args()
    bundle = train_outlook(pd.read_csv(args.data), joblib.load(args.base),
                           sha256(Path(args.base).read_bytes()).hexdigest(), args.max_iter)
    Path(args.save).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.save)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(report(bundle))
    print(f"saved evaluated outlook to {args.save}", flush=True)


if __name__ == "__main__":
    main()
