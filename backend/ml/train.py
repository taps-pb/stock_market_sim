"""Train baselines + gradient-boosted trees and report directional accuracy.

Observable-only (the honest task) vs observable+oracle (the latent ceiling),
tested on UNSEEN seeds so the model must generalize to a fresh market. Run:

    python -m ml.train --data ml/data/dataset.csv
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import OBSERVABLE_COLS, ORACLE_COLS


def seed_split(df: pd.DataFrame, test_frac: float = 0.2):
    """Hold out the highest-numbered seeds as an unseen-market test set."""
    seeds = sorted(df["seed"].unique())
    n_test = max(1, round(len(seeds) * test_frac))
    test_seeds = set(seeds[-n_test:])
    tr = df[~df["seed"].isin(test_seeds)]
    te = df[df["seed"].isin(test_seeds)]
    return tr, te, sorted(test_seeds)


def _metrics(y, pred, proba=None) -> dict:
    m = {"acc": accuracy_score(y, pred), "bal_acc": balanced_accuracy_score(y, pred),
         "f1": f1_score(y, pred, zero_division=0)}
    if proba is not None and len(np.unique(y)) > 1:
        m["auc"] = roc_auc_score(y, proba)
    return m


def train_eval(df: pd.DataFrame) -> dict:
    tr, te, test_seeds = seed_split(df)
    ytr, yte = tr["y"].to_numpy(), te["y"].to_numpy()
    results: dict[str, dict] = {}

    # --- baselines ----------------------------------------------------
    maj = int(round(ytr.mean()))
    results["baseline_majority"] = _metrics(yte, np.full_like(yte, maj))
    persist = (te["ret_1"].to_numpy() > 0).astype(int)  # predict "continues last move"
    results["baseline_persistence"] = _metrics(yte, persist)

    # --- models -------------------------------------------------------
    def fit(cols, model):
        model.fit(tr[cols], ytr)
        proba = model.predict_proba(te[cols])[:, 1]
        return _metrics(yte, (proba >= 0.5).astype(int), proba)

    results["logistic_observable"] = fit(
        OBSERVABLE_COLS, make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)))
    results["gbm_observable"] = fit(OBSERVABLE_COLS, HistGradientBoostingClassifier(max_iter=300))
    results["gbm_oracle"] = fit(OBSERVABLE_COLS + ORACLE_COLS,
                                HistGradientBoostingClassifier(max_iter=300))
    return {"results": results, "test_seeds": test_seeds,
            "base_rate": float(yte.mean()), "n_train": len(tr), "n_test": len(te)}


def _report(out: dict) -> str:
    r = out["results"]
    lines = [
        f"test on unseen seeds {out['test_seeds']}  |  train rows {out['n_train']:,}  test rows {out['n_test']:,}",
        f"base rate (y=1 up on test): {out['base_rate']:.3f}",
        "",
        f"{'model':24s} {'acc':>7} {'bal_acc':>8} {'auc':>7} {'f1':>7}",
        "-" * 56,
    ]
    for name, m in r.items():
        lines.append(f"{name:24s} {m['acc']:7.3f} {m['bal_acc']:8.3f} "
                     f"{m.get('auc', float('nan')):7.3f} {m['f1']:7.3f}")
    edge = r["gbm_observable"]["acc"] - max(r["baseline_majority"]["acc"], r["baseline_persistence"]["acc"])
    lift = r["gbm_oracle"]["acc"] - r["gbm_observable"]["acc"]
    lines += [
        "-" * 56,
        f"observable edge over best baseline: {edge:+.3f}  (>0 => learnable signal exists)",
        f"oracle lift over observable:        {lift:+.3f}  (>0 => hidden latents add predictive power)",
    ]
    return "\n".join(lines)


def save_model(df: pd.DataFrame, path: str) -> None:
    """Fit the observable-only model on all data and persist it for live serving."""
    import joblib
    model = HistGradientBoostingClassifier(max_iter=300)
    model.fit(df[OBSERVABLE_COLS].to_numpy(), df["y"].to_numpy())  # array in => array in at serve (no warning)
    joblib.dump({"model": model, "cols": OBSERVABLE_COLS}, path)
    print(f"saved deployable model -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ml/data/dataset.csv")
    ap.add_argument("--report", default="ml/report.md")
    ap.add_argument("--save", default="", help="also fit on all data and save a live model here")
    a = ap.parse_args()
    df = pd.read_csv(a.data)
    out = train_eval(df)
    text = _report(out)
    print(text)
    with open(a.report, "w") as f:
        f.write("# ML prediction report\n\n```\n" + text + "\n```\n")
    if a.save:
        save_model(df, a.save)


if __name__ == "__main__":
    main()
