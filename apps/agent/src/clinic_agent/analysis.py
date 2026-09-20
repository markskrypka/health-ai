"""What a call felt like to the caller, and what it teaches — worked out beside the calls, never on them.

Two readings, both by the events service (console.py) and both from the call's log alone:

- while a call runs, the caller's mood after each of their turns, about a second behind (`mood_of_turn`);
- after it ends, the whole call once: mood across it, where it rubbed, how hard the caller had to work, one line
  of summary and one thing to learn (`analyse`). Kept on disk beside the logs, so a call is only ever read once.

The model reads what the caller said and what the agent did. It is told the callers on the phone line are mostly
the organizers' simulated personas: the reading is of the conversation, not of a person.
"""

import json

from google import genai
from google.genai import types

from . import config

ANALYSIS_DIR = config.ROOT / "logs" / "analysis"
MOOD_SCALE = "-2 upset, -1 uneasy, 0 neutral, 1 content, 2 pleased"

_client: genai.Client | None = None


def _gemini() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GOOGLE_API_KEY)
    return _client


def transcript(events: list[dict]) -> list[dict]:
    """The call as a reader needs it: who said what, and what the agent did in between — with each caller turn's
    position in the log, which is how a mood finds its turn on the screen."""
    lines = []
    for seq, e in enumerate(events):
        kind = e["kind"]
        if kind == "caller":
            lines.append({"seq": seq, "who": "caller", "text": e["text"]})
        elif kind == "agent" and e.get("text"):
            lines.append({"who": "agent", "text": e["text"] + (" [the caller talked over this]" if e.get("cut_off") else "")})
        elif kind == "tool_result":
            status = (e.get("result") or {}).get("status")
            lines.append({"who": "system", "text": f'{e.get("name")} → {status}'})
        elif kind == "recorded":
            lines.append({"who": "system", "text": f'recorded: {e.get("action")} {(e.get("payload") or {}).get("reason", "")}'.strip()})
        elif kind in ("quiet_line", "wrap_up_clock", "inferred_at_hangup", "hung_up_undecided", "discarded"):
            lines.append({"who": "system", "text": kind.replace("_", " ")})
    return lines


def _as_text(lines: list[dict]) -> str:
    return "\n".join(f'[{l["seq"]}] caller: {l["text"]}' if l["who"] == "caller" else f'{l["who"]}: {l["text"]}' for l in lines)


async def _ask(prompt: str, schema: dict) -> dict:
    reply = await _gemini().aio.models.generate_content(
        model=config.LLM_MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0.2,
                                           thinking_config=types.ThinkingConfig(thinking_level="minimal")))
    return json.loads(reply.text)


async def mood_of_turn(events: list[dict]) -> int | None:
    """The caller's mood at their latest turn, from the last few lines of the call."""
    lines = transcript(events)
    if not lines or lines[-1]["who"] != "caller":
        return None
    out = await _ask(
        "A caller is on the phone with a clinic's receptionist (an AI agent). Here are the last lines of the call; the caller's "
        f"turns are numbered. Rate the caller's mood at their LAST turn on this scale: {MOOD_SCALE}. Judge what they say and how "
        "the call is going for them (being asked to repeat, being refused, getting what they wanted) — not politeness formulas.\n\n"
        + _as_text(lines[-8:]),
        {"type": "OBJECT", "properties": {"mood": {"type": "INTEGER"}}, "required": ["mood"]})
    return max(-2, min(2, int(out["mood"])))


_ANALYSIS = {
    "type": "OBJECT",
    "properties": {
        "mood": {"type": "NUMBER", "description": "the caller's mood across the whole call, -2 to 2"},
        "label": {"type": "STRING", "description": "one or two words for it"},
        "by_turn": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"seq": {"type": "INTEGER"}, "mood": {"type": "INTEGER"}},
                                               "required": ["seq", "mood"]}},
        "friction": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "moments that cost the caller effort, each in a few words; empty if none"},
        "effort": {"type": "STRING", "description": "low, medium or high: how hard the caller had to work for what they got"},
        "summary": {"type": "STRING", "description": "what happened on the call, one sentence"},
        "lesson": {"type": "STRING", "description": "the one thing worth changing in the agent because of this call, or 'nothing' — one sentence"},
    },
    "required": ["mood", "label", "by_turn", "friction", "effort", "summary", "lesson"],
}


async def analyse(call_id: str, events: list[dict]) -> dict:
    """The finished call, read once. The reading is kept: `logs/analysis/<call_id>.json`."""
    kept = ANALYSIS_DIR / f"{call_id}.json"
    if kept.exists():
        return json.loads(kept.read_text(encoding="utf-8"))
    lines = transcript(events)
    if not any(l["who"] == "caller" for l in lines):
        return {"mood": None, "label": "no words", "by_turn": {}, "friction": [], "effort": "low", "summary": "Nobody spoke on this call.", "lesson": "nothing"}
    out = await _ask(
        "This is a finished phone call to a clinic's receptionist, an AI agent that books, moves and cancels appointments and "
        "must refuse what the clinic's rules forbid. 'system' lines say what the agent's code did. The caller's turns are numbered. "
        "Many callers on this line are simulated personas written by a hackathon's organizers; read the conversation as it stands.\n"
        f"Rate the caller's mood ({MOOD_SCALE}) across the call and at each of their numbered turns (by_turn, with the turn's number "
        "as seq). Name the moments of friction — asked to repeat, misheard, talked over, long silence, a refusal badly explained — and "
        "be specific and brief. A correct refusal that was explained well is not friction. Then the rest of the fields.\n\n" + _as_text(lines),
        _ANALYSIS)
    out["by_turn"] = {str(t["seq"]): max(-2, min(2, int(t["mood"]))) for t in out.get("by_turn", [])}
    out["mood"] = max(-2.0, min(2.0, float(out["mood"])))
    out["model"] = config.LLM_MODEL
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    kept.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def kept(call_id: str) -> dict | None:
    path = ANALYSIS_DIR / f"{call_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
