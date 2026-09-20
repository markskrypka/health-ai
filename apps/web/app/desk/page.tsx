"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Play, Rows3 } from "lucide-react";
import { EVENTS_URL } from "@/lib/config";
import { DeskStore } from "@/lib/desk-store";
import { build } from "@/lib/events";
import { CallList } from "@/components/desk/CallList";
import { Chat, ChatHeader } from "@/components/desk/Chat";
import { PatientPanel } from "@/components/desk/PatientPanel";
import { NO_NAMES, type Names } from "@/components/desk/ActionCard";

const NOTHING: never[] = [];

export default function Desk() {
  const store = useMemo(() => new DeskStore(), []);
  const state = useSyncExternalStore(store.subscribe, store.snapshot, store.snapshot);
  const [tab, setTab] = useState<"live" | "past">("live");
  const [selected, setSelected] = useState<string>();
  const [names, setNames] = useState<Names>(NO_NAMES);
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
  const events = (selected && state.events[selected]) || NOTHING;
  const view = useMemo(() => (selected && events.length ? build(events) : undefined), [selected, events]);
  const listMoods = useMemo(() => {
    const out: Record<string, number | undefined> = {};
    for (const [id, a] of Object.entries(state.analysis)) out[id] = a.mood;
    for (const [id, byTurn] of Object.entries(state.moods)) {
      const values = Object.entries(byTurn).sort(([a], [b]) => Number(a) - Number(b)).map(([, v]) => v);
      if (values.length && out[id] == null) out[id] = values[values.length - 1];
    }
    return out;
  }, [state.analysis, state.moods]);

  const replayMany = async () => {
    const finished = calls.filter((c) => !c.live && c.source !== "replay" && c.outcome.length > 0 && c.seconds > 40).slice(0, 10);
    await Promise.all(finished.map((c) => store.replay(c.call_id, 1)));
    setTab("live");
  };

  return (
    <div className="flex h-full flex-col">
      <nav className="flex items-center gap-4 border-b border-line bg-card px-5 py-2.5">
        <Link href="/" className="text-sm font-semibold tracking-tight"><span className="text-clinic">Clínica Arenal</span> · front desk</Link>
        <span className={`text-xs ${state.connected ? "text-good" : "text-bad"}`}>{state.connected ? "● connected to the call logs" : "○ events service not reachable — is it running on 7870?"}</span>
        <span className="flex-1" />
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
    </div>
  );
}
