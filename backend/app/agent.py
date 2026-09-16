"""A forecast-driven trading policy. Inputs are public quotes and its own account.

There is deliberately no engine, institution phase or future price in this API.
Orders are planned now and compete in the next tick's matching queue.
"""
from __future__ import annotations


def plan_orders(quotes: list[dict], signals: dict, account: dict, limits: dict,
                ages: dict[str, int], horizon: int, liquidate: bool = False,
                hold_benchmark: bool = False, spent: dict | None = None) -> list[dict]:
    positions = {p["symbol"]: p for p in account["positions"]}
    orders = []
    exiting = set()
    reckless = limits.get("risk_profile") == "super_risky"
    fee = limits["fee_bps"] / 10_000
    slip = limits["slippage_bps"] / 10_000
    equity = max(0, account["total"])
    cash = account["available_cash"]
    room = max(0, equity * limits["max_exposure"] - account["equity"])
    for quote in quotes:
        symbol = quote["symbol"]
        pos, signal = positions.get(symbol), signals.get(symbol)
        reason = None
        if pos and liquidate:
            reason = "Close remaining inventory"
        elif pos and not hold_benchmark:
            if pos["last"] <= pos["avg"] * (1 - limits["stop_loss"]):
                reason = "Position stop reached"
            elif reckless and signal and signal["prob"] < .50:
                reason = "Fear exit: forecast flipped bearish"
            elif ages.get(symbol, 0) >= (3 if reckless else horizon):
                reason = "FOMO rotation: three-tick maximum hold" if reckless else "Forecast holding period elapsed"
            elif signal and signal["prob"] < 0.45:
                reason = "Forecast reversed"
        if reason:
            # Liquidation is an actual market order; scarce depth may leave inventory.
            orders.append(dict(symbol=symbol, side="SELL", qty=pos["shares"],
                               price=None, reason=reason, reference=quote["bid"] or quote["last"]))
            exiting.add(symbol)
    if liquidate:
        return orders
    candidates = quotes if hold_benchmark else sorted(
        quotes, key=lambda q: signals.get(q["symbol"], {}).get("return_pct", 0), reverse=True)
    for quote in candidates:
        symbol, ask = quote["symbol"], quote["ask"]
        if not ask or not quote["bid"]:
            continue
        if hold_benchmark:
            budget = max(0, limits["capital"] * limits["max_exposure"] / len(quotes)
                         - (spent or {}).get(symbol, 0))
        else:
            signal = signals.get(symbol)
            if symbol in exiting or not signal or signal["prob"] < limits["min_probability"]:
                continue
            edge = signal["price"] / ask - 1 - 2 * fee - slip
            if not reckless and edge < limits["min_edge_bps"] / 10_000:
                continue
            if symbol in positions and not reckless:
                continue
            current = positions.get(symbol, {}).get("value", 0)
            budget = max(0, equity * limits["max_position"] - current)
        limit = round(ask * (1 + slip), 2)
        depth = sum(q for p, q in quote["depth"]["asks"] if p <= limit)
        qty = min(int(min(budget, room, cash) / (limit * (1 + fee))),
                  max(0, int(depth * limits["participation"])))
        if qty <= 0:
            continue
        committed = qty * limit * (1 + fee)
        cash -= committed
        room -= committed
        reason = ("Build equal-weight buy-and-hold allocation" if hold_benchmark else
                  ("FOMO entry: chase bullish forecast; pyramid toward maximum greed allocation" if reckless else
                   f"Forecast edge {edge * 10_000:.0f} bps after estimated costs; up probability {signal['prob']:.0%}"))
        orders.append(dict(symbol=symbol, side="BUY", qty=qty, price=limit,
                           reason=reason, reference=ask))
    return orders
