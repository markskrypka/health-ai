"use client";

import { useEffect, useState } from "react";
import { CalendarDays, FileText, ShieldCheck, Stethoscope } from "lucide-react";
import { EVENTS_URL } from "@/lib/config";
import { age, slotWords, type CallView } from "@/lib/events";
import { Avatar, Chip } from "@/components/ui";
import type { Names } from "./ActionCard";

type Upcoming = { appointment_id: string; start_time: string; provider: string; site: string; type: string };

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 text-[13px]">
      <span className="shrink-0 text-faint">{label}</span>
      <span className="min-w-0 text-right font-medium">{children}</span>
    </div>
  );
}

function Section({ icon: Icon, title, children }: { icon: React.ComponentType<{ className?: string }>; title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line px-5 py-4">
      <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-faint"><Icon className="size-3.5" />{title}</h3>
      {children}
    </section>
  );
}

export function PatientPanel({ view, names }: { view?: CallView; names: Names }) {
  const patient = view?.patient;
  const patientId = patient?.patient_id;
  const [upcoming, setUpcoming] = useState<{ id: string; rows: Upcoming[] } | null>(null);

  useEffect(() => {
    if (!patientId) return;
    let stale = false;
    fetch(`${EVENTS_URL}/api/patients/${encodeURIComponent(patientId)}/appointments`)
      .then((r) => (r.ok ? r.json() : { appointments: [] }))
      .then((body: { appointments: Upcoming[] }) => { if (!stale) setUpcoming({ id: patientId, rows: body.appointments }); })
      .catch(() => { if (!stale) setUpcoming({ id: patientId, rows: [] }); });
    return () => { stale = true; };
  }, [patientId]);

  if (!view || !patient?.name) {
    const typed = view ? Object.entries(view.form).filter(([, f]) => f?.value) : [];
    return (
      <aside className="pane h-full w-[320px] shrink-0 overflow-y-auto border-l border-line bg-card">
        <div className="flex flex-col items-center px-6 pb-6 pt-12 text-center">
          <Avatar size={72} />
          <p className="mt-4 text-sm font-semibold">{view ? "Not identified yet" : "No call selected"}</p>
          <p className="mt-1 text-xs text-faint">{view ? "The card fills in the moment the agent recognises the caller." : "Pick a call on the left."}</p>
        </div>
        {typed.length > 0 && (
          <Section icon={FileText} title="Heard so far">
            {typed.map(([k, f]) => <Row key={k} label={k.replaceAll("_", " ")}>{k === "national_id" || k === "phone" ? `•••••${f!.value.slice(-4)}` : f!.value}</Row>)}
          </Section>
        )}
      </aside>
    );
  }

  const years = age(patient.date_of_birth);
  const rows = upcoming && upcoming.id === patientId ? upcoming.rows : null;
  const changes = view.decisions.filter((d) => !d.replaced);

  return (
    <aside className="pane h-full w-[320px] shrink-0 overflow-y-auto border-l border-line bg-card">
      <div className="flex animate-arrive flex-col items-center px-6 pb-5 pt-8 text-center">
        <Avatar patientId={patient.patient_id} name={patient.name} size={88} className="shadow-sm" />
        <h2 className="mt-3 text-base font-semibold leading-tight">{patient.name}</h2>
        <p className="mt-0.5 text-xs text-soft">
          {[years != null ? `${years} years` : "", patient.sex ? (patient.sex.toLowerCase().startsWith("f") ? "female" : patient.sex.toLowerCase().startsWith("m") ? "male" : patient.sex) : "", patient.patient_id].filter(Boolean).join(" · ")}
        </p>
        <div className="mt-2 flex flex-wrap justify-center gap-1">
          {patient.status === "identified" && <Chip tone="clinic"><ShieldCheck className="size-3" />identified{patient.matched_on?.length ? ` on ${patient.matched_on.map((m) => m.replaceAll("_", " ")).join(" + ")}` : ""}</Chip>}
          {patient.status === "one_field_only" && <Chip tone="warn">one detail only</Chip>}
          {patient.seen_before != null && <Chip>{patient.seen_before ? "seen before" : "first visit"}</Chip>}
        </div>
      </div>

      <Section icon={FileText} title="On file">
        {patient.date_of_birth && <Row label="Born">{patient.date_of_birth.split("-").reverse().join("/")}</Row>}
        {patient.national_id_masked && <Row label="DNI / NIE"><span className="font-mono">{patient.national_id_masked}</span></Row>}
        {patient.phone_masked && <Row label="Phone"><span className="font-mono">{patient.phone_masked}</span></Row>}
        <Row label="Plan">{patient.insurer ? names.plans[patient.insurer] ?? patient.insurer : "none on file"}</Row>
        <Row label="Referrals">{patient.referrals?.length ? patient.referrals.map((r) => names.specialties[r] ?? r).join(", ") : "none"}</Row>
        {patient.note && <p className="mt-2 rounded-lg bg-wash px-3 py-2 text-xs leading-relaxed text-soft">{patient.note}</p>}
      </Section>

      <Section icon={CalendarDays} title="Upcoming">
        {rows === null && <p className="text-xs text-faint">reading the diary…</p>}
        {rows?.length === 0 && <p className="text-xs text-faint">Nothing on the books.</p>}
        {rows?.map((a) => (
          <div key={a.appointment_id} className="py-1.5 text-[13px]">
            <div className="font-medium">{slotWords(a.start_time)}</div>
            <div className="text-xs text-soft">{a.provider} · {a.site.replace("Arenal ", "")} · {a.type}</div>
          </div>
        ))}
      </Section>

      <Section icon={Stethoscope} title="This call">
        {changes.length === 0 && <p className="text-xs text-faint">Nothing decided yet.</p>}
        {changes.map((d, i) => (
          <div key={i} className="py-1.5 text-[13px]">
            <div className="font-medium">
              {d.action === "book" ? "+ Booked" : d.action === "reschedule" ? "→ Moved" : d.action === "cancel" ? "− Cancelled" : d.action === "register" ? "+ Registered" : d.action === "escalate" ? "! Escalated" : "· No booking"}
              {d.payload.slot ? ` · ${slotWords(String(d.payload.slot))}` : ""}
            </div>
            <div className="text-xs text-soft">
              {[d.payload.provider_id && (names.providers[String(d.payload.provider_id)] ?? d.payload.provider_id), d.payload.location_id && (names.locations[String(d.payload.location_id)] ?? d.payload.location_id),
                d.payload.appointment_id, d.payload.reason].filter(Boolean).join(" · ")}
            </div>
          </div>
        ))}
      </Section>
    </aside>
  );
}
