import { describe, expect, it } from "vitest";

import { MULAW_SILENCE, decodeMulaw, decodeMulawSample, encodeMulaw, encodeMulawSample } from "./mulaw";

const FULL_SCALE = 32767;

function sine(freq: number, dbfs: number, samples = 8000, rate = 8000): Int16Array {
  const amplitude = FULL_SCALE * 10 ** (dbfs / 20);
  const out = new Int16Array(samples);
  // The phase offset keeps a 1 kHz tone at 8 kHz from landing on the same eight values every period.
  for (let i = 0; i < samples; i++) out[i] = Math.round(amplitude * Math.sin((2 * Math.PI * freq * i) / rate + 0.37));
  return out;
}

function snrDb(original: Int16Array, decoded: Int16Array): number {
  let signal = 0;
  let noise = 0;
  for (let i = 0; i < original.length; i++) {
    signal += original[i] ** 2;
    noise += (original[i] - decoded[i]) ** 2;
  }
  return 10 * Math.log10(signal / noise);
}

describe("µ-law codec", () => {
  it("encodes the known G.711 vectors", () => {
    expect(encodeMulawSample(0)).toBe(0xff);
    expect(encodeMulawSample(32767)).toBe(0x80);
    expect(encodeMulawSample(-32768)).toBe(0x00);
    expect(Array.from(encodeMulaw(Int16Array.of(0, 32767, -32768)))).toEqual([0xff, 0x80, 0x00]);
  });

  it("encodes silence to 0xFF", () => {
    expect(MULAW_SILENCE).toBe(0xff);
    expect(Array.from(encodeMulaw(new Int16Array(160)))).toEqual(new Array(160).fill(0xff));
  });

  it("decodes the known G.711 vectors", () => {
    // The same four values Python's audioop.ulaw2lin gives — the codec the reference client uses.
    expect(Array.from(decodeMulaw(Uint8Array.of(0x00, 0x80, 0xff, 0x7f)))).toEqual([-32124, 32124, 0, 0]);
    expect(decodeMulawSample(0xff)).toBe(0);
  });

  it("gives every byte back after decode then encode", () => {
    for (let byte = 0; byte < 256; byte++) {
      const expected = byte === 0x7f ? 0xff : byte; // 0x7F is "minus zero": it decodes to 0, and 0 encodes to 0xFF
      expect(encodeMulawSample(decodeMulawSample(byte))).toBe(expected);
    }
  });

  it("rises with the input: a louder sample never decodes quieter", () => {
    let previous = -Infinity;
    for (let sample = -32768; sample <= 32767; sample += 7) {
      const decoded = decodeMulawSample(encodeMulawSample(sample));
      expect(decoded).toBeGreaterThanOrEqual(previous);
      previous = decoded;
    }
  });

  it("keeps a 1 kHz sine within normal G.711 error across amplitudes", () => {
    for (const dbfs of [-3, -10, -20, -30]) {
      const original = sine(1000, dbfs);
      const snr = snrDb(original, decodeMulaw(encodeMulaw(original)));
      expect(snr, `SNR at ${dbfs} dBFS`).toBeGreaterThan(30);
    }
    // µ-law trades resolution for range: quiet speech keeps a usable ratio too.
    const quiet = sine(1000, -40);
    expect(snrDb(quiet, decodeMulaw(encodeMulaw(quiet))), "SNR at -40 dBFS").toBeGreaterThan(25);
  });

  it("never drifts by more than half a step of the loudest segment", () => {
    const original = sine(1004, -1);
    const decoded = decodeMulaw(encodeMulaw(original));
    for (let i = 0; i < original.length; i++) expect(Math.abs(original[i] - decoded[i])).toBeLessThanOrEqual(1024);
  });
});
