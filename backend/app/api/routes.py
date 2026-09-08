"""Local experiment controls, observed exchange data, and saved results."""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from .. import runtime
from ..arena import Experiment
from ..engine.market import Side

router = APIRouter()


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capital: float = Field(default=100_000, ge=1000, le=1_000_000, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)
    duration: int = Field(default=1500, ge=100, le=10_000, strict=True)
    scenario: Literal["balanced", "volatile", "retail"] = "balanced"
    max_position: float = Field(default=.20, ge=.01, le=.30, allow_inf_nan=False)
    max_exposure: float = Field(default=.60, ge=.1, le=.9, allow_inf_nan=False)
    max_drawdown: float = Field(default=.08, ge=.01, le=.30, allow_inf_nan=False)


class ControlIn(BaseModel):
    action: Literal["pause", "resume", "finish", "halt_agent", "speed"]
    speed: Literal[1, 5, 20] = 1


class OrderIn(BaseModel):
    symbol: str
    side: Side
    qty: int = Field(gt=0, strict=True)
    price: float | None = Field(default=None, ge=.01, allow_inf_nan=False, strict=True)


@router.get("/api/state")
async def state():
    return runtime.state


@router.post("/api/runs")
async def start_run(body: RunIn):
    if not runtime.arena.terminal:
        raise HTTPException(409, "Finish the current experiment before funding another one")
    try:
        settings = Experiment(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    next_arena = runtime.create_arena(settings)
    if not next_arena.predictor:
        raise HTTPException(503, next_arena.error)
    if not runtime.arena.archived:
        runtime.store.save(runtime.arena)
    runtime.arena = next_arena
    return runtime.refresh()


@router.post("/api/control")
async def control(body: ControlIn):
    arena = runtime.arena
    if body.action == "speed":
        runtime.speed = body.speed
    elif body.action == "finish":
        arena.finish()
    elif body.action == "pause" and arena.status == "running":
        arena.status = "paused"
    elif body.action == "resume" and arena.status == "paused":
        arena.status = "running"
    elif body.action == "halt_agent" and not arena.terminal:
        arena.agent_halted = True
        arena._plan(liquidate=arena.status == "settling")
    else:
        raise HTTPException(409, "Control is not available in the current experiment state")
    return runtime.refresh()


@router.get("/api/runs")
async def runs():
    return runtime.store.list()


@router.get("/api/runs/{run_id}")
async def run_result(run_id: str):
    result = runtime.store.get(run_id)
    if result is None:
        raise HTTPException(404, "experiment not found")
    return result


@router.get("/api/symbols/{symbol}/candles")
async def candles(symbol: str):
    engine = runtime.arena.engine
    if symbol not in engine.books:
        raise HTTPException(404, "unknown symbol")
    return engine.candle_list(symbol)


@router.get("/api/portfolio")
async def portfolio():
    return runtime.arena.engine.portfolio()


@router.post("/api/orders")
async def place_order(order: OrderIn):
    engine = runtime.arena.engine
    if runtime.arena.status != "running":
        raise HTTPException(409, "Manual trading requires a running experiment")
    if order.symbol not in engine.books:
        raise HTTPException(404, "unknown symbol")
    try:
        fills = engine.submit_user_order(order.symbol, order.side, order.qty, order.price)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"filled": sum(f.qty for f in fills),
            "avg_price": round(sum(f.price * f.qty for f in fills) / sum(f.qty for f in fills), 2) if fills else None,
            "portfolio": engine.portfolio()}


@router.delete("/api/orders/{order_id}")
async def cancel_order(order_id: int):
    if not runtime.arena.engine.cancel_user_order(order_id):
        raise HTTPException(404, "open order not found")
    return runtime.arena.engine.portfolio()


@router.websocket("/ws")
async def ws(sock: WebSocket):
    await runtime.hub.connect(sock)
    try:
        await sock.send_json(runtime.state)
        while True:
            await sock.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        runtime.hub.drop(sock)
