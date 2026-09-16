"""Historical information boundaries, exact scoring, execution and durable results."""
import asyncio
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.arena import Arena, Experiment, RunStore
from app.replay import (DatasetStore, HistoricalArena, HORIZON, MAX_BYTES, direction_metrics,
                        model_fingerprint, split_dates, train_historical, training_rows)
from ml.predict import Predictor


@pytest.fixture(scope="module")
def frame():
    rng = np.random.default_rng(1729)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .015, 1000)))
    return pd.DataFrame(dict(date=pd.bdate_range('2010-01-01', periods=1000).strftime('%Y-%m-%d'),
                             symbol='SECRET', open=close * .999, high=close * 1.01,
                             low=close * .99, close=close, volume=1000))


@pytest.fixture(scope="module")
def models(frame):
    return Predictor(str(Path(__file__).resolve().parents[1] / 'ml/model.pkl')), train_historical(frame, split_dates(frame), max_iter=10)


def test_import_is_normalized_idempotent_validated_and_fingerprinted(tmp_path, frame):
    store = DatasetStore(tmp_path)
    raw = frame.to_csv(index=False).encode()
    meta = store.import_csv(raw, '../secret.csv')
    assert meta['name'] == 'secret.csv' and meta['max_duration'] == 130
    assert store.import_csv(raw, 'other.csv') == meta
    assert len(store.list()) == 1
    pd.testing.assert_frame_equal(store.load(meta['id']), frame, check_dtype=False)
    for bad in [b'', b'x' * (MAX_BYTES + 1), b'wrong,header\n1,2', b'\xff']:
        with pytest.raises(ValueError):
            store.import_csv(bad, 'bad.csv')
    for changed in [pd.concat([frame, frame.iloc[:1]]), frame.iloc[::-1], frame.iloc[:200],
                    frame.assign(close=np.nan), frame.assign(volume=-1), frame.assign(low=1e6),
                    frame.assign(date='2020-99-99'), frame.assign(symbol='../../escape')]:
        with pytest.raises(ValueError):
            store.import_csv(changed.to_csv(index=False).encode(), 'bad.csv')
    with pytest.raises(ValueError):
        store.load('../escape')
    (tmp_path / f"{meta['id']}.csv").write_bytes(raw + b'changed')
    with pytest.raises(ValueError, match='fingerprint'):
        store.load(meta['id'])
    assert store.import_csv(raw, 'repaired.csv')['id'] == meta['id']
    assert len(store.load(meta['id'])) == 1000


def test_test_outcomes_cannot_change_training_or_calibration(frame, models):
    splits = split_dates(frame)
    assert splits['train_end'] == frame.date.iloc[699]
    assert splits['calibration_start'] == frame.date.iloc[720]
    assert splits['calibration_end'] == frame.date.iloc[849]
    assert splits['test_start'] == frame.date.iloc[870]
    changed = frame.copy()
    changed.loc[changed.date >= frame.date.iloc[850], 'close'] *= 5
    before, after = training_rows(frame, splits), training_rows(changed, splits)
    for key in before:
        for a, b in zip(before[key], after[key]):
            np.testing.assert_array_equal(a, b)
    fitted = train_historical(changed, splits, max_iter=10)
    assert model_fingerprint(fitted) == model_fingerprint(models[1])
    # Last train decision is index 679: target index 699, never calibration data.
    assert before['train'][1][-1] == pytest.approx(frame.close.iloc[699] / frame.close.iloc[679] - 1)


def test_blind_prefix_maturity_pause_and_reproducibility(frame, models):
    sim, historical = models
    first = HistoricalArena(frame, 'a' * 64, 42, 100, sim, historical)
    changed = frame.copy()
    changed.loc[first.start + 25:, 'close'] *= 3
    second = HistoricalArena(changed, 'a' * 64, 42, 100, sim, historical)
    for _ in range(25):
        first.step(); second.step()
        assert first.predictions == second.predictions
    live = first.snapshot()
    assert live['replay']['metrics']['n'] == 1
    call = first.outcomes[0]
    assert call['day'] == 1 and call['target_day'] == 21
    assert call['actual'] == frame.close.iloc[first.start + 20]
    encoded = json.dumps(live, allow_nan=False)
    assert 'SECRET' not in encoded and frame.date.iloc[first.start] not in encoded
    assert live['replay']['reveal'] is None and len(live['replay']['bars']) == 25 + 59
    first.status = 'paused'; first.step()
    assert first.elapsed == 25
    first.status = 'running'
    while not first.terminal:
        first.step()
    assert first.elapsed == 100 and first.metrics()['n'] == 4
    assert first.snapshot()['replay']['unscored_checkpoints'] == 1
    assert first.snapshot()['replay']['reveal']['symbol'] == 'SECRET'
    repeated = HistoricalArena(frame, 'a' * 64, 42, 100, sim, historical)
    while not repeated.terminal:
        repeated.step()
    assert first.result()['replay'] == repeated.result()['replay']
    json.dumps(first.result(), allow_nan=False)


def test_paper_next_open_target_close_fees_and_stranded_inventory(frame, models, monkeypatch):
    from app import replay
    monkeypatch.setattr(replay, 'predict_prices', lambda artifact, row, initial, cols:
                        dict(prob=.9, price=float(initial * 1.1), lower=float(initial), upper=float(initial * 1.2), return_pct=10.))
    arena = HistoricalArena(frame, 'b' * 64, 2, 100, *models)
    arena.step()
    assert arena.paper['historical']['position'] is None
    arena.step()
    entry = float(frame.open.iloc[arena.start + 1])
    assert arena.paper['historical']['position']['entry'] == entry
    for _ in range(19):
        arena.step()
    p = arena.paper['historical']
    close = float(frame.close.iloc[arena.start + 20])
    assert p['trades'] == 1 and p['net_pnl'] == pytest.approx(close * .9999 - entry * 1.0001)
    assert p['fees'] == pytest.approx((entry + close) * .0001)
    while not arena.terminal:
        arena.step()
    assert arena.paper['historical']['trades'] == 4
    assert arena.paper['historical']['position']['target_day'] == 101
    assert arena.snapshot()['replay']['paper']['historical']['unrealized_pnl'] != 0
    early = HistoricalArena(frame, 'b' * 64, 2, 100, *models)
    early.step(); early.finish(); early.step()
    assert early.elapsed == 1 and early.paper['historical']['pending'] == 21
    assert early.paper['historical']['position'] is None and early.paper['historical']['fees'] == 0
    assert direction_metrics([True, False], [True, True]) == {'accuracy': .5, 'balanced_accuracy': .5}
    assert direction_metrics([False], [False])['balanced_accuracy'] is None


def test_archive_pagination_old_runs_finish_and_interrupt(tmp_path, frame, models):
    store = RunStore(tmp_path / 'runs.db')
    synthetic = Arena(Experiment(), None)
    store.save(synthetic)
    arena = HistoricalArena(frame, 'c' * 64, 3, 100, *models)
    arena.step(); arena.finish()
    assert arena.elapsed == 1 and arena.snapshot()['replay']['reveal']
    store.save(arena); store.save(arena)
    page = store.page(limit=1)
    assert page['total'] == 2 and len(page['items']) == 1
    assert store.page(limit=1, offset=1)['items'][0]['id'] != page['items'][0]['id']
    assert store.page(kind='historical')['total'] == 1
    assert store.get(arena.id)['replay']['predictions'] == arena.predictions
    arena = HistoricalArena(frame, 'd' * 64, 4, 100, *models)
    arena.status = 'interrupted'
    assert arena.terminal and arena.snapshot()['replay']['reveal']['end'] is None
    store.save(arena)
    assert store.page()['total'] == 3
    # Old archives have no kind field; pagination must not strand them beyond page one.
    old = synthetic.result()
    old['arena'].pop('kind')
    with sqlite3.connect(store.path) as db:
        for i in range(32):
            old['arena']['id'] = f'old-{i}'
            db.execute('INSERT INTO runs VALUES (?, ?, ?)', (f'old-{i}', synthetic.created_at, json.dumps(old)))
    page1, page2 = store.page(), store.page(offset=30)
    assert page1['total'] == 35 and len(page1['items']) == 30 and len(page2['items']) == 5
    assert {r['id'] for r in page1['items']}.isdisjoint(r['id'] for r in page2['items'])
    assert store.page(kind='synthetic')['total'] == 33


def test_forecast_metrics_against_hand_calculated_outcomes(frame, models):
    arena = HistoricalArena(frame, 'f' * 64, 42, 100, *models)
    arena.outcomes = [
        dict(initial=100., actual=110., actual_up=True, persistence_up=False, majority_up=True,
             models={n: dict(price=108., prob=.8, lower=105., upper=110.) for n in ('transfer', 'historical')}),
        dict(initial=100., actual=90., actual_up=False, persistence_up=True, majority_up=True,
             models={n: dict(price=94., prob=.2, lower=91., upper=99.) for n in ('transfer', 'historical')}),
    ]
    metrics = arena.metrics()
    m = metrics['historical']
    assert m['accuracy'] == m['balanced_accuracy'] == 1.
    assert m['mae'] == 3. and m['baseline_mae'] == 10.
    assert m['return_mae_bps'] == pytest.approx(300.)
    assert m['baseline_return_mae_bps'] == pytest.approx(1000.)
    assert m['coverage'] == .5 and m['verdict'] == 'Useful signal'
    assert metrics['persistence']['balanced_accuracy'] == 0.
    assert metrics['majority']['balanced_accuracy'] == .5


def test_routes_controls_and_historical_exchange_guards(tmp_path, frame, models, monkeypatch):
    from app import runtime
    from app.api import routes
    from fastapi import HTTPException
    from starlette.requests import Request
    monkeypatch.setattr(runtime, 'store', RunStore(tmp_path / 'runs.db'))
    monkeypatch.setattr(runtime, 'datasets', DatasetStore(tmp_path / 'datasets'))
    monkeypatch.setattr(runtime, 'starting', False)
    arena = HistoricalArena(frame, 'e' * 64, 7, 100, *models)
    monkeypatch.setattr(runtime, 'arena', arena)
    monkeypatch.setattr(runtime, 'state', arena.snapshot())
    monkeypatch.setattr(runtime, 'speed', 1)
    async def exercise():
        await routes.control(routes.ControlIn(action='pause'))
        arena.step(); assert arena.elapsed == 0
        await routes.control(routes.ControlIn(action='resume'))
        await routes.control(routes.ControlIn(action='speed', speed=20))
        assert runtime.speed == 20
        for action in [routes.portfolio, lambda: routes.candles('SECRET'), lambda: routes.cancel_order(1),
                       lambda: routes.place_order(routes.OrderIn(symbol='SECRET', side='BUY', qty=1))]:
            with pytest.raises(HTTPException) as e:
                await action()
            assert e.value.status_code == 409
        with pytest.raises(HTTPException):
            await routes.start_replay(routes.ReplayIn(dataset_id='a' * 64))
        raw = frame.to_csv(index=False).encode()
        async def receive():
            return {'type': 'http.request', 'body': raw, 'more_body': False}
        req = Request({'type': 'http', 'headers': [(b'content-type', b'text/csv')]}, receive)
        metadata = await routes.import_dataset(req, 'daily.csv')
        assert len(await routes.datasets()) == 1
        await routes.control(routes.ControlIn(action='finish'))
        assert (await routes.runs(30, 0, None))['total'] == 1
        started = await routes.start_replay(routes.ReplayIn(dataset_id=metadata['id'], duration=100))
        assert started['kind'] == 'historical' and started['arena']['elapsed'] == 0
        assert not runtime.starting
    asyncio.run(exercise())
