"""What is happening on the line, and what happened: a read-only page over the per-call event logs.

A separate process on purpose — it reads logs/calls/*.jsonl and never touches the server that takes the calls:

    .venv/bin/python -m uvicorn clinic_agent.console:app --port 7870      →  http://127.0.0.1:7870
"""

import json
import statistics
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from . import config

app = FastAPI(title="Clínica Arenal — call console")
PAGE = Path(__file__).with_name("console.html")
LIVE_WITHIN_SECS = 20  # a log still being written to belongs to a call in progress


def _events(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _summary(path: Path) -> dict:
    events = _events(path)
    ended = next((e for e in events if e["kind"] == "call_ended"), None)
    decided = [e for e in events if e["kind"] == "recorded"]
    modified = path.stat().st_mtime
    return {
        "call_id": path.stem,
        "started_at": modified - (events[-1]["t"] if events else 0),
        "live": ended is None and time.time() - modified < LIVE_WITHIN_SECS,
        "seconds": ended["t"] if ended else (events[-1]["t"] if events else 0),
        "decided_at": decided[-1]["t"] if decided else None,
        "outcome": [_in_words(a) for a in (ended or {}).get("submissions", [])],
        "delivered": all(p.get("http") in (200, 201, 409) for p in (ended or {}).get("posted", [])),
        "turns": sum(1 for e in events if e["kind"] == "caller"),
        "lookups": sum(1 for e in events if e["kind"] == "tool_call"),
        "first_words": next((e["text"] for e in events if e["kind"] == "caller" and len(e["text"]) > 12), ""),
        "flags": sorted({flag for e in events if (flag := _FLAGS.get(e["kind"]))}),
    }


# Moments worth a badge in the list: the call did something other than the plain path.
_FLAGS = {"wrap_up_clock": "wrap-up clock", "inferred_at_hangup": "decided at hang-up", "recovered_leaked_call": "recovered tool call",
          "voice": "changed voice", "listening_model": "Catalan ear", "blocked": "rule applied", "refusal_not_recorded": "refusal dropped",
          "quiet_line": "nudged a quiet line"}


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


@app.get("/", response_class=HTMLResponse)
async def page() -> str:
    return PAGE.read_text(encoding="utf-8")


@app.get("/api/calls")
async def calls(limit: int = 60) -> list[dict]:
    return [_summary(p) for p in _logs()[:limit]]


@app.get("/api/calls/{call_id}")
async def call(call_id: str, after: int = 0) -> dict:
    path = config.CALL_LOG_DIR / f"{Path(call_id).name}.jsonl"
    if not path.exists():
        raise HTTPException(404, "no such call")
    events = _events(path)
    return {"summary": _summary(path), "events": events[after:], "next": len(events)}


@app.get("/api/numbers")
async def numbers(hours: float = 12) -> dict:
    """What the calls of the last hours say about the agent: how long, how fast, how they ended."""
    since = time.time() - hours * 3600
    done = [s for p in _logs() if p.stat().st_mtime >= since and (s := _summary(p))["outcome"]]
    lookups = [e for p in _logs() if p.stat().st_mtime >= since for e in _lookup_times(_events(p))]
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
