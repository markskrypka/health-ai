"use client";

import clsx from "clsx";
import { Globe, Phone, RotateCcw } from "lucide-react";
import { clock, type Summary } from "@/lib/events";
import { Avatar, Chip, LiveDot, Mood, useNow } from "@/components/ui";

const SOURCE_ICON = { phone: Phone, web: Globe, replay: RotateCcw } as const;

function outcomeWord(s: Summary): { text: string; tone: "good" | "warn" | "bad" | "plain" } {
  const first = s.outcome[0]?.split(" ")[0];
  if (!first) return { text: s.ended ? "no decision" : s.stage, tone: s.ended ? "bad" : "plain" };
  const more = s.outcome.length > 1 ? ` +${s.outcome.length - 1}` : "";
  if (first === "BOOK") return { text: `Booked${more}`, tone: "good" };
  if (first === "RESCHEDULE") return { text: `Moved${more}`, tone: "good" };
  if (first === "REGISTER") return { text: `Registered${more}`, tone: "good" };
  if (first === "CANCEL") return { text: `Cancelled${more}`, tone: "warn" };
  if (first === "ESCALATE") return { text: "Escalated", tone: "bad" };
  return { text: s.outcome[0].replace("NO_ACTION ", "").replaceAll("_", " "), tone: "plain" };
}

export function CallList({ calls, tab, onTab, selected, onSelect, moods }: {
  calls: Summary[]; tab: "live" | "past"; onTab: (t: "live" | "past") => void; selected?: string; onSelect: (id: string) => void;
  moods: Record<string, number | undefined>;
}) {
  const now = useNow(1000);
  const live = calls.filter((c) => c.live).sort((a, b) => b.started_at - a.started_at);
  // A replay that has finished is not a call that happened: it leaves the list.
  const past = calls.filter((c) => !c.live && c.source !== "replay").sort((a, b) => b.started_at - a.started_at);
  const shown = tab === "live" ? live : past;

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-r border-line bg-card">
      <div className="flex gap-1 border-b border-line p-2">
        {(["live", "past"] as const).map((t) => (
          <button key={t} onClick={() => onTab(t)}
                  className={clsx("flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
                                  tab === t ? "bg-ink text-white" : "text-soft hover:bg-wash")}>
            {t === "live" ? <>{live.length > 0 && <LiveDot />} Live <span className="tabular-nums opacity-70">{live.length}</span></>
                          : <>Past <span className="tabular-nums opacity-70">{past.length}</span></>}
          </button>
        ))}
      </div>

      <div className="pane flex-1 overflow-y-auto">
        {shown.length === 0 && (
          <p className="px-6 py-16 text-center text-sm text-faint">
            {tab === "live" ? "No call on the line. The next one appears here the moment it connects." : "No finished calls yet."}
          </p>
        )}
        {shown.map((c) => {
          const Icon = SOURCE_ICON[c.source] ?? Phone;
          const seconds = c.live ? now / 1000 - c.started_at : c.seconds;
          const outcome = outcomeWord(c);
          return (
            <button key={c.call_id} onClick={() => onSelect(c.call_id)}
                    className={clsx("flex w-full animate-arrive items-start gap-3 border-b border-line px-3 py-3 text-left transition",
                                    selected === c.call_id ? "bg-clinic-soft/60" : "hover:bg-wash/60")}>
              <Avatar patientId={c.patient_id} name={c.patient_name} size={40} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold">{c.patient_name || "Unknown caller"}</span>
                  <Mood value={moods[c.call_id]} className="text-sm" />
                </span>
                <span className={clsx("mt-0.5 block truncate text-xs", c.live ? "text-clinic" : outcome.tone === "good" ? "text-good" : outcome.tone === "warn" ? "text-warn" : outcome.tone === "bad" ? "text-bad" : "text-soft")}>
                  {c.live ? `${c.stage}…` : outcome.text}
                </span>
                {!c.live && c.first_words && <span className="mt-0.5 block truncate text-xs text-faint">“{c.first_words}”</span>}
                <span className="mt-1.5 flex flex-wrap items-center gap-1">
                  <Chip><Icon className="size-3" />{c.source}</Chip>
                  <Chip>{c.language.toUpperCase()}</Chip>
                  {c.pipeline?.id && <Chip tone="tool">pipeline {c.pipeline.id}</Chip>}
                  {c.dry_run && <Chip tone="warn">dry run</Chip>}
                  {!c.live && c.ended && !c.delivered && <Chip tone="bad">not delivered</Chip>}
                  {c.flags.length > 0 && <Chip title={c.flags.join(" · ")}>{c.flags.length} note{c.flags.length > 1 ? "s" : ""}</Chip>}
                </span>
              </span>
              <span className="flex shrink-0 flex-col items-end gap-1 pt-0.5">
                <span className="font-mono text-xs tabular-nums text-soft">{clock(seconds)}</span>
                {c.live && <LiveDot />}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
