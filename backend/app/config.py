"""Simulation configuration + seed companies. All the calibration knobs live here."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Config:
    seed: int = 42
    tick_ms: int = 250          # wall-clock per tick when run live
    n_traders: int = 60         # 20-100 across the stocks
    trend_window: int = 20      # ticks back used as the "recent trend" reference
    candle_ticks: int = 20      # ticks per OHLCV candle
    order_ttl: int = 8          # ticks a resting order lives before auto-cancel
    user_cash: float = 100_000  # starting cash for the human trader

    # fundamentals
    fund_drift: float = 0.001       # per-tick eps random-walk vol
    earnings_period: int = 400      # ticks between earnings events
    earnings_surprise: float = 0.06 # stdev of earnings surprise (eps jump)

    # emotion dynamics (fear/greed in 0..1)
    fear_decay: float = 0.88
    greed_decay: float = 0.88
    k_fear_drop: float = 1.0    # weight of recent drop into fear
    k_greed_rally: float = 4.0  # weight of recent rally into greed (x fomo_sensitivity)

    # decision weights
    w_value: float = 1.2
    w_momentum: float = 1.0
    w_greed: float = 0.8
    w_fear: float = 1.2
    buy_threshold: float = 0.15
    sell_threshold: float = 0.15

    # archetype mix (weights, normalized). Order-flow character of the market.
    mix: dict[str, float] = field(default_factory=lambda: {
        "whale": 0.08,
        "value": 0.15,
        "momentum": 0.18,
        "fomo": 0.22,
        "weak_hands": 0.15,
        "swing": 0.08,
        "scalper": 0.05,
        "contrarian": 0.05,
        "noise": 0.04,
    })
    n_market_makers_per_symbol: int = 1


# symbol, name, sector, initial price, eps, base_pe, growth, quality(0..1)
SEED_COMPANIES = [
    ("NOVA", "Nova Dynamics", "Tech", 120.0, 4.0, 25.0, 0.20, 0.8),
    ("HELX", "Helix Bio", "Biotech", 80.0, 1.6, 40.0, 0.35, 0.5),
    ("ATLS", "Atlas Energy", "Energy", 45.0, 4.5, 9.0, 0.05, 0.7),
    ("ORCA", "Orca Retail", "Consumer", 60.0, 3.0, 18.0, 0.10, 0.6),
    ("VANE", "Vane Motors", "Auto", 30.0, 1.2, 22.0, 0.15, 0.55),
    ("CIRR", "Cirrus Cloud", "Tech", 150.0, 3.0, 45.0, 0.30, 0.75),
]
