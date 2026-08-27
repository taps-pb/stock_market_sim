"""Company fundamentals: slow drift + discrete earnings events, and fair_value().

Fair value is a *signal* traders read (scaled by their own skill), never the price.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Company:
    symbol: str
    name: str
    sector: str
    price0: float
    eps: float
    base_pe: float
    growth: float
    quality: float  # 0..1 composite of margin/low-debt

    def fair_value(self) -> float:
        pe = self.base_pe * (1 + self.growth) * (0.5 + 0.5 * self.quality)
        return max(0.5, self.eps * pe)

    def evolve(self, tick: int, rng: np.random.Generator, cfg) -> tuple | None:
        """Drift eps each tick; fire an earnings surprise on the schedule."""
        self.eps *= 1 + rng.normal(0, cfg.fund_drift)
        if tick > 0 and tick % cfg.earnings_period == 0:
            surprise = float(rng.normal(0, cfg.earnings_surprise))
            self.eps = max(0.05, self.eps * (1 + surprise))
            return ("earnings", self.symbol, surprise)
        return None


def build_companies(seed_rows) -> dict[str, Company]:
    out: dict[str, Company] = {}
    for sym, name, sector, price0, eps, base_pe, growth, quality in seed_rows:
        # calibrate base_pe so fair_value starts at price0
        c = Company(sym, name, sector, price0, eps, base_pe, growth, quality)
        c.base_pe = base_pe * (price0 / c.fair_value())
        out[sym] = c
    return out
