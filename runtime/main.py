"""FRIDAY Runtime — FastAPI server entry point.

Exposes:
  GET  /health           — liveness check
  POST /command          — typed command input
  POST /correction       — correction submission
  POST /confirm          — confirm/reject pending action
  WS   /ws               — real-time event stream to Swift app
"""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Callable, Awaitable

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from runtime.config import settings
from runtime.pipeline import Pipeline
from runtime.router import memory_router, routines_router, settings_router, commands_router
from shared.schemas import CommandRequest, CommandResponse, CorrectionRequest
from shared.events import RuntimeEvent

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("friday.runtime")

pipeline: Pipeline | None = None
_clients: list[WebSocket] = []


async def _broadcast(event: RuntimeEvent) -> None:
    dead = []
    for ws in _clients:
        try:
            await ws.send_json(event.model_dump(mode="json"))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    logger.info("Initialising FRIDAY database...")
    init_db()

    logger.info("Starting pipeline...")
    pipeline = Pipeline()
    pipeline.set_broadcast(_broadcast)
    await pipeline.start()

    logger.info("FRIDAY runtime ready on %s:%d", settings.host, settings.port)
    yield

    logger.info("Shutting down FRIDAY runtime...")
    await pipeline.stop()


app = FastAPI(title="FRIDAY Runtime", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memory_router)
app.include_router(routines_router)
app.include_router(settings_router)
app.include_router(commands_router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    logger.info("Swift client connected (total: %d)", len(_clients))
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "command" and pipeline:
                result = await pipeline.handle_typed_command(data["text"])
                await ws.send_json(result.model_dump())

            elif msg_type == "correction" and pipeline:
                await pipeline.handle_correction(
                    data.get("bad", ""),
                    data["corrected"],
                    data.get("audio_hash", ""),
                )

            elif msg_type == "confirm" and pipeline:
                await pipeline.handle_confirmation(data.get("confirmed", False))

    except WebSocketDisconnect:
        _clients.remove(ws)
        logger.info("Swift client disconnected (total: %d)", len(_clients))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "state": pipeline.state if pipeline else "not_started",
        "clients": len(_clients),
    }


@app.post("/command", response_model=CommandResponse)
async def command(req: CommandRequest):
    if not pipeline:
        return CommandResponse(transcript=req.text, tool_called="error", spoken_response="", success=False, error="Pipeline not ready")
    return await pipeline.handle_typed_command(req.text)


@app.post("/correction")
async def correction(req: CorrectionRequest):
    if pipeline:
        await pipeline.handle_correction(req.bad_transcript, req.corrected_text, req.audio_hash)
    return {"ok": True}


@app.post("/confirm")
async def confirm(data: dict):
    if pipeline:
        await pipeline.handle_confirmation(data.get("confirmed", False))
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(
        "runtime.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="debug" if settings.debug else "info",
    )
