"""Process-wide singletons: the running simulation + the WebSocket hub."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import WebSocket

from .config import Config, SEED_COMPANIES
from .engine.simulation import SimEngine

cfg = Config()
engine = SimEngine(cfg, SEED_COMPANIES)

# Optional live prediction model (train it with `python -m ml.train --save ml/model.pkl`).
_MODEL_PATH = Path(__file__).resolve().parents[1] / "ml" / "model.pkl"
try:
    from ml.predict import Predictor
    predictor: "Predictor | None" = Predictor(str(_MODEL_PATH)) if _MODEL_PATH.exists() else None
except Exception:
    logging.getLogger(__name__).exception("Price model could not be loaded; regenerate data and retrain")
    predictor = None

state: dict = engine.snapshot()  # latest snapshot (+ model signals), served over REST too


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def drop(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        msg = json.dumps(payload)
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                self.drop(ws)


hub = Hub()


async def run_loop() -> None:
    """Step the sim on a fixed clock and push each snapshot to all clients."""
    global state
    dt = cfg.tick_ms / 1000
    while True:
        snap = engine.step()
        if predictor is not None:
            snap["model"] = predictor.step(engine)  # {signals, accuracy, n, horizon}
        state = snap
        await hub.broadcast(snap)
        await asyncio.sleep(dt)
