"""Simulation configuration + seed companies. All the calibration knobs live here."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Config:
    seed: int = 42
    tick_ms: int = 250          # wall-clock per tick when run live
    n_traders: int = 200        # retail-heavy crowd; a few big players move it
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

    # institutional campaign (smart money: accumulate -> markup -> distribute -> markdown).
    # The edge is passive: accumulate cheap, let RETAIL mark it up, distribute into
    # their strength, then step aside for the markdown. Chasing your own pump loses.
    campaign_alloc: float = 0.6   # target inventory = this fraction of capital in the stock
    mk_start: float = 0.08        # accumulate while price is within this of fair (buy the range)
    mk_target: float = 0.18       # distribute once retail has pushed price this far above fair
    md_target: float = 0.10       # markdown ends when price is this far below fair (re-accumulate)
    accum_rate: float = 0.02      # per-tick chunk as fraction of target
    distrib_rate: float = 0.03    # offload rate into the crowd
    short_cap_frac: float = 0.4   # markdown may press net short up to this fraction of target
    # phase timeouts (ticks) so a campaign always cycles even in a one-sided market
    accum_timeout: int = 300      # proceed with a partial position if it can't fully load
    markup_timeout: int = 160     # give up waiting for retail to pump; distribute anyway
    distribute_timeout: int = 160 # give up waiting for buyers; move to markdown
    markdown_timeout: int = 200   # stop pressing; re-accumulate

    # archetype mix (weights, normalized). Retail is the crowd; institutions are few
    # but huge. Tiers are defined in archetypes.TIER for grouping/analytics.
    mix: dict[str, float] = field(default_factory=lambda: {
        # smart money (few, huge, market-moving)
        "institution": 0.05,   # runs accumulate/markup/distribute/markdown campaigns
        "whale": 0.03,         # opportunistic big value, buys the dips
        "pension": 0.03,       # slow, passive, very long horizon
        # informed / professional
        "value": 0.08,
        "contrarian": 0.04,
        "swing": 0.06,
        "momentum": 0.12,
        "scalper": 0.05,
        # retail crowd (many, small, emotional) — the ones who get trapped
        "fomo": 0.20,
        "weak_hands": 0.13,
        "retail": 0.11,
        "bagholder": 0.05,
        "noise": 0.05,
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
