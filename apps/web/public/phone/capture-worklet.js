/* global AudioWorkletProcessor, registerProcessor, sampleRate */
/**
 * The caller's side of the browser phone, on the audio thread: audio at the context's native rate in,
 * 8 kHz 16-bit chunks of 20 ms out. lib/phone/index.ts µ-law encodes each chunk and sends it as one
 * `media` frame, so the audio clock — not a timer — paces the call.
 *
 * The resampling is a plain-JS copy of lib/phone/resample.ts (a worklet cannot import TypeScript):
 * a Blackman-windowed sinc low-pass evaluated at each output sample's fractional position in the source.
 * lib/phone/worklets.test.ts runs this file against that one. Change them together.
 */

const CUTOFF_OF_TARGET_RATE = 0.475;
const ZERO_CROSSINGS = 14;
const KERNEL_PHASES = 32;

function buildKernel(fromRate, toRate) {
  const cutoff = (CUTOFF_OF_TARGET_RATE * toRate) / fromRate; // cycles per source sample
  const halfLen = Math.ceil(ZERO_CROSSINGS / (2 * cutoff));
  const taps = 2 * halfLen;
  const table = new Float32Array((KERNEL_PHASES + 1) * taps);
  const row = new Float64Array(taps);
  for (let p = 0; p <= KERNEL_PHASES; p++) {
    const frac = p / KERNEL_PHASES;
    let sum = 0;
    for (let j = 0; j < taps; j++) {
      const t = j - halfLen + 1 - frac;
      const x = 2 * cutoff * t;
      const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x);
      const w = (Math.PI * t) / halfLen;
      const blackman = 0.42 + 0.5 * Math.cos(w) + 0.08 * Math.cos(2 * w);
      row[j] = sinc * blackman;
      sum += row[j];
    }
    for (let j = 0; j < taps; j++) table[p * taps + j] = row[j] / sum;
  }
  return { halfLen, taps, phases: KERNEL_PHASES, table };
}

class PhoneCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    const targetRate = opts.targetRate || 8000;
    this.chunkSamples = opts.chunkSamples || 160; // 20 ms at 8 kHz: one `media` frame
    this.ratio = sampleRate / targetRate;
    this.kernel = buildKernel(sampleRate, targetRate);
    this.buf = new Float32Array(this.kernel.taps + 8192);
    this.len = this.kernel.halfLen - 1; // leading zeros stand in for the past
    this.pos = this.kernel.halfLen - 1; // centre of the next output sample, in buf coordinates
    this.chunk = new Int16Array(this.chunkSamples);
    this.filled = 0;
    this.stopped = false;
    this.port.onmessage = (event) => {
      if (event.data && event.data.type === "stop") this.stopped = true;
    };
  }

  process(inputs, outputs) {
    if (this.stopped) return false;
    const channels = inputs[0];
    const block = channels && channels.length > 0 ? channels[0] : null;
    // No input (a clip that has ended, a microphone not connected yet) is silence, not a pause:
    // the line must keep carrying frames, because the server's voice detection needs a continuous stream.
    const blockLength = block ? block.length : outputs[0] && outputs[0][0] ? outputs[0][0].length : 128;

    if (this.len + blockLength > this.buf.length) {
      const grown = new Float32Array(this.len + blockLength + 8192);
      grown.set(this.buf.subarray(0, this.len));
      this.buf = grown;
    }
    if (block) this.buf.set(block, this.len);
    else this.buf.fill(0, this.len, this.len + blockLength);
    this.len += blockLength;

    const halfLen = this.kernel.halfLen;
    const taps = this.kernel.taps;
    const phases = this.kernel.phases;
    const table = this.kernel.table;
    const buf = this.buf;
    const ready = this.len - halfLen; // an output is complete once the filter's right edge has arrived
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
      this.emit(acc);
      pos += this.ratio;
    }

    const keepFrom = Math.min(this.len, Math.max(0, Math.floor(pos) - halfLen + 1));
    buf.copyWithin(0, keepFrom, this.len);
    this.len -= keepFrom;
    this.pos = pos - keepFrom;
    return true; // the output stays silent: the caller does not hear themselves
  }

  emit(sample) {
    const scaled = Math.round(sample * 32768);
    this.chunk[this.filled++] = scaled > 32767 ? 32767 : scaled < -32768 ? -32768 : scaled;
    if (this.filled === this.chunkSamples) {
      const full = this.chunk;
      this.port.postMessage({ type: "chunk", samples: full }, [full.buffer]);
      this.chunk = new Int16Array(this.chunkSamples);
      this.filled = 0;
    }
  }
}

registerProcessor("phone-capture", PhoneCaptureProcessor);
