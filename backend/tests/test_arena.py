"""Funded-agent execution, information timing, risk limits and durable results."""
from dataclasses import asdict
import json

import pytest

from app.agent import plan_orders
from app.arena import AI_ID, HOLD_ID, Arena, Experiment, RunStore
from app.engine.market import Order, Side
from app.engine.orderbook import OrderBook
from app.evaluate import summarize


class PublicPredictor:
    horizon = 10
    def step(self, engine):
        return {'signals': {s: {'price': engine.last[s] * 1.05, 'prob': .9, 'return_pct': 5}
                            for s in engine.symbols}}


def test_policy_respects_capital_exposure_and_costs_without_private_inputs():
    settings = {**asdict(Experiment(capital=1000)), 'fee_bps': 1}
    quote = dict(symbol='X', last=100, bid=99.9, ask=100, depth={'asks': [(100, 100)], 'bids': [(99.9, 100)]})
    account = dict(total=1000, available_cash=1000, equity=0, positions=[])
    orders = plan_orders([quote], {'X': {'price': 110, 'prob': .9}}, account, settings, {}, 20)
    assert len(orders) == 1
    assert orders[0]['qty'] * orders[0]['price'] * 1.0001 <= 1000 * settings['max_position']
    assert plan_orders([quote], {'X': {'price': 100.1, 'prob': .9}}, account, settings, {}, 20) == []
    assert plan_orders([quote], {'X': {'price': 110, 'prob': .4}}, account, settings, {}, 20) == []
    account['equity'] = 600
    assert plan_orders([quote], {'X': {'price': 110, 'prob': .9}}, account, settings, {}, 20) == []
    account['positions'] = [dict(symbol='X', shares=2, last=98, avg=100)]
    exits = plan_orders([quote], {}, account, settings, {'X': 20}, 20)
    assert exits[0]['side'] == 'SELL' and exits[0]['qty'] == 2


def test_super_risky_profile_uses_maximum_limits_fomo_and_fear():
    settings = {**asdict(Experiment(risk_profile='super_risky', max_position=.30,
                    max_exposure=.90, max_drawdown=.30, stop_loss=.15,
                    min_probability=.50, min_edge_bps=0, slippage_bps=100,
                    participation=.50)), 'fee_bps': 1}
    quote = dict(symbol='X', last=100, bid=99.9, ask=100,
                 depth={'asks': [(100, 100)], 'bids': [(99.9, 100)]})
    account = dict(total=1000, available_cash=1000, equity=0, positions=[])
    # A bullish classification still chases when forecast return cannot cover costs.
    signal = {'X': {'price': 100.1, 'prob': .50, 'return_pct': .1}}
    orders = plan_orders([quote], signal,
                         account, settings, {}, 20)
    assert orders[0]['qty'] == 2 and orders[0]['reason'].startswith('FOMO entry')
    account.update(available_cash=900, equity=100,
                   positions=[dict(symbol='X', shares=1, last=100, avg=100, value=100)])
    adds = plan_orders([quote], signal, account, settings, {'X': 1}, 20)
    assert len(adds) == 1 and adds[0]['side'] == 'BUY' and adds[0]['qty'] == 1
    assert 100 + adds[0]['qty'] * adds[0]['price'] * 1.0001 <= 300
    rotation = plan_orders([quote], signal, account, settings, {'X': 3}, 20)
    assert len(rotation) == 1 and rotation[0]['side'] == 'SELL'
    assert rotation[0]['reason'].startswith('FOMO rotation')
    exits = plan_orders([quote], {'X': {'price': 99, 'prob': .49}}, account, settings, {'X': 1}, 20)
    assert len(exits) == 1 and exits[0]['reason'].startswith('Fear exit')
    with pytest.raises(ValueError, match='risk profile'):
        Experiment(risk_profile='reckless')


def test_super_risky_profile_plans_every_tick_after_warmup():
    arena = Arena(Experiment(duration=100, risk_profile='super_risky'), PublicPredictor())
    while arena.engine.tick < 61:
        arena.step()
    assert arena.pending  # tick 61 is not a normal five-tick decision boundary
    arena.engine.by_id[AI_ID].cash -= 35_000
    arena.engine.by_id['NEWS'].cash += 35_000
    arena.step()
    assert arena.drawdowns[AI_ID] > .30 and not arena.agent_halted
    assert arena.snapshot()['arena']['policy_version'] == 2
    arena.agent_halted = True  # Explicit manual halt still wins over FOMO.
    arena.step()
    assert not any(tid == AI_ID and order['side'] == 'BUY' for tid, order in arena.pending)


def test_ioc_partially_fills_and_never_leaves_a_resting_order():
    book = OrderBook('X')
    book.add(Order('X', Side.SELL, 3, 100, 'seller'))
    incoming = Order('X', Side.BUY, 8, 100, 'buyer', ioc=True)
    assert sum(t.qty for t in book.add(incoming)) == 3
    assert book.best_bid() is None and book.best_ask() is None


def test_agent_orders_execute_next_tick_and_conserve_money():
    arena = Arena(Experiment(duration=100), PublicPredictor())
    engine = arena.engine
    initial = sum(t.cash for t in engine.by_id.values())
    shares = {s: sum(t.positions.get(s, 0) for t in engine.by_id.values()) for s in engine.symbols}
    for _ in range(60):
        arena.step()
    assert not engine.executions[AI_ID] and arena.pending
    arena.status = 'paused'
    arena.step()
    assert engine.tick == 60  # pausing does not consume queued orders
    arena.status = 'running'
    while not arena.terminal:
        arena.step()
        assert engine.by_id[AI_ID].cash >= -1e-7
        assert all(q >= 0 for q in engine.by_id[AI_ID].positions.values())
        assert not engine.open_orders[AI_ID]
    fills = engine.executions[AI_ID]
    assert fills and all(t['tick'] >= 61 for t in fills)
    orders = [d for d in arena.decisions if d['side'] != 'WAIT']
    assert all(d['execution_tick'] == d['tick'] + 1 for d in orders)
    assert sum(d['filled'] for d in orders if d['trader'] == AI_ID) == sum(t['qty'] for t in fills)
    assert sum(t.cash for t in engine.by_id.values()) + engine.fees == pytest.approx(initial)
    assert {s: sum(t.positions.get(s, 0) for t in engine.by_id.values()) for s in engine.symbols} == shares
    account = arena.account(AI_ID)
    assert account['net_pnl'] == pytest.approx(account['total'] - account['initial'], abs=.01)
    assert account['realized_pnl'] + account['unrealized_pnl'] == pytest.approx(account['net_pnl'], abs=.10)
    assert account['fees'] > 0
    assert arena.status == 'completed'
    json.dumps(arena.result(), allow_nan=False)


def test_halt_cancels_planned_buys_and_persists_without_erasing_results(tmp_path):
    arena = Arena(Experiment(duration=100), PublicPredictor())
    for _ in range(65):
        arena.step()
    arena.agent_halted = True
    arena._plan(liquidate=False)
    assert not any(tid == AI_ID and order['side'] == 'BUY' for tid, order in arena.pending)
    arena.finish()
    while not arena.terminal:
        arena.step()
    store = RunStore(tmp_path / 'runs.db')
    store.save(arena)
    store.save(arena)  # idempotent shutdown/save
    assert len(store.list()) == 1
    saved = store.get(arena.id)
    assert saved['arena']['agent'] == arena.account(AI_ID)
    assert saved['arena']['fills'] == arena.engine.executions[AI_ID]
    assert store.get('missing') is None


def test_seed_reproduces_actual_fills_and_account_results():
    results = []
    for _ in range(2):
        arena = Arena(Experiment(seed=91, duration=100), PublicPredictor())
        while not arena.terminal:
            arena.step()
        results.append((arena.account(AI_ID), arena.engine.executions[AI_ID]))
    assert results[0] == results[1]
    with pytest.raises(ValueError):
        Experiment(capital=float('nan'))
    with pytest.raises(ValueError):
        Experiment(max_position=.3, max_exposure=.2)


def test_drawdown_halts_buys_and_illiquidity_never_creates_fake_cash():
    arena = Arena(Experiment(duration=100), PublicPredictor())
    for _ in range(65):
        arena.step()
    # An equity shock must stop new risk without waiting for a decision interval.
    arena.engine.by_id[AI_ID].cash -= 20_000
    arena.engine.by_id['NEWS'].cash += 20_000
    arena.step()
    assert arena.agent_halted
    assert not any(tid == AI_ID and d['side'] == 'BUY' for tid, d in arena.pending)

    empty = Arena(Experiment(duration=100), PublicPredictor())
    engine = empty.engine
    engine.traders = []
    engine.cfg.news_prob = 0
    symbol = engine.symbols[0]
    price = engine.last[symbol]
    engine._submit(Order(symbol, Side.SELL, 1, price, 'NEWS'))
    engine._submit(Order(symbol, Side.BUY, 1, None, AI_ID, ioc=True))
    cash = engine.by_id[AI_ID].cash
    empty.finish()
    while not empty.terminal:
        empty.step()
    assert empty.engine.tick == 100
    account = empty.account(AI_ID)
    assert account['cash'] == pytest.approx(cash, abs=.01)
    assert account['illiquid_shares'] == 1 and account['liquidation_value'] is None
    assert empty.snapshot()['arena']['verdict'] == 'Open inventory'


def test_summary_keeps_agent_losses_when_benchmark_cannot_liquidate():
    result = summarize([dict(agent=dict(positions=[], net_pnl=-100, return_pct=-.1),
                             benchmark=dict(positions=[{'symbol': 'X', 'shares': 1}]), excess_pnl=-50)])
    assert result['losses'] == 1 and result['agent_settled'] == 1
    assert result['paired_settled'] == 0 and result['benchmark_open_inventory_runs'] == 1
    assert result['mean_return_pct'] == -.1 and result['mean_excess_pnl'] is None
