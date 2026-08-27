"""Continuous double-auction order book with price-time priority.

Each side is a SortedDict[price] -> deque[Order]. Bids matched high-first,
asks low-first; within a price level, FIFO (time priority). Resting orders
keep their own price; the aggressor's crossing is what generates a trade at
the resting (passive) price.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable

from sortedcontainers import SortedDict

from .market import Order, Side, Trade


class OrderBook:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._bids: SortedDict[float, deque[Order]] = SortedDict()  # ascending; best = last
        self._asks: SortedDict[float, deque[Order]] = SortedDict()  # ascending; best = first
        self._loc: dict[int, tuple[Side, float]] = {}  # order id -> (side, price) for cancel

    # --- top of book ---------------------------------------------------
    def best_bid(self) -> float | None:
        return self._bids.peekitem(-1)[0] if self._bids else None

    def best_ask(self) -> float | None:
        return self._asks.peekitem(0)[0] if self._asks else None

    def mid(self) -> float | None:
        b, a = self.best_bid(), self.best_ask()
        if b is None or a is None:
            return None
        return (b + a) / 2

    def spread(self) -> float | None:
        b, a = self.best_bid(), self.best_ask()
        return None if b is None or a is None else a - b

    def depth(self, levels: int = 10) -> dict[str, list[tuple[float, int]]]:
        """Top N (price, total_qty) per side for the frontend ladder."""
        bids = [(p, sum(o.qty for o in q)) for p, q in reversed(self._bids.items()[-levels:])]
        asks = [(p, sum(o.qty for o in q)) for p, q in self._asks.items()[:levels]]
        return {"bids": bids, "asks": asks}

    # --- mutation ------------------------------------------------------
    def add(self, order: Order) -> list[Trade]:
        """Match `order` against the book; rest any residual (limit only)."""
        book = self._asks if order.side is Side.BUY else self._bids
        trades = self._match(order, book)
        if order.qty > 0 and order.price is not None:
            self._rest(order)
        return trades

    def cancel(self, order_id: int) -> bool:
        loc = self._loc.pop(order_id, None)
        if loc is None:
            return False
        side, price = loc
        book = self._bids if side is Side.BUY else self._asks
        level = book.get(price)
        if level is None:
            return False
        for i, o in enumerate(level):
            if o.id == order_id:
                del level[i]
                break
        if not level:
            del book[price]
        return True

    # --- internals -----------------------------------------------------
    def _crosses(self, order: Order, resting_price: float) -> bool:
        if order.price is None:  # market order takes any price
            return True
        if order.side is Side.BUY:
            return order.price >= resting_price
        return order.price <= resting_price

    def _opposite_prices(self, order: Order, book: SortedDict) -> Iterable[float]:
        # BUY consumes cheapest asks first; SELL consumes highest bids first.
        return iter(book) if order.side is Side.BUY else reversed(book)

    def _match(self, order: Order, book: SortedDict) -> list[Trade]:
        trades: list[Trade] = []
        for price in list(self._opposite_prices(order, book)):
            if order.qty <= 0 or not self._crosses(order, price):
                break
            level = book[price]
            while level and order.qty > 0:
                resting = level[0]
                fill = min(order.qty, resting.qty)
                buy_id = order.trader_id if order.side is Side.BUY else resting.trader_id
                sell_id = resting.trader_id if order.side is Side.BUY else order.trader_id
                trades.append(Trade(self.symbol, price, fill, buy_id, sell_id, order.side))
                order.qty -= fill
                resting.qty -= fill
                if resting.qty == 0:
                    level.popleft()
                    self._loc.pop(resting.id, None)
            if not level:
                del book[price]
        return trades

    def _rest(self, order: Order) -> None:
        book = self._bids if order.side is Side.BUY else self._asks
        book.setdefault(order.price, deque()).append(order)
        self._loc[order.id] = (order.side, order.price)
