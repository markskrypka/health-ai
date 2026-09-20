/**
 * A phone in the browser: it calls the voice agent over the same wire the telephony harness uses
 * (Twilio Media Streams over a WebSocket — see wire.ts), with the microphone as the caller's voice.
 *
 * Framework-free, and nothing here touches `window` or audio at import time, so a Next.js client
 * component can import it and the server render stays clean. Everything starts inside `start()`.
 *
 *   microphone (or test clip) → capture worklet: native rate → 8 kHz, 20 ms chunks
 *                             → here: µ-law, base64, one `media` frame per chunk → socket
 *   socket → here: base64, µ-law → playback worklet: ring buffer, 8 kHz → native rate → speakers
 *
 * start() goes: audio context (inside the click) → microphone and worklets → wait until audio really
 * flows → only then the socket. So a refused microphone or a dead sound card never reaches the server.
 *
 * One Phone is one call. For the next call, make a new Phone with a new callId.
 */

import { MULAW_SILENCE, decodeMulaw, encodeMulaw } from "./mulaw";
import { FRAME_SAMPLES, FrameAssembler, OutboundStream, WIRE_SAMPLE_RATE, bytesToBase64, parseInbound } from "./wire";

export type PhoneState = "idle" | "connecting" | "live" | "ended" | "error";

export interface PhoneOptions {
  /** The call server's socket, e.g. ws://127.0.0.1:7861/ws. An https page needs wss:// (localhost excepted). */
  url: string;
  /** Sent as callSid and as customParameters.call_id. */
  callId: string;
  /** customParameters.from_number; the key is left out when this is empty. */
  fromNumber?: string;
  /** Further customParameters, all strings (e.g. screen: "1", prefill: "{...json...}", pipeline: "A"). */
  params?: Record<string, string>;
  /** Every state change. `detail` is a sentence for a person: always set on "error", sometimes on "ended". */
  onState?: (state: PhoneState, detail?: string) => void;
  /**
   * Meter levels, about 15 times a second while live. 0..1 on a decibel scale: 0 is -50 dBFS or quieter,
   * 1 is full scale, speech sits around 0.5–0.8. `mic` is what is being sent (0 while muted); `agent`
   * is what is coming out of the speakers right now — not what has merely arrived, since the server
   * sends ahead of real time.
   */
  onLevel?: (mic: number, agent: number) => void;
  /**
   * TEST MODE: no microphone. This audio file (wav/mp3) is fetched, decoded and streamed as the caller's
   * voice in real time; after it, silence frames keep the line open.
   */
  testClipUrl?: string;
  /** TEST MODE: how long after the call goes live the clip starts. Default 0 (it talks over the greeting). */
  testClipDelayMs?: number;
  /** Where the two worklet files are served from. Default "/phone" (apps/web/public/phone). */
  workletBaseUrl?: string;
  /** Agent audio held before playback starts, or starts again after running dry. Default 80 ms. */
  jitterMs?: number;
}

/** An error whose message is already a sentence for a person. */
class PhoneError extends Error {}

/** Thrown inside start() when hangUp() overtook it. Not a failure: nothing is reported. */
class Cancelled extends Error {}

const CLEAN_CLOSE_CODES = [1000, 1001, 1005];
/** How long the audio may take to start. A cold sound card takes a second or two; Bluetooth, longer. */
const AUDIO_START_LIMIT_MS = 8000;
const LEVEL_FLOOR_DB = -50;

/** RMS of a full-scale-1 signal to a 0..1 meter value on a decibel scale. */
export function levelFromRms(rms: number): number {
  if (!(rms > 0)) return 0;
  const level = 1 - (20 * Math.log10(rms)) / LEVEL_FLOOR_DB;
  return level < 0 ? 0 : level > 1 ? 1 : level;
}

/** Meters rise fast and fall slowly. */
function follow(current: number, target: number, rise: number, fall: number): number {
  return current + (target - current) * (target > current ? rise : fall);
}

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function describeMicrophoneError(err: unknown): string {
  const name = typeof err === "object" && err !== null && "name" in err ? String((err as { name: unknown }).name) : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Microphone access was denied. Allow the microphone for this site, then call again.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No microphone was found.";
    case "NotReadableError":
    case "AbortError":
      return "The microphone could not be opened. Another application may be using it.";
    default:
      return `The microphone could not be opened: ${messageOf(err)}`;
  }
}

export class Phone {
  private readonly options: PhoneOptions;
  private currentState: PhoneState = "idle";
  private started: Promise<void> | null = null;
  private finished = false; // teardown has run: every later callback is a no-op
  private muted = false;

  private context: AudioContext | null = null;
  private microphone: MediaStream | null = null;
  private clipSource: AudioBufferSourceNode | null = null;
  private captureNode: AudioWorkletNode | null = null;
  private playbackNode: AudioWorkletNode | null = null;
  private nodes: AudioNode[] = []; // held so nothing is collected mid-call, and all are disconnected after

  private socket: WebSocket | null = null;
  private cancelWait: (() => void) | null = null; // start() waits on one thing at a time; hangUp() ends the wait
  private onFirstChunk: (() => void) | null = null;
  private outbound: OutboundStream | null = null;
  private readonly assembler = new FrameAssembler();
  private silencePayload = "";

  private micLevel = 0;
  private agentLevel = 0;
  private agentBufferedMs = 0;
  private draining: { state: "ended" | "error"; detail?: string } | null = null;
  private drainTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(options: PhoneOptions) {
    this.options = options;
  }

  get state(): PhoneState {
    return this.currentState;
  }

  /**
   * Call from a user gesture (a click): browsers only let audio start there.
   * Resolves once the call is live — or has failed, or was hung up first. It does not reject: a failure
   * arrives as state "error" with a sentence in `detail`. Calling it again returns the same promise.
   */
  start(): Promise<void> {
    if (!this.started) this.started = this.run();
    return this.started;
  }

  /** Sends `stop`, closes the socket, stops the microphone, closes the audio. Safe to call at any time, any number of times. */
  hangUp(): void {
    if (this.finished || !this.started) return;
    const socket = this.socket;
    if (socket && this.outbound && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(this.outbound.stop());
      } catch {
        // the socket went away between the check and the send: there is nobody left to tell
      }
    }
    this.teardown("ended");
  }

  /** Muted: µ-law silence (0xFF) goes out instead of the microphone. The line stays open. */
  setMuted(muted: boolean): void {
    this.muted = muted;
    if (muted) this.micLevel = 0;
  }

  // ── starting ────────────────────────────────────────────────────────────────────────────────────

  private async run(): Promise<void> {
    this.setState("connecting");
    try {
      // First, and with no await before it: Safari only lets an AudioContext start inside the gesture.
      const context = this.openContext();
      // The microphone before the socket: a caller who refuses it never starts a call on the server.
      const [voice] = await Promise.all([
        this.options.testClipUrl ? this.loadClip(context, this.options.testClipUrl) : this.openMicrophone(),
        this.loadWorklets(context),
      ]);
      this.alive();
      this.buildGraph(context, voice);
      // Dial only once audio is really flowing. A cold sound card can take two seconds to start; a call
      // opened before that gives the server a line that carries nothing, and its greeting is heard late.
      await this.audioFlowing(context);
      this.alive();

      this.outbound = new OutboundStream(this.options);
      this.silencePayload = bytesToBase64(new Uint8Array(FRAME_SAMPLES).fill(MULAW_SILENCE));
      const socket = await this.openSocket();
      this.alive();
      socket.send(this.outbound.connected());
      socket.send(this.outbound.start());
      this.setState("live"); // from here every capture chunk becomes a `media` frame
      this.clipSource?.start(context.currentTime + Math.max(0, this.options.testClipDelayMs ?? 0) / 1000);
    } catch (err) {
      if (this.finished || err instanceof Cancelled) return;
      this.teardown("error", err instanceof PhoneError ? err.message : `The call could not start: ${messageOf(err)}`);
    }
  }

  /** hangUp() can overtake start() at any await; this is checked after each one. */
  private alive(): void {
    if (this.finished) throw new Cancelled();
  }

  private openContext(): AudioContext {
    if (typeof window === "undefined" || typeof AudioContext === "undefined") {
      throw new PhoneError("This browser cannot play audio (no AudioContext).");
    }
    // The native rate, not 8000: browsers differ on odd rates, so the worklets resample instead.
    const context = new AudioContext({ latencyHint: "interactive" });
    this.context = context;
    if (!context.audioWorklet) {
      throw new PhoneError("This page cannot process audio. It needs https or localhost, and a current browser.");
    }
    context.onstatechange = () => {
      // Safari suspends ("interrupted") when another app takes the audio; a live call takes it back.
      if (!this.finished && context.state !== "running" && context.state !== "closed") void context.resume().catch(() => {});
    };
    // Not awaited: outside a user gesture it stays pending until the page is clicked, and start() must not hang on it.
    void context.resume().catch(() => {});
    return context;
  }

  private async loadWorklets(context: AudioContext): Promise<void> {
    const base = (this.options.workletBaseUrl ?? "/phone").replace(/\/$/, "");
    for (const file of ["capture-worklet.js", "playback-worklet.js"]) {
      try {
        await context.audioWorklet.addModule(`${base}/${file}`);
      } catch (err) {
        throw new PhoneError(`The audio worklet ${base}/${file} could not be loaded: ${messageOf(err)}`);
      }
    }
  }

  private async openMicrophone(): Promise<MediaStream> {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw new PhoneError("The microphone is not available here. It needs https or localhost.");
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
    } catch (err) {
      throw new PhoneError(describeMicrophoneError(err));
    }
    if (this.finished) {
      for (const track of stream.getTracks()) track.stop(); // hung up while the permission prompt was open
      throw new Cancelled();
    }
    this.microphone = stream;
    return stream;
  }

  private async loadClip(context: AudioContext, url: string): Promise<AudioBuffer> {
    let data: ArrayBuffer;
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.arrayBuffer();
    } catch (err) {
      throw new PhoneError(`The test clip ${url} could not be fetched: ${messageOf(err)}`);
    }
    try {
      // The callback form works in every Safari; where a promise comes back too, the callbacks have it covered.
      return await new Promise<AudioBuffer>((resolve, reject) => {
        const pending = context.decodeAudioData(data, resolve, reject) as Promise<AudioBuffer> | undefined;
        pending?.catch(() => {});
      });
    } catch (err) {
      throw new PhoneError(`The test clip ${url} could not be decoded: ${messageOf(err)}`);
    }
  }

  private buildGraph(context: AudioContext, voice: MediaStream | AudioBuffer): void {
    // Caller: voice → capture worklet → a closed gain → speakers. The closed gain is there only because
    // a node is processed when something downstream pulls it; the caller never hears themselves.
    const capture = new AudioWorkletNode(context, "phone-capture", {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
      channelCount: 1, // a stereo microphone or clip is mixed down before it reaches the worklet
      channelCountMode: "explicit",
      channelInterpretation: "speakers",
      processorOptions: { targetRate: WIRE_SAMPLE_RATE, chunkSamples: FRAME_SAMPLES },
    });
    capture.port.onmessage = (event: MessageEvent) => this.onCaptureMessage(event.data);
    capture.onprocessorerror = () => this.teardown("error", "The microphone audio processor stopped unexpectedly.");
    const closed = context.createGain();
    closed.gain.value = 0;
    capture.connect(closed).connect(context.destination);

    let source: AudioNode;
    if (voice instanceof AudioBuffer) {
      this.clipSource = context.createBufferSource();
      this.clipSource.buffer = voice;
      source = this.clipSource; // started when the call goes live
    } else {
      source = context.createMediaStreamSource(voice);
    }
    source.connect(capture);

    // Agent: playback worklet → low-pass → speakers. Linear interpolation leaves faint copies of the voice
    // above 4 kHz; a fourth-order Butterworth at 3.7 kHz takes that telephone "sizzle" off.
    const playback = new AudioWorkletNode(context, "phone-playback", {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [1],
      processorOptions: { sourceRate: WIRE_SAMPLE_RATE, jitterMs: this.options.jitterMs ?? 80 },
    });
    playback.port.onmessage = (event: MessageEvent) => this.onPlaybackMessage(event.data);
    playback.onprocessorerror = () => this.teardown("error", "The agent audio processor stopped unexpectedly.");
    let tail: AudioNode = playback;
    const filters: AudioNode[] = [];
    for (const q of [0.5412, 1.3066]) {
      const lowpass = context.createBiquadFilter();
      lowpass.type = "lowpass";
      lowpass.frequency.value = Math.min(3700, context.sampleRate * 0.45);
      lowpass.Q.value = 20 * Math.log10(q); // a lowpass BiquadFilterNode takes its Q in decibels
      tail.connect(lowpass);
      tail = lowpass;
      filters.push(lowpass);
    }
    tail.connect(context.destination);

    this.captureNode = capture;
    this.playbackNode = playback;
    this.nodes = [source, capture, closed, playback, ...filters];
  }

  /** Resolves with the capture worklet's first chunk: proof that the audio clock runs and pulls the graph. */
  private audioFlowing(context: AudioContext): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const done = () => {
        clearTimeout(timer);
        this.onFirstChunk = null;
        this.cancelWait = null;
      };
      const timer = setTimeout(() => {
        done();
        reject(
          new PhoneError(
            context.state === "running"
              ? "The audio did not start. Check the sound output of this computer, then call again."
              : "The browser did not let the audio start. Start the call with a click.",
          ),
        );
      }, AUDIO_START_LIMIT_MS);
      this.onFirstChunk = () => {
        done();
        resolve();
      };
      this.cancelWait = () => {
        done();
        reject(new Cancelled());
      };
    });
  }

  private openSocket(): Promise<WebSocket> {
    const url = this.options.url;
    return new Promise<WebSocket>((resolve, reject) => {
      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch (err) {
        reject(new PhoneError(`The call server address ${url} cannot be opened: ${messageOf(err)}`));
        return;
      }
      this.socket = socket;
      let opened = false;
      this.cancelWait = () => reject(new Cancelled());
      socket.onopen = () => {
        opened = true;
        this.cancelWait = null;
        resolve(socket);
      };
      socket.onmessage = (event: MessageEvent) => this.onSocketMessage(event.data);
      socket.onerror = () => {}; // says nothing useful; a close event always follows and carries the code
      socket.onclose = (event: CloseEvent) => {
        if (opened) this.onSocketClosed(event);
        else reject(new PhoneError(`The call server at ${url} could not be reached.`));
      };
    });
  }

  // ── the call ────────────────────────────────────────────────────────────────────────────────────

  private onCaptureMessage(message: { type?: string; samples?: Int16Array } | null): void {
    if (this.finished || message?.type !== "chunk" || !message.samples) return;
    this.onFirstChunk?.();
    if (this.draining || this.currentState !== "live") return; // not on the line yet, or no longer
    this.assembler.push(message.samples, (frame) => this.sendFrame(frame));
  }

  private sendFrame(frame: Int16Array): void {
    const socket = this.socket;
    if (!socket || !this.outbound || socket.readyState !== WebSocket.OPEN) return;
    let payload = this.silencePayload;
    let rms = 0;
    if (!this.muted) {
      payload = bytesToBase64(encodeMulaw(frame));
      let sum = 0;
      for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
      rms = Math.sqrt(sum / frame.length) / 32768;
    }
    this.micLevel = follow(this.micLevel, levelFromRms(rms), 0.6, 0.2);
    socket.send(this.outbound.media(payload));
  }

  private onSocketMessage(data: unknown): void {
    if (this.finished || !this.playbackNode) return;
    const event = parseInbound(data);
    if (event.kind === "media") {
      const samples = decodeMulaw(event.payload);
      this.playbackNode.port.postMessage({ type: "push", samples }, [samples.buffer as ArrayBuffer]);
    } else if (event.kind === "clear") {
      this.playbackNode.port.postMessage({ type: "clear" }); // barge-in: what is queued goes now
    }
  }

  private onPlaybackMessage(message: { type?: string; rms?: number; buffered?: number } | null): void {
    if (this.finished || !message) return;
    if (message.type === "level") {
      this.agentLevel = follow(this.agentLevel, levelFromRms(message.rms ?? 0), 0.8, 0.4);
      this.agentBufferedMs = ((message.buffered ?? 0) / WIRE_SAMPLE_RATE) * 1000;
      if (this.currentState === "live") this.reportLevels(this.micLevel, this.agentLevel);
    } else if (message.type === "drained" && this.draining) {
      // The ring is empty, but the last of it is still on its way through the sound card.
      const context = this.context;
      const latencyMs = context ? ((context.baseLatency || 0) + (context.outputLatency || 0)) * 1000 : 0;
      this.finishAfter(Math.min(1000, latencyMs + 150));
    }
  }

  private onSocketClosed(event: CloseEvent): void {
    if (this.finished) return;
    this.socket = null;
    const clean = event.wasClean && CLEAN_CLOSE_CODES.includes(event.code);
    const outcome = clean
      ? { state: "ended" as const, detail: "The agent ended the call." }
      : { state: "error" as const, detail: `The line to the call server dropped (code ${event.code}).` };
    if (this.currentState !== "live") {
      this.teardown(outcome.state, outcome.detail);
      return;
    }
    // The caller's side stops at once. The agent's last words are already here — the server sends ahead
    // of real time — so they are played out before the audio closes. hangUp() cuts this short.
    this.draining = outcome;
    this.stopCapture();
    this.micLevel = 0;
    const context = this.context;
    if (!context || context.state !== "running" || !this.playbackNode) {
      this.teardown(outcome.state, outcome.detail);
      return;
    }
    this.playbackNode.port.postMessage({ type: "drain" });
    this.finishAfter(Math.min(60_000, this.agentBufferedMs + 2_000)); // the limit, should "drained" never come
  }

  private finishAfter(ms: number): void {
    if (this.drainTimer !== null) clearTimeout(this.drainTimer);
    this.drainTimer = setTimeout(() => {
      this.drainTimer = null;
      const outcome = this.draining ?? { state: "ended" as const };
      this.teardown(outcome.state, outcome.detail);
    }, ms);
  }

  // ── ending ──────────────────────────────────────────────────────────────────────────────────────

  private stopCapture(): void {
    if (this.microphone) for (const track of this.microphone.getTracks()) track.stop();
    this.microphone = null;
    try {
      this.clipSource?.stop();
    } catch {
      // it was never started
    }
    this.clipSource = null;
    if (this.captureNode) {
      this.captureNode.port.onmessage = null;
      this.captureNode.onprocessorerror = null;
      this.captureNode.port.postMessage({ type: "stop" });
    }
    this.captureNode = null;
  }

  private teardown(state: "ended" | "error", detail?: string): void {
    if (this.finished) return;
    this.finished = true;
    if (this.drainTimer !== null) clearTimeout(this.drainTimer);
    this.drainTimer = null;

    const cancel = this.cancelWait;
    this.cancelWait = null;
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        try {
          socket.close(1000);
        } catch {
          // already closing
        }
      }
    }
    cancel?.(); // start() may still be waiting for the audio to start or the socket to open

    this.stopCapture();
    if (this.playbackNode) {
      this.playbackNode.port.onmessage = null;
      this.playbackNode.onprocessorerror = null;
      this.playbackNode.port.postMessage({ type: "stop" });
    }
    this.playbackNode = null;
    for (const node of this.nodes) {
      try {
        node.disconnect();
      } catch {
        // never connected
      }
    }
    this.nodes = [];
    const context = this.context;
    this.context = null;
    if (context) {
      context.onstatechange = null;
      if (context.state !== "closed") void context.close().catch(() => {});
    }

    const wasLive = this.currentState === "live";
    this.micLevel = 0;
    this.agentLevel = 0;
    if (wasLive) this.reportLevels(0, 0); // the meters fall to rest
    this.setState(state, detail);
  }

  // The owner's callbacks run inside socket and audio handlers: one that throws must not stop a call or a cleanup.

  private setState(state: PhoneState, detail?: string): void {
    this.currentState = state;
    try {
      this.options.onState?.(state, detail);
    } catch (err) {
      console.error("Phone: onState threw", err);
    }
  }

  private reportLevels(mic: number, agent: number): void {
    try {
      this.options.onLevel?.(mic, agent);
    } catch (err) {
      console.error("Phone: onLevel threw", err);
    }
  }
}
