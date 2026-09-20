"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { EVENTS_URL } from "@/lib/config";
import { Mood } from "@/components/ui";

type Row = {
  id: string; label: string; parts: string; calls: number; median_secs: number | null; median_decided_at: number | null; median_answer_secs: number | null;
  median_cost_usd: number | null; mood: number | null; read: number; decided: number; with_notes: number; not_delivered: number;
};

const show = (v: number | null, unit = "", digits = 0) => (v == null ? "—" : `${v.toFixed(digits)}${unit}`);

/** Finished calls side by side, by the pipeline that took them. */
export function Pipelines({ onClose }: { onClose: () => void }) {
  const [rows, setRows] = useState<Row[]>();
  const [reading, setReading] = useState(false);
  const count = () => fetch(`${EVENTS_URL}/api/pipelines`).then((r) => r.json()).then((body: { pipelines: Row[] }) => setRows(body.pipelines)).catch(() => setRows([]));
  useEffect(() => { void count(); }, []);
  const readMore = async () => {
    setReading(true);
    await fetch(`${EVENTS_URL}/api/analysis?limit=30`, { method: "POST" }).catch(() => {});
    await count();
    setReading(false);
  };

  return (
    <div className="fixed inset-0 z-20 flex items-start justify-center bg-ink/30 p-10 backdrop-blur-[2px]" onClick={onClose}>
      <div className="w-full max-w-5xl animate-arrive rounded-2xl border border-line bg-card shadow-xl" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center gap-3 border-b border-line px-6 py-4">
          <div className="flex-1">
            <h2 className="text-base font-semibold">Pipelines, side by side</h2>
            <p className="text-xs text-soft">Every call says in its first log line which agent took it. Same desk, same measures — so a change to the agent is compared, not guessed.</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-soft hover:bg-wash"><X className="size-4" /></button>
        </header>
        <div className="overflow-x-auto px-6 py-4">
          {!rows ? <p className="py-8 text-center text-sm text-faint">counting…</p> : (
            <table className="w-full text-left text-[13px]">
              <thead className="text-[11px] uppercase tracking-wider text-faint">
                <tr>{["Pipeline", "Calls", "Call length", "Decided at", "Answers in", "Caller's mood", "With notes", "Not delivered", "Cost per call"].map((h) => <th key={h} className="px-2 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-line align-top">
                    <td className="px-2 py-3"><div className="font-semibold">{r.id === "earlier" ? "—" : r.id} · {r.label}</div><div className="max-w-[300px] text-xs text-faint">{r.parts}</div></td>
                    <td className="px-2 py-3 tabular-nums">{r.calls}</td>
                    <td className="px-2 py-3 tabular-nums">{show(r.median_secs, " s")}</td>
                    <td className="px-2 py-3 tabular-nums">{show(r.median_decided_at, " s")}</td>
                    <td className="px-2 py-3 tabular-nums">{show(r.median_answer_secs, " s", 1)}</td>
                    <td className="px-2 py-3"><span className="flex items-center gap-1.5 tabular-nums"><Mood value={r.mood} />{r.mood == null ? "—" : `${r.mood > 0 ? "+" : ""}${r.mood.toFixed(1)}`}<span className="text-xs text-faint">({r.read} read)</span></span></td>
                    <td className="px-2 py-3 tabular-nums">{r.with_notes}</td>
                    <td className="px-2 py-3 tabular-nums">{r.not_delivered}</td>
                    <td className="px-2 py-3 tabular-nums">{r.median_cost_usd == null ? "—" : `≈ $${r.median_cost_usd.toFixed(3)}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button onClick={readMore} disabled={reading} className="mt-3 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-soft transition hover:bg-wash disabled:opacity-50">
            {reading ? "reading…" : "Read the moods of 30 more calls"}
          </button>
          <p className="mt-3 text-xs text-faint">Medians over finished calls. Mood is read by a model from the call&rsquo;s log after it ends, −2 to +2. Cost is an estimate at list prices from what each call logged: model tokens, characters spoken, minutes listened to.</p>
        </div>
      </div>
    </div>
  );
}
