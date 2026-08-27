"""SimEngine: the per-tick loop that turns trader psychology into a price series."""
from __future__ import annotations

from collections import Counter, deque

import numpy as np

from .archetypes import TIER, build_traders
from .fundamentals import build_companies
from .market import Candle, Order, Side
from .orderbook import OrderBook
from .trader import Quote, Traits, Trader

USER_ID = "USER"


class SimEngine:
    def __init__(self, cfg, seed_companies) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.companies = build_companies(seed_companies)
        self.symbols = list(self.companies)
        self.books = {s: OrderBook(s) for s in self.symbols}
        prices0 = {s: self.companies[s].price0 for s in self.symbols}
        self.traders = build_traders(cfg, self.symbols, prices0, self.rng)
        # the human is a trader in the same book; activity=0 so it never auto-trades
        inert = Traits(cfg.user_cash, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1, 0.0, 0.0)
        self.user = Trader(id=USER_ID, archetype="user", traits=inert,
                           focus=self.symbols[0], cash=cfg.user_cash)
        self.traders.append(self.user)
        self.by_id = {t.id: t for t in self.traders}
        self.tick = 0

        self.last = {s: self.companies[s].price0 for s in self.symbols}
        self.history = {s: deque([self.last[s]], maxlen=cfg.trend_window + 1) for s in self.symbols}
        self.candles: dict[str, deque[Candle]] = {s: deque(maxlen=600) for s in self.symbols}
        self._cur: dict[str, Candle | None] = {s: None for s in self.symbols}
        self.tape: deque = deque(maxlen=100)
        self.events: deque = deque(maxlen=50)
        self.order_reg: dict[int, tuple[str, str, int]] = {}  # id -> (trader, symbol, tick)
        self.flow = {s: [0, 0] for s in self.symbols}  # per-tick [buy_vol, sell_vol] by aggressor

    # --- public --------------------------------------------------------
    def step(self) -> dict:
        self.tick += 1
        for s in self.symbols:
            self.flow[s][0] = self.flow[s][1] = 0  # reset per-tick signed volume
        for c in self.companies.values():
            e = c.evolve(self.tick, self.rng, self.cfg)
            if e:
                self.events.appendleft({"tick": self.tick, "type": e[0], "symbol": e[1], "surprise": round(e[2], 3)})
        self._expire_orders()

        quotes = {s: self._quote(s) for s in self.symbols}
        for t in self.traders:
            t.update_emotion(quotes[t.focus], self.cfg)

        orders: list[Order] = []
        for t in self.traders:
            orders.extend(t.decide(quotes[t.focus], self.cfg, self.rng))
        self.rng.shuffle(orders)

        for o in orders:
            for tr in self.books[o.symbol].add(o):
                self._apply_fill(tr)
            if o.qty > 0 and o.price is not None:
                self.order_reg[o.id] = (o.trader_id, o.symbol, self.tick)

        for s in self.symbols:
            self.history[s].append(self.last[s])
        return self.snapshot()

    def submit_user_order(self, symbol: str, side: Side, qty: int, price: float | None, trader_id: str = "USER") -> list:
        """Inject a user order into the same book the population trades in."""
        o = Order(symbol, side, qty, price, trader_id)
        fills = self.books[symbol].add(o)
        for tr in fills:
            self._apply_fill(tr)
        if o.qty > 0 and o.price is not None:
            self.order_reg[o.id] = (trader_id, symbol, self.tick)
        return fills

    def snapshot(self) -> dict:
        phases = self._smart_money_phases()
        syms = []
        for s in self.symbols:
            b = self.books[s]
            cur = self._cur[s]
            syms.append({
                "symbol": s, "name": self.companies[s].name, "last": round(self.last[s], 2),
                "fair": round(self.companies[s].fair_value(), 2),
                "bid": b.best_bid(), "ask": b.best_ask(),
                "open": round(cur.open, 2) if cur else round(self.last[s], 2),
                "volume": cur.volume if cur else 0,
                "depth": b.depth(8),
                "phase": phases.get(s),  # what the institutions are doing here
            })
        return {
            "tick": self.tick, "symbols": syms,
            "sentiment": self._sentiment(),
            "groups": self._groups(),
            "trades": list(self.tape)[:30],
            "events": list(self.events)[:10],
        }

    def _smart_money_phases(self) -> dict[str, str]:
        by_sym: dict[str, list[str]] = {}
        for t in self.traders:
            if t.traits.is_institution:
                by_sym.setdefault(t.focus, []).append(t.phase)
        return {s: Counter(ph).most_common(1)[0][0] for s, ph in by_sym.items()}

    def _groups(self) -> dict[str, int]:
        return dict(Counter(TIER.get(t.archetype, "other") for t in self.traders))

    def portfolio(self) -> dict:
        u = self.user
        positions = []
        equity = 0.0
        for s, sh in u.positions.items():
            if sh == 0:
                continue
            last = self.last[s]
            avg = u.entry.get(s, last)
            value = sh * last
            equity += value
            positions.append({"symbol": s, "shares": sh, "avg": round(avg, 2),
                              "last": round(last, 2), "value": round(value, 2),
                              "pnl": round((last - avg) * sh, 2)})
        return {"cash": round(u.cash, 2), "positions": positions,
                "equity": round(equity, 2), "total": round(u.cash + equity, 2)}

    def candle_list(self, symbol: str) -> list[dict]:
        cs = list(self.candles[symbol])
        if self._cur[symbol]:
            cs.append(self._cur[symbol])
        return [{"t": c.t, "o": round(c.open, 2), "h": round(c.high, 2),
                 "l": round(c.low, 2), "c": round(c.close, 2), "v": c.volume} for c in cs]

    # --- internals -----------------------------------------------------
    def _quote(self, s: str) -> Quote:
        h = self.history[s]
        ref = h[0] if len(h) == h.maxlen else self.last[s]
        b = self.books[s]
        return Quote(s, self.last[s], ref, self.companies[s].fair_value(), b.best_bid(), b.best_ask())

    def _apply_fill(self, tr) -> None:
        s, p, q = tr.symbol, tr.price, tr.qty
        self.last[s] = p
        rel = p / max(self.companies[s].fair_value(), 1e-6)  # price relative to fair, at fill time
        buyer, seller = self.by_id.get(tr.buy_trader_id), self.by_id.get(tr.sell_trader_id)
        if buyer:
            old = buyer.positions.get(s, 0)
            new = old + q
            if new > 0:
                buyer.entry[s] = (buyer.entry.get(s, p) * max(old, 0) + p * q) / new
            buyer.positions[s] = new
            buyer.cash -= p * q
            buyer.buy_qty += q
            buyer.buy_notional += p * q
            buyer.buy_rel += rel * q
        if seller:
            seller.positions[s] = seller.positions.get(s, 0) - q
            seller.cash += p * q
            if seller.positions[s] <= 0:
                seller.entry.pop(s, None)
            seller.sell_qty += q
            seller.sell_notional += p * q
            seller.sell_rel += rel * q
        self._candle(s).update(p, q)
        self.flow[s][0 if tr.aggressor is Side.BUY else 1] += q
        self.tape.appendleft({"tick": self.tick, "symbol": s, "price": round(p, 2),
                              "qty": q, "aggressor": tr.aggressor.value})

    def _candle(self, s: str) -> Candle:
        bucket = self.tick // self.cfg.candle_ticks
        cur = self._cur[s]
        if cur is None or cur.t != bucket:
            if cur is not None:
                self.candles[s].append(cur)
            px = self.last[s]
            cur = Candle(s, bucket, px, px, px, px)
            self._cur[s] = cur
        return cur

    def _expire_orders(self) -> None:
        for oid, (tid, sym, placed) in list(self.order_reg.items()):
            t = self.by_id.get(tid)
            mm = bool(t and t.traits.is_market_maker)
            if mm or self.tick - placed >= self.cfg.order_ttl:
                self.books[sym].cancel(oid)
                del self.order_reg[oid]

    def _sentiment(self) -> dict:
        real = [t for t in self.traders if not t.traits.is_market_maker and t.id != USER_ID]
        return {"fear": round(float(np.mean([t.fear for t in real])), 3),
                "greed": round(float(np.mean([t.greed for t in real])), 3)}
