"""What is happening on the line, and what happened: the events service behind the screens.

A separate process on purpose — it reads logs/calls/*.jsonl and never touches a server that takes calls:

    .venv/bin/python -m uvicorn clinic_agent.console:app --port 7870      →  http://127.0.0.1:7870

The log is the bus. Every call server appends to its call's log the moment something happens; this service follows
the folder and pushes each new line to the browsers (`/api/stream`, server-sent events). So the phone line is watched
live without a change to it, a browser call looks the same as a phone call, and a replay of a recorded call
(`/api/replay`) travels the same road as a live one.
"""

import asyncio
import json
import statistics
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from . import config
from .clinic import ClinicClient, ClinicError
from .tail import LogTail, read_events

PAGE = Path(__file__).with_name("console.html")
# A log still being written to belongs to a call in progress. A caller may think for a while, and the agent's
# nudge comes at ten seconds, so a quiet line still writes something well inside this.
LIVE_WITHIN_SECS = 45
POLL_SECS = 0.15
WEB_ORIGINS = ["http://localhost:3100", "http://127.0.0.1:3100"]


class Hub:
    """Everyone watching. A browser that falls too far behind is dropped; it reconnects and starts from a snapshot."""

    def __init__(self) -> None:
        self.watchers: set[asyncio.Queue] = set()

    def publish(self, message: dict) -> None:
        for queue in list(self.watchers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                self.watchers.discard(queue)  # its stream ends at the next keep-alive; the browser reconnects


hub = Hub()
# Replays live in memory only: a replay must never be mistaken for a call that happened.
replays: dict[str, list[dict]] = {}
replay_started: dict[str, float] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.api = ClinicClient()
    follower = asyncio.create_task(_follow())
    yield
    follower.cancel()
    await app.state.api.aclose()


app = FastAPI(title="Clínica Arenal — events service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=WEB_ORIGINS, allow_methods=["*"], allow_headers=["*"])


async def _follow() -> None:
    tail = LogTail(config.CALL_LOG_DIR)
    while True:
        touched: list[str] = []
        for call_id, seq, event in tail.poll():
            hub.publish({"type": "event", "call_id": call_id, "seq": seq, "event": event})
            if call_id not in touched:
                touched.append(call_id)
        for call_id in touched:  # the list's line for that call: who, where the call is, how it ended
            hub.publish({"type": "call", "summary": _summary_of(call_id)})
        await asyncio.sleep(POLL_SECS)


# ------------------------------------------------------------------ reading calls

def _path(call_id: str) -> Path:
    return config.CALL_LOG_DIR / f"{Path(call_id).name}.jsonl"


def _events_of(call_id: str) -> list[dict]:
    if call_id in replays:
        return replays[call_id]
    path = _path(call_id)
    if not path.exists():
        raise HTTPException(404, "no such call")
    return read_events(path)


_summaries: dict[str, tuple[tuple[float, int], dict]] = {}  # call_id -> ((mtime, size), summary without "live")


def _summary_of(call_id: str) -> dict:
    if call_id in replays:
        events = replays[call_id]
        last_at = replay_started[call_id] + (events[-1]["t"] if events else 0)
        return _summarise(call_id, events, last_at)
    stat = _path(call_id).stat()
    key = (stat.st_mtime, stat.st_size)
    cached = _summaries.get(call_id)
    if cached is None or cached[0] != key:
        cached = (key, _summarise(call_id, read_events(_path(call_id)), stat.st_mtime))
        _summaries[call_id] = cached
    summary = dict(cached[1])
    summary["live"] = not summary["ended"] and time.time() - stat.st_mtime < LIVE_WITHIN_SECS
    return summary


def _summarise(call_id: str, events: list[dict], last_at: float) -> dict:
    started = next((e for e in events if e["kind"] == "call_started"), {})
    ended = next((e for e in events if e["kind"] == "call_ended"), None)
    decided = [e for e in events if e["kind"] == "recorded"]
    who = _who(events)
    return {
        "call_id": call_id,
        "started_at": last_at - (events[-1]["t"] if events else 0),
        "ended": ended is not None,
        "live": ended is None and time.time() - last_at < LIVE_WITHIN_SECS,
        "seconds": ended["t"] if ended else (events[-1]["t"] if events else 0),
        "decided_at": decided[-1]["t"] if decided else None,
        "outcome": [_in_words(a) for a in (ended or {}).get("submissions", [])],
        "actions": (ended or {}).get("submissions", []),
        "delivered": all(p.get("http") in (200, 201, 409) for p in (ended or {}).get("posted", [])),
        # A dry run (a browser call, a local test) captures its decisions and POSTs nothing: no attempt is made.
        "dry_run": bool(ended) and any(p.get("attempts") == 0 for p in ended.get("posted", [])),
        "turns": sum(1 for e in events if e["kind"] == "caller"),
        "lookups": sum(1 for e in events if e["kind"] == "tool_call"),
        "first_words": next((e["text"] for e in events if e["kind"] == "caller" and len(e["text"]) > 12), ""),
        "flags": sorted({flag for e in events if (flag := _FLAGS.get(e["kind"]))}),
        "source": started.get("source") or "phone",
        "replay_of": started.get("replay_of"),
        "pipeline": started.get("pipeline"),
        "language": _language(events),
        "patient_id": who.get("patient_id"),
        "patient_name": who.get("name"),
        "stage": _stage(events, ended),
    }


def _who(events: list[dict]) -> dict:
    """The patient this call turned out to be about: the last one identified."""
    who: dict = {}
    for e in events:
        if e["kind"] == "tool_result" and e.get("name") == "find_patient" and (e.get("result") or {}).get("patient_id"):
            who = {"patient_id": e["result"]["patient_id"], "name": e["result"].get("full_name")}
        elif e["kind"] == "recorded" and e.get("action") == "register":
            p = e.get("payload") or {}
            who = {"patient_id": None, "name": " ".join(filter(None, (p.get("given_name"), p.get("first_surname"), p.get("second_surname"))))}
    return who


def _language(events: list[dict]) -> str:
    language = "en"
    for e in events:
        if e["kind"] == "voice":
            language = e.get("language") or language
        elif e["kind"] == "listening_model":
            language = "ca"
    return language


def _stage(events: list[dict], ended: dict | None) -> str:
    """Where the call is, in a few words — what the list shows under a caller's name."""
    if ended is not None:
        return "ended"
    stage = "connected"
    for e in events:
        kind = e["kind"]
        if kind == "tool_call":
            stage = {"find_patient": "identifying", "find_slots": "searching", "list_appointments": "checking appointments",
                     "nearest_site": "finding the nearest clinic", "register_patient": "registering",
                     "check_national_id": "checking the id"}.get(e.get("name"), stage)
        elif kind == "patient":
            stage = "identified"
        elif kind == "offer":
            stage = "offered " + (e["offers"][0]["when"] if e.get("offers") else "a slot")
        elif kind == "blocked":
            stage = f'rule: {e.get("reason")}'
        elif kind == "recorded":
            stage = f'{str(e.get("action")).replace("-", " ")} recorded'
        elif kind == "discarded":
            stage = "decision taken back"
    return stage


# Moments worth a badge in the list: the call did something other than the plain path.
_FLAGS = {"wrap_up_clock": "wrap-up clock", "inferred_at_hangup": "decided at hang-up", "recovered_leaked_call": "recovered tool call",
          "voice": "changed voice", "listening_model": "Catalan ear", "blocked": "rule applied", "refusal_not_recorded": "refusal dropped",
          "quiet_line": "nudged a quiet line", "discarded": "decision taken back"}


def _in_words(action: dict) -> str:
    kind = action.get("action")
    if kind == "book":
        return f'BOOK {action["patient_id"]} · {action["provider_id"]} · {action["location_id"]} · {action["slot"][:16].replace("T", " ")}'
    if kind == "reschedule":
        return f'RESCHEDULE {action["appointment_id"]} → {action["slot"][:16].replace("T", " ")}'
    if kind == "cancel":
        return f'CANCEL {action["appointment_id"]}'
    if kind == "register":
        return f'REGISTER {action.get("given_name", "")} {action.get("first_surname", "")}'
    return f'{str(kind).upper().replace("-", "_")} {action.get("reason", "")}'.strip()


def _logs() -> list[Path]:
    return sorted(config.CALL_LOG_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def _recent(limit: int) -> list[dict]:
    running = [_summary_of(call_id) for call_id in reversed(list(replays))]
    return running + [_summary_of(p.stem) for p in _logs()[:limit]]


# ------------------------------------------------------------------ routes

@app.get("/", response_class=HTMLResponse)
async def page() -> str:
    return PAGE.read_text(encoding="utf-8")


@app.get("/api/calls")
async def calls(limit: int = 60) -> list[dict]:
    return _recent(limit)


@app.get("/api/calls/{call_id}")
async def call(call_id: str, after: int = 0) -> dict:
    events = _events_of(call_id)
    return {"summary": _summary_of(call_id), "events": events[after:], "next": len(events)}


@app.get("/api/stream")
async def stream(request: Request, limit: int = 300) -> StreamingResponse:
    """Server-sent events: first the recent calls, then every new event of every call as it is written.

    An event carries its position in its call's log (`seq`), the same position `/api/calls/{id}` counts to in
    `next` — so a screen that opens a call half-way loads it once and takes the stream from there, with no gap
    and nothing twice."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    hub.watchers.add(queue)

    async def lines():
        try:
            yield _sse({"type": "hello", "calls": _recent(limit), "now": time.time()})
            while queue in hub.watchers and not await request.is_disconnected():
                try:
                    yield _sse(await asyncio.wait_for(queue.get(), timeout=10))
                except asyncio.TimeoutError:
                    yield ": still here\n\n"
        finally:
            hub.watchers.discard(queue)

    return StreamingResponse(lines(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(message: dict) -> str:
    return f"data: {json.dumps(message, ensure_ascii=False, default=str)}\n\n"


class ReplayRequest(BaseModel):
    call_id: str
    speed: float = 1.0


@app.post("/api/replay")
async def replay(req: ReplayRequest) -> dict:
    """Play a recorded call again as if it were happening now — for building the screens without paying for
    calls, and for showing them when the room's network fails. Always labelled a replay."""
    source = read_events(_path(req.call_id)) if _path(req.call_id).exists() else None
    if not source:
        raise HTTPException(404, "no such call")
    call_id = f"replay-{uuid.uuid4().hex[:8]}"
    replays[call_id] = []
    replay_started[call_id] = time.time()
    asyncio.create_task(_replay(call_id, req.call_id, source, max(req.speed, 0.1)))
    return {"call_id": call_id, "replay_of": req.call_id, "seconds": source[-1]["t"] / max(req.speed, 0.1)}


async def _replay(call_id: str, of: str, source: list[dict], speed: float) -> None:
    t0 = time.monotonic()
    for seq, original in enumerate(source):
        await asyncio.sleep(max(0.0, original["t"] / speed - (time.monotonic() - t0)))
        event = dict(original)
        if event["kind"] == "call_started":
            event.update(source="replay", replay_of=of)
        replays[call_id].append(event)
        hub.publish({"type": "event", "call_id": call_id, "seq": seq, "event": event})
        if event["kind"] not in ("caller", "agent", "hearing", "speaking"):
            hub.publish({"type": "call", "summary": _summary_of(call_id)})


@app.get("/api/patients/{patient_id}/appointments")
async def appointments(patient_id: str) -> dict:
    """The patient's upcoming appointments, in words — read from the clinic, which this service may only read."""
    api: ClinicClient = app.state.api
    try:
        cat, rows = await asyncio.gather(api.catalogue(), api.appointments(patient_id))
    except ClinicError as err:
        raise HTTPException(err.status if err.status in (400, 404, 422) else 502, str(err.detail)[:200]) from err
    names = _names(cat)
    return {"appointments": [{**row, "provider": names["providers"].get(row["provider_id"], row["provider_id"]),
                              "site": names["locations"].get(row["location_id"], row["location_id"]),
                              "type": names["types"].get(row["appointment_type_id"], row["appointment_type_id"])}
                             for row in sorted(rows, key=lambda r: r["start_time"])]}


@app.get("/api/catalogue")
async def catalogue() -> dict:
    """Names for the ids the events carry: doctors, sites, kinds of appointment, plans."""
    return _names(await app.state.api.catalogue())


def _names(cat: dict) -> dict:
    return {
        "providers": {p["id"]: p["name"] for p in cat.get("providers", [])},
        "specialties": {sp["id"]: sp["name"] for sp in cat.get("specialties", [])},
        "provider_specialty": {p["id"]: p["specialty_id"] for p in cat.get("providers", [])},
        "locations": {l["id"]: l["name"] for l in cat.get("locations", [])},
        "types": {t["id"]: t["name"] for t in cat.get("appointment_types", [])},
        "plans": {p["id"]: p.get("name", p["id"]) for p in cat.get("plans", [])},
    }


@app.get("/api/numbers")
async def numbers(hours: float = 12) -> dict:
    """What the calls of the last hours say about the agent: how long, how fast, how they ended."""
    since = time.time() - hours * 3600
    recent = [p for p in _logs() if p.stat().st_mtime >= since]
    done = [s for p in recent if (s := _summary_of(p.stem))["outcome"]]
    lookups = [secs for p in recent for secs in _lookup_times(read_events(p))]
    outcomes: dict[str, int] = {}
    for s in done:
        for line in s["outcome"]:
            outcomes[line.split()[0]] = outcomes.get(line.split()[0], 0) + 1
    return {
        "calls": len(done),
        "median_call_secs": round(statistics.median(s["seconds"] for s in done), 1) if done else None,
        "median_decided_at_secs": round(statistics.median(s["decided_at"] for s in done if s["decided_at"]), 1) if done else None,
        "over_150_secs": sum(1 for s in done if s["seconds"] > 150),
        "outcomes": outcomes,
        "median_lookup_ms": round(statistics.median(lookups) * 1000) if lookups else None,
        "flags": {flag: sum(1 for s in done if flag in s["flags"]) for flag in sorted(set(_FLAGS.values()))},
        "not_delivered": sum(1 for s in done if not s["delivered"]),
    }


def _lookup_times(events: list[dict]) -> list[float]:
    """Seconds between each tool call and its result."""
    started: dict[str, float] = {}
    out = []
    for e in events:
        if e["kind"] == "tool_call":
            started[e["name"]] = e["t"]
        elif e["kind"] == "tool_result" and e["name"] in started:
            out.append(e["t"] - started.pop(e["name"]))
    return out
