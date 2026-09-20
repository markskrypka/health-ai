/* global AudioWorkletProcessor, registerProcessor, sampleRate */
/**
 * The agent's side of the browser phone, on the audio thread: 8 kHz samples in by message, audio at
 * the context's native rate out (linear interpolation, the same math as upsampleLinear in
 * lib/phone/resample.ts). lib/phone/worklets.test.ts runs this file.
 *
 * The server sends the agent's voice at up to twice real time, so whole sentences wait here: the ring
 * starts at a minute and grows. That is also why `clear` matters — when the caller interrupts, seconds
 * of queued speech must go at once.
 *
 * Messages in:   { type: "push", samples: Int16Array }   agent audio, 8 kHz
 *                { type: "clear" }                       barge-in: empty the ring now
 *                { type: "drain" }                       no more audio is coming: play what is left, then say so
 *                { type: "stop" }                        the call is over: let the node be collected
 * Messages out:  { type: "level", rms, buffered, playing, underruns }   about 15 a second
 *                { type: "drained" }                                    once, after `drain`, when the ring is empty
 */

const MAX_BUFFERED_SECONDS = 600;

class PhonePlaybackProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.sourceRate = opts.sourceRate || 8000;
    const jitterMs = typeof opts.jitterMs === "number" ? opts.jitterMs : 80;
    this.step = this.sourceRate / sampleRate; // source samples per output sample, below 1
    this.startThreshold = Math.max(2, Math.round((this.sourceRate * jitterMs) / 1000));
    this.flushAfterFrames = Math.round(sampleRate * 0.12); // a tail shorter than the threshold still gets played
    this.capacity = this.sourceRate * 60;
    this.ring = new Float32Array(this.capacity);
    this.readIdx = 0;
    this.count = 0; // samples waiting in the ring
    this.frac = 0; // position between ring[readIdx] and the sample after it
    this.playing = false;
    this.draining = false;
    this.drainedSent = false;
    this.stopped = false;
    this.idleFrames = 0; // output frames since the last push
    this.underruns = 0;
    this.held = 0; // the last value sent out: it fades, so a cut never leaves a step
    this.decay = Math.exp(-1 / (0.002 * sampleRate)); // 2 ms
    this.reportEvery = Math.round(sampleRate / 15);
    this.sumSquares = 0;
    this.framesSinceReport = 0;
    this.port.onmessage = (event) => this.onMessage(event.data);
  }

  onMessage(message) {
    if (!message) return;
    if (message.type === "push" && message.samples) this.push(message.samples);
    else if (message.type === "clear") this.clear();
    else if (message.type === "drain") this.draining = true;
    else if (message.type === "stop") this.stopped = true;
  }

  push(samples) {
    const incoming = samples.length;
    if (this.count + incoming > this.capacity) this.grow(this.count + incoming);
    const room = this.capacity - this.count;
    const take = incoming < room ? incoming : room; // past ten minutes queued, the newest is dropped
    let write = (this.readIdx + this.count) % this.capacity;
    for (let i = 0; i < take; i++) {
      this.ring[write] = samples[i] / 32768;
      write = write + 1 === this.capacity ? 0 : write + 1;
    }
    this.count += take;
    this.idleFrames = 0;
  }

  grow(needed) {
    const limit = this.sourceRate * MAX_BUFFERED_SECONDS;
    let capacity = this.capacity;
    while (capacity < needed && capacity < limit) capacity *= 2;
    if (capacity > limit) capacity = limit;
    if (capacity === this.capacity) return;
    const ring = new Float32Array(capacity);
    for (let i = 0; i < this.count; i++) ring[i] = this.ring[(this.readIdx + i) % this.capacity];
    this.ring = ring;
    this.capacity = capacity;
    this.readIdx = 0;
  }

  clear() {
    this.readIdx = 0;
    this.count = 0;
    this.frac = 0;
    this.playing = false; // the next sentence builds its own jitter buffer
  }

  process(inputs, outputs) {
    if (this.stopped) return false;
    const out = outputs[0] && outputs[0][0];
    if (!out) return true;
    const frames = out.length;

    // Start (or start again after running dry) only with a little audio in hand, so network jitter does
    // not turn into a stutter. A tail too short to reach the threshold is played once nothing more comes.
    if (!this.playing && this.count >= 2) {
      if (this.count >= this.startThreshold || this.draining || this.idleFrames >= this.flushAfterFrames) {
        this.playing = true;
        this.frac = 0;
      }
    }

    const ring = this.ring;
    const capacity = this.capacity;
    for (let i = 0; i < frames; i++) {
      let value;
      if (this.playing && this.count >= 2) {
        const s0 = ring[this.readIdx];
        const next = this.readIdx + 1 === capacity ? 0 : this.readIdx + 1;
        value = s0 + (ring[next] - s0) * this.frac;
        this.frac += this.step;
        while (this.frac >= 1 && this.count > 0) {
          this.frac -= 1;
          this.readIdx = this.readIdx + 1 === capacity ? 0 : this.readIdx + 1;
          this.count -= 1;
        }
      } else {
        if (this.playing) {
          // Ran dry: silence until the jitter buffer has filled again — never a loop of old audio.
          this.playing = false;
          this.underruns += 1;
          this.count = 0; // one sample cannot be interpolated; an eight-thousandth of a second goes
          this.frac = 0;
        }
        value = this.held * this.decay;
        if (value < 1e-5 && value > -1e-5) value = 0;
      }
      this.held = value;
      out[i] = value;
      this.sumSquares += value * value;
    }
    for (let c = 1; c < outputs[0].length; c++) outputs[0][c].set(out);

    this.idleFrames += frames;
    this.framesSinceReport += frames;
    if (this.framesSinceReport >= this.reportEvery) {
      this.port.postMessage({
        type: "level",
        rms: Math.sqrt(this.sumSquares / this.framesSinceReport),
        buffered: this.count,
        playing: this.playing,
        underruns: this.underruns,
      });
      this.sumSquares = 0;
      this.framesSinceReport = 0;
    }
    if (this.draining && !this.drainedSent && !this.playing && this.count < 2) {
      this.drainedSent = true;
      this.port.postMessage({ type: "drained" });
    }
    return true;
  }
}

registerProcessor("phone-playback", PhonePlaybackProcessor);
