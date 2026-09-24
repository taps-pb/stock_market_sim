"""One local experiment, driven by the same Arena used for offline evaluation."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import WebSocket
from ml.predict import Predictor
from .arena import Arena, Experiment, RunStore
from .replay import DatasetStore

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "ml" / "model.pkl"
OUTLOOK_PATH = ROOT / "ml" / "outlook.pkl"
store = RunStore(ROOT / "data" / "runs.sqlite3")
datasets = DatasetStore(ROOT / "data" / "replay")
starting = False
speed = 1


def create_arena(settings: Experiment) -> Arena:
    try:
        predictor = Predictor(str(MODEL_PATH), str(OUTLOOK_PATH) if OUTLOOK_PATH.is_file() else None)
    except Exception:
        logging.getLogger(__name__).exception("Unable to load the trading model")
        predictor = None
    return Arena(settings, predictor)


# ponytail: one local workspace; isolate engines per workspace if multi-user access is added.
arena = create_arena(Experiment())
state = arena.snapshot()


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)

    def drop(self, ws: WebSocket):
        self.clients.discard(ws)

    async def broadcast(self, payload: dict):
        message = json.dumps(payload, allow_nan=False)
        async def send(ws):
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=1)
            except Exception:
                self.drop(ws)
        await asyncio.gather(*(send(ws) for ws in list(self.clients)))


hub = Hub()


def refresh():
    global state
    state = arena.snapshot()
    state["arena"]["speed"] = speed
    if arena.terminal and not arena.archived:
        store.save(arena)
    return state


async def run_loop():
    while True:
        started = asyncio.get_running_loop().time()
        try:
            for _ in range(speed):
                arena.step()
            refresh()
            await hub.broadcast(state)
        except Exception as exc:
            logging.getLogger(__name__).exception("Experiment stopped")
            arena.status, arena.error = "failed", str(exc)
            arena.pending = []
            refresh()
        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(.01, .25 - elapsed))
