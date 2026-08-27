"""Guards the centerpiece: the psychology, not just the plumbing."""
import numpy as np

from app.config import Config, SEED_COMPANIES
from app.engine.archetypes import _traits
from app.engine.market import Side
from app.engine.simulation import SimEngine
from app.engine.trader import Quote, Trader

CFG = Config()


def make(kind, focus="X", cash=1e6, pos=0, entry=None):
    t = _traits(kind, np.random.default_rng(0))
    t.activity = 1.0  # remove the activity roll so decide() is deterministic
    tr = Trader(id=kind, archetype=kind, traits=t, focus=focus, cash=cash)
    if pos:
        tr.positions[focus] = pos
        tr.entry[focus] = entry
    return tr


def test_weak_hands_panic_but_whale_buys_the_dip():
    # a small ~3% dip below a holder's entry
    q = Quote("X", last=97, ref=100, fair=100, best_bid=96.5, best_ask=97.5)
    rng = np.random.default_rng(1)

    weak = make("weak_hands", pos=100, entry=100.0)
    for _ in range(3):
        weak.update_emotion(q, CFG)
    weak_orders = weak.decide(q, CFG, rng)
    assert weak_orders and weak_orders[0].side is Side.SELL  # panics out on a small dip

    whale = make("whale", pos=100, entry=100.0)
    for _ in range(3):
        whale.update_emotion(q, CFG)
    assert whale.fear < 0.3                                   # doesn't flinch
    assert not any(o.side is Side.SELL for o in whale.decide(q, CFG, rng))


def test_fomo_chases_rally_but_value_stays_disciplined():
    # price rallied 12% and is now slightly above fair value
    q = Quote("X", last=112, ref=100, fair=110, best_bid=111.5, best_ask=112.5)
    rng = np.random.default_rng(2)

    fomo = make("fomo", cash=50_000)
    for _ in range(4):
        fomo.update_emotion(q, CFG)
    assert fomo.greed > 0.2
    assert fomo.decide(q, CFG, rng)[0].side is Side.BUY       # chases the top

    value = make("value", cash=300_000)
    for _ in range(4):
        value.update_emotion(q, CFG)
    assert not any(o.side is Side.BUY for o in value.decide(q, CFG, rng))  # won't overpay


def test_market_reverts_toward_fair_value_and_stays_consistent():
    eng = SimEngine(Config(), SEED_COMPANIES)
    for _ in range(1500):
        eng.step()
    devs = []
    for s in eng.symbols:
        fair = eng.companies[s].fair_value()
        dev = abs(eng.last[s] - fair) / fair
        devs.append(dev)
        assert eng.last[s] > 0
        assert dev < 0.6                                     # no runaway detachment / dead peg
        bb, ba = eng.books[s].best_bid(), eng.books[s].best_ask()
        if bb is not None and ba is not None:
            assert bb < ba                                   # book invariant
        assert sum(c["v"] for c in eng.candle_list(s)) > 0   # the stock actually traded
    assert sum(devs) / len(devs) < 0.25                      # market tracks fundamentals on average
