"""Portraits for the front desk: a generated face for the patients we demo with, by patient id.

The clinic's records carry no photo — only a sex and a date of birth — and its patients are the organizers'
invented personas. So the faces are invented too: one image-model call each, written to
apps/web/public/patients/<patient_id>.jpg, and listed in index.json, which is how the screens know a portrait
exists. Everyone else keeps their initials.

    .venv/bin/python apps/agent/scripts/portraits.py            the eight patients who rang most often
    .venv/bin/python apps/agent/scripts/portraits.py 12         the twelve
"""

import asyncio
import io
import json
import sys
from collections import Counter
from datetime import date

from google import genai
from google.genai import types
from PIL import Image

from clinic_agent import config
from clinic_agent.clinic import ClinicClient
from clinic_agent.tail import read_events

OUT = config.ROOT / "apps" / "web" / "public" / "patients"
MODEL = "gemini-3.1-flash-image"


def regulars(how_many: int) -> list[tuple[str, str]]:
    """(patient_id, full name) of the patients the call logs know best."""
    seen: Counter = Counter()
    names: dict[str, str] = {}
    for path in config.CALL_LOG_DIR.glob("*.jsonl"):
        for e in read_events(path):
            result = e.get("result") or {}
            if e["kind"] == "tool_result" and e.get("name") == "find_patient" and result.get("patient_id"):
                seen[result["patient_id"]] += 1
                names[result["patient_id"]] = result["full_name"]
    return [(pid, names[pid]) for pid, _ in seen.most_common(how_many)]


def portrait_of(client: genai.Client, sex: str, age: int) -> Image.Image:
    who = "woman" if sex.lower().startswith("f") else "man" if sex.lower().startswith("m") else "person"
    if age < 13:
        who = "girl" if who == "woman" else "boy" if who == "man" else "child"
    prompt = (f"A photorealistic head-and-shoulders portrait photograph of a {age}-year-old Spanish {who}, looking at the camera with a "
              "relaxed, friendly expression. Everyday clothes. Plain light warm-grey studio background, soft daylight, shallow depth "
              "of field, square framing, the face centred. The kind of photo on a clinic's patient record. No text, no watermark.")
    reply = client.models.generate_content(model=MODEL, contents=prompt,
                                           config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    for part in reply.candidates[0].content.parts:
        if part.inline_data:
            return Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
    raise RuntimeError("the model returned no image")


async def main() -> None:
    how_many = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "index.json"
    have: list[str] = json.loads(index_path.read_text()) if index_path.exists() else []
    api, client = ClinicClient(), genai.Client(api_key=config.GOOGLE_API_KEY)
    try:
        for patient_id, name in regulars(how_many):
            if patient_id in have and (OUT / f"{patient_id}.jpg").exists():
                continue
            record = next((m for m in await api.directory(name=name) if m["patient_id"] == patient_id), None)
            if record is None:
                print(f"{patient_id}: the directory does not return them by name — skipped")
                continue
            born = date.fromisoformat(record["date_of_birth"])
            age = (date.today() - born).days // 365
            image = await asyncio.to_thread(portrait_of, client, record.get("sex") or "", age)
            side = min(image.size)
            left, top = (image.width - side) // 2, (image.height - side) // 2
            image.crop((left, top, left + side, top + side)).resize((384, 384), Image.LANCZOS).save(OUT / f"{patient_id}.jpg", quality=88)
            have.append(patient_id)
            index_path.write_text(json.dumps(sorted(set(have))))
            print(f"{patient_id}: a {age}-year-old, {record.get('sex') or 'sex not on file'} — done")
    finally:
        await api.aclose()


if __name__ == "__main__":
    asyncio.run(main())
