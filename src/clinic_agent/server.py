"""The WebSocket server the harness dials: `wss://<host>/ws`, Twilio Media Streams format.

Run:  .venv/bin/python -m uvicorn clinic_agent.server:app --host 0.0.0.0 --port 7860
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from loguru import logger
from pipecat.runner.utils import parse_telephony_websocket

from .bot import run_call
from .clinic import ClinicClient
from .dashboard import DASHBOARD_HTML, get_call_history, live_events_generator
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


PHONE_HTML_PATH = Path(__file__).parent / "phone.html"


@app.get("/", response_class=HTMLResponse)
async def dashboard_index() -> HTMLResponse:
    """The live visual control room for the jury and real-time monitoring."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/phone", response_class=HTMLResponse)
async def web_phone() -> HTMLResponse:
    """Web phone simulator to test calls from browsers or mobile devices."""
    if PHONE_HTML_PATH.exists():
        content = PHONE_HTML_PATH.read_text(encoding="utf-8")
    else:
        content = "<h1>Web phone not found</h1>"
    return HTMLResponse(content=content)


@app.get("/api/live")
async def live_stream() -> StreamingResponse:
    """SSE stream emitting live call events in real time."""
    return StreamingResponse(live_events_generator(), media_type="text/event-stream")


@app.get("/api/calls")
async def call_history() -> JSONResponse:
    """List recent calls and audit metrics."""
    return JSONResponse(content=get_call_history())


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
