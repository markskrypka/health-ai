import Link from "next/link";
import { Headset, PhoneCall } from "lucide-react";

export default function Home() {
  return (
    <main className="mx-auto flex h-full max-w-3xl flex-col justify-center gap-10 px-6">
      <header>
        <p className="text-sm font-medium tracking-wide text-clinic">CLÍNICA ARENAL</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">One agent answers the phone. Two screens show it working.</h1>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/call" className="group rounded-2xl border border-line bg-card p-6 transition hover:border-clinic-line hover:shadow-sm">
          <PhoneCall className="size-6 text-clinic" />
          <h2 className="mt-4 text-lg font-semibold">The caller&rsquo;s screen</h2>
          <p className="mt-1 text-sm text-soft">Call the clinic from the browser. The form fills itself while you talk, and the free slots appear on a calendar.</p>
        </Link>
        <Link href="/desk" className="group rounded-2xl border border-line bg-card p-6 transition hover:border-clinic-line hover:shadow-sm">
          <Headset className="size-6 text-clinic" />
          <h2 className="mt-4 text-lg font-semibold">The front desk</h2>
          <p className="mt-1 text-sm text-soft">Every call as it happens: the conversation, what the agent did and why, the patient, and what we learn afterwards.</p>
        </Link>
      </div>
    </main>
  );
}
