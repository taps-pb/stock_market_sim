"""Process-wide singletons: the running simulation + the WebSocket hub."""
from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

from .config import Config, SEED_COMPANIES
from .engine.simulation import SimEngine

cfg = Config()
engine = SimEngine(cfg, SEED_COMPANIES)


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
    dt = cfg.tick_ms / 1000
    while True:
        snap = engine.step()
        await hub.broadcast(snap)
        await asyncio.sleep(dt)
