"""FastAPI app: serves REST + WebSocket and runs the sim loop in the background."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .runtime import run_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_loop())
    yield
    task.cancel()


app = FastAPI(title="Stock Market Simulator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
app.include_router(router)
