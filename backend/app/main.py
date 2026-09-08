"""FastAPI app: serves REST + WebSocket and runs the sim loop in the background."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from . import runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(runtime.run_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    if not runtime.arena.terminal:
        runtime.arena.status = "interrupted"
    if not runtime.arena.archived:
        runtime.store.save(runtime.arena)


app = FastAPI(title="Market Lab · Trading Arena", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.include_router(router)
