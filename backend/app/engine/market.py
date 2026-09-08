"""Core domain types for the market: orders, trades, candles.

Prices are floats quantized to TICK. Quantities are integer shares.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import count
from math import isfinite

TICK = 0.01  # minimum price increment


def quantize(price: float) -> float:
    """Snap a price to the tick grid so equal levels compare equal (no float drift)."""
    return round(round(price / TICK) * TICK, 2)


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


_order_seq = count(1)


@dataclass
class Order:
    symbol: str
    side: Side
    qty: int
    price: float | None  # None = market order (take whatever the book offers)
    trader_id: str
    id: int = field(default_factory=lambda: next(_order_seq))
    ioc: bool = False  # immediate-or-cancel: never rest unfilled shares

    def __post_init__(self) -> None:
        if not isinstance(self.side, Side):
            raise ValueError("invalid order side")
        if isinstance(self.qty, bool) or not isinstance(self.qty, int) or self.qty <= 0:
            raise ValueError("order qty must be a positive integer")
        if self.price is not None:
            if not isfinite(self.price) or not isfinite(self.price / TICK) or self.price <= 0:
                raise ValueError("order price must be finite and positive")
            self.price = quantize(self.price)
            if self.price < TICK:
                raise ValueError("order price must be at least one tick")


@dataclass
class Trade:
    symbol: str
    price: float
    qty: int
    buy_trader_id: str
    sell_trader_id: str
    aggressor: Side  # side of the incoming order that crossed the spread
    seq: int = field(default_factory=lambda: next(_order_seq))


@dataclass
class Candle:
    symbol: str
    t: int  # bucket index (tick // candle_ticks)
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

    def update(self, price: float, qty: int) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += qty
