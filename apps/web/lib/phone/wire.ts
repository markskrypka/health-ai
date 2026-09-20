/**
 * The wire the call server speaks: Twilio Media Streams — JSON text frames carrying 8 kHz mono µ-law,
 * 20 ms (160 bytes) per `media` frame, base64. The shapes are those of apps/agent/scripts/local_call.py,
 * the reference client that already works against the server. Pure: no sockets, no browser audio.
 */

export const WIRE_SAMPLE_RATE = 8000;
export const FRAME_SAMPLES = 160;
export const FRAME_MS = 20;

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** "MZ" and 32 hex digits, the way Twilio names a stream. */
export function newStreamSid(): string {
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") crypto.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  let hex = "";
  for (const b of bytes) hex += b.toString(16).padStart(2, "0");
  return `MZ${hex}`;
}

export interface CallIdentity {
  /** Sent as start.callSid and as customParameters.call_id: the server names the call by it. */
  callId: string;
  /** customParameters.from_number; the key is left out when this is empty. */
  fromNumber?: string;
  /** Further customParameters. call_id and from_number above win over the same keys here. */
  params?: Record<string, string>;
  streamSid?: string;
}

/** Builds one call's outbound messages, in order, and keeps the counters Twilio keeps. */
export class OutboundStream {
  readonly streamSid: string;
  private readonly callId: string;
  private readonly customParameters: Record<string, string>;
  private sequence = 2; // `start` is 1; the first media frame is 2
  private chunk = 1;
  private timestampMs = 0;

  constructor(identity: CallIdentity) {
    this.callId = identity.callId;
    this.streamSid = identity.streamSid ?? newStreamSid();
    this.customParameters = { ...identity.params, call_id: identity.callId };
    if (identity.fromNumber) this.customParameters.from_number = identity.fromNumber;
  }

  connected(): string {
    return JSON.stringify({ event: "connected", protocol: "Call", version: "1.0.0" });
  }

  start(): string {
    return JSON.stringify({
      event: "start",
      sequenceNumber: "1",
      streamSid: this.streamSid,
      start: {
        accountSid: "AC-local",
        streamSid: this.streamSid,
        callSid: this.callId,
        tracks: ["inbound"],
        mediaFormat: { encoding: "audio/x-mulaw", sampleRate: WIRE_SAMPLE_RATE, channels: 1 },
        customParameters: this.customParameters,
      },
    });
  }

  /** One 20 ms frame; `payload` is the base64 of 160 µ-law bytes. */
  media(payload: string): string {
    const message = JSON.stringify({
      event: "media",
      sequenceNumber: String(this.sequence),
      streamSid: this.streamSid,
      media: { track: "inbound", chunk: String(this.chunk), timestamp: String(this.timestampMs), payload },
    });
    this.sequence += 1;
    this.chunk += 1;
    this.timestampMs += FRAME_MS;
    return message;
  }

  stop(): string {
    return JSON.stringify({
      event: "stop",
      sequenceNumber: String(this.sequence),
      streamSid: this.streamSid,
      stop: { accountSid: "AC-local", callSid: this.callId },
    });
  }
}

export type InboundEvent =
  | { kind: "media"; payload: Uint8Array } // the agent's voice, µ-law 8 kHz
  | { kind: "clear" } // the caller interrupted: drop the agent audio still queued
  | { kind: "ignored" }; // `mark` and anything else

export function parseInbound(data: unknown): InboundEvent {
  if (typeof data !== "string") return { kind: "ignored" };
  let message: unknown;
  try {
    message = JSON.parse(data);
  } catch {
    return { kind: "ignored" };
  }
  if (typeof message !== "object" || message === null) return { kind: "ignored" };
  const { event, media } = message as { event?: unknown; media?: { payload?: unknown } | null };
  if (event === "clear") return { kind: "clear" };
  if (event === "media" && media && typeof media.payload === "string") {
    try {
      return { kind: "media", payload: base64ToBytes(media.payload) };
    } catch {
      return { kind: "ignored" }; // not base64
    }
  }
  return { kind: "ignored" };
}

/** Cuts a stream of 8 kHz chunks of any size into exact 160-sample frames; the remainder waits. */
export class FrameAssembler {
  private readonly pending = new Int16Array(FRAME_SAMPLES);
  private filled = 0;

  push(chunk: Int16Array, emit: (frame: Int16Array) => void): void {
    let offset = 0;
    while (offset < chunk.length) {
      const take = Math.min(FRAME_SAMPLES - this.filled, chunk.length - offset);
      this.pending.set(chunk.subarray(offset, offset + take), this.filled);
      this.filled += take;
      offset += take;
      if (this.filled === FRAME_SAMPLES) {
        emit(this.pending.slice()); // a copy: `pending` is reused for the next frame
        this.filled = 0;
      }
    }
  }
}
