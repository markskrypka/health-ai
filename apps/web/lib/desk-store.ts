// The front desk's connection to the events service: one stream for every call, loaded calls kept whole.
//
// The stream gives each event its position in its call's log (`seq`). A call the desk saw from its first line
// simply grows; a call joined half-way is loaded once (`/api/calls/{id}` counts to the same positions) and then
// grows from the stream — no gap, nothing twice.

import { EVENTS_URL } from "./config";
import type { CallEvent, Summary } from "./events";

export type Analysis = {
  mood?: number; // −2 … +2 across the call
  label?: string;
  by_turn?: Record<string, number>; // seq of a caller turn -> mood
  friction?: string[];
  effort?: string;
  summary?: string;
  lesson?: string;
  pending?: boolean;
  error?: string;
};

export type DeskState = {
  connected: boolean;
  calls: Record<string, Summary>;
  events: Record<string, CallEvent[]>;
  moods: Record<string, Record<number, number>>;
  analysis: Record<string, Analysis>;
};

type Message =
  | { type: "hello"; calls: Summary[] }
  | { type: "call"; summary: Summary }
  | { type: "event"; call_id: string; seq: number; event: CallEvent }
  | { type: "mood"; call_id: string; seq: number; mood: number }
  | { type: "analysis"; call_id: string; analysis: Analysis };

export class DeskStore {
  private state: DeskState = { connected: false, calls: {}, events: {}, moods: {}, analysis: {} };
  private listeners = new Set<() => void>();
  private source?: EventSource;
  private loading = new Set<string>();

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  snapshot = () => this.state;

  private set(change: Partial<DeskState>) {
    this.state = { ...this.state, ...change };
    this.listeners.forEach((l) => l());
  }

  start() {
    if (this.source) return;
    const source = new EventSource(`${EVENTS_URL}/api/stream`);
    this.source = source;
    source.onopen = () => this.set({ connected: true });
    source.onerror = () => this.set({ connected: false }); // the browser reconnects by itself
    source.onmessage = (raw) => this.take(JSON.parse(raw.data) as Message);
  }

  stop() {
    this.source?.close();
    this.source = undefined;
  }

  private take(message: Message) {
    if (message.type === "hello") {
      const calls: Record<string, Summary> = {};
      for (const s of message.calls) calls[s.call_id] = s;
      this.set({ calls, connected: true });
      // After a reconnect, anything loaded may have missed lines.
      for (const id of Object.keys(this.state.events)) if (calls[id] && !calls[id].ended) void this.load(id, true);
    } else if (message.type === "call") {
      this.set({ calls: { ...this.state.calls, [message.summary.call_id]: message.summary } });
    } else if (message.type === "event") {
      const have = this.state.events[message.call_id];
      if (!have) {
        if (message.seq === 0) this.set({ events: { ...this.state.events, [message.call_id]: [message.event] } });
        else void this.load(message.call_id);
      } else if (message.seq === have.length) {
        this.set({ events: { ...this.state.events, [message.call_id]: [...have, message.event] } });
      } else if (message.seq > have.length) {
        void this.load(message.call_id, true);
      }
    } else if (message.type === "mood") {
      const moods = { ...this.state.moods, [message.call_id]: { ...this.state.moods[message.call_id], [message.seq]: message.mood } };
      this.set({ moods });
    } else if (message.type === "analysis") {
      this.set({ analysis: { ...this.state.analysis, [message.call_id]: message.analysis } });
    }
  }

  async load(callId: string, again = false) {
    if (this.loading.has(callId) || (!again && this.state.events[callId])) return;
    this.loading.add(callId);
    try {
      const res = await fetch(`${EVENTS_URL}/api/calls/${encodeURIComponent(callId)}`);
      if (!res.ok) return;
      const body = (await res.json()) as { summary: Summary; events: CallEvent[]; moods?: Record<number, number>; analysis?: Analysis | null };
      const have = this.state.events[callId];
      if (!have || body.events.length >= have.length)
        this.set({
          events: { ...this.state.events, [callId]: body.events }, calls: { ...this.state.calls, [callId]: body.summary },
          moods: { ...this.state.moods, [callId]: { ...body.moods, ...this.state.moods[callId] } },
          analysis: body.analysis ? { ...this.state.analysis, [callId]: body.analysis } : this.state.analysis,
        });
    } finally {
      this.loading.delete(callId);
    }
  }

  async replay(callId: string, speed = 1): Promise<string | undefined> {
    const res = await fetch(`${EVENTS_URL}/api/replay`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ call_id: callId, speed }),
    });
    return res.ok ? ((await res.json()) as { call_id: string }).call_id : undefined;
  }

  async analyse(callId: string) {
    const known = this.state.analysis[callId];
    if (known && !known.error) return;
    this.set({ analysis: { ...this.state.analysis, [callId]: { pending: true } } });
    try {
      const res = await fetch(`${EVENTS_URL}/api/calls/${encodeURIComponent(callId)}/analysis`);
      const analysis = res.ok ? ((await res.json()) as Analysis) : { error: `the events service answered ${res.status}` };
      this.set({ analysis: { ...this.state.analysis, [callId]: analysis } });
    } catch {
      this.set({ analysis: { ...this.state.analysis, [callId]: { error: "the events service did not answer" } } });
    }
  }
}
