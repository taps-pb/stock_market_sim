"""Price forecasts with disjoint training, calibration and unseen-seed evaluation."""
from __future__ import annotations

import argparse
from math import ceil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score

from app.config import Config, SIM_VERSION
from .features import OBSERVABLE_COLS, ORACLE_COLS

SCHEMA_VERSION = 3
INTERVAL_COVERAGE = 0.8


def seed_split(df: pd.DataFrame, test_frac: float = 0.2):
    """Hold out complete markets; no overlapping labels cross a split boundary."""
    seeds = sorted(df["seed"].unique())
    if len(seeds) < 3 or not 0 < test_frac < 1:
        raise ValueError("need at least three seeds for training, calibration and testing")
    n_test = min(len(seeds) - 2, max(1, round(len(seeds) * test_frac)))
    test_seeds = [int(s) for s in seeds[-n_test:]]
    return df[~df["seed"].isin(test_seeds)], df[df["seed"].isin(test_seeds)], test_seeds


def forecast(artifact: dict, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Same return predictions and interval ordering at evaluation and serving."""
    median = artifact["median"].predict(x)
    low = artifact["lower"].predict(x)
    high = artifact["upper"].predict(x)
    pad = artifact["interval_pad"]
    lower = np.minimum(np.minimum(low, high), median) - pad
    upper = np.maximum(np.maximum(low, high), median) + pad
    return np.maximum(median, -0.999), np.maximum(lower, -0.999), np.maximum(upper, -0.999)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def _fit_calibrator(method: str, p: np.ndarray, y: np.ndarray):
    if len(np.unique(y)) < 2:
        raise ValueError("calibration needs both up and non-up examples; record longer markets")
    if method == "isotonic":
        return IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(p, y)
    return LogisticRegression(C=1e6).fit(_logit(p), y)


def _calibrate(method: str, model, p: np.ndarray) -> np.ndarray:
    return model.predict(p) if method == "isotonic" else model.predict_proba(_logit(p))[:, 1]


def up_probability(artifact: dict, x: np.ndarray) -> np.ndarray:
    """Calibrated up probability; same mapping at evaluation and serving."""
    c = artifact["calibrator"]
    return np.clip(_calibrate(c["method"], c["model"], artifact["model"].predict_proba(x)[:, 1]), 0, 1)


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    index = np.minimum((p * bins).astype(int), bins - 1)
    return [{"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": int((index == b).sum()),
             "mean_prob": float(p[index == b].mean()), "up_rate": float(y[index == b].mean())}
            for b in range(bins) if (index == b).any()]


def _metrics(y, pred, proba=None) -> dict:
    m = {"acc": float(accuracy_score(y, pred)), "bal_acc": float(balanced_accuracy_score(y, pred)),
         "f1": float(f1_score(y, pred, zero_division=0))}
    if proba is not None and len(np.unique(y)) > 1:
        m["auc"] = float(roc_auc_score(y, proba))
        m["brier"] = float(np.mean((proba - y) ** 2))
    return m


def backtest(df: pd.DataFrame, predicted: np.ndarray, fee_bps: float) -> dict:
    """Long-only, one-share quote replay; next-tick entry, non-overlapping holds.

    ponytail: one share at displayed quotes, no market impact; use engine replay
    before evaluating larger orders or a strategy that changes the market.
    """
    rows = df.assign(predicted=predicted).sort_values(["seed", "tick", "symbol"])
    busy = {}
    exits = {}
    terminal = {}
    for key, group in rows.groupby(["seed", "symbol"]):
        liquid = group[np.isfinite(group.exit_bid) & (group.exit_bid_qty > 0)]
        exits[key] = ((liquid.tick + liquid.horizon).to_numpy(), liquid.exit_bid.to_numpy())
        terminal[key] = float(group.iloc[-1].future_price)
    profits, returns = [], []
    open_positions = delayed_exits = 0
    unrealized = 0.0
    fee = fee_bps / 10_000
    for r in rows.itertuples():
        key = (r.seed, r.symbol)
        if r.tick < busy.get(key, 0):
            continue
        # This decision uses only the quote at prediction time, never future quotes.
        cost_estimate = (r.ask - r.bid) / r.price + 2 * fee
        if not np.isfinite(cost_estimate) or r.predicted <= cost_estimate:
            continue
        if not np.isfinite(r.entry_ask) or r.entry_ask_qty < 1:
            continue
        cost = r.entry_ask * (1 + fee)
        exit_ticks, exit_bids = exits[key]
        index = int(np.searchsorted(exit_ticks, r.tick + r.horizon))
        if index == len(exit_ticks):
            # Keep the position open when no buyer appears; never erase a bad fill.
            busy[key] = float("inf")
            open_positions += 1
            unrealized += terminal[key] - cost
            continue
        busy[key] = int(exit_ticks[index])
        delayed_exits += int(exit_ticks[index] > r.tick + r.horizon)
        pnl = exit_bids[index] * (1 - fee) - cost
        profits.append(pnl)
        returns.append(pnl / cost)
    return {"trades": len(profits), "net_pnl": float(sum(profits)),
            "mean_return_bps": float(np.mean(returns) * 10_000) if returns else 0.0,
            "win_rate": float(np.mean(np.array(profits) > 0)) if profits else 0.0,
            "fee_bps": fee_bps, "delayed_exits": delayed_exits,
            "open_positions": open_positions, "unrealized_pnl": unrealized}


def train_eval(df: pd.DataFrame, max_iter: int = 120) -> dict:
    required = OBSERVABLE_COLS + ORACLE_COLS + ["seed", "tick", "y", "target_return", "future_price", "price", "horizon", "sim_version"]
    if not set(required) <= set(df.columns):
        raise ValueError("old or incomplete dataset; regenerate with python -m ml.record")
    if df.empty or (df["sim_version"] != SIM_VERSION).any() or df["horizon"].nunique() != 1 or df["horizon"].iloc[0] < 1:
        raise ValueError("dataset must use the current simulator and one positive horizon")
    if not np.isfinite(df[required].to_numpy(dtype=float)).all():
        raise ValueError("training features and targets must be finite")
    tr, te, test_seeds = seed_split(df)
    calibration_seed = int(tr["seed"].max())
    calibration = tr[tr["seed"] == calibration_seed]
    tr = tr[tr["seed"] != calibration_seed]
    if tr["y"].nunique() < 2:
        raise ValueError("training needs both up and non-up examples; record longer markets")
    x = tr[OBSERVABLE_COLS].to_numpy()
    xte = te[OBSERVABLE_COLS].to_numpy()
    ytr, yte = tr["y"].to_numpy(), te["y"].to_numpy()
    # No random early-stopping split through overlapping time-series labels.
    params = dict(max_iter=max_iter, max_leaf_nodes=15, l2_regularization=1.0,
                  early_stopping=False, random_state=42)
    artifact = {"schema_version": SCHEMA_VERSION, "sim_version": SIM_VERSION,
                "cols": list(OBSERVABLE_COLS), "horizon": int(df["horizon"].iloc[0]),
                "interval_coverage": INTERVAL_COVERAGE, "interval_pad": 0.0,
                "train_seeds": [int(s) for s in sorted(tr["seed"].unique())],
                "calibration_seeds": [calibration_seed], "test_seeds": test_seeds}
    for name, quantile in [("lower", 0.1), ("median", 0.5), ("upper", 0.9)]:
        artifact[name] = HistGradientBoostingRegressor(loss="quantile", quantile=quantile, **params)
        artifact[name].fit(x, tr["target_return"].to_numpy())
    artifact["model"] = HistGradientBoostingClassifier(**params).fit(x, ytr)

    # Thin calibration labels to one horizon per symbol to reduce overlap.
    calibration = calibration[calibration["tick"] % artifact["horizon"] == 0]
    if calibration.empty:
        raise ValueError("not enough calibration history; record longer markets")
    _, lo, hi = forecast(artifact, calibration[OBSERVABLE_COLS].to_numpy())
    ycal = calibration["target_return"].to_numpy()
    scores = np.maximum(np.maximum(lo - ycal, ycal - hi), 0)
    level = min(1, ceil((len(scores) + 1) * INTERVAL_COVERAGE) / len(scores))
    artifact["interval_pad"] = float(np.quantile(scores, level, method="higher"))

    # Choose isotonic or Platt by two-fold, time-split Brier within the calibration seed only.
    raw_cal = artifact["model"].predict_proba(calibration[OBSERVABLE_COLS].to_numpy())[:, 1]
    yup = calibration["y"].to_numpy()
    first = calibration["tick"].to_numpy() <= np.median(calibration["tick"])
    brier = {"uncalibrated": float(np.mean((raw_cal - yup) ** 2))}
    for method in ("platt", "isotonic"):
        crossed = np.empty(len(yup))
        for fit in (first, ~first):
            crossed[~fit] = _calibrate(method, _fit_calibrator(method, raw_cal[fit], yup[fit]), raw_cal[~fit])
        brier[method] = float(np.mean((crossed - yup) ** 2))
    method = min(("platt", "isotonic"), key=brier.get)
    artifact["calibrator"] = {"method": method, "model": _fit_calibrator(method, raw_cal, yup),
                              "calibration_brier": brier}

    proba = artifact["model"].predict_proba(xte)[:, 1]
    calibrated = up_probability(artifact, xte)
    pred, lo, hi = forecast(artifact, xte)
    oracle = HistGradientBoostingClassifier(**params).fit(tr[OBSERVABLE_COLS + ORACLE_COLS].to_numpy(), ytr)
    oracle_proba = oracle.predict_proba(te[OBSERVABLE_COLS + ORACLE_COLS].to_numpy())[:, 1]
    results = {
        "baseline_majority": _metrics(yte, np.full_like(yte, int(ytr.mean() >= 0.5))),
        "baseline_persistence": _metrics(yte, (te["ret_1"].to_numpy() > 0).astype(int)),
        "gbm_observable": _metrics(yte, (proba >= 0.5).astype(int), proba),
        "gbm_calibrated": _metrics(yte, (calibrated >= 0.5).astype(int), calibrated),
        "gbm_oracle": _metrics(yte, (oracle_proba >= 0.5).astype(int), oracle_proba),
    }
    actual = te["target_return"].to_numpy()
    price = te["price"].to_numpy()
    errors = (pred - actual) * price
    naive_errors = actual * price
    price_metrics = {"mae": float(np.mean(np.abs(errors))),
                     "baseline_mae": float(np.mean(np.abs(naive_errors))),
                     "rmse": float(np.sqrt(np.mean(errors ** 2))),
                     "return_mae_bps": float(np.mean(np.abs(pred - actual)) * 10_000),
                     "baseline_return_mae_bps": float(np.mean(np.abs(actual)) * 10_000),
                     "coverage": float(np.mean((actual >= lo) & (actual <= hi))),
                     "interval_width_bps": float(np.mean(hi - lo) * 10_000)}
    artifact["evaluation"] = {"direction_accuracy": results["gbm_calibrated"]["acc"], **price_metrics}
    return {"results": results, "price": price_metrics,
            "reliability": {"uncalibrated": reliability(yte, proba), "calibrated": reliability(yte, calibrated)},
            "above_entry_threshold": {"uncalibrated": float(np.mean(proba >= 0.62)),
                                      "calibrated": float(np.mean(calibrated >= 0.62))},
            "backtest": backtest(te, pred, Config().fee_bps),
            "test_seeds": test_seeds, "calibration_seeds": [calibration_seed],
            "n_train": len(tr), "n_calibration": len(calibration), "n_test": len(te),
            "artifact": artifact}


def _report(out: dict) -> str:
    p, b, a = out["price"], out["backtest"], out["artifact"]
    lines = [
        f"Simulator v{SIM_VERSION}; {a['horizon']}-tick forecasts. Synthetic data only.",
        f"Training seeds {a['train_seeds']}; calibration {out['calibration_seeds']}; unseen test {out['test_seeds']}.",
        f"Rows: {out['n_train']:,} training, {out['n_calibration']:,} thinned calibration, {out['n_test']:,} test.",
        "", "| Direction model | Accuracy | Balanced accuracy | AUC |", "|---|---:|---:|---:|",
    ]
    for name, m in out["results"].items():
        auc = f"{m['auc']:.3f}" if "auc" in m else "—"
        lines.append(f"| {name} | {m['acc']:.3f} | {m['bal_acc']:.3f} | {auc} |")
    lines += ["", f"Price MAE: **${p['mae']:.3f}**; unchanged-price baseline: **${p['baseline_mae']:.3f}**.",
              f"Price RMSE: ${p['rmse']:.3f}. Return MAE: {p['return_mae_bps']:.1f} bps "
              f"(baseline {p['baseline_return_mae_bps']:.1f} bps).",
              f"Nominal 80% interval: measured coverage **{p['coverage']:.1%}**, mean width {p['interval_width_bps']:.1f} bps.",
              "", f"Up probability calibration: **{a['calibrator']['method']}**, chosen by two-fold time-split Brier on calibration seed {out['calibration_seeds']} "
              f"({', '.join(f'{k} {v:.4f}' for k, v in a['calibrator']['calibration_brier'].items())}); refit on that seed only.",
              f"Test Brier: uncalibrated **{out['results']['gbm_observable']['brier']:.4f}**, calibrated **{out['results']['gbm_calibrated']['brier']:.4f}**. "
              f"Test rows at or above the 62% entry threshold: {out['above_entry_threshold']['uncalibrated']:.1%} uncalibrated, "
              f"{out['above_entry_threshold']['calibrated']:.1%} calibrated.",
              "", "| Reliability (test) | Bin | Rows | Mean probability | Observed up rate |", "|---|---|---:|---:|---:|"]
    lines += [f"| {name} | {r['bin']} | {r['n']:,} | {r['mean_prob']:.3f} | {r['up_rate']:.3f} |"
              for name, rows in out["reliability"].items() for r in rows]
    lines += ["", f"One-share long-only quote replay: {b['trades']} closed trades, realized net P&L **${b['net_pnl']:.2f}**, "
              f"mean net return {b['mean_return_bps']:.1f} bps/trade, win rate {b['win_rate']:.1%}.",
              f"Entry at next-tick ask; exit at horizon bid or the next available bid; {b['fee_bps']} bps fee each side. No overlapping positions per symbol.",
              f"Delayed exits: {b['delayed_exits']}; positions still open: {b['open_positions']} "
              f"(unrealized P&L at final last price: ${b['unrealized_pnl']:.2f}; not guaranteed executable).",
              "", "These are simulator benchmarks, not evidence of real-market performance. Interval coverage is empirical, "
              "not guaranteed under new regimes. Calibrated probabilities are empirical on one calibration seed, not probabilities of profitable execution. "
              "Quote replay assumes one share can fill at recorded quotes, without changing subsequent market behavior; "
              "it is not a scalable execution backtest. Test labels overlap, so row count is not an independent sample count.",
              "", "The saved model uses only training seeds; the interval pad and probability calibrator use only the calibration seed; test markets are never fitted. "
              "Agent emotions, campaign phases and live intrinsic value are oracle-only features.",
              "", "Method references: [scikit-learn quantile regression](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), "
              "[time-ordered evaluation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)."]
    return "\n".join(lines)


def save_model(df: pd.DataFrame, path: str, artifact: dict | None = None) -> None:
    artifact = artifact if artifact is not None else train_eval(df)["artifact"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    print(f"saved evaluated model to {path}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ml/data/dataset.csv")
    ap.add_argument("--report", default="ml/report.md")
    ap.add_argument("--save", default="")
    a = ap.parse_args()
    df = pd.read_csv(a.data)
    out = train_eval(df)
    report = _report(out)
    print(report, flush=True)
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text("# ML prediction report\n\n" + report + "\n")
    if a.save:
        save_model(df, a.save, out["artifact"])


if __name__ == "__main__":
    main()
