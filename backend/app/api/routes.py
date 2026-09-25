"""Local experiment controls, observed exchange data, and saved results."""
from __future__ import annotations

import asyncio
from typing import Literal
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .. import runtime
from ..arena import Experiment
from ..engine.market import Side
from ..replay import HistoricalArena, MAX_BYTES
from ml.predict import Predictor

router = APIRouter()


def synthetic_engine():
    if isinstance(runtime.arena, HistoricalArena):
        raise HTTPException(409, "Order books and manual trading are unavailable during historical replay")
    return runtime.arena.engine


class ReplayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)
    duration: int = Field(default=100, ge=100, le=10_000, strict=True)


@router.post("/api/replay-datasets")
async def import_dataset(request: Request, name: str = "history.csv"):
    if request.headers.get("content-type", "").split(";")[0] != "text/csv":
        raise HTTPException(415, "Upload a text/csv body")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "CSV exceeds 10 MiB")
    try:
        return await asyncio.to_thread(runtime.datasets.import_csv, bytes(raw), name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/replay-datasets")
async def datasets():
    return runtime.datasets.list()


@router.post("/api/replay-runs")
async def start_replay(body: ReplayIn):
    if not runtime.arena.terminal or runtime.starting:
        raise HTTPException(409, "Finish the current experiment before starting another one")
    runtime.starting = True
    try:
        def build():
            frame = runtime.datasets.load(body.dataset_id)
            predictor = Predictor(str(runtime.MODEL_PATH))
            return HistoricalArena(frame, body.dataset_id, body.seed, body.duration, predictor)
        next_arena = await asyncio.to_thread(build)
        if not runtime.arena.archived:
            runtime.store.save(runtime.arena)
        runtime.arena = next_arena
        return runtime.refresh()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (OSError, KeyError) as exc:
        raise HTTPException(503, "Unable to load replay data or the simulator model") from exc
    finally:
        runtime.starting = False


class MarketIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    news_prob: float = Field(ge=0, le=.5, allow_inf_nan=False)
    news_notional: float = Field(ge=10_000, le=250_000, allow_inf_nan=False)
    stress_enter_prob: float = Field(ge=0, le=.05, allow_inf_nan=False)
    retail_multiplier: float = Field(ge=.5, le=3, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def numeric_fields(cls, data):
        if isinstance(data, dict) and any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in data.values()):
            raise ValueError("custom market values must be numbers")
        return data


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capital: float = Field(default=100_000, ge=1000, le=1_000_000, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2**32 - 1, strict=True)
    duration: int = Field(default=1500, ge=100, le=10_000, strict=True)
    scenario: Literal["balanced", "volatile", "retail", "custom"] = "balanced"
    risk_profile: Literal["cautious", "balanced", "assertive", "super_risky"] = "balanced"
    max_position: float = Field(default=.20, ge=.01, le=.30, allow_inf_nan=False)
    max_exposure: float = Field(default=.60, ge=.1, le=.9, allow_inf_nan=False)
    max_drawdown: float = Field(default=.08, ge=.01, le=.30, allow_inf_nan=False)
    stop_loss: float = Field(default=.025, ge=.005, le=.15, allow_inf_nan=False)
    min_probability: float = Field(default=.62, ge=.5, le=.95, allow_inf_nan=False)
    min_edge_bps: float = Field(default=20, ge=0, le=200, allow_inf_nan=False)
    slippage_bps: float = Field(default=25, ge=0, le=100, allow_inf_nan=False)
    participation: float = Field(default=.25, ge=.01, le=.5, allow_inf_nan=False)
    market: MarketIn | None = None

    @model_validator(mode="after")
    def market_matches_scenario(self):
        if (self.scenario == "custom") != (self.market is not None):
            raise ValueError("market overrides are required only for the custom scenario")
        return self


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
    if not runtime.arena.terminal or runtime.starting:
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
    elif body.action == "halt_agent" and not arena.terminal and not isinstance(arena, HistoricalArena):
        arena.agent_halted = True
        arena._plan(liquidate=arena.status == "settling")
    else:
        raise HTTPException(409, "Control is not available in the current experiment state")
    return runtime.refresh()


@router.get("/api/runs")
async def runs(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
               kind: Literal["synthetic", "historical"] | None = None,
               scenario: Literal["balanced", "volatile", "retail", "custom"] | None = None,
               status: Literal["completed", "interrupted", "failed"] | None = None,
               outcome: Literal["profit", "loss"] | None = None):
    return runtime.store.page(limit, offset, kind, scenario, status, outcome)


@router.get("/api/runs/{run_id}")
async def run_result(run_id: str):
    result = runtime.store.get(run_id)
    if result is None:
        raise HTTPException(404, "experiment not found")
    return result


@router.get("/api/decisions")
async def decisions():
    if isinstance(runtime.arena, HistoricalArena):
        raise HTTPException(409, "The decision journal is unavailable during historical replay")
    return runtime.arena.actionable_decisions()


@router.get("/api/symbols/{symbol}/candles")
async def candles(symbol: str):
    engine = synthetic_engine()
    if symbol not in engine.books:
        raise HTTPException(404, "unknown symbol")
    return engine.candle_list(symbol)


@router.get("/api/portfolio")
async def portfolio():
    return synthetic_engine().portfolio()


@router.post("/api/orders")
async def place_order(order: OrderIn):
    engine = synthetic_engine()
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
    engine = synthetic_engine()
    if not engine.cancel_user_order(order_id):
        raise HTTPException(404, "open order not found")
    return engine.portfolio()


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
