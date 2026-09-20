"""The WebSocket server the harness dials: `wss://<host>/ws`, Twilio Media Streams format.

Run:  .venv/bin/python -m uvicorn clinic_agent.server:app --host 0.0.0.0 --port 7860
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from loguru import logger
from pipecat.runner.utils import parse_telephony_websocket

from .bot import run_call
from .clinic import ClinicClient
from .session import CallSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.api = ClinicClient()
    app.state.active = {}  # call_id -> CallSession, read-only view for observability
    catalogue = await app.state.api.catalogue()
    logger.info(f'catalogue loaded: {len(catalogue["providers"])} providers, {catalogue["patient_count"]} patients')
    yield
    await app.state.api.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    active: dict[str, CallSession] = app.state.active
    return {"status": "ok", "active_calls": len(active)}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    transport_type, call_data = await parse_telephony_websocket(websocket)
    if transport_type != "twilio" or not call_data.get("call_id"):
        logger.warning(f"unexpected handshake: {transport_type}")
        await websocket.close()
        return
    logger.info(f'[{call_data["call_id"]}] call connected')
    await run_call(websocket, dict(call_data), app.state.api, app.state.active)
