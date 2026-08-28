"""REST: static/historical reads + user order entry (the write path is validated)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .. import runtime
from ..engine.market import Side
from ..engine.simulation import USER_ID
from ..runtime import engine, hub

router = APIRouter()


class OrderIn(BaseModel):
    symbol: str
    side: Side
    qty: int = Field(gt=0)
    price: float | None = Field(default=None, gt=0)  # None = market order


@router.get("/api/state")
def state():
    return runtime.state  # latest snapshot incl. model signals (kept fresh by the sim loop)


@router.get("/api/symbols/{symbol}/candles")
def candles(symbol: str):
    if symbol not in engine.books:
        raise HTTPException(404, "unknown symbol")
    return engine.candle_list(symbol)


@router.get("/api/portfolio")
def portfolio():
    return engine.portfolio()


@router.post("/api/orders")
def place_order(order: OrderIn):
    if order.symbol not in engine.books:
        raise HTTPException(404, "unknown symbol")
    user = engine.user
    ref = engine.last[order.symbol] if order.price is None else order.price
    if order.side is Side.BUY and order.qty * ref > user.cash:
        raise HTTPException(400, "insufficient cash")
    if order.side is Side.SELL and order.qty > user.positions.get(order.symbol, 0):
        raise HTTPException(400, "insufficient shares")
    fills = engine.submit_user_order(order.symbol, order.side, order.qty, order.price, USER_ID)
    return {
        "filled": sum(f.qty for f in fills),
        "avg_price": round(sum(f.price * f.qty for f in fills) / sum(f.qty for f in fills), 2) if fills else None,
        "portfolio": engine.portfolio(),
    }


@router.websocket("/ws")
async def ws(sock: WebSocket):
    await hub.connect(sock)
    try:
        await sock.send_json(runtime.state)  # immediate first paint (incl. model signals)
        while True:
            await sock.receive_text()  # keepalive; server pushes on its own clock
    except WebSocketDisconnect:
        hub.drop(sock)
    except Exception:
        hub.drop(sock)
