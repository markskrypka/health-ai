"""Play the harness against our own server: Twilio Media Streams frames, a synthesized patient.

A scripted caller, not a simulated one — it says its next line whenever the agent stops talking.
Good for one thing: proving the wire, the audio loop and the tools work before the real harness dials.

Run the server with DRY_RUN_SUBMIT=1, then:  .venv/bin/python apps/agent/scripts/local_call.py [english|spanish|catalan|web|calendar|newpatient] [ws url]
"""

import asyncio
import audioop
import base64
import json
import os
import sys
import time
import uuid

import httpx
import websockets

from clinic_agent import config

FRAME = 160  # 20 ms of 8 kHz µ-law
SILENCE = b"\xff" * FRAME
# scenario -> (the number the call comes from, the caller's voice, what the caller says). The callers are
# published personas, so the clinic knows them. Deepgram has no Catalan voice: Gemini speaks that caller.
SCENARIOS = {
    "english": ("+34711330529", "aura-2-luna-en", [
        "Hi, I'd like to book a general practice appointment, the earliest one you have please.",
        "My name is Josefa Domínguez Navarro.",
        "My D N I is 4 8 0 6 4 7 1 6 Y.",
        "Yes, that works for me. Please book it.",
        "Thank you very much. Goodbye."]),
    "spanish": ("+34711330529", "aura-2-nestor-es", [
        "Hola, buenos días. Quería pedir la primera cita libre de medicina general.",
        "Me llamo Josefa Domínguez Navarro.",
        "Sí, me viene bien. Resérvela, por favor.",
        "Muchas gracias. Adiós."]),
    # A call from the clinic's web page: no caller id, the form filled in — so nobody asks her who she is.
    "web": ("", "aura-2-luna-en", [
        "Hi, I'd like to book a general practice appointment, the earliest one you have please.",
        "Yes, that works for me. Please book it.",
        "Thank you very much. Goodbye."]),
    # The same caller reads another time off the calendar on her screen, and takes that one.
    "calendar": ("", "aura-2-luna-en", [
        "Hi, I'd like to book a general practice appointment, the earliest one you have please.",
        "Could I have Tuesday the twenty-second at half past ten instead?",
        "Yes, please book that one.",
        "Thank you very much. Goodbye."]),
    # Someone new registers from the web page and then, as a person would, asks to book — which no call can do for
    # a new patient. The agent has to say so plainly and must not invent a reason (seen live: it did, for 12 minutes).
    "newpatient": ("", "aura-2-luna-en", [
        "Hi, I'm not a patient of yours yet. I'd like to register, please.",
        "My name is Marcos Prueba Demo.",
        "My D N I is 1 2 3 4 5 6 7 8 Z, and I was born on the ninth of November, two thousand and one.",
        "My phone number is 6 0 5, 6 5 6, 7 6 9. My email is marcos dot prueba at gmail dot com. And I'm with Sanitas.",
        "Great. Now I'd like to book an appointment with a general practitioner, please.",
        "But I just registered. Why can't you book it now?",
        "Okay, thank you. Goodbye."]),
    "catalan": ("+34669394942", "gemini", [
        "Bon dia. Voldria demanar la primera hora lliure de traumatologia. Necessito que m'atengui algú amb qui pugui parlar en català.",
        "Em dic Teresa López García.",
        "Sí, em va bé. Reservi-la, si us plau.",
        "Moltes gràcies. Adéu."]),
}
SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "english"
URL = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:7860/ws"
FROM_NUMBER, VOICE, LINES = SCENARIOS[SCENARIO]
# What the web page adds to the `start` message (clinic_agent/screen.py): that it is a screen, and the form.
WEB = {"screen": "1", **({"pipeline": os.environ["PIPELINE"]} if os.getenv("PIPELINE") else {}),
       **({"prefill": json.dumps({"name": "Josefa Domínguez Navarro", "national_id": "48064716Y"})} if SCENARIO != "newpatient" else {}),
       } if SCENARIO in ("web", "calendar", "newpatient") else {}
DG = {"Authorization": f"Token {config.DEEPGRAM_API_KEY}"}


async def synthesize(text: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post("https://api.deepgram.com/v1/speak",
                            params={"model": VOICE, "encoding": "mulaw", "sample_rate": 8000, "container": "none"},
                            headers=DG, json={"text": text})
        r.raise_for_status()
        return r.content


def gemini_speech(client, text: str) -> bytes:
    from google.genai import types

    reply = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts", contents=f"Say this in Catalan, naturally, as a phone caller: {text}",
        config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")))))
    pcm_24k = reply.candidates[0].content.parts[0].inline_data.data  # 16-bit mono
    pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
    return audioop.lin2ulaw(pcm_8k, 2)


async def transcribe(ulaw: bytes) -> str:
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.post("https://api.deepgram.com/v1/listen",
                            params={"model": "nova-3", "language": "multi", "encoding": "mulaw", "sample_rate": 8000, "smart_format": "true"},
                            headers={**DG, "Content-Type": "audio/basic"}, content=ulaw)
        r.raise_for_status()
        return r.json()["results"]["channels"][0]["alternatives"][0]["transcript"]


def loud(payload: bytes) -> bool:
    quiet = sum(1 for b in payload if b in (0xFF, 0x7F, 0xFE, 0x7E))
    return quiet < len(payload) * 0.9


async def main() -> None:
    if VOICE == "gemini":
        from google import genai
        client = genai.Client(api_key=config.GOOGLE_API_KEY)
        clips = [gemini_speech(client, line) for line in LINES]  # one after another: the client is not thread-safe
    else:
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
            "customParameters": {"call_id": call_sid, **({"from_number": FROM_NUMBER} if FROM_NUMBER else {}), **WEB}}}))

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

        async def wait_for_agent(min_wait: float, quiet_for: float = 2.6, give_up: float = 25.0) -> None:
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
