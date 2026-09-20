/**
 * G.711 µ-law (PCMU): the codec on the telephony wire — 8 kHz, one byte per sample.
 * Pure functions, no browser APIs: safe to import anywhere, tested in node.
 */

const BIAS = 0x84; // 132: added before the segment search so all eight segments share one shape
const CLIP = 32635; // the largest magnitude that still fits in 15 bits once the bias is added

/** The µ-law byte for digital silence (linear 0). A silent 20 ms frame is 160 of these. */
export const MULAW_SILENCE = 0xff;

/** One 16-bit linear sample (-32768..32767) to one µ-law byte. */
export function encodeMulawSample(sample: number): number {
  const sign = sample < 0 ? 0x80 : 0;
  let magnitude = sample < 0 ? -sample : sample;
  if (magnitude > CLIP) magnitude = CLIP;
  magnitude += BIAS; // now 132..32767: the highest set bit is bit 7..14
  const exponent = 24 - Math.clz32(magnitude); // the segment, 0..7
  const mantissa = (magnitude >> (exponent + 3)) & 0x0f;
  return ~(sign | (exponent << 4) | mantissa) & 0xff; // µ-law bytes travel inverted
}

/** One µ-law byte to one 16-bit linear sample (-32124..32124). */
export function decodeMulawSample(byte: number): number {
  const u = ~byte & 0xff;
  const exponent = (u >> 4) & 0x07;
  const mantissa = u & 0x0f;
  const magnitude = (((mantissa << 3) + BIAS) << exponent) - BIAS;
  return u & 0x80 ? -magnitude : magnitude;
}

const DECODE_TABLE = buildDecodeTable();

function buildDecodeTable(): Int16Array {
  const table = new Int16Array(256);
  for (let byte = 0; byte < 256; byte++) table[byte] = decodeMulawSample(byte);
  return table;
}

export function encodeMulaw(pcm: Int16Array): Uint8Array {
  const out = new Uint8Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) out[i] = encodeMulawSample(pcm[i]);
  return out;
}

export function decodeMulaw(mulaw: Uint8Array): Int16Array {
  const out = new Int16Array(mulaw.length);
  for (let i = 0; i < mulaw.length; i++) out[i] = DECODE_TABLE[mulaw[i]];
  return out;
}
