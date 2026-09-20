import { describe, expect, it } from "vitest";
import { build, reduce, empty, slotWords, clock, initials, age, type CallEvent } from "./events";

// The shape of a real call log (apps/agent/src/clinic_agent/session.py), with invented people.
const booking: CallEvent[] = [
  { t: 0, kind: "call_started", has_caller_id: true },
  { t: 8.1, kind: "caller", text: "I need the earliest appointment with doctor Peral, please." },
  { t: 8.4, kind: "agent", text: "" },
  { t: 12.7, kind: "agent", text: "May I have your full name, please?" },
  { t: 18.2, kind: "caller", text: "Ana Ejemplo Prueba." },
  { t: 19.2, kind: "tool_call", name: "find_patient", args: { name: "Ana Ejemplo Prueba", use_caller_id: true } },
  { t: 19.6, kind: "patient", patient_id: "P09999", matched_on: ["name", "phone"], status: "identified" },
  { t: 19.6, kind: "tool_result", name: "find_patient", result: { status: "identified", patient_id: "P09999", full_name: "Ana Ejemplo Prueba", date_of_birth: "1946-09-26", has_visited_before: true, insurer_on_file: "mapfre", referrals_on_file: ["orthopaedics"] } },
  { t: 22.2, kind: "tool_call", name: "find_slots", args: { specialty_id: "orthopaedics", day_kind: "earliest", patient_id: "P09999" } },
  { t: 22.3, kind: "offer", offers: [{ slot_ref: "S1", when: "Friday 25 September at 10:45", doctor: "Dra. Nuria Peral", site: "Arenal Norte", payable_with: ["mapfre"] }], notes: [] },
  { t: 22.3, kind: "tool_result", name: "find_slots", result: { status: "slots_found", offers: [], notes: [], say: "Offer the FIRST one only." } },
  { t: 23.9, kind: "agent", text: "The earliest with Dra. Peral is Friday at a quarter to eleven." },
  { t: 25.0, kind: "caller", text: "Yes, that works." },
  { t: 26.4, kind: "tool_call", name: "book", args: { slot_ref: "S1", patient_id: "P09999" } },
  { t: 26.4, kind: "recorded", action: "book", payload: { patient_id: "P09999", provider_id: "PR10", location_id: "norte", slot: "2026-09-25T10:45:00+02:00" }, replaced: [] },
  { t: 26.4, kind: "tool_result", name: "book", result: { status: "recorded", say: "Recorded — it is sent when the call ends." } },
  { t: 30.0, kind: "agent", text: "You are booked for Friday at a quarter to eleven." },
  { t: 40.0, kind: "submit", action: "book", payload: {}, http: 200, attempts: 1 },
  { t: 40.0, kind: "call_ended", submissions: [], posted: [] },
];

describe("a plain booking", () => {
  const view = build(booking);

  it("shows the turns that were spoken and skips a turn that was only a lookup", () => {
    const turns = view.items.filter((i) => i.type === "turn");
    expect(turns.map((t) => t.type === "turn" && t.who)).toEqual(["caller", "agent", "caller", "agent", "caller", "agent"]);
  });

  it("puts the identification on one card: what was said, who was found, how long it took", () => {
    const card = view.items.find((i) => i.type === "action" && i.action.kind === "identify");
    expect(card?.type === "action" && card.action).toMatchObject({ kind: "identify", status: "identified", ms: 400, patient: { patient_id: "P09999", name: "Ana Ejemplo Prueba" } });
    expect(view.patient).toMatchObject({ insurer: "mapfre", seen_before: true, matched_on: ["name", "phone"] });
  });

  it("fills the form from what the agent acted on, then ticks it from the record", () => {
    const afterCall = booking.slice(0, 6).reduce((v, e, i) => reduce(v, e, i), empty());
    expect(afterCall.form.name).toEqual({ value: "Ana Ejemplo Prueba", state: "heard" });
    expect(view.form.name).toEqual({ value: "Ana Ejemplo Prueba", state: "on_file" });
    expect(view.form.date_of_birth).toEqual({ value: "1946-09-26", state: "on_file" });
  });

  it("keeps the offer on the search card and the booked slot for the calendar", () => {
    const search = view.items.find((i) => i.type === "action" && i.action.kind === "search");
    expect(search?.type === "action" && search.action).toMatchObject({ status: "slots_found", offers: [{ slot_ref: "S1" }] });
    expect(view.booked).toMatchObject({ slot: "2026-09-25T10:45:00+02:00", action: "book" });
  });

  it("links a sentence of the agent to the actions behind it — why did it say that?", () => {
    const offer = view.items.find((i) => i.type === "turn" && i.text.startsWith("The earliest"));
    const because = offer?.type === "turn" ? offer.because : [];
    const kinds = because.map((id) => { const it = view.items.find((x) => x.id === id); return it?.type === "action" ? it.action.kind : ""; });
    expect(kinds).toEqual(["identify", "search"]);
  });

  it("ends with the submission and the end of the call", () => {
    expect(view.ended).toBe(true);
    expect(view.items.at(-2)).toMatchObject({ action: { kind: "submit", http: 200, dryRun: false } });
  });
});

describe("a change of mind", () => {
  it("strikes the decision a new one replaces", () => {
    const events: CallEvent[] = [
      ...booking.slice(0, 16),
      { t: 31, kind: "recorded", action: "book", payload: { patient_id: "P09999", slot: "2026-09-25T11:00:00+02:00" }, replaced: [{ action: "book" }] },
    ];
    const decisions = build(events).items.filter((i) => i.type === "action" && i.action.kind === "decision");
    expect(decisions.map((d) => d.type === "action" && d.action.kind === "decision" && d.action.replaced)).toEqual([true, false]);
    expect(build(events).booked?.slot).toBe("2026-09-25T11:00:00+02:00");
  });

  it("takes a decision back entirely", () => {
    const view = build([...booking.slice(0, 16), { t: 31, kind: "discarded" }]);
    expect(view.booked).toBeUndefined();
    expect(view.decisions.at(-1)?.replaced).toBe(true);
  });
});

describe("a booking the code refused", () => {
  it("shows the refusal and its reason", () => {
    const view = build([
      { t: 0, kind: "call_started", has_caller_id: false },
      { t: 5, kind: "tool_call", name: "book", args: { slot_ref: "S9" } },
      { t: 5, kind: "tool_result", name: "book", result: { status: "error", say: "That slot was never offered." } },
    ]);
    expect(view.items.at(-1)).toMatchObject({ action: { kind: "refused", tool: "book", why: "That slot was never offered." } });
  });
});

describe("words as they arrive", () => {
  it("shows the caller's words before the turn is finished, and clears them when it is", () => {
    let view = reduce(empty(), { t: 1, kind: "hearing", text: "my name is" }, 0);
    expect(view.hearing).toBe("my name is");
    view = reduce(view, { t: 2, kind: "caller", text: "My name is Ana." }, 1);
    expect(view.hearing).toBe("");
  });

  it("keeps the greeting, which is spoken by code and never becomes a turn of the model", () => {
    let view = empty();
    ["Clínica", "Arenal,", "good", "morning."].forEach((w, i) => { view = reduce(view, { t: 1 + i / 10, kind: "speaking", text: w }, i); });
    expect(view.speaking).toBe("Clínica Arenal, good morning.");
    view = reduce(view, { t: 3, kind: "hearing", text: "Hi" }, 4);
    expect(view.speaking).toBe("");
    expect(view.items.at(-1)).toMatchObject({ who: "agent", text: "Clínica Arenal, good morning.", spokenOnly: true });
  });

  it("does not say a talked-over reply twice: the finished turn replaces its first words", () => {
    let view = empty();
    ["One", "moment,", "please.", "The", "earliest", "appointment", "is", "with"].forEach((w, i) => { view = reduce(view, { t: 1, kind: "speaking", text: w }, i); });
    view = reduce(view, { t: 2, kind: "hearing", text: "Yes" }, 8);
    view = reduce(view, { t: 2.5, kind: "agent", text: "The earliest appointment is with", cut_off: true }, 9);
    const turns = view.items.filter((i) => i.type === "turn");
    expect(turns).toHaveLength(1);
    expect(turns[0]).toMatchObject({ text: "The earliest appointment is with", cutOff: true });
  });

  it("hangs the seconds to answer on the agent's next turn", () => {
    let view = reduce(empty(), { t: 1, kind: "latency", secs: 1.3 }, 0);
    view = reduce(view, { t: 2, kind: "agent", text: "Good morning." }, 1);
    expect(view.items[0]).toMatchObject({ latency: 1.3 });
  });
});

describe("a turn with no words in it", () => {
  it("is not shown", () => {
    const view = build([{ t: 0, kind: "call_started" }, { t: 3, kind: "hearing", text: "" }, { t: 4, kind: "caller", text: "" }]);
    expect(view.items.filter((i) => i.type === "turn")).toHaveLength(0);
  });
});

describe("small words", () => {
  it("reads a slot off its text, in Madrid time whatever the browser's zone", () => {
    expect(slotWords("2026-09-25T10:45:00+02:00")).toBe("Fri 25 Sep · 10:45");
  });
  it("formats seconds, initials and ages", () => {
    expect(clock(75.4)).toBe("01:15");
    expect(initials("Ana Ejemplo Prueba")).toBe("AE");
    expect(initials("")).toBe("?");
    expect(age("1946-09-26", new Date("2026-09-20"))).toBe(79);
  });
});

describe("the appointments on the books", () => {
  it("are listed from the lookup's result", () => {
    const view = build([
      { t: 0, kind: "call_started", has_caller_id: true },
      { t: 5, kind: "tool_call", name: "list_appointments", args: { patient_id: "P09999" } },
      { t: 5.1, kind: "tool_result", name: "list_appointments", result: { status: "ok", upcoming: [{ appointment_id: "A009999", doctor: "Dra. Ejemplo", site: "Arenal Norte", when: "Tuesday 13 October at 11:45" }] } },
    ]);
    expect(view.items.at(-1)).toMatchObject({ action: { kind: "appointments", status: "ok", items: [{ appointment_id: "A009999" }], ms: 100 } });
  });
});

// Every real call on this machine must build: the logs are the truth about what the agent writes.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const LOGS = join(__dirname, "..", "..", "..", "logs", "calls");
describe.skipIf(!existsSync(LOGS))("every call log on this machine", () => {
  it("builds without throwing, and an ended call ends with its end", () => {
    const files = readdirSync(LOGS).filter((f) => f.endsWith(".jsonl"));
    let ended = 0;
    for (const file of files) {
      const events = readFileSync(join(LOGS, file), "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l) as CallEvent);
      const view = build(events);
      if (events.some((e) => e.kind === "call_ended")) {
        ended += 1;
        expect(view.ended, file).toBe(true);
        expect(view.items.at(-1), file).toMatchObject({ action: { kind: "ended" } });
      }
      const opened = events.filter((e) => e.kind === "tool_call" && ["find_patient", "find_slots", "list_appointments", "nearest_site", "check_national_id"].includes(String(e.name))).length;
      const cards = view.items.filter((i) => i.type === "action" && ["identify", "search", "appointments", "nearest", "check_id"].includes(i.action.kind)).length;
      expect(cards, file).toBe(opened);
    }
    expect(ended).toBeGreaterThan(0);
  });
});
