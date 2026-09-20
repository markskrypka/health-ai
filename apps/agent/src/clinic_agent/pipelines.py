"""Which agent took the call. Every call says so in its first log line, so calls can be compared by pipeline.

A pipeline is the set of parts a call ran on. Two differ today, in the voice: A speaks with ElevenLabs, B with
Deepgram Aura-2 — both paths exist in speech.voice_service. A phone call runs the default (A when the ElevenLabs
key is set, else B; `PIPELINE` in the environment overrides it); a call from the web page may ask for one.
"""

import hashlib
import os
import subprocess

from . import config

PIPELINES: dict[str, dict] = {
    "A": {"label": "ElevenLabs voice", "voice": "elevenlabs"},
    "B": {"label": "Deepgram voice", "voice": "deepgram"},
}


def default() -> str:
    return "A" if config.ELEVENLABS_API_KEY else "B"


def pick(asked: str | None = None) -> str:
    """The pipeline for one call: what the call asked for, else the environment's, else the default. A pipeline whose
    voice has no key is never picked."""
    for wanted in (asked, os.getenv("PIPELINE")):
        if wanted in PIPELINES and (PIPELINES[wanted]["voice"] != "elevenlabs" or config.ELEVENLABS_API_KEY):
            return wanted
    return default()


def voice(pipeline_id: str) -> str:
    return PIPELINES[pipeline_id]["voice"]


def _read_build() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT, capture_output=True,
                              text=True, timeout=2).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# The commit this process was started from — read once, when the server starts, never during a call.
_BUILD = _read_build()


def describe(pipeline_id: str, system_prompt: str) -> dict:
    """The parts, in words, for the call's first log line."""
    speaks = (f"elevenlabs {config.ELEVENLABS_MODEL}" if voice(pipeline_id) == "elevenlabs" else "deepgram aura-2")
    return {"id": pipeline_id, "label": PIPELINES[pipeline_id]["label"], "stt": "deepgram nova-3 multi",
            "llm": f"{config.LLM_MODEL} · minimal thinking", "tts": speaks,
            "prompt": hashlib.sha1(system_prompt.encode()).hexdigest()[:8], "build": _BUILD}
