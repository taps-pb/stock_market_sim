"""Light guards for the ML layer: dataset sanity + the leakage boundary."""
import numpy as np

from ml.features import META_COLS, OBSERVABLE_COLS, ORACLE_COLS
from ml.record import build_dataset
from ml.train import train_eval


def test_observable_set_has_no_latent():
    # the honest feature set must not contain any oracle/latent column
    assert set(OBSERVABLE_COLS).isdisjoint(ORACLE_COLS)
    assert not any(c.startswith("o_") for c in OBSERVABLE_COLS)  # oracle cols are o_*
    assert set(OBSERVABLE_COLS).isdisjoint(META_COLS + ["y"])


def test_dataset_is_clean_and_labeled():
    df = build_dataset(seeds=[1, 2], ticks=500)
    assert len(df) > 0
    feats = OBSERVABLE_COLS + ORACLE_COLS
    assert not df[feats].isna().any().any()          # no NaN/inf holes
    assert np.isfinite(df[feats].to_numpy()).all()
    assert set(df["y"].unique()) == {0, 1}           # both directions present
    assert df["seed"].nunique() == 2


def test_pipeline_runs_and_produces_valid_accuracy():
    df = build_dataset(seeds=[1, 2, 3], ticks=600)
    out = train_eval(df)
    for m in out["results"].values():
        assert 0.0 <= m["acc"] <= 1.0
    # the oracle should not do worse than observable (it strictly sees more)
    assert out["results"]["gbm_oracle"]["acc"] >= out["results"]["gbm_observable"]["acc"] - 0.05
