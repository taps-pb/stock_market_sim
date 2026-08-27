"""The centerpiece: a trader is a trait vector + mutable emotional state + decide().

Behavior is path-dependent — fear/greed evolve from price action and the trader's
own P&L, so "weak hands sell on a small dip" is emergent, not scripted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .market import Order, Side


@dataclass
class Quote:
    symbol: str
    last: float
    ref: float          # price `trend_window` ticks ago (recent-trend reference)
    fair: float         # true fair value; trader distorts it by its own skill
    best_bid: float | None
    best_ask: float | None


@dataclass
class Traits:
    capital: float          # cash scale -> order size / market impact
    risk_tolerance: float   # 0..1 drawdown tolerated
    panic_threshold: float  # fractional drop/drawdown that trips fear-selling
    fomo_sensitivity: float # how hard rallies pump greed
    conviction: float       # 0..1 hold-through-noise vs react
    herding: float          # 0..1 momentum weight
    skill: float            # 0..1 fair-value accuracy
    horizon: int            # ticks; longer = calmer
    loss_aversion: float    # 0..1 disposition effect
    activity: float         # 0..1 probability of acting per tick
    is_market_maker: bool = False
    is_noise: bool = False


@dataclass
class Trader:
    id: str
    archetype: str
    traits: Traits
    focus: str                       # symbol this trader mainly trades
    cash: float
    positions: dict[str, int] = field(default_factory=dict)
    entry: dict[str, float] = field(default_factory=dict)  # avg cost per symbol
    fear: float = 0.0
    greed: float = 0.0
    _bias: float = 0.0               # persistent fair-value estimation error

    # --- emotion -------------------------------------------------------
    def update_emotion(self, q: Quote, cfg) -> None:
        ret = (q.last - q.ref) / q.ref if q.ref else 0.0
        pos = self.positions.get(self.focus, 0)
        pnl = (q.last - self.entry.get(self.focus, q.last)) / q.last if pos > 0 else 0.0

        drop = max(0.0, -ret) / max(self.traits.panic_threshold, 1e-3)
        drawdown = max(0.0, -pnl) / max(self.traits.panic_threshold, 1e-3) * self.traits.loss_aversion
        calm = 1.0 - 0.5 * self.traits.conviction
        self.fear = _clamp(self.fear * cfg.fear_decay + max(drop, drawdown) * cfg.k_fear_drop * 0.05 * calm)
        self.greed = _clamp(self.greed * cfg.greed_decay
                            + max(0.0, ret) * cfg.k_greed_rally * self.traits.fomo_sensitivity)

    # --- decision ------------------------------------------------------
    def decide(self, q: Quote, cfg, rng: np.random.Generator) -> list[Order]:
        t = self.traits
        if t.is_market_maker:
            return self._make_market(q, rng)
        if rng.random() > t.activity:
            return []
        if t.is_noise:
            return self._noise(q, rng)

        fair = q.fair * (1 + self._bias)
        value_sig = (fair - q.last) / q.last
        mom_sig = (q.last - q.ref) / q.ref if q.ref else 0.0
        score = (cfg.w_value * t.conviction * t.skill * value_sig
                 + cfg.w_momentum * t.herding * mom_sig
                 + cfg.w_greed * self.greed * (1 - t.skill)   # chasing is a low-skill behavior
                 - cfg.w_fear * self.fear)

        pos = self.positions.get(self.focus, 0)
        pnl = (q.last - self.entry.get(self.focus, q.last)) / q.last if pos > 0 else 0.0

        # panic exit dominates everything
        if pos > 0 and (self.fear > 0.6 or pnl < -t.panic_threshold):
            return self._order(Side.SELL, q, rng, aggression=0.7 + 0.3 * self.fear, frac=1.0)
        if score > cfg.buy_threshold and self.cash > q.last:
            return self._order(Side.BUY, q, rng, aggression=_clamp(0.35 + 0.4 * t.conviction + self.greed))
        if score < -cfg.sell_threshold and pos > 0:
            return self._order(Side.SELL, q, rng, aggression=_clamp(0.35 + 0.4 * t.conviction + self.fear))
        return []

    # --- order construction -------------------------------------------
    def _order(self, side: Side, q: Quote, rng, aggression: float, frac: float | None = None) -> list[Order]:
        if side is Side.BUY:
            budget = self.cash * (0.05 + 0.25 * self.traits.conviction) * (1 + self.greed)
            qty = int(budget / q.last)
        else:
            pos = self.positions.get(self.focus, 0)
            qty = pos if frac == 1.0 else int(pos * (0.3 + 0.5 * self.fear))
        if qty <= 0:
            return []
        price = self._price(side, q, aggression, rng)
        return [Order(self.focus, side, qty, price, self.id)]

    def _price(self, side: Side, q: Quote, aggression: float, rng) -> float:
        ba, bb = q.best_ask, q.best_bid
        if side is Side.BUY:
            if aggression > 0.5 and ba is not None:
                return ba * (1 + 0.001 * aggression)   # cross the spread (marketable)
            return bb or q.last                        # join the bid (passive, at touch)
        if aggression > 0.5 and bb is not None:
            return bb * (1 - 0.001 * aggression)
        return ba or q.last                            # join the ask (passive, at touch)

    def _make_market(self, q: Quote, rng) -> list[Order]:
        mid = q.last if q.last else q.fair
        spread = mid * 0.002
        size = max(1, int(self.traits.capital / mid / 200))
        return [
            Order(self.focus, Side.BUY, size, mid - spread, self.id),
            Order(self.focus, Side.SELL, size, mid + spread, self.id),
        ]

    def _noise(self, q: Quote, rng) -> list[Order]:
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        if side is Side.SELL and self.positions.get(self.focus, 0) <= 0:
            side = Side.BUY
        qty = int(rng.integers(1, 20))
        px = q.last * (1 + rng.normal(0, 0.004))
        return [Order(self.focus, side, qty, px, self.id)]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x
