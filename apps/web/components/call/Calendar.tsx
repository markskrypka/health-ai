"use client";

import clsx from "clsx";
import { CalendarCheck, CalendarDays, Check } from "lucide-react";
import { slotWords, type CallView, type Offer, type Slot } from "@/lib/events";
import type { Names } from "@/components/desk/ActionCard";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MAX_DAYS = 6;
const MAX_TIMES = 14;

const dayOf = (iso: string) => iso.slice(0, 10);
const timeOf = (iso: string) => iso.slice(11, 16);

function dayWords(day: string): { weekday: string; date: string } {
  const d = new Date(`${day}T00:00:00Z`);
  return { weekday: DAYS[d.getUTCDay()], date: `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}` };
}

/** "Monday 21 September at 09:00" → "09:00": the offers are in words, the calendar matches them by doctor and time. */
function offered(offers: Offer[], slot: Slot): number {
  return offers.findIndex((o) => o.doctor === slot.provider && o.when.endsWith(timeOf(slot.start)) && o.when.includes(` ${Number(dayOf(slot.start).slice(8))} `));
}

export function Calendar({ view, names }: { view: CallView; names: Names }) {
  const byDay = new Map<string, Map<string, Slot[]>>();
  for (const slot of view.slots) {
    const times = byDay.get(dayOf(slot.start)) ?? new Map<string, Slot[]>();
    times.set(timeOf(slot.start), [...(times.get(timeOf(slot.start)) ?? []), slot]);
    byDay.set(dayOf(slot.start), times);
  }
  const days = [...byDay.keys()].sort().slice(0, MAX_DAYS);
  const booked = view.booked;

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-line bg-card">
      <header className="flex items-center gap-2 border-b border-line px-5 py-3.5">
        <CalendarDays className="size-4 text-clinic" />
        <h2 className="text-sm font-semibold">Free appointments</h2>
        {view.searchLabel && <span className="truncate text-xs text-soft">· {view.searchLabel}</span>}
        <span className="flex-1" />
        {view.slots.length > 0 && <span className="text-xs text-faint">{view.slots.length} free</span>}
      </header>

      {days.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-8 py-16 text-center">
          <CalendarDays className="size-8 text-line" />
          <p className="text-sm font-medium text-soft">Tell us what you need.</p>
          <p className="max-w-xs text-xs text-faint">As soon as the receptionist looks in the diary, every free time appears here — say the day and time that suits you.</p>
        </div>
      ) : (
        <div className="pane grid min-h-0 flex-1 auto-cols-fr grid-flow-col gap-px overflow-y-auto bg-line">
          {days.map((day) => {
            const words = dayWords(day);
            const times = [...byDay.get(day)!.entries()].sort(([a], [b]) => a.localeCompare(b));
            return (
              <div key={day} className="flex min-w-0 animate-arrive flex-col bg-card">
                <div className="sticky top-0 border-b border-line bg-card px-2 py-2 text-center">
                  <div className="text-[11px] font-medium uppercase tracking-wider text-faint">{words.weekday}</div>
                  <div className="text-sm font-semibold">{words.date}</div>
                </div>
                <div className="flex flex-col gap-1 p-1.5">
                  {times.slice(0, MAX_TIMES).map(([time, slots]) => {
                    const said = slots.some((s) => offered(view.offers, s) === 0);
                    const alsoOffered = slots.some((s) => offered(view.offers, s) > 0);
                    const mine = booked && slots.some((s) => s.start === booked.slot && (!booked.provider_id || s.provider_id === booked.provider_id));
                    return (
                      <div key={time} title={slots.map((s) => `${s.provider} · ${s.site}`).join("\n")}
                           className={clsx("rounded-lg border px-2 py-1.5 text-center transition",
                                           mine ? "border-good bg-good text-white shadow-sm" : said ? "border-clinic bg-clinic-soft text-clinic" : alsoOffered ? "border-clinic-line bg-card text-clinic" : "border-line bg-card text-ink")}>
                        <div className="flex items-center justify-center gap-1 text-[13px] font-semibold tabular-nums">{mine && <Check className="size-3.5" />}{time}</div>
                        <div className={clsx("truncate text-[10px]", mine ? "text-white/85" : "text-faint")}>
                          {mine ? "yours" : said ? "offered to you" : slots.length > 1 ? `${slots.length} doctors` : slots[0].provider.replace(/^(Dra?\.|D\.)\s+/, "").split(" ").slice(0, 2).join(" ")}
                        </div>
                      </div>
                    );
                  })}
                  {times.length > MAX_TIMES && <div className="py-1 text-center text-[11px] text-faint">+{times.length - MAX_TIMES} later</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {booked && (
        <footer className="flex animate-arrive items-center gap-3 border-t border-good/30 bg-good-soft px-5 py-3.5">
          <span className="inline-flex size-8 items-center justify-center rounded-full bg-good text-white"><CalendarCheck className="size-4" /></span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-good">{booked.action === "reschedule" ? "Your appointment was moved" : "Your appointment"}</div>
            <div className="truncate text-[13px] text-ink">
              {slotWords(booked.slot)}{booked.provider_id ? ` · ${names.providers[booked.provider_id] ?? booked.provider_id}` : ""}{booked.location_id ? ` · ${names.locations[booked.location_id] ?? booked.location_id}` : ""}
            </div>
          </div>
        </footer>
      )}
    </section>
  );
}
