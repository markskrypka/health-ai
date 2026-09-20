import { describe, expect, it } from "vitest";

import { FRAME_SAMPLES, FrameAssembler, OutboundStream, base64ToBytes, bytesToBase64, newStreamSid, parseInbound } from "./wire";

describe("outbound messages — the shapes of apps/agent/scripts/local_call.py", () => {
  const stream = new OutboundStream({ callId: "call-42", fromNumber: "+34711330529", streamSid: "MZtest" });

  it("opens with `connected`", () => {
    expect(JSON.parse(stream.connected())).toEqual({ event: "connected", protocol: "Call", version: "1.0.0" });
  });

  it("then `start`, carrying the call id twice and the caller's number", () => {
    expect(JSON.parse(stream.start())).toEqual({
      event: "start",
      sequenceNumber: "1",
      streamSid: "MZtest",
      start: {
        accountSid: "AC-local",
        streamSid: "MZtest",
        callSid: "call-42",
        tracks: ["inbound"],
        mediaFormat: { encoding: "audio/x-mulaw", sampleRate: 8000, channels: 1 },
        customParameters: { call_id: "call-42", from_number: "+34711330529" },
      },
    });
  });

  it("then `media` frames that count up from 2, in 20 ms steps, all numbers as strings", () => {
    expect(JSON.parse(stream.media("AAAA"))).toEqual({
      event: "media",
      sequenceNumber: "2",
      streamSid: "MZtest",
      media: { track: "inbound", chunk: "1", timestamp: "0", payload: "AAAA" },
    });
    const second = JSON.parse(stream.media("BBBB"));
    expect(second.sequenceNumber).toBe("3");
    expect(second.media).toEqual({ track: "inbound", chunk: "2", timestamp: "20", payload: "BBBB" });
  });

  it("and closes with `stop`, which takes the next sequence number", () => {
    expect(JSON.parse(stream.stop())).toEqual({
      event: "stop",
      sequenceNumber: "4",
      streamSid: "MZtest",
      stop: { accountSid: "AC-local", callSid: "call-42" },
    });
  });
});

describe("customParameters", () => {
  const parametersOf = (stream: OutboundStream) => JSON.parse(stream.start()).start.customParameters;

  it("leaves from_number out when there is none", () => {
    expect(parametersOf(new OutboundStream({ callId: "c" }))).toEqual({ call_id: "c" });
    expect(parametersOf(new OutboundStream({ callId: "c", fromNumber: "" }))).toEqual({ call_id: "c" });
  });

  it("carries the extra parameters as they are", () => {
    const params = { screen: "1", prefill: '{"name":"Josefa"}', pipeline: "A" };
    expect(parametersOf(new OutboundStream({ callId: "c", fromNumber: "+34", params }))).toEqual({
      ...params,
      call_id: "c",
      from_number: "+34",
    });
  });

  it("does not let an extra parameter rename the call", () => {
    expect(parametersOf(new OutboundStream({ callId: "real", params: { call_id: "other" } })).call_id).toBe("real");
  });

  it("names a stream the way Twilio does", () => {
    expect(newStreamSid()).toMatch(/^MZ[0-9a-f]{32}$/);
    expect(newStreamSid()).not.toBe(newStreamSid());
  });
});

describe("base64", () => {
  it("round-trips every byte value", () => {
    const bytes = Uint8Array.from({ length: 256 }, (_, i) => i);
    expect(bytesToBase64(bytes)).toBe(Buffer.from(bytes).toString("base64"));
    expect(Array.from(base64ToBytes(bytesToBase64(bytes)))).toEqual(Array.from(bytes));
  });

  it("encodes a silent frame the way the reference client does", () => {
    const silence = new Uint8Array(FRAME_SAMPLES).fill(0xff);
    expect(bytesToBase64(silence)).toBe(Buffer.alloc(160, 0xff).toString("base64"));
  });
});

describe("inbound messages", () => {
  it("reads the agent's audio", () => {
    const payload = Buffer.from([0xff, 0x80, 0x00]).toString("base64");
    const event = parseInbound(JSON.stringify({ event: "media", streamSid: "MZ1", media: { payload } }));
    expect(event.kind).toBe("media");
    if (event.kind === "media") expect(Array.from(event.payload)).toEqual([0xff, 0x80, 0x00]);
  });

  it("reads `clear`", () => {
    expect(parseInbound(JSON.stringify({ event: "clear", streamSid: "MZ1" }))).toEqual({ kind: "clear" });
  });

  it("ignores `mark` and everything else it was not told about", () => {
    for (const data of [
      JSON.stringify({ event: "mark", mark: { name: "m1" } }),
      JSON.stringify({ event: "media" }),
      JSON.stringify({ event: "media", media: { payload: 7 } }),
      JSON.stringify({ event: "media", media: { payload: "not base64 !!" } }),
      JSON.stringify(["media"]),
      "null",
      "not json",
      new ArrayBuffer(4),
      undefined,
    ]) {
      expect(parseInbound(data)).toEqual({ kind: "ignored" });
    }
  });
});

describe("FrameAssembler", () => {
  it("cuts chunks of any size into exact 160-sample frames, in order, keeping the remainder", () => {
    const assembler = new FrameAssembler();
    const frames: Int16Array[] = [];
    let next = 0;
    for (const size of [21, 22, 21, 160, 1, 95, 400, 0, 80]) {
      const chunk = Int16Array.from({ length: size }, () => next++);
      assembler.push(chunk, (frame) => frames.push(frame));
    }
    expect(frames.length).toBe(Math.floor(800 / 160));
    expect(frames.every((frame) => frame.length === FRAME_SAMPLES)).toBe(true);
    expect(Array.from(frames.flatMap((frame) => Array.from(frame)))).toEqual(Array.from({ length: 800 }, (_, i) => i));
  });

  it("hands out frames that stay as they were when the next one is built", () => {
    const assembler = new FrameAssembler();
    const frames: Int16Array[] = [];
    assembler.push(new Int16Array(160).fill(1), (frame) => frames.push(frame));
    assembler.push(new Int16Array(160).fill(2), (frame) => frames.push(frame));
    expect(frames[0][0]).toBe(1);
    expect(frames[1][0]).toBe(2);
  });
});
