"use client";

import { Coins, Gauge, GraduationCap, Timer, TriangleAlert } from "lucide-react";
import type { Analysis } from "@/lib/desk-store";
import type { CallView, Summary } from "@/lib/events";
import { Chip, Mood } from "@/components/ui";

const median = (values: number[]) => (values.length ? [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)] : undefined);

/** What a finished call teaches: how it felt, where it rubbed, what it took in seconds and money, which agent took it. */
export function Insights({ summary, view, analysis }: { summary: Summary; view: CallView; analysis?: Analysis }) {
  const answer = summary.answer_secs ?? median(view.latencies);
  const lookup = median(view.lookupMs);
  const pipeline = view.pipeline ?? summary.pipeline;
  return (
    <section className="border-b border-line bg-card/70 px-5 py-3 text-[13px]">
      <div className="mx-auto flex max-w-[760px] flex-col gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {summary.outcome.length
            ? summary.outcome.map((o, i) => <Chip key={i} tone={o.startsWith("NO_ACTION") ? "plain" : o.startsWith("ESCALATE") ? "bad" : o.startsWith("CANCEL") ? "warn" : "good"}>{o}</Chip>)
            : <Chip tone="plain">no decision recorded</Chip>}
          {summary.ended && (summary.dry_run ? <Chip tone="warn">captured, not sent</Chip> : summary.delivered ? <Chip tone="good">delivered to the clinic</Chip> : <Chip tone="bad">not delivered</Chip>)}
          {summary.flags.map((f) => <Chip key={f} tone="tool"><TriangleAlert className="size-3" />{f}</Chip>)}
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-soft">
          <span className="flex items-center gap-1.5"><Timer className="size-3.5" />{Math.round(summary.seconds)} s{summary.decided_at != null ? ` · decided at ${Math.round(summary.decided_at)} s` : ""}</span>
          {answer != null && <span className="flex items-center gap-1.5"><Gauge className="size-3.5" />answers in {answer.toFixed(1)} s</span>}
          {lookup != null && <span>lookups {lookup} ms</span>}
          {summary.cost_usd != null && <span className="flex items-center gap-1.5" title="An estimate at list prices: model tokens, characters spoken, minutes listened to"><Coins className="size-3.5" />≈ ${summary.cost_usd.toFixed(3)}</span>}
          {pipeline?.id
            ? <span title={`prompt ${pipeline.prompt} · build ${pipeline.build}`}>pipeline <b className="text-ink">{pipeline.id}</b> · {[pipeline.stt, pipeline.llm, pipeline.tts].filter(Boolean).join(" · ")}</span>
            : <span>an earlier build — no pipeline recorded</span>}
        </div>

        {analysis?.pending && <p className="text-xs text-faint">reading the call…</p>}
        {analysis?.error && <p className="text-xs text-bad">The call could not be read: {analysis.error}.</p>}
        {analysis && !analysis.pending && !analysis.error && (
          <div className="flex gap-3 rounded-xl bg-wash px-3.5 py-2.5">
            <Mood value={analysis.mood} className="text-2xl leading-none" />
            <div className="min-w-0 flex-1 space-y-1">
              <p className="text-ink"><b>{analysis.label}</b> · effort {analysis.effort} — {analysis.summary}</p>
              {analysis.friction && analysis.friction.length > 0 && <p className="text-xs text-soft">Friction: {analysis.friction.join(" · ")}</p>}
              {analysis.lesson && analysis.lesson.toLowerCase() !== "nothing" && <p className="flex items-start gap-1.5 text-xs text-clinic"><GraduationCap className="mt-px size-3.5 shrink-0" />{analysis.lesson}</p>}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
