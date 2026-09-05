"""Exchange guarantees under outstanding orders, sweeping fills, and simulation flow."""
import math

import numpy as np
import pytest

from app.config import Config, SEED_COMPANIES
from app.engine.market import Order, Side
from app.engine.orderbook import OrderBook
from app.engine.simulation import SimEngine, USER_ID
from app.engine.trader import Quote


def test_reservations_market_sweeps_and_cancel_are_atomic():
    eng = SimEngine(Config(user_cash=1000), SEED_COMPANIES)
    symbol = eng.symbols[0]
    eng.submit_user_order(symbol, Side.BUY, 9, 100)
    order_id = eng.portfolio()["orders"][0]["id"]
    with pytest.raises(ValueError, match="available cash"):
        eng.submit_user_order(eng.symbols[1], Side.BUY, 2, 100)
    for _ in range(eng.cfg.order_ttl + 1):
        eng.tick += 1
        eng._expire_orders()
    assert eng.portfolio()["orders"]  # human orders are good until cancelled
    assert eng.cancel_user_order(order_id)
    assert eng.available_cash(USER_ID) == 1000

    # Last price is 120, but executable asks are 150 and 200. Check the whole sweep.
    eng.submit_user_order(symbol, Side.SELL, 2, 150, "NEWS")
    eng.submit_user_order(symbol, Side.SELL, 5, 200, "NEWS")
    before = eng.books[symbol].depth()
    with pytest.raises(ValueError, match="available cash"):
        eng.submit_user_order(symbol, Side.BUY, 6, None)
    assert eng.books[symbol].depth() == before
    fills = eng.submit_user_order(symbol, Side.BUY, 5, None)
    assert sum(t.qty for t in fills) == 5
    assert eng.user.cash == pytest.approx(1000 - 900 * 1.0001)
    eng.submit_user_order(symbol, Side.SELL, 4, 250)
    with pytest.raises(ValueError, match="available shares"):
        eng.submit_user_order(symbol, Side.SELL, 2, 250)


def test_self_trade_prevention_and_order_validation():
    book = OrderBook("X")
    own = Order("X", Side.SELL, 10, 100, "me")
    book.add(own)
    book.add(Order("X", Side.SELL, 5, 101, "other"))
    incoming = Order("X", Side.BUY, 5, 101, "me")
    assert book.execution_quote(incoming) == (5, 505)
    trades = book.add(incoming)
    assert own.qty == 0 and len(trades) == 1 and trades[0].sell_trader_id == "other"
    for price in [0, -1, float("nan"), float("inf"), 1e308, 0.001]:
        with pytest.raises(ValueError):
            Order("X", Side.BUY, 1, price, "me")
    for qty in [0, -1, 0.5, True]:
        with pytest.raises(ValueError):
            Order("X", Side.BUY, qty, 1, "me")


def test_market_conserves_cash_and_shares_with_finite_accounts():
    eng = SimEngine(Config(), SEED_COMPANIES)
    accounts = list(eng.by_id.values())
    cash = sum(t.cash for t in accounts)
    shares = {s: sum(t.positions.get(s, 0) for t in accounts) for s in eng.symbols}
    for _ in range(700):
        eng.step()
        assert all(t.cash >= -1e-7 for t in accounts)
        assert all(q >= 0 for t in accounts if not (t.traits.is_institution or t.traits.is_market_maker)
                   for q in t.positions.values())
    assert math.isclose(sum(t.cash for t in accounts) + eng.fees, cash, abs_tol=1e-5)
    assert {s: sum(t.positions.get(s, 0) for t in accounts) for s in eng.symbols} == shares
    assert eng.fees > 0


def test_market_maker_widens_and_reduces_depth_when_volatile():
    eng = SimEngine(Config(), SEED_COMPANIES)
    mm = next(t for t in eng.traders if t.traits.is_market_maker)
    calm = mm.decide(Quote(mm.focus, 100, 100, 100, 99, 101, 0), eng.cfg, np.random.default_rng(1))
    stress = mm.decide(Quote(mm.focus, 100, 100, 100, 99, 101, 0.02), eng.cfg, np.random.default_rng(1))
    assert stress[1].price - stress[0].price > calm[1].price - calm[0].price
    assert sum(o.qty for o in stress) < sum(o.qty for o in calm)
