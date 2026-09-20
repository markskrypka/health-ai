import { describe, expect, it } from "vitest";

import { Downsampler, buildKernel, downsample, upsampleLinear } from "./resample";

function tone(freq: number, rate: number, seconds = 1, amplitude = 0.5): Float32Array {
  const out = new Float32Array(Math.round(rate * seconds));
  for (let i = 0; i < out.length; i++) out[i] = amplitude * Math.sin((2 * Math.PI * freq * i) / rate);
  return out;
}

function zeroCrossings(x: Float32Array): number {
  let count = 0;
  for (let i = 1; i < x.length; i++) if (x[i - 1] < 0 !== x[i] < 0) count++;
  return count;
}

function rms(x: Float32Array): number {
  let sum = 0;
  for (const v of x) sum += v * v;
  return Math.sqrt(sum / x.length);
}

/** The steady middle of a clip: the filter's start and end ramps are left out of level measurements. */
function middle(x: Float32Array, margin = 200): Float32Array {
  return x.subarray(margin, x.length - margin);
}

const dB = (ratio: number) => 20 * Math.log10(ratio);

describe.each([48000, 44100])("downsample %i → 8000", (rate) => {
  it("gives the right number of samples", () => {
    const out = downsample(tone(440, rate), rate);
    expect(Math.abs(out.length - 8000)).toBeLessThanOrEqual(1);
    const short = downsample(tone(440, rate, 0.02), rate); // one 20 ms block
    expect(Math.abs(short.length - 160)).toBeLessThanOrEqual(1);
  });

  it("keeps a 440 Hz sine at 440 Hz and at its amplitude", () => {
    const out = downsample(tone(440, rate), rate);
    expect(Math.abs(zeroCrossings(out) - 880)).toBeLessThanOrEqual(2); // one second: two crossings a cycle
    const amplitude = rms(middle(out)) * Math.SQRT2;
    expect(amplitude).toBeGreaterThan(0.49);
    expect(amplitude).toBeLessThan(0.51);
  });

  it("strongly attenuates a 6 kHz tone, which 8 kHz cannot carry", () => {
    const source = tone(6000, rate);
    const out = downsample(source, rate);
    expect(dB(rms(middle(out)) / rms(source)), "6 kHz, dB").toBeLessThan(-40);
  });

  it("attenuates everything that would fold into the speech band", () => {
    // f above 4 kHz lands on 8000 - f: from 4.6 kHz up, that is inside 0–3.4 kHz.
    for (const freq of [4600, 5000, 7000, 7600, 9000, 12000, 15000]) {
      const source = tone(freq, rate);
      expect(dB(rms(middle(downsample(source, rate))) / rms(source)), `${freq} Hz, dB`).toBeLessThan(-40);
    }
  });

  it("passes the telephone band nearly untouched", () => {
    for (const freq of [300, 1000, 2000, 3000]) {
      const source = tone(freq, rate);
      const gain = dB(rms(middle(downsample(source, rate))) / rms(source));
      expect(Math.abs(gain), `${freq} Hz, dB`).toBeLessThan(0.5);
    }
  });

  it("has unity gain at DC, wherever an output lands between source samples", () => {
    const out = middle(downsample(new Float32Array(rate / 10).fill(0.25), rate), 40);
    for (const v of out) expect(Math.abs(v - 0.25)).toBeLessThan(1e-5);
  });

  it("gives the same samples in 128-sample blocks as in one piece", () => {
    const source = tone(440, rate, 0.25);
    const whole = downsample(source, rate);
    const sampler = new Downsampler(rate);
    const pieces: number[] = [];
    for (let i = 0; i < source.length; i += 128) pieces.push(...sampler.process(source.subarray(i, i + 128)));
    expect(pieces.length).toBeGreaterThan(whole.length - 20); // the streamed copy was not flushed
    for (let i = 0; i < pieces.length; i++) expect(Math.abs(pieces[i] - whole[i])).toBeLessThan(1e-6);
  });

  it("starts in time: the first output sample is the first input sample", () => {
    const click = new Float32Array(rate / 10);
    click[0] = 1;
    const out = downsample(click, rate);
    let peak = 0;
    for (let i = 1; i < out.length; i++) if (Math.abs(out[i]) > Math.abs(out[peak])) peak = i;
    expect(peak).toBe(0);
  });
});

describe("the kernel", () => {
  it("reaches fourteen lobes each side, whatever the source rate", () => {
    expect(buildKernel(48000, 8000).taps).toBe(178);
    expect(buildKernel(44100, 8000).taps).toBe(164);
  });

  it("closes at zero, so one row hands over to the next without a step", () => {
    const { taps, phases, table } = buildKernel(44100, 8000);
    // The last row is the first row one source sample later: same numbers, shifted by one tap.
    for (let j = 1; j < taps; j++) expect(table[phases * taps + j]).toBeCloseTo(table[j - 1], 7);
    expect(Math.abs(table[phases * taps])).toBeLessThan(1e-7);
    expect(Math.abs(table[taps - 1])).toBeLessThan(1e-7);
  });

  it("refuses to upsample", () => {
    expect(() => buildKernel(4000, 8000)).toThrow(RangeError);
  });
});

describe.each([48000, 44100])("upsampleLinear 8000 → %i", (rate) => {
  it("gives the right number of samples", () => {
    expect(upsampleLinear(tone(440, 8000), 8000, rate).length).toBe(rate);
  });

  it("keeps a 440 Hz sine at 440 Hz and roughly at its amplitude", () => {
    const out = upsampleLinear(tone(440, 8000), 8000, rate);
    expect(Math.abs(zeroCrossings(out) - 880)).toBeLessThanOrEqual(2);
    const amplitude = rms(middle(out)) * Math.SQRT2;
    expect(amplitude).toBeGreaterThan(0.48); // straight lines between samples shave a little off the peaks
    expect(amplitude).toBeLessThan(0.5);
  });

  it("passes through the source samples themselves", () => {
    const source = tone(1000, 8000, 0.05);
    const out = upsampleLinear(source, 8000, 48000);
    for (let i = 0; i < source.length; i++) expect(out[i * 6]).toBeCloseTo(source[i], 6);
  });
});
