import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

const repo = resolve(import.meta.dirname, "../../..");
const callsDir = join(repo, "logs", "calls");
const analysisDir = join(repo, "logs", "analysis");
await mkdir(callsDir, { recursive: true });
await mkdir(analysisDir, { recursive: true });

const patients = [
  ["P00001", "Josefa Domínguez Navarro", "1946-09-26", "female"],
  ["P00003", "Teresa López García", "1965-03-14", "female"],
  ["P00004", "Álvaro Martín Santos", "1987-11-02", "male"],
  ["P00005", "Lucía Ortega Ruiz", "1992-07-19", "female"],
];

const pipelines = {
  A: { id: "A", label: "Warm voice", stt: "Deepgram Nova-3", llm: "Gemini 2.5 Flash", tts: "ElevenLabs Flash" },
  B: { id: "B", label: "Fast fallback", stt: "Deepgram Nova-3", llm: "Gemini 2.5 Flash", tts: "Deepgram Aura-2" },
};

function events(index) {
  const [patientId, fullName, dateOfBirth, sex] = patients[index % patients.length];
  const pipeline = index % 3 === 0 ? pipelines.B : pipelines.A;
  const slotHour = 9 + (index % 6);
  const slot = `2026-09-${String(22 + (index % 5)).padStart(2, "0")}T${String(slotHour).padStart(2, "0")}:30:00+02:00`;
  const source = index % 4 === 0 ? "web" : "phone";
  return [
    { t: 0, kind: "call_started", has_caller_id: true, source, pipeline, prefilled: source === "web" ? ["name", "national id"] : [] },
    { t: 1.2, kind: "speaking", text: `Clínica Arenal, good morning${source === "web" ? `, ${fullName.split(" ")[0]}` : ""}.` },
    { t: 4.4, kind: "caller", text: index % 2 ? "I need the earliest appointment with a general practitioner, please." : "Could I book the next available general practice appointment?" },
    { t: 4.6, kind: "latency", secs: 1.1 + (index % 4) * 0.1 },
    { t: 6.1, kind: "agent", text: "Of course. May I have your full name, please?" },
    { t: 10.2, kind: "caller", text: fullName },
    { t: 10.4, kind: "tool_call", name: "find_patient", args: { name: fullName, use_caller_id: true }, by: source === "web" ? "form" : undefined },
    { t: 10.7, kind: "patient", patient_id: patientId, matched_on: ["name", "phone"], status: "identified", card: { given_name: fullName.split(" ")[0], first_surname: fullName.split(" ")[1], second_surname: fullName.split(" ")[2], date_of_birth: dateOfBirth, sex, insurer: "sanitas", has_visited_before: true, referrals: [], national_id_masked: "•••••716Y", phone_masked: "••••••0529", note: "Prefers concise appointment confirmations." } },
    { t: 10.8, kind: "tool_result", name: "find_patient", result: { status: "identified", patient_id: patientId, full_name: fullName, date_of_birth: dateOfBirth, has_visited_before: true, insurer_on_file: "sanitas", referrals_on_file: [] } },
    { t: 12.3, kind: "agent", text: `Thank you, ${fullName.split(" ")[0]}. One moment while I check the diary.` },
    { t: 13.0, kind: "tool_call", name: "find_slots", args: { specialty_id: "general_practice", day_kind: "earliest", patient_id: patientId } },
    { t: 13.4, kind: "availability", label: "The next 14 days", slots: Array.from({ length: 18 }, (_, j) => ({ slot_ref: `S${index}-${j}`, start_time: `2026-09-${String(22 + (j % 5)).padStart(2, "0")}T${String(9 + (j % 8)).padStart(2, "0")}:30:00+02:00`, provider_id: "PR1", location_id: "centro" })) },
    { t: 13.5, kind: "offer", offers: [{ slot_ref: `S${index}-0`, when: `Tuesday at ${slotHour}:30`, doctor: "Dr. Rafael Ortiz", site: "Arenal Centro", payable_with: ["sanitas"] }], notes: [] },
    { t: 13.6, kind: "tool_result", name: "find_slots", result: { status: "slots_found", offers: [], notes: [], say: "Offer the first one only." } },
    { t: 15.0, kind: "latency", secs: 1.3 + (index % 3) * 0.1 },
    { t: 16.4, kind: "agent", text: `The earliest appointment is with Dr. Ortiz at Arenal Centro, at ${slotHour}:30. The other free times are visible on your screen.` },
    { t: 21.1, kind: "caller", text: "Yes, that works for me. Please book it." },
    { t: 21.3, kind: "tool_call", name: "book", args: { slot_ref: `S${index}-0`, patient_id: patientId } },
    { t: 21.4, kind: "recorded", action: "book", payload: { patient_id: patientId, provider_id: "PR1", location_id: "centro", appointment_type_id: "consultation", policy_id: "sanitas", slot }, replaced: [] },
    { t: 21.5, kind: "tool_result", name: "book", result: { status: "recorded", say: "Recorded — it is sent when the call ends." } },
    { t: 23.2, kind: "agent", text: "Done. You are booked. Is there anything else I can help with?" },
    { t: 26.3, kind: "caller", text: "No, thank you. Goodbye." },
    { t: 27.4, kind: "agent", text: "You are welcome. Goodbye." },
    { t: 45.0, kind: "usage", llm_prompt_tokens: 4100 + index * 13, llm_completion_tokens: 220 + index, tts_characters: 310, seconds: 48 },
    { t: 48.4, kind: "submit", action: "book", payload: {}, http: source === "web" ? 0 : 200, attempts: source === "web" ? 0 : 1 },
    { t: 48.4, kind: "call_ended", submissions: [{ action: "book", patient_id: patientId, provider_id: "PR1", location_id: "centro", appointment_type_id: "consultation", policy_id: "sanitas", slot }], posted: [{ action: "book", http: source === "web" ? 0 : 200, attempts: source === "web" ? 0 : 1 }] },
  ];
}

for (let i = 0; i < 12; i += 1) {
  const id = `demo-${String(i + 1).padStart(2, "0")}`;
  const call = events(i);
  await writeFile(join(callsDir, `${id}.jsonl`), `${call.map((event) => JSON.stringify(event)).join("\n")}\n`);
  await writeFile(join(analysisDir, `${id}.json`), `${JSON.stringify({
    mood: 1.4 + (i % 3) * 0.2,
    by_turn: { 4: 0, 9: 1, 16: 1, 21: 2 },
    friction: i % 4 === 0 ? ["Caller paused while choosing a time"] : [],
    effort: "Low",
    summary: "The caller identified themselves, accepted the earliest suitable appointment, and completed the booking.",
    lesson: "Showing the full calendar while speaking one recommendation helps the caller decide quickly.",
  }, null, 2)}\n`);
}

console.log(`Wrote 12 synthetic, clearly demo-only call logs to ${callsDir}`);
