"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";
import { initials } from "@/lib/events";

/** The time now, refreshed on a beat — for clocks that tick while a call runs. */
export function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
}

const TINTS = ["bg-[#dbeafe] text-[#1e3a8a]", "bg-[#dcfce7] text-[#14532d]", "bg-[#fde68a] text-[#713f12]", "bg-[#fbcfe8] text-[#831843]",
  "bg-[#e9d5ff] text-[#581c87]", "bg-[#fed7aa] text-[#7c2d12]", "bg-[#cffafe] text-[#164e63]"];

// Which patients have a generated portrait (public/patients/index.json, written by the portrait script).
let portraits: Promise<Set<string>> | undefined;
const knownPortraits = () =>
  (portraits ??= fetch("/patients/index.json").then((r) => (r.ok ? r.json() : [])).then((ids: string[]) => new Set(ids)).catch(() => new Set<string>()));

/** The patient's generated portrait when there is one for them, their initials otherwise. */
export function Avatar({ patientId, name, size = 40, className }: { patientId?: string | null; name?: string | null; size?: number; className?: string }) {
  const [hasPortrait, setHasPortrait] = useState(false);
  const seed = [...(patientId || name || "?")].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  const style = { width: size, height: size, fontSize: Math.round(size * 0.38) };
  useEffect(() => {
    let stale = false;
    void knownPortraits().then((ids) => { if (!stale) setHasPortrait(Boolean(patientId && ids.has(patientId))); });
    return () => { stale = true; };
  }, [patientId]);
  if (patientId && hasPortrait)
    return (
      // eslint-disable-next-line @next/next/no-img-element -- a small local file, shown at several sizes
      <img src={`/patients/${patientId}.jpg`} alt={name ?? ""} style={style} onError={() => setHasPortrait(false)}
           className={clsx("shrink-0 rounded-full object-cover ring-1 ring-black/5", className)} />
    );
  return (
    <span style={style} className={clsx("inline-flex shrink-0 items-center justify-center rounded-full font-semibold", name ? TINTS[seed % TINTS.length] : "bg-wash text-faint", className)}>
      {initials(name)}
    </span>
  );
}

export function Chip({ children, tone = "plain", className, title }: { children: React.ReactNode; tone?: "plain" | "clinic" | "good" | "warn" | "bad" | "tool" | "live"; className?: string; title?: string }) {
  const tones = {
    plain: "bg-wash text-soft", clinic: "bg-clinic-soft text-clinic", good: "bg-good-soft text-good", warn: "bg-warn-soft text-warn",
    bad: "bg-bad-soft text-bad", tool: "bg-tool-soft text-tool", live: "bg-live text-white",
  };
  return <span title={title} className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap", tones[tone], className)}>{children}</span>;
}

export function LiveDot({ className }: { className?: string }) {
  return <span className={clsx("inline-block size-2 rounded-full bg-live animate-pulse-dot", className)} />;
}

const MOODS: [number, string, string][] = [[1.2, "😊", "pleased"], [0.4, "🙂", "content"], [-0.4, "😐", "neutral"], [-1.2, "😕", "uneasy"], [-9, "😠", "upset"]];

/** A caller's mood, −2 … +2, as a face. */
export function Mood({ value, className }: { value?: number | null; className?: string }) {
  if (value == null || Number.isNaN(value)) return null;
  const [, face, word] = MOODS.find(([floor]) => value >= floor)!;
  return <span title={`caller's mood: ${word} (${value > 0 ? "+" : ""}${value.toFixed(1)})`} className={className}>{face}</span>;
}
