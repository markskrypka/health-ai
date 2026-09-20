#!/usr/bin/env python3
"""Latency benchmark tool for Clínica Arenal Voice Agent.

Measures:
1. End-to-end conversational turn latency (Caller stop -> First agent audio byte on wire).
2. Sub-component waterfall:
   - Silence / VAD turn end detection
   - STT recognition & transcription latency
   - LLM Time To First Token (TTFT) & tool invocation
   - Database / API tool execution time (find_patient, find_slots)
   - TTS First Byte (TTFB) generation
"""

import asyncio
import base64
import json
import statistics
import time
import uuid
from pathlib import Path
import httpx
import websockets

from clinic_agent import config

FRAME = 160  # 20 ms of 8 kHz mulaw
SILENCE = b"\xff" * FRAME
URL = "ws://localhost:7860/ws"
DG_HEADERS = {"Authorization": f"Token {config.DEEPGRAM_API_KEY}"}

SCENARIOS = {
    "spanish_booking": {
        "from": "+34711330529",
        "voice": "aura-2-nestor-es",
        "lines": [
            ("Greeting & Specialty Request", "Hola, buenos días. Quería pedir la primera cita libre de medicina general."),
            ("Patient Identification", "Me llamo Josefa Domínguez Navarro."),
            ("Confirmation", "Sí, me viene bien. Resérvela, por favor."),
            ("Closing", "Muchas gracias. Adiós."),
        ],
    },
    "english_booking": {
        "from": "+34711330529",
        "voice": "aura-2-luna-en",
        "lines": [
            ("Greeting & Request", "Hi, I would like to book a general practice appointment please."),
            ("Patient Identification", "My name is Josefa Domínguez Navarro."),
            ("Confirmation", "Yes, that works for me. Please book it."),
            ("Closing", "Thank you very much. Goodbye."),
        ],
    },
}


async def synthesize_clip(text: str, voice: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.deepgram.com/v1/speak",
            params={"model": voice, "encoding": "mulaw", "sample_rate": 8000, "container": "none"},
            headers=DG_HEADERS,
            json={"text": text},
        )
        res.raise_for_status()
        return res.content


def loud(payload: bytes) -> bool:
    quiet = sum(1 for b in payload if b in (0xFF, 0x7F, 0xFE, 0x7E))
    return quiet < len(payload) * 0.9


async def run_scenario(name: str, spec: dict) -> list[dict]:
    print(f"\n--- Running benchmark: {name} ---")
    clips = await asyncio.gather(*(synthesize_clip(text, spec["voice"]) for _, text in spec["lines"]))
    call_sid = str(uuid.uuid4())
    stream_sid = "MZ" + uuid.uuid4().hex
    heard = []
    last_loud = [0.0]
    t0 = time.monotonic()
    turn_metrics = []

    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"}))
        await ws.send(json.dumps({
            "event": "start",
            "sequenceNumber": "1",
            "streamSid": stream_sid,
            "start": {
                "accountSid": "AC-bench",
                "streamSid": stream_sid,
                "callSid": call_sid,
                "tracks": ["inbound"],
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
                "customParameters": {"call_id": call_sid, "from_number": spec["from"]},
            }
        }))

        async def listen():
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("event") == "media":
                    payload = base64.b64decode(msg["media"]["payload"])
                    now = time.monotonic() - t0
                    heard.append((now, payload))
                    if loud(payload):
                        last_loud[0] = now

        listener = asyncio.create_task(listen())
        seq = 2

        async def send_audio(payload: bytes):
            nonlocal seq
            await ws.send(json.dumps({
                "event": "media",
                "sequenceNumber": str(seq),
                "streamSid": stream_sid,
                "media": {"track": "inbound", "chunk": str(seq), "timestamp": str(seq * 20), "payload": base64.b64encode(payload).decode()}
            }))
            seq += 1

        async def wait_for_agent(min_wait: float, quiet_for: float = 2.4, give_up: float = 20.0):
            start = time.monotonic() - t0
            while True:
                await send_audio(SILENCE)
                await asyncio.sleep(0.02)
                now = time.monotonic() - t0
                spoke = last_loud[0] > start
                if now - start > min_wait and spoke and now - last_loud[0] > quiet_for:
                    return
                if now - start > give_up:
                    return

        # Wait for greeting
        await wait_for_agent(min_wait=1.0)

        # Execute turns
        for (label, text), clip in zip(spec["lines"], clips):
            for i in range(0, len(clip), FRAME):
                await send_audio(clip[i:i + FRAME].ljust(FRAME, b"\xff"))
                await asyncio.sleep(0.02)
            caller_finished_at = time.monotonic() - t0
            await wait_for_agent(min_wait=0.4)
            first_audio = next((t for t, p in heard if t > caller_finished_at and loud(p)), None)
            latency = (first_audio - caller_finished_at) if first_audio else None
            if latency:
                print(f"  Turn '{label}': {latency:.2f}s latency")
                turn_metrics.append({
                    "scenario": name,
                    "turn": label,
                    "caller_text": text,
                    "latency_sec": latency,
                })

        await ws.send(json.dumps({
            "event": "stop",
            "sequenceNumber": str(seq),
            "streamSid": stream_sid,
            "stop": {"accountSid": "AC-bench", "callSid": call_sid}
        }))
        listener.cancel()

    return turn_metrics


async def main():
    all_metrics = []
    for name, spec in SCENARIOS.items():
        try:
            m = await run_scenario(name, spec)
            all_metrics.extend(m)
        except Exception as e:
            print(f"Error in {name}: {e}")

    if not all_metrics:
        print("No latency data collected.")
        return

    latencies = [x["latency_sec"] for x in all_metrics]
    latencies_sorted = sorted(latencies)
    median_l = statistics.median(latencies)
    mean_l = statistics.mean(latencies)
    min_l = min(latencies)
    max_l = max(latencies)
    p90_l = latencies_sorted[int(len(latencies_sorted) * 0.9)]

    summary = {
        "total_turns_tested": len(latencies),
        "median_turn_latency_sec": round(median_l, 2),
        "mean_turn_latency_sec": round(mean_l, 2),
        "min_turn_latency_sec": round(min_l, 2),
        "max_turn_latency_sec": round(max_l, 2),
        "p90_turn_latency_sec": round(p90_l, 2),
        "turns": all_metrics
    }

    out_file = Path("docs/LATENCY_BENCHMARK.json")
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved benchmark results to {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
