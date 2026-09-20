/**
 * The Phone's behaviour — the order it does things in, what it sends, how it cleans up — against
 * stand-ins for the browser: no real audio, no real socket. Importing ./index up here, before any
 * stand-in exists, is itself the check that the module touches nothing at import time.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Phone, type PhoneOptions, type PhoneState, levelFromRms } from "./index";
import { decodeMulaw } from "./mulaw";
import { base64ToBytes } from "./wire";

class FakePort {
  onmessage: ((event: { data: unknown }) => void) | null = null;
  sent: { type: string; samples?: Int16Array }[] = [];
  postMessage(message: { type: string; samples?: Int16Array }) {
    this.sent.push(message);
  }
  deliver(data: unknown) {
    this.onmessage?.({ data });
  }
}

class FakeNode {
  outputs: FakeNode[] = [];
  disconnected = false;
  connect(target: FakeNode) {
    this.outputs.push(target);
    return target;
  }
  disconnect() {
    this.disconnected = true;
  }
}

class FakeParam {
  value = 1;
}

class FakeBufferSource extends FakeNode {
  buffer: unknown = null;
  startedAt: number | null = null;
  stopped = false;
  start(when: number) {
    this.startedAt = when;
  }
  stop() {
    this.stopped = true;
  }
}

class FakeAudioBuffer {}

class FakeTrack {
  stopped = false;
  stop() {
    this.stopped = true;
  }
}

class FakeStream {
  tracks = [new FakeTrack()];
  getTracks() {
    return this.tracks;
  }
}

class FakeAudioContext {
  static last: FakeAudioContext | null = null;
  static failModule: string | null = null;
  state = "suspended";
  sampleRate = 48000;
  currentTime = 12;
  baseLatency = 0.01;
  outputLatency = 0.02;
  destination = new FakeNode();
  modules: string[] = [];
  worklets: Record<string, FakeWorkletNode> = {};
  sources: FakeNode[] = [];
  clipSource: FakeBufferSource | null = null;
  onstatechange: (() => void) | null = null;
  audioWorklet = {
    addModule: async (url: string) => {
      if (FakeAudioContext.failModule && url.endsWith(FakeAudioContext.failModule)) throw new Error("404");
      this.modules.push(url);
    },
  };
  constructor() {
    FakeAudioContext.last = this;
  }
  async resume() {
    this.state = "running";
  }
  async close() {
    this.state = "closed";
  }
  createGain() {
    return Object.assign(new FakeNode(), { gain: new FakeParam() });
  }
  createBiquadFilter() {
    return Object.assign(new FakeNode(), { type: "", frequency: new FakeParam(), Q: new FakeParam() });
  }
  createMediaStreamSource(stream: FakeStream) {
    const node = Object.assign(new FakeNode(), { stream });
    this.sources.push(node);
    return node;
  }
  createBufferSource() {
    this.clipSource = new FakeBufferSource();
    return this.clipSource;
  }
  decodeAudioData(_data: ArrayBuffer, ok: (buffer: FakeAudioBuffer) => void) {
    ok(new FakeAudioBuffer());
  }
}

class FakeWorkletNode extends FakeNode {
  port = new FakePort();
  onprocessorerror: (() => void) | null = null;
  constructor(
    context: FakeAudioContext,
    public name: string,
    public options: { processorOptions: Record<string, unknown> },
  ) {
    super();
    context.worklets[name] = this;
  }
}

class FakeSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static all: FakeSocket[] = [];
  readyState = FakeSocket.CONNECTING;
  sent: string[] = [];
  closedWith: number | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: { code: number; wasClean: boolean }) => void) | null = null;
  constructor(public url: string) {
    FakeSocket.all.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close(code: number) {
    this.closedWith = code;
    this.readyState = FakeSocket.CLOSED;
  }
  // the server's side
  accept() {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }
  say(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
  drop(code: number, wasClean: boolean) {
    this.readyState = FakeSocket.CLOSED;
    this.onerror?.();
    this.onclose?.({ code, wasClean });
  }
  get messages() {
    return this.sent.map((raw) => JSON.parse(raw));
  }
}

/** Lets every promise that can settle, settle. */
async function settle() {
  for (let i = 0; i < 50; i++) await Promise.resolve();
}

let microphone: { grant: (stream: FakeStream) => void; refuse: (err: unknown) => void; asked: number; constraints: unknown };
let fetched: string[];

beforeEach(() => {
  FakeSocket.all = [];
  FakeAudioContext.last = null;
  FakeAudioContext.failModule = null;
  fetched = [];
  microphone = { grant: () => {}, refuse: () => {}, asked: 0, constraints: null };
  const getUserMedia = (constraints: unknown) =>
    new Promise<FakeStream>((resolve, reject) => {
      microphone.asked += 1;
      microphone.constraints = constraints;
      microphone.grant = resolve;
      microphone.refuse = reject;
    });
  vi.stubGlobal("window", {});
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  vi.stubGlobal("AudioContext", FakeAudioContext);
  vi.stubGlobal("AudioWorkletNode", FakeWorkletNode);
  vi.stubGlobal("AudioBuffer", FakeAudioBuffer);
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("fetch", async (url: string) => {
    fetched.push(url);
    return { ok: true, status: 200, arrayBuffer: async () => new ArrayBuffer(8) };
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function makePhone(extra: Partial<PhoneOptions> = {}) {
  const states: [PhoneState, string | undefined][] = [];
  const levels: [number, number][] = [];
  const phone = new Phone({
    url: "ws://127.0.0.1:7861/ws",
    callId: "call-1",
    fromNumber: "+34711330529",
    params: { screen: "1" },
    onState: (state, detail) => states.push([state, detail]),
    onLevel: (mic, agent) => levels.push([mic, agent]),
    ...extra,
  });
  return { phone, states, levels };
}

const chunk = (value: number) => ({ type: "chunk", samples: new Int16Array(160).fill(value) });

/** The audio clock starts: the capture worklet delivers its first 20 ms. */
async function audioStarts() {
  FakeAudioContext.last!.worklets["phone-capture"].port.deliver(chunk(0));
  await settle();
}

/** A call that is live: microphone granted, audio flowing, socket accepted. */
async function liveCall(extra: Partial<PhoneOptions> = {}) {
  const made = makePhone(extra);
  const stream = new FakeStream();
  const started = made.phone.start();
  await settle();
  microphone.grant(stream);
  await settle();
  await audioStarts();
  const socket = FakeSocket.all[0];
  socket.accept();
  await started;
  const context = FakeAudioContext.last!;
  return { ...made, stream, socket, context, capture: context.worklets["phone-capture"], playback: context.worklets["phone-playback"] };
}

describe("starting a call", () => {
  it("is idle until started, and importing it touched nothing", () => {
    const { phone, states } = makePhone();
    expect(phone.state).toBe("idle");
    expect(states).toEqual([]);
    expect(FakeAudioContext.last).toBeNull();
  });

  it("opens the audio inside the gesture, asks for the microphone, waits for audio to flow, and only then dials", async () => {
    const { phone, states } = makePhone();
    void phone.start();
    expect(FakeAudioContext.last).not.toBeNull(); // created before the first await: Safari needs the gesture
    expect(states).toEqual([["connecting", undefined]]);
    await settle();
    expect(microphone.asked).toBe(1);
    expect(microphone.constraints).toEqual({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    expect(FakeAudioContext.last!.modules).toEqual(["/phone/capture-worklet.js", "/phone/playback-worklet.js"]);
    expect(FakeSocket.all.length).toBe(0); // nobody is called until the caller can speak
    microphone.grant(new FakeStream());
    await settle();
    expect(FakeSocket.all.length).toBe(0); // nor while the sound card is still waking up
    await audioStarts();
    expect(FakeSocket.all.map((socket) => socket.url)).toEqual(["ws://127.0.0.1:7861/ws"]);
    expect(phone.state).toBe("connecting");
  });

  it("goes live with `connected` then `start`, and start() resolves", async () => {
    const { phone, states, socket, context } = await liveCall();
    expect(phone.state).toBe("live");
    expect(states.map(([state]) => state)).toEqual(["connecting", "live"]);
    expect(context.state).toBe("running");
    const [connected, start] = socket.messages;
    expect(connected).toEqual({ event: "connected", protocol: "Call", version: "1.0.0" });
    expect(start.event).toBe("start");
    expect(start.start.callSid).toBe("call-1");
    expect(start.start.streamSid).toBe(start.streamSid);
    expect(start.start.mediaFormat).toEqual({ encoding: "audio/x-mulaw", sampleRate: 8000, channels: 1 });
    expect(start.start.customParameters).toEqual({ screen: "1", call_id: "call-1", from_number: "+34711330529" });
  });

  it("wires microphone → capture → a closed gain, and playback → low-pass → speakers", async () => {
    const { context, capture, playback, stream } = await liveCall();
    expect(context.sources[0]).toMatchObject({ stream });
    expect(context.sources[0].outputs).toEqual([capture]);
    expect(capture.options).toMatchObject({ channelCount: 1, channelCountMode: "explicit" });
    const closed = capture.outputs[0] as FakeNode & { gain: FakeParam };
    expect(closed.gain.value).toBe(0);
    expect(closed.outputs).toEqual([context.destination]);
    let node: FakeNode = playback;
    let hops = 0;
    while (node !== context.destination && hops++ < 5) node = node.outputs[0];
    expect(node).toBe(context.destination);
    expect(hops).toBe(3); // two filter stages, then the speakers
  });

  it("returns the same promise when started twice", async () => {
    const { phone } = makePhone();
    expect(phone.start()).toBe(phone.start());
    await settle();
    expect(microphone.asked).toBe(1);
  });
});

describe("during a call", () => {
  it("sends one µ-law media frame per 20 ms chunk, counting up", async () => {
    const { capture, socket } = await liveCall();
    capture.port.deliver(chunk(0));
    capture.port.deliver(chunk(32767));
    const frames = socket.messages.slice(2);
    expect(frames.map((frame) => frame.event)).toEqual(["media", "media"]);
    expect(frames.map((frame) => frame.sequenceNumber)).toEqual(["2", "3"]);
    expect(frames.map((frame) => frame.media.chunk)).toEqual(["1", "2"]);
    expect(frames.map((frame) => frame.media.timestamp)).toEqual(["0", "20"]);
    expect(frames[0].media.track).toBe("inbound");
    expect(Array.from(base64ToBytes(frames[0].media.payload))).toEqual(new Array(160).fill(0xff));
    expect(Array.from(base64ToBytes(frames[1].media.payload))).toEqual(new Array(160).fill(0x80));
  });

  it("sends silence, and still one frame per chunk, while muted", async () => {
    const { phone, capture, socket } = await liveCall();
    phone.setMuted(true);
    capture.port.deliver(chunk(20000));
    phone.setMuted(false);
    capture.port.deliver(chunk(20000));
    const [muted, open] = socket.messages.slice(2);
    expect(Array.from(base64ToBytes(muted.media.payload))).toEqual(new Array(160).fill(0xff));
    expect(base64ToBytes(open.media.payload)[0]).not.toBe(0xff);
    expect(open.media.chunk).toBe("2");
  });

  it("drops capture chunks until the call is live", async () => {
    const { phone } = makePhone();
    void phone.start();
    await settle();
    microphone.grant(new FakeStream());
    await settle();
    await audioStarts();
    FakeAudioContext.last!.worklets["phone-capture"].port.deliver(chunk(5000));
    const socket = FakeSocket.all[0];
    expect(socket.sent).toEqual([]);
    socket.accept();
    await settle();
    expect(socket.messages.map((message) => message.event)).toEqual(["connected", "start"]);
  });

  it("plays the agent's audio, and drops what is queued on `clear`", async () => {
    const { socket, playback } = await liveCall();
    const payload = Buffer.from([0xff, 0x80, 0x00, 0x7f]).toString("base64");
    socket.say({ event: "media", streamSid: "MZ", media: { payload } });
    socket.say({ event: "mark", mark: { name: "ignored" } });
    socket.say({ event: "clear", streamSid: "MZ" });
    expect(playback.port.sent.map((message) => message.type)).toEqual(["push", "clear"]);
    expect(Array.from(playback.port.sent[0].samples!)).toEqual(Array.from(decodeMulaw(Uint8Array.of(0xff, 0x80, 0x00, 0x7f))));
  });

  it("reports levels as the playback worklet ticks: what is sent, and what is heard", async () => {
    const { phone, capture, playback, levels } = await liveCall();
    playback.port.deliver({ type: "level", rms: 0, buffered: 0 });
    expect(levels).toEqual([[0, 0]]);
    capture.port.deliver(chunk(8000));
    playback.port.deliver({ type: "level", rms: 0.2, buffered: 4000 });
    const [mic, agent] = levels[1];
    expect(mic).toBeGreaterThan(0.2);
    expect(mic).toBeLessThanOrEqual(1);
    expect(agent).toBeGreaterThan(0.4);
    expect(agent).toBeLessThanOrEqual(1);
    phone.setMuted(true);
    capture.port.deliver(chunk(8000));
    playback.port.deliver({ type: "level", rms: 0.2, buffered: 4000 });
    expect(levels[2][0]).toBe(0); // muted: nothing is being sent
  });

  it("maps RMS to a 0..1 meter on a decibel scale", () => {
    expect(levelFromRms(0)).toBe(0);
    expect(levelFromRms(10 ** (-60 / 20))).toBe(0);
    expect(levelFromRms(10 ** (-25 / 20))).toBeCloseTo(0.5, 6);
    expect(levelFromRms(1)).toBe(1);
    expect(levelFromRms(4)).toBe(1);
  });
});

describe("ending a call", () => {
  it("hangs up: `stop`, socket closed, microphone off, audio closed — once", async () => {
    const { phone, states, levels, socket, stream, context, capture, playback } = await liveCall();
    capture.port.deliver(chunk(0));
    phone.hangUp();
    phone.hangUp();
    const last = socket.messages.at(-1);
    expect(last).toMatchObject({ event: "stop", sequenceNumber: "3", stop: { accountSid: "AC-local", callSid: "call-1" } });
    expect(socket.closedWith).toBe(1000);
    expect(stream.tracks[0].stopped).toBe(true);
    expect(context.state).toBe("closed");
    expect(capture.port.sent.at(-1)).toEqual({ type: "stop" });
    expect(playback.port.sent.at(-1)).toEqual({ type: "stop" });
    expect([capture, playback, context.sources[0]].every((node) => node.disconnected)).toBe(true);
    expect(phone.state).toBe("ended");
    expect(states.map(([state]) => state)).toEqual(["connecting", "live", "ended"]);
    expect(levels.at(-1)).toEqual([0, 0]);
    const sentBefore = socket.sent.length;
    capture.port.deliver(chunk(0)); // a late chunk from the audio thread
    expect(socket.sent.length).toBe(sentBefore);
  });

  it("when the agent hangs up: the microphone stops at once, its last words play out, then ended", async () => {
    vi.useFakeTimers();
    const { phone, states, socket, stream, context, playback } = await liveCall();
    playback.port.deliver({ type: "level", rms: 0.2, buffered: 24000 }); // three seconds still queued
    socket.drop(1000, true);
    expect(stream.tracks[0].stopped).toBe(true);
    expect(playback.port.sent.at(-1)).toEqual({ type: "drain" });
    expect(phone.state).toBe("live");
    expect(context.state).toBe("running");
    vi.advanceTimersByTime(2500);
    expect(phone.state).toBe("live"); // still speaking
    playback.port.deliver({ type: "drained" });
    vi.advanceTimersByTime(100);
    expect(context.state).toBe("running"); // the sound card still holds the last 30 ms
    vi.advanceTimersByTime(100);
    expect(context.state).toBe("closed");
    expect(states.at(-1)).toEqual(["ended", "The agent ended the call."]);
  });

  it("does not wait for ever if the playback worklet never answers", async () => {
    vi.useFakeTimers();
    const { phone, socket, playback } = await liveCall();
    playback.port.deliver({ type: "level", rms: 0.2, buffered: 8000 });
    socket.drop(1000, true);
    vi.advanceTimersByTime(2999);
    expect(phone.state).toBe("live");
    vi.advanceTimersByTime(2);
    expect(phone.state).toBe("ended");
  });

  it("lets the caller cut the agent's last words short", async () => {
    vi.useFakeTimers();
    const { phone, states, socket, context } = await liveCall();
    socket.drop(1000, true);
    phone.hangUp();
    expect(context.state).toBe("closed");
    expect(states.at(-1)).toEqual(["ended", undefined]);
    vi.advanceTimersByTime(60_000);
    expect(states.filter(([state]) => state === "ended").length).toBe(1);
  });

  it("calls a dropped line an error, in words", async () => {
    vi.useFakeTimers();
    const { states, socket, stream } = await liveCall();
    socket.drop(1006, false);
    expect(stream.tracks[0].stopped).toBe(true);
    vi.advanceTimersByTime(3000);
    expect(states.at(-1)).toEqual(["error", "The line to the call server dropped (code 1006)."]);
  });
});

describe("failing to start", () => {
  it("reports a refused microphone in words, never dials, closes the audio, and start() still resolves", async () => {
    const { phone, states } = makePhone();
    const started = phone.start();
    await settle();
    microphone.refuse(Object.assign(new Error("Permission denied"), { name: "NotAllowedError" }));
    await expect(started).resolves.toBeUndefined();
    expect(states.at(-1)).toEqual(["error", "Microphone access was denied. Allow the microphone for this site, then call again."]);
    expect(FakeSocket.all.length).toBe(0);
    expect(FakeAudioContext.last!.state).toBe("closed");
  });

  it("reports a server that cannot be reached, and lets go of the microphone", async () => {
    const { phone, states } = makePhone();
    const stream = new FakeStream();
    const started = phone.start();
    await settle();
    microphone.grant(stream);
    await settle();
    await audioStarts();
    FakeSocket.all[0].drop(1006, false);
    await started;
    expect(states.at(-1)).toEqual(["error", "The call server at ws://127.0.0.1:7861/ws could not be reached."]);
    expect(stream.tracks[0].stopped).toBe(true);
    expect(FakeAudioContext.last!.state).toBe("closed");
  });

  it("reports a worklet that will not load, and never leaves the microphone on", async () => {
    FakeAudioContext.failModule = "playback-worklet.js";
    const { phone, states } = makePhone();
    const stream = new FakeStream();
    const started = phone.start();
    await started;
    expect(states.at(-1)?.[0]).toBe("error");
    expect(states.at(-1)?.[1]).toContain("/phone/playback-worklet.js");
    microphone.grant(stream); // the permission prompt is answered after the failure
    await settle();
    expect(stream.tracks[0].stopped).toBe(true);
    expect(FakeSocket.all.length).toBe(0);
  });

  it("can be hung up while the permission prompt is open", async () => {
    const { phone, states } = makePhone();
    const stream = new FakeStream();
    const started = phone.start();
    await settle();
    phone.hangUp();
    expect(states.map(([state]) => state)).toEqual(["connecting", "ended"]);
    microphone.grant(stream);
    await started;
    expect(stream.tracks[0].stopped).toBe(true);
    expect(FakeSocket.all.length).toBe(0);
    expect(states.map(([state]) => state)).toEqual(["connecting", "ended"]);
  });

  it("says so, in words, when the audio never starts — and never dials", async () => {
    vi.useFakeTimers();
    const { phone, states } = makePhone();
    const stream = new FakeStream();
    const started = phone.start();
    await settle();
    microphone.grant(stream);
    await settle();
    vi.advanceTimersByTime(7999);
    expect(phone.state).toBe("connecting");
    vi.advanceTimersByTime(2);
    await started;
    expect(states.at(-1)).toEqual(["error", "The audio did not start. Check the sound output of this computer, then call again."]);
    expect(stream.tracks[0].stopped).toBe(true);
    expect(FakeSocket.all.length).toBe(0);
  });

  it("blames the missing click when the browser kept the audio suspended", async () => {
    vi.useFakeTimers();
    const { phone, states } = makePhone();
    const started = phone.start();
    await settle();
    FakeAudioContext.last!.state = "suspended";
    microphone.grant(new FakeStream());
    await settle();
    vi.advanceTimersByTime(8001);
    await started;
    expect(states.at(-1)).toEqual(["error", "The browser did not let the audio start. Start the call with a click."]);
  });

  it("can be hung up while waiting for the audio to start", async () => {
    vi.useFakeTimers();
    const { phone, states } = makePhone();
    const stream = new FakeStream();
    const started = phone.start();
    await settle();
    microphone.grant(stream);
    await settle();
    phone.hangUp();
    await started;
    vi.advanceTimersByTime(20_000); // the start limit must not fire after the hang-up
    expect(states.map(([state]) => state)).toEqual(["connecting", "ended"]);
    expect(stream.tracks[0].stopped).toBe(true);
    expect(FakeSocket.all.length).toBe(0);
  });

  it("can be hung up while the socket is opening", async () => {
    const { phone, states } = makePhone();
    const started = phone.start();
    await settle();
    microphone.grant(new FakeStream());
    await settle();
    await audioStarts();
    phone.hangUp();
    await started;
    expect(FakeSocket.all[0].closedWith).toBe(1000);
    expect(FakeSocket.all[0].sent).toEqual([]); // no `stop` for a call that never started
    expect(states.map(([state]) => state)).toEqual(["connecting", "ended"]);
  });

  it("survives an owner callback that throws", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const { phone, context } = await liveCall({
      onState: () => {
        throw new Error("the UI broke");
      },
    });
    phone.hangUp();
    expect(context.state).toBe("closed");
    expect(errors).toHaveBeenCalled();
    errors.mockRestore();
  });
});

describe("test mode", () => {
  it("streams the clip instead of the microphone, starting once live, after the asked delay", async () => {
    const { phone } = makePhone({ testClipUrl: "/clips/caller.wav", testClipDelayMs: 1500 });
    const started = phone.start();
    await settle();
    expect(microphone.asked).toBe(0);
    expect(fetched).toEqual(["/clips/caller.wav"]);
    const context = FakeAudioContext.last!;
    expect(context.clipSource!.outputs).toEqual([context.worklets["phone-capture"]]);
    expect(context.clipSource!.startedAt).toBeNull();
    await audioStarts();
    FakeSocket.all[0].accept();
    await started;
    expect(phone.state).toBe("live");
    expect(context.clipSource!.startedAt).toBeCloseTo(13.5); // currentTime 12 + 1.5 s
    phone.hangUp();
    expect(context.clipSource!.stopped).toBe(true);
  });
});
