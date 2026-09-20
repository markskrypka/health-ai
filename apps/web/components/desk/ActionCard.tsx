"use client";

import clsx from "clsx";
import {
  BadgeCheck, CalendarCheck, CalendarClock, CalendarSearch, CalendarX, CircleAlert, ClipboardList, Ear, FileBadge, Languages,
  MapPin, PhoneIncoming, PhoneOff, Send, ShieldAlert, Siren, Timer, Undo2, UserPlus, UserSearch, UserX, Volume2,
} from "lucide-react";
import { slotWords, type Action, type Offer } from "@/lib/events";
import { Avatar, Chip } from "@/components/ui";

export type Names = { providers: Record<string, string>; locations: Record<string, string>; types: Record<string, string>; plans: Record<string, string>; specialties: Record<string, string> };
export const NO_NAMES: Names = { providers: {}, locations: {}, types: {}, plans: {}, specialties: {} };

const s = (v: unknown) => (v == null ? "" : String(v));

function Shell({ icon: Icon, tone, title, ms, children, highlighted, struck }: {
  icon: React.ComponentType<{ className?: string }>; tone: "tool" | "good" | "warn" | "bad" | "clinic" | "plain"; title: React.ReactNode; ms?: number;
  children?: React.ReactNode; highlighted?: boolean; struck?: boolean;
}) {
  const tones = {
    tool: "border-line bg-card", good: "border-good/30 bg-good-soft/60", warn: "border-warn/30 bg-warn-soft/60", bad: "border-bad/30 bg-bad-soft/60",
    clinic: "border-clinic-line bg-clinic-soft/50", plain: "border-line bg-wash/50",
  };
  const iconTones = { tool: "bg-tool-soft text-tool", good: "bg-good text-white", warn: "bg-warn text-white", bad: "bg-bad text-white", clinic: "bg-clinic text-white", plain: "bg-wash text-soft" };
  return (
    <div className={clsx("mx-auto w-full max-w-[520px] animate-arrive rounded-xl border px-3.5 py-3 shadow-[0_1px_0_rgba(0,0,0,0.02)] transition",
                         tones[tone], highlighted && "ring-2 ring-clinic/50", struck && "opacity-55")}>
      <div className="flex items-center gap-2.5">
        <span className={clsx("inline-flex size-6 shrink-0 items-center justify-center rounded-md", iconTones[tone])}><Icon className="size-3.5" /></span>
        <span className={clsx("min-w-0 flex-1 truncate text-[13px] font-semibold", struck && "line-through")}>{title}</span>
        {ms != null && <span className="font-mono text-[11px] tabular-nums text-faint">{ms} ms</span>}
      </div>
      {children && <div className={clsx("mt-2 text-[13px] text-soft", struck && "line-through")}>{children}</div>}
    </div>
  );
}

function Said({ args }: { args: Record<string, unknown> }) {
  const parts = Object.entries(args).filter(([, v]) => v !== "" && v != null && v !== false);
  if (!parts.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {parts.map(([k, v]) => <Chip key={k} tone="tool"><span className="opacity-60">{k.replaceAll("_", " ")}</span>{v === true ? "" : ` ${maskIfId(k, s(v))}`}</Chip>)}
    </div>
  );
}

/** The desk never shows a whole national id or phone number: the last characters are enough to recognise one. */
function maskIfId(key: string, value: string): string {
  if (key === "national_id" || key === "phone") return value.length > 4 ? `${"•".repeat(Math.min(5, value.length - 4))}${value.slice(-4)}` : value;
  return value;
}

function Offers({ offers }: { offers: Offer[] }) {
  if (!offers.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {offers.map((o, i) => (
        <span key={o.slot_ref} className={clsx("rounded-lg border px-2 py-1 text-xs", i === 0 ? "border-clinic-line bg-clinic-soft text-clinic" : "border-line bg-card text-soft")}>
          <span className="font-semibold">{o.when.replace(/^(\w{3})\w* (\d+) (\w{3})\w* at /, "$1 $2 $3 · ")}</span>
          <span className="opacity-70"> · {o.doctor} · {o.site.replace("Arenal ", "")}</span>
          {i === 0 && <span className="ml-1 opacity-70">← said</span>}
        </span>
      ))}
    </div>
  );
}

const DECISION = {
  book: { icon: CalendarCheck, tone: "good", title: "Booked" },
  reschedule: { icon: CalendarClock, tone: "good", title: "Moved" },
  cancel: { icon: CalendarX, tone: "warn", title: "Cancelled" },
  register: { icon: UserPlus, tone: "good", title: "Registered" },
  "no-action": { icon: ShieldAlert, tone: "plain", title: "Ended without booking" },
  escalate: { icon: Siren, tone: "bad", title: "Escalated — told to call 112" },
} as const;

const NOTE: Record<string, { icon: React.ComponentType<{ className?: string }>; text: string }> = {
  voice: { icon: Volume2, text: "The voice changed language" },
  listening_model: { icon: Ear, text: "Catalan heard — the listening model changed" },
  quiet_line: { icon: Timer, text: "The line went quiet — the agent asked if the caller is still there" },
  wrap_up_clock: { icon: Timer, text: "Wrap-up clock: thirty seconds left, the agent is told to record the outcome" },
  inferred_at_hangup: { icon: PhoneOff, text: "The caller hung up before a decision — the code recorded what the call had settled" },
  recovered_leaked_call: { icon: Undo2, text: "The model wrote a tool call as text — the code ran it instead of saying it" },
  refusal_not_recorded: { icon: ShieldAlert, text: "A refusal was dropped: another decision stands" },
  discarded: { icon: Undo2, text: "The caller took the decision back" },
  hung_up_undecided: { icon: PhoneOff, text: "The caller hung up before deciding — nothing was booked" },
};

export function ActionCard({ action, names, highlighted }: { action: Action; names: Names; highlighted?: boolean }) {
  switch (action.kind) {
    case "connected":
      return (
        <div className="flex animate-arrive items-center justify-center gap-2 text-xs text-faint">
          <PhoneIncoming className="size-3.5" />
          <span>Call connected · {action.callerId ? "caller id known" : "no caller id"}{action.prefilled?.length ? ` · details from the web form: ${action.prefilled.join(", ")}` : ""}</span>
        </div>
      );

    case "identify": {
      const found = action.status === "identified" || action.status === "one_field_only";
      const title = action.status === "running" ? "Looking the caller up…"
        : action.status === "identified" ? `Identified${action.patient?.matched_on?.length ? ` · ${action.patient.matched_on.map((m) => m.replaceAll("_", " ")).join(" + ")}` : ""}`
        : action.status === "one_field_only" ? "Found on one detail only — a second is needed"
        : action.status === "several_match" ? "Several patients match — one more detail needed"
        : action.status === "not_found" ? "Nobody on file matches"
        : action.status === "invalid_national_id" ? "That is not a valid id — asking again"
        : action.status === "need_identifier" ? "Needs a name or an identifier" : "The lookup failed";
      const Icon = action.status === "running" ? UserSearch : found ? BadgeCheck : UserX;
      return (
        <Shell icon={Icon} tone={action.status === "running" ? "tool" : found ? "clinic" : "warn"} title={title} ms={action.ms} highlighted={highlighted}>
          {found && action.patient ? (
            <div className="flex items-center gap-3">
              <Avatar patientId={action.patient.patient_id} name={action.patient.name} size={44} />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{action.patient.name}</div>
                <div className="text-xs">{action.patient.patient_id}{action.by === "form" ? " · from the web form, before the greeting" : ""}</div>
              </div>
            </div>
          ) : <Said args={action.said} />}
        </Shell>
      );
    }

    case "check_id":
      return <Shell icon={FileBadge} tone="tool" title={action.status === "running" ? "Checking the id's letter…" : `Id check: ${action.status.replaceAll("_", " ")}`} ms={action.ms} highlighted={highlighted}><Said args={action.said} /></Shell>;

    case "appointments":
      return (
        <Shell icon={ClipboardList} tone="tool" title={action.status === "running" ? "Reading the appointments on the books…" : `Appointments on the books: ${action.items.length}`} ms={action.ms} highlighted={highlighted}>
          {action.items.length > 0 && (
            <ul className="space-y-0.5">
              {action.items.map((a, i) => <li key={i} className="text-xs">{s(a.when) || slotWords(s(a.start_time))} · {s(a.doctor) || names.providers[s(a.provider_id)] || s(a.provider_id)} · {s(a.site) || names.locations[s(a.location_id)] || s(a.location_id)}</li>)}
            </ul>
          )}
        </Shell>
      );

    case "nearest":
      return (
        <Shell icon={MapPin} tone="tool" title={action.status === "running" ? "Finding the nearest clinic…" : `Nearest clinic: ${s(action.result.nearest ?? action.status)}${action.result.distance_km != null ? ` · ${s(action.result.distance_km)} km` : ""}`} ms={action.ms} highlighted={highlighted}>
          <Said args={action.said} />
          {action.result.directions ? <p className="mt-1.5 text-xs">{s(action.result.directions)}</p> : null}
        </Shell>
      );

    case "search": {
      const blocked = action.status === "blocked";
      const none = action.status === "no_availability";
      const title = action.status === "running" ? "Searching the diary…"
        : action.status === "slots_found" ? "Free slots found"
        : blocked ? `A clinic rule stops this: ${s(action.reason).replaceAll("_", " ")}`
        : none ? "Nothing free matches" : `Search: ${action.status.replaceAll("_", " ")}`;
      const q = action.query;
      const query = {
        specialty: names.specialties[s(q.specialty_id)] ?? q.specialty_id, doctor: q.provider_name, site: names.locations[s(q.location_id)] ?? q.location_id,
        when: q.date_iso || q.weekday || (q.day_kind && q.day_kind !== "earliest" ? q.day_kind : ""), time: q.time, part: q.part_of_day && q.part_of_day !== "any" ? q.part_of_day : "",
        plan: q.insurer, language: q.language, after: q.after_appointment_id, from: q.caller_address, earliest: q.day_kind === "earliest" || (!q.date_iso && !q.weekday && !q.day_kind) ? true : "",
      };
      return (
        <Shell icon={blocked ? ShieldAlert : CalendarSearch} tone={action.status === "running" ? "tool" : blocked ? "warn" : none ? "plain" : "tool"} title={title} ms={action.ms} highlighted={highlighted}>
          <Said args={query} />
          <Offers offers={action.offers} />
          {action.slots && action.slots.length > 0 && <p className="mt-1.5 text-xs text-faint">{action.slots.length} free slots behind this offer — on the caller&rsquo;s calendar.</p>}
          {action.notes.map((n, i) => <p key={i} className="mt-1.5 text-xs"><CircleAlert className="mr-1 inline size-3 -translate-y-px" />{n}</p>)}
        </Shell>
      );
    }

    case "decision": {
      const d = DECISION[action.action] ?? DECISION["no-action"];
      const p = action.payload;
      return (
        <Shell icon={d.icon} tone={d.tone} title={action.replaced ? `${d.title} — replaced` : d.title} highlighted={highlighted} struck={action.replaced}>
          {(action.action === "book" || action.action === "reschedule") && (
            <span className="text-ink"><b>{slotWords(s(p.slot))}</b>{p.provider_id ? ` · ${names.providers[s(p.provider_id)] ?? s(p.provider_id)}` : ""}{p.location_id ? ` · ${names.locations[s(p.location_id)] ?? s(p.location_id)}` : ""}
              {p.appointment_type_id ? ` · ${names.types[s(p.appointment_type_id)] ?? s(p.appointment_type_id)}` : ""}{p.policy_id ? ` · paid by ${names.plans[s(p.policy_id)] ?? s(p.policy_id)}` : ""}
              {action.action === "reschedule" && p.appointment_id ? ` · was ${s(p.appointment_id)}` : ""}</span>
          )}
          {action.action === "cancel" && <span className="text-ink">Appointment <b>{s(p.appointment_id)}</b></span>}
          {action.action === "register" && <span className="text-ink"><b>{[p.given_name, p.first_surname, p.second_surname].map(s).filter(Boolean).join(" ")}</b>{p.insurer ? ` · ${names.plans[s(p.insurer)] ?? s(p.insurer)}` : ""}</span>}
          {(action.action === "no-action" || action.action === "escalate") && <span className="text-ink">Reason: <code className="rounded bg-black/5 px-1 py-0.5 font-mono text-xs">{s(p.reason)}</code></span>}
        </Shell>
      );
    }

    case "refused":
      return <Shell icon={ShieldAlert} tone="warn" title={`The code refused ${action.tool.replaceAll("_", " ")}: ${action.status.replaceAll("_", " ")}`} highlighted={highlighted}>{action.why}</Shell>;

    case "note": {
      const n = NOTE[action.what] ?? { icon: Languages, text: action.what.replaceAll("_", " ") };
      return (
        <div className="flex animate-arrive items-center justify-center gap-2 text-xs text-faint">
          <n.icon className="size-3.5" /><span>{n.text}{action.detail ? ` (${action.detail})` : ""}</span>
        </div>
      );
    }

    case "submit": {
      const ok = [200, 201, 409].includes(action.http);
      return (
        <Shell icon={Send} tone={action.dryRun ? "plain" : ok ? "good" : "bad"} highlighted={highlighted}
               title={action.dryRun ? `Captured, not sent — a dry run (${action.action})` : ok ? `Sent to the clinic: ${action.action} · HTTP ${action.http}${action.attempts > 1 ? ` after ${action.attempts} attempts` : ""}` : `Not delivered: ${action.action} · HTTP ${action.http} after ${action.attempts} attempts`} />
      );
    }

    case "ended":
      return (
        <div className="flex animate-arrive items-center justify-center gap-2 pb-2 text-xs text-faint">
          <PhoneOff className="size-3.5" /><span>Call ended after {Math.round(action.seconds)} s</span>
        </div>
      );
  }
}
