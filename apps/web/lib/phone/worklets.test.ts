/**
 * The two worklets are plain JS that only a browser's audio thread runs. Here they run in node instead,
 * inside a stand-in for that thread's globals, so their math is held to resample.ts without a browser.
 */
import { readFileSync } from "node:fs";
import { runInThisContext } from "node:vm";

import { describe, expect, it } from "vitest";

import { Downsampler, upsampleLinear } from "./resample";

const BLOCK = 128; // one render quantum

interface Processor {
  port: { onmessage: ((event: { data: unknown }) => void) | null };
  process(inputs: Float32Array[][], outputs: Float32Array[][]): boolean;
}

interface LevelMessage {
  type: "level";
  rms: number;
  buffered: number;
  playing: boolean;
  underruns: number;
}

function loadWorklet(file: string, sampleRate: number, processorOptions: Record<string, unknown> = {}) {
  const url = new URL(`../../public/phone/${file}`, import.meta.url);
  const posted: { type: string }[] = [];
  class AudioWorkletProcessor {
    port = { onmessage: null, postMessage: (message: { type: string }) => void posted.push(message) };
  }
  const registered: Record<string, new (options: unknown) => Processor> = {};
  const registerProcessor = (name: string, ctor: new (options: unknown) => Processor) => void (registered[name] = ctor);
  const body = `(function (AudioWorkletProcessor, registerProcessor, sampleRate) {${readFileSync(url, "utf8")}\n})`;
  runInThisContext(body, { filename: file })(AudioWorkletProcessor, registerProcessor, sampleRate);
  const [name] = Object.keys(registered);
  const processor = new registered[name]({ processorOptions });
  return { name, processor, posted, send: (data: unknown) => processor.port.onmessage?.({ data }) };
}

function tone(freq: number, rate: number, seconds: number, amplitude = 0.5): Float32Array {
  const out = new Float32Array(Math.round(rate * seconds));
  for (let i = 0; i < out.length; i++) out[i] = amplitude * Math.sin((2 * Math.PI * freq * i) / rate);
  return out;
}

function toInt16(x: Float32Array): Int16Array {
  return Int16Array.from(x, (v) => Math.max(-32768, Math.min(32767, Math.round(v * 32768))));
}

describe.each([48000, 44100])("capture worklet at %i Hz", (rate) => {
  const chunksOf = (posted: { type: string }[]) =>
    (posted as { type: string; samples: Int16Array }[]).filter((m) => m.type === "chunk").map((m) => m.samples);

  it("registers as phone-capture", () => {
    expect(loadWorklet("capture-worklet.js", rate).name).toBe("phone-capture");
  });

  it("emits 20 ms chunks of 160 samples, the same samples resample.ts gives", () => {
    const { processor, posted } = loadWorklet("capture-worklet.js", rate);
    const source = tone(440, rate, 1);
    for (let i = 0; i + BLOCK <= source.length; i += BLOCK) {
      expect(processor.process([[source.subarray(i, i + BLOCK)]], [[new Float32Array(BLOCK)]])).toBe(true);
    }
    const chunks = chunksOf(posted);
    expect(chunks.length).toBeGreaterThanOrEqual(49); // a second is 50 chunks; the last is still filling
    expect(chunks.every((chunk) => chunk instanceof Int16Array && chunk.length === 160)).toBe(true);

    const sampler = new Downsampler(rate);
    const expected = toInt16(sampler.process(source.subarray(0, Math.floor(source.length / BLOCK) * BLOCK)));
    const got = chunks.flatMap((chunk) => Array.from(chunk));
    for (let i = 0; i < got.length; i++) expect(Math.abs(got[i] - expected[i])).toBeLessThanOrEqual(1);
  });

  it("leaves its own output silent: the caller does not hear themselves", () => {
    const { processor } = loadWorklet("capture-worklet.js", rate);
    const output = new Float32Array(BLOCK);
    processor.process([[tone(440, rate, BLOCK / rate)]], [[output]]);
    expect(output.every((v) => v === 0)).toBe(true);
  });

  it("keeps the line open with silence when nothing is connected to it", () => {
    const { processor, posted } = loadWorklet("capture-worklet.js", rate);
    for (let i = 0; i < Math.ceil(rate / BLOCK); i++) processor.process([[]], [[new Float32Array(BLOCK)]]);
    const chunks = chunksOf(posted);
    expect(chunks.length).toBeGreaterThanOrEqual(49);
    expect(chunks.every((chunk) => chunk.every((v) => v === 0))).toBe(true);
  });

  it("clips instead of wrapping when the input is too hot", () => {
    const { processor, posted } = loadWorklet("capture-worklet.js", rate);
    const loud = new Float32Array(BLOCK).fill(1.5);
    for (let i = 0; i < 200; i++) processor.process([[loud]], [[new Float32Array(BLOCK)]]);
    const last = chunksOf(posted).at(-1);
    expect(last?.every((v) => v === 32767)).toBe(true);
  });

  it("ends when told to stop", () => {
    const { processor, send } = loadWorklet("capture-worklet.js", rate);
    send({ type: "stop" });
    expect(processor.process([[new Float32Array(BLOCK)]], [[new Float32Array(BLOCK)]])).toBe(false);
  });
});

describe.each([48000, 44100])("playback worklet at %i Hz", (rate) => {
  function load(options: Record<string, unknown> = {}) {
    const worklet = loadWorklet("playback-worklet.js", rate, options);
    const render = (seconds: number): Float32Array => {
      const blocks = Math.ceil((seconds * rate) / BLOCK);
      const out = new Float32Array(blocks * BLOCK);
      for (let b = 0; b < blocks; b++) {
        const block = new Float32Array(BLOCK);
        expect(worklet.processor.process([], [[block]])).toBe(true);
        out.set(block, b * BLOCK);
      }
      return out;
    };
    const levels = () => worklet.posted.filter((m): m is LevelMessage => m.type === "level");
    return { ...worklet, render, levels };
  }
  const silent = (x: Float32Array) => x.every((v) => v === 0);

  it("registers as phone-playback", () => {
    expect(load().name).toBe("phone-playback");
  });

  it("plays what it is given, upsampled exactly as upsampleLinear does", () => {
    const { send, render } = load();
    const source = tone(440, 8000, 0.5);
    send({ type: "push", samples: toInt16(source) });
    const out = render(0.4);
    const expected = upsampleLinear(Float32Array.from(toInt16(source), (v) => v / 32768), 8000, rate);
    for (let i = 0; i < out.length; i++) expect(Math.abs(out[i] - expected[i])).toBeLessThan(1e-5);
  });

  it("waits for 80 ms in hand before it starts", () => {
    const { send, render } = load();
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.04)) });
    expect(silent(render(0.05))).toBe(true);
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.04)) });
    expect(silent(render(0.05))).toBe(false);
  });

  it("still plays a tail too short to reach that threshold, once nothing more comes", () => {
    const { send, render } = load();
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.04)) });
    expect(silent(render(0.1))).toBe(true);
    expect(silent(render(0.1))).toBe(false);
  });

  it("drops everything queued the moment `clear` arrives (barge-in)", () => {
    const { send, render, levels } = load();
    send({ type: "push", samples: toInt16(tone(440, 8000, 5)) });
    expect(silent(render(0.2))).toBe(false);
    send({ type: "clear" });
    const after = render(0.3);
    expect(silent(after.subarray(Math.round(rate * 0.03)))).toBe(true); // a 2 ms fade, then nothing
    expect(Math.max(...after.subarray(0, BLOCK).map(Math.abs))).toBeLessThanOrEqual(0.5); // a fade, not a pop
    expect(levels().at(-1)?.buffered).toBe(0);
    // and the next sentence plays
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.5)) });
    expect(silent(render(0.1))).toBe(false);
  });

  it("goes silent when it runs dry — never a loop of old audio — and picks up again", () => {
    const { send, render, levels } = load();
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.2)) });
    const out = render(1);
    expect(silent(out.subarray(Math.round(rate * 0.25)))).toBe(true);
    expect(levels().at(-1)).toMatchObject({ playing: false, buffered: 0, underruns: 1 });
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.2)) });
    expect(silent(render(0.1))).toBe(false);
  });

  it("holds more than a minute: the server sends whole sentences ahead of real time", () => {
    const { send, render, levels } = load();
    const second = toInt16(tone(440, 8000, 1));
    for (let i = 0; i < 90; i++) send({ type: "push", samples: second });
    render(0.2);
    const level = levels().at(-1);
    expect(level?.buffered).toBeGreaterThan(8000 * 89.7);
    expect(level?.buffered).toBeLessThanOrEqual(8000 * 90);
  });

  it("keeps the order of the audio across a wrap of its ring and a growth", () => {
    const { send, render } = load();
    const ramp = (from: number, n: number) => Int16Array.from({ length: n }, (_, i) => from + i);
    send({ type: "push", samples: new Int16Array(8000 * 59) });
    render(58.5); // the read position is now near the end of the one-minute ring
    send({ type: "push", samples: ramp(0, 16000) }); // wraps
    send({ type: "push", samples: new Int16Array(8000 * 70) }); // grows while wrapped
    const out = render(3).map((v) => v * 32768);
    let peak = 0;
    for (let i = 1; i < out.length; i++) if (out[i] > out[peak]) peak = i;
    expect(out[peak]).toBeCloseTo(15999, 0); // the whole ramp came through, to its last sample
    let first = 0;
    while (out[first] <= 0) first++;
    expect(peak - first).toBeGreaterThan(rate * 1.99); // two seconds of ramp, none of it lost or repeated
    for (let i = first + 1; i <= peak; i++) expect(out[i]).toBeGreaterThanOrEqual(out[i - 1]); // never a step back
  });

  it("reports the level of what it plays about 15 times a second", () => {
    const { send, render, levels } = load();
    send({ type: "push", samples: toInt16(tone(440, 8000, 2)) });
    render(1);
    expect(levels().length).toBeGreaterThanOrEqual(14);
    expect(levels().length).toBeLessThanOrEqual(16);
    expect(levels().at(-1)?.rms).toBeCloseTo(0.5 / Math.SQRT2, 2);
  });

  it("plays out what is left when told to drain, then says so once", () => {
    const { send, render, posted } = load();
    send({ type: "push", samples: toInt16(tone(440, 8000, 0.03)) }); // under the start threshold
    send({ type: "drain" });
    expect(silent(render(0.02))).toBe(false); // no waiting for a threshold that will never be reached
    render(0.2);
    expect(posted.filter((m) => m.type === "drained").length).toBe(1);
  });

  it("says drained at once when there was nothing left", () => {
    const { send, render, posted } = load();
    send({ type: "drain" });
    render(0.01);
    expect(posted.filter((m) => m.type === "drained").length).toBe(1);
  });

  it("ends when told to stop", () => {
    const { processor, send } = load();
    send({ type: "stop" });
    expect(processor.process([], [[new Float32Array(BLOCK)]])).toBe(false);
  });
});
