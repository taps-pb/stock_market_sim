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
        # Order counts must not change future earnings/news draws in policy comparisons.
        self.market_rng = np.random.default_rng(np.random.SeedSequence([cfg.seed, 1]))
        self.companies = build_companies(seed_companies)
        self.symbols = list(self.companies)
        for i, c in enumerate(self.companies.values()):
            c.earnings_offset = i * cfg.earnings_period // len(self.symbols)
        self.stressed = False
        self.fees = 0.0
        self.books = {s: OrderBook(s) for s in self.symbols}
        prices0 = {s: self.companies[s].price0 for s in self.symbols}
        self.traders = build_traders(cfg, self.symbols, prices0, self.rng)
        # the human is a trader in the same book; activity=0 so it never auto-trades
        inert = Traits(cfg.user_cash, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1, 0.0, 0.0)
        self.user = Trader(id=USER_ID, archetype="user", traits=inert,
                           focus=self.symbols[0], cash=cfg.user_cash)
        self.traders.append(self.user)
        self.by_id = {t.id: t for t in self.traders}
        # News trades have a funded counterparty, so cash and shares are conserved.
        news = Trader("NEWS", "outside", inert, self.symbols[0], cfg.news_capital)
        for s, px in prices0.items():
            news.positions[s] = int(cfg.news_capital / 2 / len(self.symbols) / px)
            news.entry[s] = px
            news.cash -= news.positions[s] * px
        self.by_id[news.id] = news
        self.tick = 0

        self.last = {s: self.companies[s].price0 for s in self.symbols}
        self.history = {s: deque([self.last[s]], maxlen=cfg.trend_window + 1) for s in self.symbols}
        self.candles: dict[str, deque[Candle]] = {s: deque(maxlen=600) for s in self.symbols}
        self._cur: dict[str, Candle | None] = {s: None for s in self.symbols}
        self.tape: deque = deque(maxlen=100)
        self.events: deque = deque(maxlen=50)
        self.order_reg: dict[int, tuple[Order, int]] = {}
        self.open_orders: dict[str, dict[int, Order]] = {tid: {} for tid in self.by_id}
        self.flow = {s: [0, 0] for s in self.symbols}  # per-tick [buy_vol, sell_vol] by aggressor
        self.volumes = {s: 0 for s in self.symbols}
        self.executions: dict[str, list[dict]] = {USER_ID: []}  # observed funded accounts only

    # --- public --------------------------------------------------------
    def step(self, external_orders: list[Order] = ()) -> dict:
        self.tick += 1
        switch = self.cfg.stress_exit_prob if self.stressed else self.cfg.stress_enter_prob
        if self.market_rng.random() < switch:
            self.stressed = not self.stressed
        volatility = self.cfg.stress_vol_multiplier if self.stressed else 1.0
        common = float(self.market_rng.normal()) * np.sqrt(self.cfg.market_variance)
        sectors = {c.sector: 0.0 for c in self.companies.values()}
        sectors = {s: float(self.market_rng.normal()) * np.sqrt(self.cfg.sector_variance) for s in sectors}
        for s in self.symbols:
            self.flow[s][0] = self.flow[s][1] = 0  # reset per-tick signed volume
            self._candle(s)  # keep zero-volume intervals and the previous close
        for c in self.companies.values():
            e = c.evolve(self.tick, self.market_rng, self.cfg, common + sectors[c.sector], volatility)
            if e:
                self.events.appendleft({"tick": self.tick, "type": e[0], "symbol": e[1], "surprise": round(e[2], 3)})
        self._expire_orders()

        quotes = {s: self._quote(s) for s in self.symbols}
        for t in self.traders:
            t.update_emotion(quotes[t.focus], self.cfg)

        orders: list[Order] = []
        for t in self.traders:
            orders.extend(t.decide(quotes[t.focus], self.cfg, self.rng))
        orders.extend(external_orders)  # submitted from the previous tick's information
        self.rng.shuffle(orders)

        for o in orders:
            self._submit(o)

        self._maybe_news()

        for s in self.symbols:
            self.history[s].append(self.last[s])
        return self.snapshot()

    def _maybe_news(self) -> None:
        """Exogenous headline: a random market order that gaps a random stock.
        Unforeseeable by design — this is what caps how predictable the market is."""
        if self.market_rng.random() >= self.cfg.news_prob:
            return
        s = self.symbols[self.market_rng.integers(0, len(self.symbols))]
        side = Side.BUY if self.market_rng.random() < 0.5 else Side.SELL
        qty = max(1, int(self.cfg.news_notional * float(self.market_rng.uniform(0.5, 1.6)) / self.last[s]))
        surprise = float(self.market_rng.uniform(0.5, 1.5)) * self.cfg.news_surprise * (1 if side is Side.BUY else -1)
        self.companies[s].eps *= float(np.exp(surprise))
        self.companies[s].published_eps *= float(np.exp(surprise))
        self._submit(Order(s, side, qty, None, "NEWS"))
        self.events.appendleft({"tick": self.tick, "type": "news", "symbol": s,
                                "surprise": round(surprise, 4)})

    def submit_user_order(self, symbol: str, side: Side, qty: int, price: float | None, trader_id: str = "USER") -> list:
        """Inject a user order into the same book the population trades in."""
        return self._submit(Order(symbol, side, qty, price, trader_id), strict=True)

    def available_cash(self, trader_id: str) -> float:
        reserved = sum(o.qty * o.price * (1 + self.cfg.fee_bps / 10_000)
                       for o in self.open_orders[trader_id].values() if o.side is Side.BUY)
        return max(0.0, self.by_id[trader_id].cash - reserved)

    def add_account(self, trader_id: str, capital: float) -> None:
        if trader_id in self.by_id or not np.isfinite(capital) or capital <= 0:
            raise ValueError("account must be new and funded with positive finite capital")
        traits = Traits(capital, 1, 1, 0, 1, 0, 0, 1, 0, 0)
        self.by_id[trader_id] = Trader(trader_id, "agent", traits, self.symbols[0], capital)
        self.open_orders[trader_id] = {}
        self.executions[trader_id] = []

    def _submit(self, o: Order, strict: bool = False) -> list:
        """One risk gate for human, bot and news orders, before any book mutation."""
        if o.symbol not in self.books or o.trader_id not in self.by_id:
            raise ValueError("unknown symbol or trader")
        t = self.by_id[o.trader_id]
        if o.side is Side.BUY:
            cash = self.available_cash(t.id)
            if o.price is None:
                _, cost = self.books[o.symbol].execution_quote(o)
                allowed = o.qty if cost * (1 + self.cfg.fee_bps / 10_000) <= cash + 1e-8 else 0
            else:
                allowed = int((cash + 1e-8) / (o.price * (1 + self.cfg.fee_bps / 10_000)))
            reason = "insufficient available cash"
        else:
            short = (int(t.traits.capital * 0.5 / self.last[o.symbol]) if t.traits.is_market_maker
                     else int(self.cfg.short_cap_frac * t.campaign_target) if t.traits.is_institution else 0)
            reserved = sum(r.qty for r in self.open_orders[t.id].values()
                           if r.symbol == o.symbol and r.side is Side.SELL)
            allowed = max(0, t.positions.get(o.symbol, 0) + short - reserved)
            reason = "insufficient available shares"
        if strict and o.qty > allowed:
            raise ValueError(reason)
        o.qty = min(o.qty, allowed)
        if o.qty <= 0:
            return []
        fills = self.books[o.symbol].add(o)
        for tr in fills:
            self._apply_fill(tr)
        if o.qty > 0 and o.price is not None and not o.ioc:
            self.order_reg[o.id] = (o, self.tick)
            self.open_orders[t.id][o.id] = o
        return fills

    def cancel_user_order(self, order_id: int) -> bool:
        o = self.open_orders[USER_ID].get(order_id)
        if o is None or o.qty <= 0:
            return False
        cancelled = self.books[o.symbol].cancel(order_id)
        self.order_reg.pop(order_id, None)
        self.open_orders[USER_ID].pop(order_id, None)
        return cancelled

    def snapshot(self) -> dict:
        phases = self._smart_money_phases()
        syms = []
        for s in self.symbols:
            b = self.books[s]
            cur = self._cur[s]
            syms.append({
                "symbol": s, "name": self.companies[s].name, "last": round(self.last[s], 2),
                "fair": round(self.companies[s].public_fair(), 2),
                "bid": b.best_bid(), "ask": b.best_ask(),
                "open": self.companies[s].price0,
                "volume": self.volumes[s],
                "sector": self.companies[s].sector,
                "history": list(self.history[s]),
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

    def portfolio(self, trader_id: str = USER_ID) -> dict:
        u = self.by_id[trader_id]
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
        return {"cash": round(u.cash, 2), "available_cash": round(self.available_cash(trader_id), 2),
                "fee_bps": self.cfg.fee_bps,
                "orders": [{"id": o.id, "symbol": o.symbol, "side": o.side.value,
                            "qty": o.qty, "price": o.price}
                           for o in self.open_orders[trader_id].values() if o.qty > 0],
                "positions": positions,
                "fees": round(u.fees_paid, 4), "realized_pnl": round(u.realized_pnl, 4),
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
        vol = float(np.std(np.diff(np.log(h)))) if len(h) > 2 else 0.0
        return Quote(s, self.last[s], ref, self.companies[s].fair_value(), b.best_bid(), b.best_ask(), vol)

    def _apply_fill(self, tr) -> None:
        s, p, q = tr.symbol, tr.price, tr.qty
        self.last[s] = p
        rel = p / max(self.companies[s].fair_value(), 1e-6)  # price relative to fair, at fill time
        buyer, seller = self.by_id[tr.buy_trader_id], self.by_id[tr.sell_trader_id]
        fee = p * q * self.cfg.fee_bps / 10_000
        self.fees += 2 * fee
        if buyer:
            old = buyer.positions.get(s, 0)
            buyer.realized_pnl += min(q, max(0, -old)) * (buyer.entry.get(s, p) - p) - fee
            buyer.fees_paid += fee
            new = old + q
            if new > 0:
                buyer.entry[s] = ((buyer.entry.get(s, p) * old + p * q) / new) if old >= 0 else p
            elif new == 0:
                buyer.entry.pop(s, None)
            buyer.positions[s] = new
            buyer.cash -= p * q + fee
            buyer.buy_qty += q
            buyer.buy_notional += p * q
            buyer.buy_rel += rel * q
        if seller:
            old = seller.positions.get(s, 0)
            seller.realized_pnl += min(q, max(0, old)) * (p - seller.entry.get(s, p)) - fee
            seller.fees_paid += fee
            seller.positions[s] = old - q
            seller.cash += p * q - fee
            if seller.positions[s] < 0:
                seller.entry[s] = ((seller.entry.get(s, p) * -old + p * q) / (q - old)) if old <= 0 else p
            elif seller.positions[s] == 0:
                seller.entry.pop(s, None)
            seller.sell_qty += q
            seller.sell_notional += p * q
            seller.sell_rel += rel * q
        self._candle(s).update(p, q)
        self.volumes[s] += q
        for tid, side in [(buyer.id, "BUY"), (seller.id, "SELL")]:
            if tid in self.executions:
                self.executions[tid].append({"tick": self.tick, "symbol": s, "side": side,
                                             "qty": q, "price": p, "fee": round(fee, 6)})
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
        for oid, (o, placed) in list(self.order_reg.items()):
            mm = self.by_id[o.trader_id].traits.is_market_maker
            if o.qty <= 0 or mm or (o.trader_id != USER_ID and self.tick - placed >= self.cfg.order_ttl):
                self.books[o.symbol].cancel(oid)
                del self.order_reg[oid]
                self.open_orders[o.trader_id].pop(oid, None)

    def _sentiment(self) -> dict:
        real = [t for t in self.traders if not t.traits.is_market_maker and t.id != USER_ID]
        if not real:
            return {"fear": 0., "greed": 0.}
        return {"fear": round(float(np.mean([t.fear for t in real])), 3),
                "greed": round(float(np.mean([t.greed for t in real])), 3)}
