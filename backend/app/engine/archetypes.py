"""Archetype presets = trait vectors. Adding a "common trader type" = one row here.

Each preset returns base Traits; build_traders jitters them per-trader so the
population varies instead of being N identical clones.
"""
from __future__ import annotations

import numpy as np

from .trader import Traits, Trader

# capital, risk_tol, panic, fomo, conviction, herding, skill, horizon, loss_av, activity
_PRESETS: dict[str, tuple] = {
    "whale":      (5_000_000, 0.90, 0.25, 0.05, 0.90, 0.10, 0.90, 500, 0.10, 0.30),
    "value":      (  300_000, 0.80, 0.20, 0.10, 0.85, 0.10, 0.85, 400, 0.20, 0.25),
    "momentum":   (  150_000, 0.60, 0.12, 0.50, 0.50, 0.90, 0.40,  60, 0.40, 0.50),
    "fomo":       (   20_000, 0.40, 0.030, 1.50, 0.20, 0.95, 0.20,  20, 0.80, 0.60),
    "weak_hands": (   15_000, 0.20, 0.025, 0.60, 0.15, 0.70, 0.25,  15, 0.95, 0.50),
    "swing":      (   80_000, 0.60, 0.10, 0.30, 0.60, 0.30, 0.60,  80, 0.40, 0.35),
    "scalper":    (   50_000, 0.50, 0.08, 0.30, 0.40, 0.60, 0.50,   5, 0.40, 0.80),
    "contrarian": (  100_000, 0.70, 0.15, 0.05, 0.70, -0.60, 0.60, 120, 0.30, 0.30),
    "noise":      (   10_000, 0.50, 0.10, 0.50, 0.30, 0.30, 0.30,  30, 0.50, 0.60),
}


def _traits(name: str, rng: np.random.Generator) -> Traits:
    cap, rt, panic, fomo, conv, herd, skill, hor, la, act = _PRESETS[name]
    j = lambda v, s=0.15: float(v * (1 + rng.normal(0, s)))  # multiplicative jitter
    return Traits(
        capital=max(2_000.0, j(cap, 0.3)),
        risk_tolerance=_c(j(rt)), panic_threshold=max(0.01, j(panic)),
        fomo_sensitivity=max(0.0, j(fomo)), conviction=_c(j(conv)),
        herding=float(np.clip(j(herd), -1, 1)), skill=_c(j(skill)),
        horizon=max(1, int(j(hor, 0.3))), loss_aversion=_c(j(la)),
        activity=_c(j(act)), is_noise=(name == "noise"),
    )


def _seed_position(tr: Trader, px: float, rng) -> None:
    """Open the market with people already holding, so sellers exist from tick 1."""
    shares = int(tr.traits.capital * float(rng.uniform(0.1, 0.5)) / px)
    if shares > 0:
        tr.positions[tr.focus] = shares
        tr.entry[tr.focus] = px
        tr.cash -= shares * px


def build_traders(cfg, symbols: list[str], prices: dict[str, float], rng: np.random.Generator) -> list[Trader]:
    traders: list[Trader] = []
    total = sum(cfg.mix.values())
    n = 0
    for name, w in cfg.mix.items():
        if name == "noise":
            continue  # handled below with guaranteed per-symbol coverage
        for _ in range(max(1, round(cfg.n_traders * w / total))):
            t = _traits(name, rng)
            focus = symbols[n % len(symbols)]  # round-robin: every stock gets traders
            n += 1
            tr = Trader(id=f"{name}-{n}", archetype=name, traits=t, focus=focus,
                        cash=t.capital, _bias=float(rng.normal(0, (1 - t.skill) * 0.15)))
            _seed_position(tr, prices[focus], rng)
            traders.append(tr)

    # noise = the always-crossing liquidity that keeps price discovery alive.
    # Guarantee >=1 per symbol so no stock deadlocks in a no-trade equilibrium.
    n_noise = max(len(symbols), round(cfg.n_traders * cfg.mix.get("noise", 0) / total))
    for i in range(n_noise):
        t = _traits("noise", rng)
        focus = symbols[i % len(symbols)]
        tr = Trader(id=f"noise-{i+1}", archetype="noise", traits=t, focus=focus, cash=t.capital)
        _seed_position(tr, prices[focus], rng)
        traders.append(tr)

    # market makers: one (or more) per symbol, always-on liquidity
    for sym in symbols:
        for k in range(cfg.n_market_makers_per_symbol):
            mm = Traits(capital=2_000_000, risk_tolerance=1.0, panic_threshold=1.0,
                        fomo_sensitivity=0.0, conviction=1.0, herding=0.0, skill=1.0,
                        horizon=1, loss_aversion=0.0, activity=1.0, is_market_maker=True)
            traders.append(Trader(id=f"mm-{sym}-{k}", archetype="market_maker",
                                  traits=mm, focus=sym, cash=mm.capital,
                                  positions={sym: 100_000}))  # inventory to quote both sides
    return traders


def _c(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))
