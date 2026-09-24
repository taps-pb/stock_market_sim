"""Long-horizon labels, unseen-market index scoring, and live serving."""
import json
from hashlib import sha256

import joblib
import numpy as np
import pytest

from app.config import Config, SEED_COMPANIES
from app.engine.simulation import SimEngine
from ml.features import HISTORY, OBSERVABLE_COLS
from ml.outlook import BASE_PRICES, calibrate_index, evaluate_index, index_rows, relabel, train_outlook
from ml.predict import Predictor
from ml.record import build_dataset
from ml.train import train_eval


def test_long_horizon_index_training_and_serving(tmp_path):
    df = build_dataset([1, 2, 3, 4], 300, horizon=20)
    base = train_eval(df, max_iter=5)["artifact"]
    model_path = tmp_path / "model.pkl"
    joblib.dump(base, model_path)
    bundle = train_outlook(df, base, sha256(model_path.read_bytes()).hexdigest(), max_iter=5)
    assert set(bundle["models"]) == {60, 120}
    assert set(bundle["index"]) == {20, 60, 120}
    assert base["test_seeds"] == bundle["models"][120]["test_seeds"]
    assert set(base["test_seeds"]).isdisjoint(base["calibration_seeds"] + base["train_seeds"])
    assert all(np.isfinite(list(bundle["index"][h]["evaluation"].values())).all() for h in (20, 60, 120))

    longer = relabel(df, 120)
    sample = longer.iloc[0]
    future = df[(df.seed == sample.seed) & (df.symbol == sample.symbol) & (df.tick == sample.tick + 100)].iloc[0]
    issue = df[(df.seed == sample.seed) & (df.symbol == sample.symbol) & (df.tick == sample.tick)].iloc[0]
    assert sample.future_price == future.future_price
    assert sample.exit_bid == future.exit_bid or (np.isnan(sample.exit_bid) and np.isnan(future.exit_bid))
    np.testing.assert_array_equal(sample[OBSERVABLE_COLS].to_numpy(dtype=float), issue[OBSERVABLE_COLS].to_numpy(dtype=float))
    assert sample.y == int(sample.future_price > sample.price)

    rows = index_rows(longer, bundle["models"][120])
    cal = base["calibration_seeds"]
    pad = calibrate_index(rows, cal, 120)
    assert pad == bundle["index"][120]["pad"]
    altered = rows.copy()
    altered.loc[altered.index.get_level_values("seed").isin(base["test_seeds"]), "actual"] *= 9
    assert calibrate_index(altered, cal, 120) == pad  # no held-out labels in calibration
    assert evaluate_index(altered, base["test_seeds"], pad)["mae"] != bundle["index"][120]["evaluation"]["mae"]

    outlook_path = tmp_path / "outlook.pkl"
    joblib.dump(bundle, outlook_path)
    predictor = Predictor(str(model_path), str(outlook_path))
    engine = SimEngine(Config(seed=99), SEED_COMPANIES)
    assert 100 * sum(engine.last[s] / BASE_PRICES[s] for s in engine.symbols) / len(engine.symbols) == 100
    for _ in range(HISTORY - 1):
        engine.step()
        state = predictor.step(engine)
    assert state["outlook"]["series"] == []
    engine.step()
    state = predictor.step(engine)
    assert [s["horizon"] for s in state["outlook"]["series"]] == [20, 60, 120]
    assert state["outlook"]["index_now"] == pytest.approx(100 * sum(engine.last[s] / BASE_PRICES[s] for s in engine.symbols) / len(engine.symbols), abs=.00005)
    for checkpoint in state["outlook"]["series"]:
        assert checkpoint["target_tick"] == engine.tick + checkpoint["horizon"]
        assert set(checkpoint["stocks"]) == set(engine.symbols)
        if checkpoint["horizon"] == 20:
            assert all(checkpoint["stocks"][s]["price"] == state["signals"][s]["price"] for s in engine.symbols)
        normalized = 100 * sum(checkpoint["stocks"][s]["price"] / BASE_PRICES[s] for s in engine.symbols) / len(engine.symbols)
        assert checkpoint["index_price"] == pytest.approx(normalized, abs=.01)
        assert checkpoint["index_lower"] <= checkpoint["index_price"] <= checkpoint["index_upper"]
    json.dumps(state, allow_nan=False)
    assert predictor.step(engine) is state
    engine.step()
    engine.step()
    assert predictor.step(engine)["outlook"]["series"] == []

    bundle["base_sha256"] = "0" * 64
    joblib.dump(bundle, outlook_path)
    with pytest.raises(ValueError, match="incompatible outlook"):
        Predictor(str(model_path), str(outlook_path))
