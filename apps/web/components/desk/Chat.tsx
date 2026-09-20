"use client";

import clsx from "clsx";
import { Globe, HelpCircle, Phone, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { clock, type CallView, type ChatItem, type Summary } from "@/lib/events";
import { Chip, LiveDot, Mood, useNow, useRevealed } from "@/components/ui";
import { ActionCard, type Names } from "./ActionCard";

const SOURCE = { phone: { icon: Phone, word: "phone line" }, web: { icon: Globe, word: "web call" }, replay: { icon: RotateCcw, word: "replay" } } as const;

export function ChatHeader({ summary, view, children }: { summary: Summary; view: CallView; children?: React.ReactNode }) {
  const now = useNow(1000);
  const seconds = summary.live ? now / 1000 - summary.started_at : summary.seconds;
  const source = SOURCE[summary.source] ?? SOURCE.phone;
  const pipeline = view.pipeline ?? summary.pipeline;
  return (
    <header className="border-b border-line bg-card px-5 py-3">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {summary.live && <LiveDot />}
            <h2 className="truncate text-[15px] font-semibold">{summary.patient_name || view.patient?.name || "Unknown caller"}</h2>
            <span className="font-mono text-xs text-faint">{summary.call_id.slice(0, 8)}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <Chip tone={summary.live ? "live" : "plain"}>{summary.live ? "on the line" : "ended"} · {clock(seconds)}</Chip>
            <Chip><source.icon className="size-3" />{source.word}</Chip>
            <Chip>{(view.language || summary.language).toUpperCase()}</Chip>
            {pipeline?.id
              ? <Chip tone="tool" title={[pipeline.stt, pipeline.llm, pipeline.tts, pipeline.build && `build ${pipeline.build}`].filter(Boolean).join(" · ")}>pipeline {pipeline.id}{pipeline.label ? ` · ${pipeline.label}` : ""}</Chip>
              : null}
            {summary.source === "replay" && <Chip tone="warn">a replay of {summary.replay_of?.slice(0, 8)} — not a live call</Chip>}
            {summary.dry_run && <Chip tone="warn">dry run</Chip>}
          </div>
        </div>
        {children}
      </div>
    </header>
  );
}

function Why({ item, items }: { item: Extract<ChatItem, { type: "turn" }>; items: ChatItem[] }) {
  const behind = item.because.map((id) => items.find((x) => x.id === id)).filter((x): x is Extract<ChatItem, { type: "action" }> => x?.type === "action");
  if (!behind.length) return <p className="mt-2 rounded-lg bg-wash px-3 py-2 text-xs text-soft">No lookup stands behind this sentence: it came from the conversation and the agent&rsquo;s instructions alone.</p>;
  return (
    <div className="mt-2 space-y-1.5 rounded-lg bg-wash px-3 py-2 text-xs text-soft">
      <p className="font-semibold text-ink">Why did it say that?</p>
      {behind.map((b) => {
        const a = b.action;
        const label = a.kind === "identify" ? `find_patient → ${a.status}` : a.kind === "search" ? `find_slots → ${a.status}${a.reason ? ` (${a.reason})` : ""}`
          : a.kind === "decision" ? `${a.action} → recorded` : a.kind === "refused" ? `${a.tool} → ${a.status}` : a.kind === "appointments" ? `list_appointments → ${a.items.length}`
          : a.kind === "check_id" ? `check_national_id → ${a.status}` : a.kind === "nearest" ? `nearest_site → ${a.status}` : a.kind;
        const why = "why" in a ? a.why : undefined;
        const notes = a.kind === "search" ? a.notes : [];
        return (
          <div key={b.id}>
            <code className="font-mono text-[11px] text-tool">{label}</code>
            {why && <p className="mt-0.5">The tool told the model: “{why}”</p>}
            {notes.map((n, i) => <p key={i} className="mt-0.5">Note from the code: “{n}”</p>)}
          </div>
        );
      })}
    </div>
  );
}

export function Chat({ view, names, moods, live }: { view: CallView; names: Names; moods: Record<number, number>; live: boolean }) {
  const [asked, setAsked] = useState<string>();
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const speaking = useRevealed(view.speaking);
  const because = asked ? (view.items.find((i) => i.id === asked) as Extract<ChatItem, { type: "turn" }> | undefined)?.because ?? [] : [];

  // Stay with the newest line unless the reader scrolled up to read something.
  useEffect(() => {
    const el = scroller.current;
    if (el && pinned.current) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [view.items.length, view.hearing, speaking]);

  return (
    <div ref={scroller} className="pane flex-1 overflow-y-auto px-5 py-5"
         onScroll={(e) => { const el = e.currentTarget; pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120; }}>
      <div className="mx-auto flex max-w-[760px] flex-col gap-3">
        {view.items.map((item) => item.type === "action"
          ? <ActionCard key={item.id} action={item.action} names={names} highlighted={because.includes(item.id)} />
          : (
            <div key={item.id} className={clsx("flex animate-arrive flex-col", item.who === "agent" ? "items-end" : "items-start")}>
              <div className={clsx("flex max-w-[78%] items-end gap-2", item.who === "agent" && "flex-row-reverse")}>
                <button type="button" disabled={item.who !== "agent"} onClick={() => setAsked(asked === item.id ? undefined : item.id)}
                        className={clsx("group rounded-2xl px-3.5 py-2 text-left text-[14px] leading-snug",
                                        item.who === "agent" ? "rounded-br-md bg-clinic text-white hover:bg-clinic/90" : "rounded-bl-md border border-line bg-card",
                                        item.spokenOnly && "bg-clinic/75", item.cutOff && "line-through decoration-white/50")}>
                  {item.text}
                  {item.who === "agent" && <HelpCircle className={clsx("ml-1.5 inline size-3.5 -translate-y-px opacity-0 transition group-hover:opacity-70", asked === item.id && "opacity-90")} />}
                </button>
                {item.who === "caller" && <Mood value={moods[item.seq]} className="pb-1 text-base" />}
              </div>
              <span className="mt-1 px-1 font-mono text-[10px] tabular-nums text-faint">
                {item.who} · {clock(item.t)}{item.latency != null ? ` · answered in ${item.latency.toFixed(1)} s` : ""}
                {item.spokenOnly ? " · said by code, not by the model" : ""}{item.cutOff ? " · the caller talked over this and did not hear it" : ""}
              </span>
              {asked === item.id && <div className="w-full max-w-[78%]"><Why item={item} items={view.items} /></div>}
            </div>
          ))}

        {view.hearing && (
          <div className="flex flex-col items-start">
            <div className="max-w-[78%] rounded-2xl rounded-bl-md border border-dashed border-line bg-card/70 px-3.5 py-2 text-[14px] leading-snug text-soft">{view.hearing}<span className="ml-0.5 animate-pulse">▍</span></div>
          </div>
        )}
        {view.speaking && (
          <div className="flex flex-col items-end">
            <div className="max-w-[78%] rounded-2xl rounded-br-md bg-clinic/70 px-3.5 py-2 text-[14px] leading-snug text-white">{speaking}<span className="ml-0.5 animate-pulse">▍</span></div>
          </div>
        )}
        {live && !view.ended && !view.hearing && !view.speaking && <div className="py-1 text-center text-xs text-faint">listening…</div>}
      </div>
    </div>
  );
}
