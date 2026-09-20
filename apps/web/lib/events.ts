// One reducer for every screen: a call's event log in, what the screen shows out.
//
// The events are the lines of logs/calls/<call_id>.jsonl, written by the agent the moment things happen
// (apps/agent/src/clinic_agent/session.py). Live calls, past calls and replays all arrive as the same list,
// so the front desk and the caller's page are both views of `build(events)`.

export type CallEvent = { t: number; kind: string } & Record<string, unknown>;

export type Summary = {
  call_id: string;
  started_at: number;
  ended: boolean;
  live: boolean;
  seconds: number;
  decided_at: number | null;
  outcome: string[];
  actions: Record<string, unknown>[];
  delivered: boolean;
  dry_run: boolean;
  turns: number;
  lookups: number;
  first_words: string;
  flags: string[];
  source: "phone" | "web" | "replay";
  replay_of?: string | null;
  pipeline?: Pipeline | null;
  language: string;
  patient_id?: string | null;
  patient_name?: string | null;
  stage: string;
  mood?: number | null; // the kept reading of a finished call, when there is one
  answer_secs?: number | null; // median seconds from the caller's last word to the agent's first
  cost_usd?: number | null; // an estimate at list prices, for calls that logged what they used
};

export type Pipeline = { id: string; label?: string; stt?: string; llm?: string; tts?: string; prompt?: string; build?: string };

export type Offer = { slot_ref: string; when: string; doctor: string; site: string; payable_with?: string[] };

export type Slot = { start: string; provider_id?: string; provider: string; location_id?: string; site: string };

export type PatientCard = {
  patient_id?: string;
  name: string;
  date_of_birth?: string;
  sex?: string;
  insurer?: string;
  seen_before?: boolean;
  referrals?: string[];
  note?: string;
  national_id_masked?: string;
  phone_masked?: string;
  matched_on?: string[];
  status?: string;
};

export type DecisionKind = "book" | "reschedule" | "cancel" | "register" | "no-action" | "escalate";

export type Action =
  | { kind: "connected"; callerId: boolean; source: string; pipeline?: Pipeline | null; prefilled?: string[] }
  | {
      kind: "identify";
      status: "running" | "identified" | "one_field_only" | "not_found" | "several_match" | "invalid_national_id" | "need_identifier" | "error";
      said: Record<string, unknown>;
      patient?: PatientCard;
      ms?: number;
      why?: string;
      by?: string;
    }
  | { kind: "check_id"; status: string; said: Record<string, unknown>; ms?: number; why?: string }
  | { kind: "appointments"; status: string; items: Record<string, unknown>[]; ms?: number; why?: string }
  | { kind: "nearest"; status: string; said: Record<string, unknown>; result: Record<string, unknown>; ms?: number; why?: string }
  | {
      kind: "search";
      status: string; // running · slots_found · blocked · no_availability · provider_not_found · …
      query: Record<string, unknown>;
      offers: Offer[];
      notes: string[];
      reason?: string;
      slots?: Slot[];
      ms?: number;
      why?: string;
    }
  | { kind: "decision"; action: DecisionKind; payload: Record<string, unknown>; replaced: boolean; why?: string }
  | { kind: "refused"; tool: string; args: Record<string, unknown>; status: string; why?: string }
  | { kind: "note"; what: string; detail?: string }
  | { kind: "submit"; action: string; http: number; attempts: number; dryRun: boolean }
  | { kind: "ended"; seconds: number };

export type ChatItem =
  | {
      type: "turn"; id: string; seq: number; t: number; who: "caller" | "agent"; text: string; latency?: number; because: string[];
      spokenOnly?: boolean; // words that left the line but were never a turn in the model's context: the greeting, "one moment", a nudge
      cutOff?: boolean; // the caller talked over this reply and did not hear it
    }
  | { type: "action"; id: string; seq: number; t: number; action: Action };

export type FieldName = "name" | "national_id" | "date_of_birth" | "phone" | "email" | "insurer";
export type Field = { value: string; state: "heard" | "on_file" };

export type CallView = {
  items: ChatItem[];
  patient?: PatientCard;
  form: Partial<Record<FieldName, Field>>;
  offers: Offer[];
  slots: Slot[];
  searchLabel?: string;
  booked?: { slot: string; provider_id?: string; location_id?: string; action: DecisionKind };
  decisions: { action: DecisionKind; payload: Record<string, unknown>; replaced: boolean; t: number }[];
  language: string;
  source: string;
  pipeline?: Pipeline | null;
  ended: boolean;
  seconds: number;
  hearing: string; // the caller's words as they are recognised, before the turn is finished
  speaking: string; // the agent's sentences as they go to the voice, before its turn is finished
  latencies: number[];
  lookupMs: number[];
  usage?: Record<string, number>;
  // bookkeeping
  open: Record<string, string>; // tool name -> id of the chat item its result will land on
  openAt: Record<string, number>;
  since: string[]; // action ids since the last sentence of the agent: they are "why it said that"
  pendingLatency?: number;
};

const DECISION_TOOLS = new Set(["book", "reschedule", "cancel", "register_patient", "end_without_booking", "escalate", "discard_recorded"]);

export function empty(): CallView {
  return {
    items: [], form: {}, offers: [], slots: [], decisions: [], language: "en", source: "phone", ended: false, seconds: 0,
    hearing: "", speaking: "", latencies: [], lookupMs: [], open: {}, openAt: {}, since: [],
  };
}

export function build(events: CallEvent[]): CallView {
  return events.reduce((view, event, seq) => reduce(view, event, seq), empty());
}

const str = (v: unknown): string => (typeof v === "string" ? v : v == null ? "" : String(v));
const obj = (v: unknown): Record<string, unknown> => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
const arr = <T = unknown>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

function push(view: CallView, item: ChatItem): CallView {
  return { ...view, items: [...view.items, item] };
}

function patch(view: CallView, id: string | undefined, change: (a: Action) => Action): CallView {
  if (!id) return view;
  return { ...view, items: view.items.map((it) => (it.type === "action" && it.id === id ? { ...it, action: change(it.action) } : it)) };
}

const plain = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, "").replace(/\s+/g, " ").trim();

/** Words the agent has spoken that no finished turn accounts for yet become a turn of their own when the caller starts. */
function settleSpoken(view: CallView, seq: number, t: number): CallView {
  const text = view.speaking.trim();
  if (!text) return view;
  return { ...push(view, { type: "turn", id: `s${seq}`, seq, t, who: "agent", text, because: [], spokenOnly: true }), speaking: "" };
}

function heard(view: CallView, fields: Partial<Record<FieldName, unknown>>): CallView["form"] {
  const form = { ...view.form };
  for (const [name, raw] of Object.entries(fields) as [FieldName, unknown][]) {
    const value = str(raw).trim();
    if (value && form[name]?.state !== "on_file") form[name] = { value, state: "heard" };
  }
  return form;
}

export function reduce(view: CallView, e: CallEvent, seq: number): CallView {
  const id = `e${seq}`;
  const base = { ...view, seconds: Math.max(view.seconds, e.t) };
  const action = (a: Action, track = true): CallView => {
    const next = push(base, { type: "action", id, seq, t: e.t, action: a });
    return track ? { ...next, since: [...next.since, id] } : next;
  };

  switch (e.kind) {
    case "call_started":
      return {
        ...action({ kind: "connected", callerId: Boolean(e.has_caller_id), source: str(e.source) || "phone",
                    pipeline: (e.pipeline as Pipeline) ?? null, prefilled: arr<string>(e.prefilled) }, false),
        source: str(e.source) || "phone",
        pipeline: (e.pipeline as Pipeline) ?? null,
      };

    case "hearing":
      return { ...settleSpoken(base, seq, e.t), hearing: str(e.text) };

    case "caller": {
      const settled = settleSpoken(base, seq, e.t);
      // A cough or a click can close a turn with no words in it: nothing was said, so nothing is shown.
      if (!str(e.text).trim()) return { ...settled, hearing: "" };
      return { ...push(settled, { type: "turn", id, seq, t: e.t, who: "caller", text: str(e.text), because: [] }), hearing: "" };
    }

    case "speaking":
      return { ...base, speaking: `${base.speaking} ${str(e.text)}`.trim() };

    case "latency":
      return { ...base, pendingLatency: Number(e.secs), latencies: [...base.latencies, Number(e.secs)] };

    case "agent": {
      const text = str(e.text).trim();
      if (!text) return { ...base, speaking: "" }; // the turn was only a lookup
      // The finished turn is the whole reply. Its first words may already stand as a spoken-only turn — the caller
      // began to talk over it — and then this replaces them rather than saying them twice.
      const last = base.items.at(-1);
      const items = last?.type === "turn" && last.spokenOnly && plain(last.text).includes(plain(text).slice(0, 24)) ? base.items.slice(0, -1) : base.items;
      const turn: ChatItem = { type: "turn", id, seq, t: e.t, who: "agent", text, latency: base.pendingLatency, because: base.since, cutOff: Boolean(e.cut_off) || undefined };
      return { ...base, items: [...items, turn], speaking: "", since: [], pendingLatency: undefined };
    }

    case "tool_call": {
      const name = str(e.name);
      const args = obj(e.args);
      const opened = { ...base, open: { ...base.open, [name]: id }, openAt: { ...base.openAt, [name]: e.t } };
      if (name === "find_patient") {
        const next = { ...opened, form: heard(opened, { name: args.name, national_id: args.national_id, date_of_birth: args.date_of_birth, phone: args.phone }) };
        return { ...push(next, { type: "action", id, seq, t: e.t, action: { kind: "identify", status: "running", said: args, by: str(e.by) || undefined } }), since: [...next.since, id] };
      }
      if (name === "check_national_id") {
        const next = { ...opened, form: heard(opened, { national_id: args.national_id }) };
        return { ...push(next, { type: "action", id, seq, t: e.t, action: { kind: "check_id", status: "running", said: args } }), since: [...next.since, id] };
      }
      if (name === "list_appointments")
        return { ...push(opened, { type: "action", id, seq, t: e.t, action: { kind: "appointments", status: "running", items: [] } }), since: [...opened.since, id] };
      if (name === "nearest_site")
        return { ...push(opened, { type: "action", id, seq, t: e.t, action: { kind: "nearest", status: "running", said: args, result: {} } }), since: [...opened.since, id] };
      if (name === "find_slots")
        return { ...push(opened, { type: "action", id, seq, t: e.t, action: { kind: "search", status: "running", query: args, offers: [], notes: [] } }), since: [...opened.since, id] };
      if (name === "register_patient") {
        const full = [args.given_name, args.first_surname, args.second_surname].map(str).filter(Boolean).join(" ");
        return { ...opened, form: heard(opened, { name: full, national_id: args.national_id, date_of_birth: args.date_of_birth, phone: args.phone, email: args.email, insurer: args.insurer }) };
      }
      return opened; // a decision tool: its card comes with `recorded`, or with a result that refuses
    }

    case "patient": {
      const card = obj(e.card);
      const given = [card.given_name, card.first_surname, card.second_surname].map(str).filter(Boolean).join(" ");
      const patient: PatientCard = {
        ...(base.patient?.patient_id === e.patient_id ? base.patient : {}),
        patient_id: str(e.patient_id), name: given || base.patient?.name || "", matched_on: arr<string>(e.matched_on), status: str(e.status),
        ...(given ? {
          date_of_birth: str(card.date_of_birth) || undefined, sex: str(card.sex) || undefined, insurer: str(card.insurer) || undefined,
          seen_before: Boolean(card.has_visited_before), referrals: arr<string>(card.referrals), note: str(card.note) || undefined,
          national_id_masked: str(card.national_id_masked) || undefined, phone_masked: str(card.phone_masked) || undefined,
        } : {}),
      };
      return { ...patch(base, base.open.find_patient, (a) => (a.kind === "identify" ? { ...a, patient } : a)), patient };
    }

    case "offer": {
      const offers = arr<Offer>(e.offers);
      const notes = arr<string>(e.notes);
      return { ...patch(base, base.open.find_slots, (a) => (a.kind === "search" ? { ...a, offers, notes } : a)), offers };
    }

    case "availability": {
      const slots = arr<Slot>(e.slots);
      return { ...patch(base, base.open.find_slots, (a) => (a.kind === "search" ? { ...a, slots } : a)), slots, searchLabel: str(e.label) || base.searchLabel };
    }

    case "blocked":
      return patch(base, base.open.find_slots, (a) => (a.kind === "search" ? { ...a, reason: str(e.reason) } : a));

    case "nearest_site":
      return patch(base, base.open.nearest_site, (a) => (a.kind === "nearest" ? { ...a, result: { ...a.result, ...e } } : a));

    case "recorded": {
      const kind = str(e.action) as DecisionKind;
      const payload = obj(e.payload);
      const gone = arr(e.replaced).length;
      // What this decision replaced is struck through, newest first.
      let left = gone;
      const items = [...base.items].reverse().map((it) => {
        if (left > 0 && it.type === "action" && it.action.kind === "decision" && !it.action.replaced) {
          left -= 1;
          return { ...it, action: { ...it.action, replaced: true } };
        }
        return it;
      }).reverse();
      let leftDecisions = gone;
      const decisions = [...base.decisions].reverse().map((d) => (leftDecisions > 0 && !d.replaced ? (leftDecisions--, { ...d, replaced: true }) : d)).reverse();
      const next: CallView = { ...base, items, decisions: [...decisions, { action: kind, payload, replaced: false, t: e.t }] };
      const booked = kind === "book" || kind === "reschedule"
        ? { slot: str(payload.slot), provider_id: str(payload.provider_id) || undefined, location_id: str(payload.location_id) || undefined, action: kind }
        : kind === "no-action" || kind === "cancel" ? undefined : next.booked;
      const withCard = push(next, { type: "action", id, seq, t: e.t, action: { kind: "decision", action: kind, payload, replaced: false } });
      return { ...withCard, booked, since: [...withCard.since, id] };
    }

    case "discarded": {
      let done = false;
      const items = [...base.items].reverse().map((it) => {
        if (!done && it.type === "action" && it.action.kind === "decision" && !it.action.replaced) {
          done = true;
          return { ...it, action: { ...it.action, replaced: true } };
        }
        return it;
      }).reverse();
      const decisions = base.decisions.map((d, i) => (i === base.decisions.length - 1 ? { ...d, replaced: true } : d));
      const struck: CallView = { ...base, items, decisions, booked: undefined };
      return push(struck, { type: "action", id, seq, t: e.t, action: { kind: "note", what: "discarded", detail: "The caller took the decision back." } });
    }

    case "tool_result": {
      const name = str(e.name);
      const result = obj(e.result);
      const status = str(result.status);
      const why = str(result.say) || undefined;
      const ms = base.openAt[name] != null ? Math.round((e.t - base.openAt[name]) * 1000) : undefined;
      const target = base.open[name];
      const closed: CallView = { ...base, lookupMs: ms != null && !DECISION_TOOLS.has(name) ? [...base.lookupMs, ms] : base.lookupMs };

      if (name === "find_patient") {
        const fromResult: PatientCard | undefined = result.patient_id ? {
          ...(closed.patient ?? { name: "" }),
          patient_id: str(result.patient_id), name: closed.patient?.name || str(result.full_name),
          date_of_birth: closed.patient?.date_of_birth ?? (str(result.date_of_birth) || undefined),
          insurer: closed.patient?.insurer ?? (str(result.insurer_on_file) || undefined),
          seen_before: closed.patient?.seen_before ?? Boolean(result.has_visited_before),
          referrals: closed.patient?.referrals ?? arr<string>(result.referrals_on_file),
          note: closed.patient?.note ?? (str(result.note) || undefined),
          status,
        } : undefined;
        const form = fromResult ? {
          ...closed.form,
          name: { value: fromResult.name, state: "on_file" as const },
          ...(fromResult.date_of_birth ? { date_of_birth: { value: fromResult.date_of_birth, state: "on_file" as const } } : {}),
          ...(fromResult.insurer ? { insurer: { value: fromResult.insurer, state: "on_file" as const } } : {}),
          ...(closed.form.national_id && fromResult.matched_on?.includes("national_id") ? { national_id: { ...closed.form.national_id, state: "on_file" as const } } : {}),
          ...(closed.form.phone && fromResult.matched_on?.includes("phone") ? { phone: { ...closed.form.phone, state: "on_file" as const } } : {}),
        } : closed.form;
        const next = patch(closed, target, (a) => (a.kind === "identify" ? { ...a, status: (status || "error") as never, patient: fromResult ?? a.patient, ms, why } : a));
        return { ...next, patient: fromResult ?? next.patient, form };
      }
      if (name === "check_national_id") return patch(closed, target, (a) => (a.kind === "check_id" ? { ...a, status: status || (result.valid ? "valid" : "checked"), ms, why } : a));
      if (name === "list_appointments")
        return patch(closed, target, (a) => (a.kind === "appointments" ? { ...a, status: status || "listed", items: arr<Record<string, unknown>>(result.upcoming ?? result.appointments), ms, why } : a));
      if (name === "nearest_site") return patch(closed, target, (a) => (a.kind === "nearest" ? { ...a, status: status || "found", result: { ...a.result, ...result }, ms, why } : a));
      if (name === "find_slots")
        return patch(closed, target, (a) => (a.kind === "search" ? { ...a, status: status || "error", reason: a.reason ?? (str(result.reason) || undefined), notes: a.notes.length ? a.notes : arr<string>(result.notes), ms, why } : a));
      if (DECISION_TOOLS.has(name) && status !== "recorded" && status !== "discarded" && status !== "registered") {
        // The agent tried to record something and code said no — the reason is the answer to "why did it say that?".
        const card = push(closed, { type: "action", id, seq, t: e.t, action: { kind: "refused", tool: name, args: {}, status: status || "refused", why } });
        return { ...card, since: [...card.since, id] };
      }
      // A decision that was recorded: its card exists already; keep the tool's words as its "why".
      const last = [...closed.items].reverse().find((it) => it.type === "action" && it.action.kind === "decision");
      return last && why ? patch(closed, last.id, (a) => (a.kind === "decision" ? { ...a, why } : a)) : closed;
    }

    case "voice":
      return { ...action({ kind: "note", what: "voice", detail: str(e.language) }, false), language: str(e.language) || base.language };
    case "listening_model":
      return { ...action({ kind: "note", what: "listening_model", detail: str(e.language) }, false), language: "ca" };
    case "hung_up_undecided":
    case "quiet_line":
    case "wrap_up_clock":
    case "inferred_at_hangup":
    case "recovered_leaked_call":
    case "refusal_not_recorded":
      return action({ kind: "note", what: e.kind, detail: e.reason ? str(e.reason) : e.offer ? `offer ${str(e.offer)}` : undefined }, false);

    case "usage":
      return { ...base, usage: obj(e) as Record<string, number> };

    case "submit":
      return action({ kind: "submit", action: str(e.action), http: Number(e.http), attempts: Number(e.attempts), dryRun: Number(e.attempts) === 0 }, false);

    case "call_ended":
      return { ...action({ kind: "ended", seconds: e.t }, false), ended: true, hearing: "", speaking: "" };

    default:
      return base;
  }
}

// ---------------------------------------------------------------- words for what happened

export function initials(name?: string | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  return parts.length ? (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase() : "?";
}

export function age(dateOfBirth?: string, now = new Date()): number | undefined {
  if (!dateOfBirth) return undefined;
  const born = new Date(dateOfBirth);
  if (Number.isNaN(born.getTime())) return undefined;
  let years = now.getFullYear() - born.getFullYear();
  if (now < new Date(now.getFullYear(), born.getMonth(), born.getDate())) years -= 1;
  return years;
}

export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** "2026-09-25T10:45:00+02:00" → "Fri 25 Sep · 10:45" — read straight off the text, so it is always Madrid time. */
export function slotWords(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (!m) return iso;
  const day = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  const weekday = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][day.getUTCDay()];
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][day.getUTCMonth()];
  return `${weekday} ${Number(m[3])} ${month} · ${m[4]}:${m[5]}`;
}
