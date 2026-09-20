"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { GitCompareArrows, Play, Rows3 } from "lucide-react";
import { EVENTS_URL } from "@/lib/config";
import { DeskStore } from "@/lib/desk-store";
import { build } from "@/lib/events";
import { CallList } from "@/components/desk/CallList";
import { Chat, ChatHeader } from "@/components/desk/Chat";
import { Insights } from "@/components/desk/Insights";
import { PatientPanel } from "@/components/desk/PatientPanel";
import { Pipelines } from "@/components/desk/Pipelines";
import { NO_NAMES, type Names } from "@/components/desk/ActionCard";

const NOTHING: never[] = [];

export default function Desk() {
  const store = useMemo(() => new DeskStore(), []);
  const state = useSyncExternalStore(store.subscribe, store.snapshot, store.snapshot);
  const [tab, setTab] = useState<"live" | "past">("live");
  const [selected, setSelected] = useState<string>();
  const [names, setNames] = useState<Names>(NO_NAMES);
  const [comparing, setComparing] = useState(false);
  const followed = useRef<Set<string>>(new Set());

  useEffect(() => {
    store.start();
    fetch(`${EVENTS_URL}/api/catalogue`).then((r) => r.json()).then(setNames).catch(() => {});
    return () => store.stop();
  }, [store]);

  const calls = useMemo(() => Object.values(state.calls), [state.calls]);

  // A call that has just connected takes the screen, once — unless someone is reading another live call.
  useEffect(() => {
    const fresh = calls.filter((c) => c.live && !followed.current.has(c.call_id)).sort((a, b) => b.started_at - a.started_at)[0];
    if (!fresh) return;
    followed.current.add(fresh.call_id);
    const current = selected ? state.calls[selected] : undefined;
    if (!current?.live) {
      setSelected(fresh.call_id);
      setTab("live");
    }
  }, [calls, selected, state.calls]);

  useEffect(() => {
    if (selected) void store.load(selected);
  }, [selected, store]);

  const summary = selected ? state.calls[selected] : undefined;
  const finished = Boolean(summary?.ended && summary.source !== "replay");

  // A finished call is read once when it is first opened; the reading is kept on disk by the events service.
  useEffect(() => {
    if (selected && finished) void store.analyse(selected);
  }, [selected, finished, store]);

  const events = (selected && state.events[selected]) || NOTHING;
  const view = useMemo(() => (selected && events.length ? build(events) : undefined), [selected, events]);
  const listMoods = useMemo(() => {
    const out: Record<string, number | undefined> = {};
    for (const c of Object.values(state.calls)) if (c.mood != null) out[c.call_id] = c.mood;
    for (const [id, a] of Object.entries(state.analysis)) if (a.mood != null) out[id] = a.mood;
    for (const [id, byTurn] of Object.entries(state.moods)) {
      const values = Object.entries(byTurn).sort(([a], [b]) => Number(a) - Number(b)).map(([, v]) => v);
      if (values.length && out[id] == null) out[id] = values[values.length - 1];
    }
    return out;
  }, [state.analysis, state.moods, state.calls]);

  const replayMany = async () => {
    const finished = calls.filter((c) => !c.live && c.source !== "replay" && c.outcome.length > 0 && c.seconds > 40).slice(0, 10);
    await Promise.all(finished.map((c) => store.replay(c.call_id, 1)));
    setTab("live");
  };

  return (
    <div className="flex h-full flex-col">
      <nav className="flex items-center gap-3.5 border-b border-line bg-card px-5 py-2.5">
        <Link href="/" className="flex items-center gap-2.5 transition hover:opacity-85" title="Prosper — GING">
          <img src="/prosper-mark.png" alt="Prosper" className="size-6 rounded-md object-contain shadow-xs" />
          <span className="text-base font-bold tracking-tight text-ink">Prosper</span>
          <span className="text-soft/60 font-light text-sm select-none">—</span>
          <span className="rounded-md border border-clinic-line/80 bg-clinic-soft/70 px-2 py-0.5 font-mono text-xs font-bold tracking-wider text-clinic shadow-2xs">
            GING
          </span>
        </Link>
        <span className="h-4 w-px bg-line" />
        <span className="text-xs font-medium text-soft">front desk</span>
        <span className={`text-xs ${state.connected ? "text-good" : "text-bad"}`}>{state.connected ? "● connected to the call logs" : "○ events service not reachable — is it running on 7870?"}</span>
        <span className="flex-1" />
        <button onClick={() => setComparing(true)} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-soft transition hover:bg-wash">
          <GitCompareArrows className="size-3.5" /> Compare pipelines
        </button>
        <button onClick={replayMany} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-soft transition hover:bg-wash" title="Replay ten recorded calls at once, at their real speed">
          <Rows3 className="size-3.5" /> Replay ten at once
        </button>
        <Link href="/call" className="rounded-lg bg-clinic px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-clinic/90">Open the caller&rsquo;s screen</Link>
      </nav>

      <div className="flex min-h-0 flex-1">
        <CallList calls={calls} tab={tab} onTab={setTab} selected={selected} onSelect={setSelected} moods={listMoods} />

        <main className="flex min-w-0 flex-1 flex-col">
          {summary && view ? (
            <>
              <ChatHeader summary={summary} view={view}>
                {!summary.live && summary.source !== "replay" && (
                  <button onClick={async () => { const id = await store.replay(summary.call_id, 1); if (id) { setSelected(id); setTab("live"); } }}
                          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-soft transition hover:bg-wash">
                    <Play className="size-3.5" /> Replay as if live
                  </button>
                )}
              </ChatHeader>
              {summary.ended && <Insights summary={summary} view={view} analysis={state.analysis[summary.call_id]} />}
              <Chat key={summary.call_id} view={view} names={names} moods={state.moods[summary.call_id] ?? state.analysis[summary.call_id]?.by_turn ?? {}} live={summary.live} />
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-sm text-faint">
              {selected ? "Loading the call…" : "Waiting for a call. Pick a past one on the left, or ring the clinic."}
            </div>
          )}
        </main>

        <PatientPanel view={view} names={names} />
      </div>
      {comparing && <Pipelines onClose={() => setComparing(false)} />}
    </div>
  );
}
