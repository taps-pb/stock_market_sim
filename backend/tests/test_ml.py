"""Causal targets, disjoint evaluation, execution costs, and live horizon scoring."""
import copy
import json
import joblib
import numpy as np
import pandas as pd
import pytest

from app.config import Config, SEED_COMPANIES
from app.engine.simulation import SimEngine
from ml.features import HISTORY, META_COLS, OBSERVABLE_COLS, ORACLE_COLS
from ml.predict import Predictor
from ml.record import build_dataset
from ml.train import backtest, forecast, seed_split, train_eval


def test_observable_set_has_no_latent_or_future_data():
    assert set(OBSERVABLE_COLS).isdisjoint(ORACLE_COLS + META_COLS)
    assert not any(c.startswith("o_") or c.startswith("sent_") for c in OBSERVABLE_COLS)
    assert set(OBSERVABLE_COLS).isdisjoint(["y", "price", "future_price", "target_return", "entry_ask", "exit_bid"])


def test_dataset_matches_exact_future_prices_and_causal_prefix():
    horizon = 7
    df = build_dataset([1], 100, horizon)
    prefix = build_dataset([1], 90, horizon)
    pd.testing.assert_frame_equal(df[df.tick <= 90 - horizon].reset_index(drop=True), prefix)
    assert np.isfinite(df[OBSERVABLE_COLS + ORACLE_COLS].to_numpy()).all()
    eng = SimEngine(Config(seed=1), SEED_COMPANIES)
    prices = {}
    for _ in range(100):
        eng.step()
        prices[eng.tick] = dict(eng.last)
    for row in df.itertuples():
        assert row.future_price == prices[row.tick + horizon][row.symbol]
        assert row.target_return == pytest.approx(row.future_price / row.price - 1)
        assert row.y == int(row.future_price > row.price)
    with pytest.raises(ValueError, match="three seeds"):
        seed_split(df)
    with pytest.raises(ValueError, match="ticks"):
        build_dataset([1], 10)


def test_training_and_live_scoring_use_saved_horizon(tmp_path):
    df = build_dataset([1, 2, 3, 4], 170, horizon=7)
    out = train_eval(df, max_iter=10)
    for m in out["results"].values():
        assert 0 <= m["acc"] <= 1
    assert 0 <= out["price"]["coverage"] <= 1
    artifact = out["artifact"]
    assert set(artifact["train_seeds"]).isdisjoint(artifact["test_seeds"] + artifact["calibration_seeds"])
    assert set(artifact["test_seeds"]).isdisjoint(artifact["calibration_seeds"])
    # Even replacing every held-out outcome cannot change the fitted model or interval.
    altered = df.copy()
    held_out = altered.seed.isin(artifact['test_seeds'])
    altered.loc[held_out, 'y'] = 1 - altered.loc[held_out, 'y']
    altered.loc[held_out, 'target_return'] *= -1
    altered.loc[held_out, 'future_price'] = altered.loc[held_out, 'price'] * (1 + altered.loc[held_out, 'target_return'])
    other = train_eval(altered, max_iter=10)['artifact']
    features = df[OBSERVABLE_COLS].to_numpy()
    np.testing.assert_array_equal(artifact['model'].predict_proba(features), other['model'].predict_proba(features))
    np.testing.assert_array_equal(forecast(artifact, features), forecast(other, features))
    path = tmp_path / "model.pkl"
    joblib.dump(artifact, path)
    predictor = Predictor(str(path))
    engine = SimEngine(Config(seed=99, candle_ticks=40), SEED_COMPANIES)
    for _ in range(HISTORY):
        engine.step()
        state = predictor.step(engine)
    assert len(state["signals"]) == len(engine.symbols)
    assert state["horizon"] == 7 and state["n"] == 0
    assert state["review"]["recent"] == []
    assert all(row["n"] == 0 and row["mae"] is None
               for row in state["review"]["by_symbol"].values())
    first_prices = dict(engine.last)
    first_signals = state["signals"]
    hidden_changed = copy.deepcopy(engine)
    for company in hidden_changed.companies.values():
        company.eps *= 10  # unpublished live fundamentals are forbidden model inputs
    for trader in hidden_changed.traders:
        trader.fear, trader.greed, trader.phase = 1., 1., 'markdown'
    for symbol in engine.symbols:
        np.testing.assert_array_equal(predictor._vector(engine, symbol), predictor._vector(hidden_changed, symbol))
    # Offline and online feature construction agree on the same market prefix.
    replay = build_dataset([99], HISTORY + 7, horizon=7)
    for s in engine.symbols:
        row = replay[replay.symbol == s].iloc[0]
        np.testing.assert_allclose(predictor._vector(engine, s), row[OBSERVABLE_COLS].to_numpy(dtype=float))
    for _ in range(6):
        engine.step()
        state = predictor.step(engine)
    assert state["review"]["recent"] == []  # actual prices withheld until target tick
    engine.step()
    state = predictor.step(engine)
    assert state["n"] == len(engine.symbols)
    expected_baseline = np.mean([abs(engine.last[s] - first_prices[s]) for s in engine.symbols])
    assert state["baseline_mae"] == pytest.approx(expected_baseline)
    assert predictor.step(engine) == state  # duplicate callback must not score twice
    assert len(state["review"]["recent"]) == len(engine.symbols)
    for call in state["review"]["recent"]:
        symbol = call["symbol"]
        assert call["issued_tick"] == HISTORY and call["target_tick"] == engine.tick
        assert call["starting_price"] == first_prices[symbol]
        assert call["actual_price"] == engine.last[symbol]
        assert call["abs_error"] == pytest.approx(abs(call["predicted_price"] - engine.last[symbol]))
        assert call["covered"] == (call["lower"] <= engine.last[symbol] <= call["upper"])
        assert state["review"]["by_symbol"][symbol]["mae"] == pytest.approx(call["abs_error"])
    for _ in range(22):
        engine.step()
        state = predictor.step(engine)
    assert len(state["review"]["recent"]) == 120
    assert state["review"]["recent"][0]["target_tick"] == engine.tick
    assert all(row["n"] == 23 for row in state["review"]["by_symbol"].values())
    json.dumps(state["review"], allow_nan=False)  # persisted snapshots and WebSocket payloads
    for sig in first_signals.values():
        assert 0 < sig["lower"] <= sig["price"] <= sig["upper"]
        assert sig["target_tick"] == HISTORY + 7
    engine.step()
    engine.step()  # a missing tick invalidates features and exact-horizon calls
    reset = predictor.step(engine)
    assert reset["n"] == 0 and not reset["signals"]
    assert reset["review"]["recent"] == []
    assert all(row["n"] == 0 and row["coverage"] is None
               for row in reset["review"]["by_symbol"].values())
    artifact["sim_version"] = -1
    joblib.dump(artifact, path)
    with pytest.raises(ValueError, match="incompatible"):
        Predictor(str(path))


def test_backtest_uses_next_ask_exit_bid_fees_and_nonoverlapping_positions():
    df = pd.DataFrame([dict(seed=1, symbol="X", tick=t, horizon=2, price=100,
                            bid=99, ask=101, entry_ask=102, entry_ask_qty=1,
                            exit_bid=101, exit_bid_qty=1, future_price=101) for t in [60, 61, 62]])
    result = backtest(df, np.full(3, 0.1), fee_bps=10)
    assert result["trades"] == 2
    assert result["net_pnl"] == pytest.approx(2 * (101 * .999 - 102 * 1.001))
    assert result["win_rate"] == 0  # rising-price signal can still lose after execution
    assert backtest(df, np.zeros(3), 10)["trades"] == 0
    df.loc[0, "exit_bid"] = np.nan
    delayed = backtest(df, np.full(3, 0.1), 10)
    assert delayed["trades"] == 1 and delayed["delayed_exits"] == 1
    df["exit_bid"] = np.nan
    stranded = backtest(df, np.full(3, 0.1), 10)
    assert stranded["trades"] == 0 and stranded["open_positions"] == 1
    assert stranded["unrealized_pnl"] == pytest.approx(101 - 102 * 1.001)
