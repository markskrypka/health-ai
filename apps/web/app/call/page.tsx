"use client";

import clsx from "clsx";
import Link from "next/link";
import { Check, Ear, Phone as PhoneIcon, PhoneOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { CALL_WS_URL, EVENTS_URL } from "@/lib/config";
import { DeskStore } from "@/lib/desk-store";
import { build, clock, empty, type FieldName } from "@/lib/events";
import { Phone, type PhoneState } from "@/lib/phone";
import { Calendar } from "@/components/call/Calendar";
import { NO_NAMES, type Names } from "@/components/desk/ActionCard";
import { useNow, useRevealed } from "@/components/ui";

const FIELDS: { name: FieldName; label: string; placeholder: string; type?: string }[] = [
  { name: "name", label: "Full name", placeholder: "Name and both surnames" },
  { name: "national_id", label: "DNI / NIE", placeholder: "12345678Z" },
  { name: "date_of_birth", label: "Date of birth", placeholder: "", type: "date" },
  { name: "phone", label: "Phone", placeholder: "600 000 000" },
  { name: "email", label: "Email", placeholder: "you@example.com", type: "email" },
  { name: "insurer", label: "Insurer", placeholder: "" },
];

const NOTHING: never[] = [];

function Level({ value, tone }: { value: number; tone: "mic" | "agent" }) {
  return (
    <div className="flex h-6 items-center gap-[3px]">
      {Array.from({ length: 14 }, (_, i) => {
        const lit = value * 14 > i;
        return <span key={i} style={{ height: `${30 + ((i * 37) % 60)}%` }}
                     className={clsx("w-[3px] rounded-full transition-colors duration-75", lit ? (tone === "mic" ? "bg-ink" : "bg-clinic") : "bg-line")} />;
      })}
    </div>
  );
}

export default function CallPage() {
  const store = useMemo(() => new DeskStore(), []);
  const state = useSyncExternalStore(store.subscribe, store.snapshot, store.snapshot);
  const [names, setNames] = useState<Names>(NO_NAMES);
  const [typed, setTyped] = useState<Partial<Record<FieldName, string>>>({});
  const [pipeline, setPipeline] = useState("A");
  const [callId, setCallId] = useState<string>();
  const [phoneState, setPhoneState] = useState<PhoneState>("idle");
  const [problem, setProblem] = useState<string>();
  const [levels, setLevels] = useState({ mic: 0, agent: 0 });
  const [startedAt, setStartedAt] = useState<number>();
  const phone = useRef<Phone | null>(null);
  const pressedAt = useRef(0);
  const now = useNow(500);

  // The one big button both starts and ends a call. A nervous double press must not end the call it has just started.
  const pressed = () => {
    const tooSoon = Date.now() - pressedAt.current < 1500;
    if (!tooSoon) pressedAt.current = Date.now();
    return !tooSoon;
  };

  useEffect(() => {
    store.start();
    fetch(`${EVENTS_URL}/api/catalogue`).then((r) => r.json()).then(setNames).catch(() => {});
    return () => store.stop();
  }, [store]);

  // Leaving the page ends the call. In development a saved file runs every cleanup and setup back to back (Fast
  // Refresh): that is not a goodbye, so the hang-up waits a moment and is called off when the page is still there.
  const leaving = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    clearTimeout(leaving.current);
    return () => { leaving.current = setTimeout(() => phone.current?.hangUp(), 400); };
  }, []);

  const events = (callId && state.events[callId]) || NOTHING;
  const view = useMemo(() => (events.length ? build(events) : empty()), [events]);
  const live = phoneState === "live" || phoneState === "connecting";

  const call = useCallback(async () => {
    if (!pressed()) return;
    const id = crypto.randomUUID();
    const clip = new URLSearchParams(window.location.search).get("clip") ?? undefined; // a recorded caller instead of the microphone: for checks
    const prefill = Object.fromEntries(Object.entries(typed).filter(([, v]) => v?.trim()));
    setCallId(id); setProblem(undefined); setStartedAt(Date.now());
    const next = new Phone({
      url: CALL_WS_URL, callId: id, testClipUrl: clip,
      params: { screen: "1", pipeline, ...(Object.keys(prefill).length ? { prefill: JSON.stringify(prefill) } : {}) },
      onState: (s, detail) => { setPhoneState(s); if (s === "error") setProblem(detail ?? "The call could not start."); },
      onLevel: (mic, agent) => setLevels({ mic, agent }),
    });
    phone.current = next;
    await next.start().catch((err: unknown) => { setPhoneState("error"); setProblem(err instanceof Error ? err.message : String(err)); });
  }, [pipeline, typed]);

  const hangUp = useCallback(() => {
    if (!pressed()) return;
    phone.current?.hangUp();
    phone.current = null;
    setLevels({ mic: 0, agent: 0 });
  }, []);

  // What a field shows: what the caller typed before ringing, else what the agent heard, ticked once the clinic's record agrees.
  const lastAgent = [...view.items].reverse().find((i) => i.type === "turn" && i.who === "agent");
  const speaking = useRevealed(view.speaking);
  const saying = view.speaking ? speaking : lastAgent?.type === "turn" ? lastAgent.text : "";
  const seconds = live && startedAt ? (now - startedAt) / 1000 : view.seconds;

  return (
    <div className="mx-auto flex h-full max-w-[1240px] flex-col gap-4 px-6 py-5">
      <nav className="flex items-center gap-3">
        <Link href="/" className="text-sm font-semibold tracking-tight text-clinic">Clínica Arenal</Link>
        <span className="text-sm text-faint">· book by talking to us</span>
        <span className="flex-1" />
        <Link href="/desk" className="text-xs text-soft underline-offset-4 hover:underline">front desk →</Link>
      </nav>

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="flex w-[400px] shrink-0 flex-col gap-4">
          <section className="rounded-2xl border border-line bg-card p-5">
            <div className="flex items-baseline justify-between">
              <h2 className="text-sm font-semibold">Your details</h2>
              <span className="text-xs text-faint">{callId ? "filling in as you talk" : "optional — or just tell us on the call"}</span>
            </div>
            <div className="mt-3 space-y-2.5">
              {FIELDS.map((f) => {
                const heard = view.form[f.name];
                const mine = typed[f.name]?.trim();
                const value = heard?.state === "on_file" ? heard.value : mine || heard?.value || "";
                const shown = f.name === "insurer" && value ? names.plans[value] ?? value
                  : f.name === "date_of_birth" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split("-").reverse().join("/") : value;
                const onFile = heard?.state === "on_file";
                const justHeard = !mine && heard?.state === "heard";
                return (
                  <label key={f.name} className="block">
                    <span className="mb-1 flex items-center justify-between text-xs font-medium text-soft">
                      {f.label}
                      {onFile ? <span className="flex animate-arrive items-center gap-1 text-good"><Check className="size-3" />on file</span>
                        : justHeard ? <span className="flex animate-arrive items-center gap-1 text-clinic"><Ear className="size-3" />heard</span> : null}
                    </span>
                    {f.name === "insurer" && !callId ? (
                      <select value={typed.insurer ?? ""} onChange={(e) => setTyped({ ...typed, insurer: e.target.value })}
                              className="h-10 w-full rounded-lg border border-line bg-paper/60 px-3 text-sm outline-none transition focus:border-clinic">
                        <option value="">—</option>
                        {Object.entries(names.plans).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
                      </select>
                    ) : (
                      <input type={callId ? "text" : f.type ?? "text"} value={callId ? shown : typed[f.name] ?? ""} placeholder={f.placeholder} readOnly={Boolean(callId)}
                             onChange={(e) => setTyped({ ...typed, [f.name]: e.target.value })}
                             className={clsx("h-10 w-full rounded-lg border px-3 text-sm outline-none transition focus:border-clinic",
                                             onFile ? "border-good/40 bg-good-soft/50" : justHeard ? "border-clinic-line bg-clinic-soft/40 italic" : "border-line bg-paper/60")} />
                    )}
                  </label>
                );
              })}
            </div>
          </section>

          <section className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-card p-5">
            {live ? (
              <button onClick={hangUp} className="inline-flex h-14 w-full items-center justify-center gap-2.5 rounded-full bg-live text-base font-semibold text-white shadow-sm transition hover:brightness-95">
                <PhoneOff className="size-5" /> Hang up · <span className="tabular-nums">{clock(seconds)}</span>
              </button>
            ) : (
              <button onClick={call} className="inline-flex h-14 w-full items-center justify-center gap-2.5 rounded-full bg-clinic text-base font-semibold text-white shadow-sm transition hover:brightness-110">
                <PhoneIcon className="size-5" /> {callId ? "Call again" : "Call the clinic"}
              </button>
            )}
            {live && (
              <div className="flex w-full items-center justify-between px-2 text-[11px] text-faint">
                <span className="flex items-center gap-2">you <Level value={levels.mic} tone="mic" /></span>
                <span className="flex items-center gap-2"><Level value={levels.agent} tone="agent" /> clinic</span>
              </div>
            )}
            {!live && (
              <div className="flex items-center gap-2 text-[11px] text-faint">
                voice
                {[["A", "ElevenLabs"], ["B", "Deepgram"]].map(([id, label]) => (
                  <button key={id} onClick={() => setPipeline(id)} className={clsx("rounded-full border px-2 py-0.5 transition", pipeline === id ? "border-clinic bg-clinic-soft text-clinic" : "border-line hover:bg-wash")}>{id} · {label}</button>
                ))}
              </div>
            )}
            {problem && <p className="w-full rounded-lg bg-bad-soft px-3 py-2 text-xs text-bad">{problem}</p>}
            {phoneState === "connecting" && <p className="text-xs text-faint">ringing…</p>}
          </section>

          {callId && (
            <section className="min-h-[88px] rounded-2xl border border-line bg-card px-5 py-4">
              {saying && <p className="animate-arrive text-[15px] leading-snug"><span className="mr-1.5 text-xs font-semibold uppercase tracking-wider text-clinic">clinic</span>{saying}{view.speaking && <span className="ml-0.5 animate-pulse">▍</span>}</p>}
              {view.hearing && <p className="mt-2 text-sm text-soft"><span className="mr-1.5 text-xs font-semibold uppercase tracking-wider text-faint">you</span>{view.hearing}<span className="ml-0.5 animate-pulse">▍</span></p>}
              {!saying && !view.hearing && <p className="text-sm text-faint">{live ? "Connecting you to the front desk…" : ""}</p>}
              {view.ended && <p className="mt-2 text-xs text-faint">The call has ended. This page is a demonstration line: what was decided is captured and shown, never sent to a real clinic.</p>}
            </section>
          )}
        </div>

        <Calendar view={view} names={names} />
      </div>
    </div>
  );
}
