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
    is_institution: bool = False  # runs a market-moving campaign (see Trader.phase)


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
    phase: str = "accumulate"        # institutions only: campaign phase
    phase_ticks: int = 0             # institutions only: ticks spent in current phase
    campaign_target: float = 0.0     # institutions only: target inventory (shares)
    buy_qty: int = 0                 # lifetime fills, for the buy-high/sell-low trap metric
    buy_notional: float = 0.0
    sell_qty: int = 0
    sell_notional: float = 0.0
    buy_rel: float = 0.0             # sum of (price/fair)*qty at fill time (beta-neutral)
    sell_rel: float = 0.0

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
        if t.is_institution:
            return self._campaign(q, cfg, rng)
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

    def _campaign(self, q: Quote, cfg, rng: np.random.Generator) -> list[Order]:
        """Smart money: accumulate low, mark it up to pull retail in, distribute
        into the crowd near the top, then let it mark down and re-accumulate.
        The 'trap' isn't scripted onto retail — it's what happens to traders who
        chase the price this creates."""
        F, P = q.fair, q.last
        inv = self.positions.get(self.focus, 0)
        T = self.campaign_target
        short_cap = -cfg.short_cap_frac * T
        self.phase_ticks += 1
        ph = self.phase
        if ph == "accumulate" and (inv >= T or self.phase_ticks > cfg.accum_timeout):
            ph = "markup"                                    # loaded up cheap (or gave up); now wait
        elif ph == "markup" and (P >= F * (1 + cfg.mk_target) or self.phase_ticks > cfg.markup_timeout):
            ph = "distribute"                                # retail pumped it (or gave up); sell
        elif ph == "distribute" and (inv <= T * 0.10 or self.phase_ticks > cfg.distribute_timeout):
            ph = "markdown"
        elif ph == "markdown" and (P <= F * (1 - cfg.md_target) or inv <= short_cap
                                   or self.phase_ticks > cfg.markdown_timeout):
            ph = "accumulate"
        if ph != self.phase:
            self.phase, self.phase_ticks = ph, 0

        jit = float(rng.uniform(0.4, 1.6))                   # noisy slicing: footprint isn't clean
        if ph == "accumulate":                               # buy cheap, passively absorb supply
            if inv >= T or self.cash < P or P > F * (1 + cfg.mk_start):
                return []
            qty = min(max(1, int(T * cfg.accum_rate * jit)), int(self.cash / P), max(1, int(T - inv)))
            return [Order(self.focus, Side.BUY, qty, self._price(Side.BUY, q, 0.45, rng), self.id)]
        if ph == "markup":                                   # step back and let retail run it
            if P > F * (1 + cfg.mk_start) or inv >= T or self.cash < P:
                return []                                    # only a small nudge before it moves
            qty = max(1, int(T * cfg.accum_rate * 0.5 * jit))
            return [Order(self.focus, Side.BUY, qty, self._price(Side.BUY, q, 0.5, rng), self.id)]
        if ph == "distribute":                               # offer into the crowd's buying (sell high)
            if inv <= 0:
                return []
            qty = max(1, min(int(T * cfg.distrib_rate * jit), inv))
            return [Order(self.focus, Side.SELL, qty, self._price(Side.SELL, q, 0.55, rng), self.id)]
        # markdown: press it down a little, then wait to re-accumulate the panic
        if inv <= short_cap:
            return []
        qty = max(1, min(int(T * cfg.distrib_rate * jit), int(inv - short_cap)))
        return [Order(self.focus, Side.SELL, qty, self._price(Side.SELL, q, 0.75, rng), self.id)]

    def _make_market(self, q: Quote, rng) -> list[Order]:
        mid = q.last if q.last else q.fair
        if not mid or mid <= 0:
            return []
        inv = self.positions.get(self.focus, 0)
        cap_sh = max(1.0, self.traits.capital * 0.5 / mid)   # inventory limit (notional)
        skew = max(-1.0, min(1.0, inv / cap_sh))             # +long / -short
        spread = mid * 0.001
        center = mid * (1 - 0.0015 * skew)                  # lean quotes to revert toward flat
        base = max(1, int(self.traits.capital / mid / 300))
        bid_sz, ask_sz = max(0, int(base * (1 - skew))), max(0, int(base * (1 + skew)))
        out = []
        if bid_sz:
            out.append(Order(self.focus, Side.BUY, bid_sz, center - spread, self.id))
        if ask_sz:
            out.append(Order(self.focus, Side.SELL, ask_sz, center + spread, self.id))
        return out

    def _noise(self, q: Quote, rng) -> list[Order]:
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        if side is Side.SELL and self.positions.get(self.focus, 0) <= 0:
            side = Side.BUY
        qty = int(rng.integers(1, 20))
        px = q.last * (1 + rng.normal(0, 0.004))
        return [Order(self.focus, side, qty, px, self.id)]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x
