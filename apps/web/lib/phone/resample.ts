/**
 * Sample-rate conversion for the browser phone. Pure math, no browser APIs.
 *
 * Down (the caller's voice, native rate → 8 kHz): a windowed-sinc low-pass evaluated at each output
 * sample's fractional position in the source. One filter does both jobs — it removes what 8 kHz cannot
 * carry (so it does not fold back as noise) and it lands between source samples, so any ratio works:
 * 48000 → 8000 is 6, 44100 → 8000 is 5.5125.
 *
 * Up (the agent's voice, 8 kHz → native rate): linear interpolation.
 *
 * public/phone/capture-worklet.js and playback-worklet.js repeat this math in plain JS, because a
 * worklet cannot import TypeScript. worklets.test.ts holds the copies to this file.
 */

/** Middle of the roll-off (-6 dB) as a share of the target rate: 3800 Hz when the target is 8000. */
export const CUTOFF_OF_TARGET_RATE = 0.475;
/** Sinc lobes kept each side of the centre. Fourteen makes the roll-off about 1500 Hz wide (3.1 → 4.5 kHz). */
export const ZERO_CROSSINGS = 14;
/** Kernel rows per source sample; an output that lands between two rows blends them. */
export const KERNEL_PHASES = 32;

export interface ResampleKernel {
  /** Source samples the filter reaches on each side of an output sample's centre. */
  halfLen: number;
  /** Coefficients per output sample: 2 * halfLen. */
  taps: number;
  /** Rows per source sample. The table holds one more, so a blend never runs off the end. */
  phases: number;
  /** (phases + 1) rows of `taps` coefficients; every row sums to 1. */
  table: Float32Array;
}

export function buildKernel(fromRate: number, toRate: number): ResampleKernel {
  if (!(toRate > 0) || !(fromRate >= toRate)) {
    throw new RangeError(`cannot downsample ${fromRate} Hz to ${toRate} Hz`);
  }
  const cutoff = (CUTOFF_OF_TARGET_RATE * toRate) / fromRate; // cycles per source sample
  const halfLen = Math.ceil(ZERO_CROSSINGS / (2 * cutoff));
  const taps = 2 * halfLen;
  const table = new Float32Array((KERNEL_PHASES + 1) * taps);
  const row = new Float64Array(taps);
  for (let p = 0; p <= KERNEL_PHASES; p++) {
    const frac = p / KERNEL_PHASES;
    let sum = 0;
    for (let j = 0; j < taps; j++) {
      const t = j - halfLen + 1 - frac; // this tap's distance from the output's centre, in source samples
      const x = 2 * cutoff * t;
      const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x);
      // Blackman: it reaches exactly zero at the edges, so the kernel has no step where one row hands
      // over to the next source sample (a Hamming window leaves one, small but real).
      const w = (Math.PI * t) / halfLen;
      const blackman = 0.42 + 0.5 * Math.cos(w) + 0.08 * Math.cos(2 * w);
      row[j] = sinc * blackman;
      sum += row[j];
    }
    for (let j = 0; j < taps; j++) table[p * taps + j] = row[j] / sum; // unity gain at DC, whatever the phase
  }
  return { halfLen, taps, phases: KERNEL_PHASES, table };
}

/** Streaming downsampler: feed blocks of any size, get the output samples each block completes. */
export class Downsampler {
  /** Source samples per output sample. */
  readonly ratio: number;
  /** Source samples the output runs behind the input (1.9 ms at 48 kHz). */
  readonly latency: number;
  private readonly kernel: ResampleKernel;
  private buf: Float32Array;
  private len: number; // valid samples in buf
  private pos: number; // centre of the next output sample, in buf coordinates

  constructor(fromRate: number, toRate = 8000) {
    this.kernel = buildKernel(fromRate, toRate);
    this.ratio = fromRate / toRate;
    this.latency = this.kernel.halfLen;
    this.buf = new Float32Array(this.kernel.taps + 4096);
    // Leading zeros stand in for the past: the first output is centred on the first input sample.
    this.len = this.kernel.halfLen - 1;
    this.pos = this.kernel.halfLen - 1;
  }

  process(input: Float32Array): Float32Array {
    const { halfLen, taps, phases, table } = this.kernel;
    if (this.len + input.length > this.buf.length) {
      const grown = new Float32Array(this.len + input.length + 4096);
      grown.set(this.buf.subarray(0, this.len));
      this.buf = grown;
    }
    this.buf.set(input, this.len);
    this.len += input.length;

    const buf = this.buf;
    const ready = this.len - halfLen; // an output is complete once the filter's right edge has arrived
    const out = new Float32Array(Math.max(0, Math.ceil((ready - this.pos) / this.ratio)) + 1);
    let n = 0;
    let pos = this.pos;
    while (pos < ready) {
      const i0 = Math.floor(pos);
      const phase = (pos - i0) * phases;
      const p0 = Math.floor(phase);
      const blend = phase - p0;
      const rowA = p0 * taps;
      const rowB = rowA + taps;
      const start = i0 - halfLen + 1;
      let acc = 0;
      for (let j = 0; j < taps; j++) {
        const a = table[rowA + j];
        acc += buf[start + j] * (a + blend * (table[rowB + j] - a));
      }
      out[n++] = acc;
      pos += this.ratio;
    }

    // Forget the source samples no later output can reach.
    const keepFrom = Math.min(this.len, Math.max(0, Math.floor(pos) - halfLen + 1));
    buf.copyWithin(0, keepFrom, this.len);
    this.len -= keepFrom;
    this.pos = pos - keepFrom;
    return out.slice(0, n);
  }
}

/** One-shot downsample of a whole clip; the output has input.length * toRate / fromRate samples (±1). */
export function downsample(input: Float32Array, fromRate: number, toRate = 8000): Float32Array {
  const sampler = new Downsampler(fromRate, toRate);
  const head = sampler.process(input);
  const tail = sampler.process(new Float32Array(sampler.latency)); // zeros push the last real samples through
  const out = new Float32Array(head.length + tail.length);
  out.set(head);
  out.set(tail, head.length);
  return out;
}

/** One-shot linear-interpolation upsample; the output has input.length * toRate / fromRate samples. */
export function upsampleLinear(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (!(fromRate > 0) || !(toRate >= fromRate)) {
    throw new RangeError(`cannot upsample ${fromRate} Hz to ${toRate} Hz`);
  }
  const step = fromRate / toRate; // source samples per output sample, below 1
  const out = new Float32Array(Math.round(input.length / step));
  const last = input.length - 1;
  for (let i = 0; i < out.length; i++) {
    const pos = i * step;
    const i0 = Math.min(last, Math.floor(pos));
    const s0 = input[i0];
    const s1 = input[Math.min(last, i0 + 1)]; // past the end, hold the last sample
    out[i] = s0 + (s1 - s0) * (pos - i0);
  }
  return out;
}
