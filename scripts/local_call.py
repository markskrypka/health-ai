"""Play the harness against our own server: Twilio Media Streams frames, a synthesized patient.

A scripted caller, not a simulated one — it says its next line whenever the agent stops talking.
Good for one thing: proving the wire, the audio loop and the tools work before the real harness dials.

Run the server with DRY_RUN_SUBMIT=1, then:  .venv/bin/python scripts/local_call.py
"""

import asyncio
import base64
import json
import sys
import time
import uuid

import httpx
import websockets

from clinic_agent import config

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:7860/ws"
FRAME = 160  # 20 ms of 8 kHz µ-law
SILENCE = b"\xff" * FRAME
LINES = [
    "Hi, I'd like to book a general practice appointment, the earliest one you have please.",
    "My name is Josefa Domínguez Navarro.",
    "My D N I is 4 8 0 6 4 7 1 6 Y.",
    "Yes, that works for me. Please book it.",
    "Thank you very much. Goodbye.",
]
DG = {"Authorization": f"Token {config.DEEPGRAM_API_KEY}"}


async def synthesize(text: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post("https://api.deepgram.com/v1/speak",
                            params={"model": "aura-2-luna-en", "encoding": "mulaw", "sample_rate": 8000, "container": "none"},
                            headers=DG, json={"text": text})
        r.raise_for_status()
        return r.content


async def transcribe(ulaw: bytes) -> str:
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.post("https://api.deepgram.com/v1/listen",
                            params={"model": "nova-3", "encoding": "mulaw", "sample_rate": 8000, "smart_format": "true"},
                            headers={**DG, "Content-Type": "audio/basic"}, content=ulaw)
        r.raise_for_status()
        return r.json()["results"]["channels"][0]["alternatives"][0]["transcript"]


def loud(payload: bytes) -> bool:
    quiet = sum(1 for b in payload if b in (0xFF, 0x7F, 0xFE, 0x7E))
    return quiet < len(payload) * 0.9


async def main() -> None:
    clips = await asyncio.gather(*(synthesize(line) for line in LINES))
    call_sid, stream_sid = str(uuid.uuid4()), "MZ" + uuid.uuid4().hex
    heard: list[tuple[float, bytes]] = []  # (time, agent audio)
    last_loud = [0.0]
    t0 = time.monotonic()

    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"}))
        await ws.send(json.dumps({"event": "start", "sequenceNumber": "1", "streamSid": stream_sid, "start": {
            "accountSid": "AC-local", "streamSid": stream_sid, "callSid": call_sid, "tracks": ["inbound"],
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
            "customParameters": {"call_id": call_sid, "from_number": "+34711330529"}}}))

        async def listen() -> None:
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("event") == "media":
                    payload = base64.b64decode(msg["media"]["payload"])
                    now = time.monotonic() - t0
                    heard.append((now, payload))
                    if loud(payload):
                        last_loud[0] = now

        listener = asyncio.create_task(listen())
        seq, chunk, ts = 2, 1, 0

        async def send(payload: bytes) -> None:
            nonlocal seq, chunk, ts
            await ws.send(json.dumps({"event": "media", "sequenceNumber": str(seq), "streamSid": stream_sid, "media": {
                "track": "inbound", "chunk": str(chunk), "timestamp": str(ts), "payload": base64.b64encode(payload).decode()}}))
            seq, chunk, ts = seq + 1, chunk + 1, ts + 20

        async def wait_for_agent(min_wait: float, quiet_for: float = 1.4, give_up: float = 25.0) -> None:
            """Line stays open (silence frames) until the agent has spoken and then gone quiet."""
            start = time.monotonic() - t0
            while True:
                await send(SILENCE)
                await asyncio.sleep(0.02)
                now = time.monotonic() - t0
                spoke = last_loud[0] > start
                if now - start > min_wait and spoke and now - last_loud[0] > quiet_for:
                    return
                if now - start > give_up:
                    print(f"  [{now:5.1f}s] (agent stayed silent for {give_up:.0f}s — moving on)")
                    return

        await wait_for_agent(min_wait=1.0)  # the greeting
        for line, clip in zip(LINES, clips):
            print(f"  [{time.monotonic() - t0:5.1f}s] CALLER: {line}")
            for i in range(0, len(clip), FRAME):
                await send(clip[i:i + FRAME].ljust(FRAME, b"\xff"))
                await asyncio.sleep(0.02)
            said_at = time.monotonic() - t0
            await wait_for_agent(min_wait=0.5)
            first = next((t for t, p in heard if t > said_at and loud(p)), None)
            if first:
                print(f"  [{first:5.1f}s] agent answered {first - said_at:.2f}s after the caller stopped")

        await ws.send(json.dumps({"event": "stop", "sequenceNumber": str(seq), "streamSid": stream_sid,
                                  "stop": {"accountSid": "AC-local", "callSid": call_sid}}))
        listener.cancel()

    audio = b"".join(p for _, p in heard)
    print(f"\ncall_id {call_sid} · {time.monotonic() - t0:.0f}s · agent audio {len(audio) / 8000:.1f}s")
    print("AGENT SAID (Deepgram transcript of what came back on the wire):\n ", await transcribe(audio))
    print(f"\nevent log: logs/calls/{call_sid}.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
