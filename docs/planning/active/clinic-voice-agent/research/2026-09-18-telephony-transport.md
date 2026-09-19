# Telephony and transport ingress beyond Twilio

Date: 2026-09-18 (Fri) · research probe, ~20 min timebox · Status: recommendation ready, gaps listed.
Legend: **[V]** verified, primary source fetched today · **[S]** strong, primary doc quoted via search snippet or several credible secondary sources · **[I]** inferred, reasoning or background knowledge not checked today.

## Question
How should calls reach our agent without defaulting to Twilio, while the harness contract is unknown?

## Decision it informs
The ingress layer per possible contract: (a) PSTN number, (b) SIP URI, (c) WebSocket audio, (d) WebRTC, plus a jury-demo fallback. Lead's update folded in: TypeScript/Node-first, Gemini Live preferred (OpenAI key available), own the orchestration, team not registered yet.

## Findings

### F1. Account gates on brand-new accounts decide more than features
1. **Twilio.** Trial: verified numbers only, sign-up country only, "some TwiML verbs are blocked during trial", 30-day expiry [V: twilio.com/docs/usage/trials]; trial message before connect and max 4 concurrent calls (another source says 5) [S: help.twilio.com/articles/360036052753]. Upgraded accounts "lacking an approved Primary Customer Profile" keep limited concurrency, inbound counted, number unpublished [V: twilio.com/docs/api/errors/10004]. "Ten at once" can fail at the carrier on a fresh Twilio account.
2. **Telnyx.** L1 accounts created after 2025-03-24 may order only LOCAL numbers in the account's own country [V: support.telnyx.com/en/articles/10715715]. L2 needs payment method + company name + phone, "up to 48 hours" [V: support.telnyx.com/en/articles/1130595-account-verification]. Outbound concurrency 2, then 10 at L2; inbound cap undocumented [V: developers.telnyx.com/docs/voice/sip-trunking/configuration/concurrent-limits]. A new Spanish account cannot buy a US/UK number before L2, and the Spanish number it can buy needs ~72 h of document validation (F6).
3. **SignalWire.** Trial ends with card + $5 top-up; in trial: calls only to/from verified numbers, 2 numbers, no SIP Domain App traffic [S: signalwire.com/docs/platform/trial-mode]. Post-trial concurrency not documented; 1 CPS outbound [S: developer.signalwire.com/guides/signalwire-rate-limits].
4. **Plivo.** Concurrent calls outside India: "No limit"; inbound 10 CPS, outbound 2 CPS [V: plivo.com/docs/voice/concepts/account-limits]. Trial credits never expire; trial outbound only to sandboxed numbers; trial inbound rules not found [S: support.plivo.com].
5. **Vonage.** Trial accounts "do not support inbound voice calls" and cannot buy numbers with the EUR 2 credit; after upgrade no concurrency cap, 3 CPS [S: api.support.vonage.com articles 212554438, 204015303].
6. **jambonz.** Cloud free 3-week trial [S: docs.jambonz.org deployment-options]; pricing page: trial licence "up to 10 concurrent sessions", cloud $8/session/month for 5–249 [V: jambonz.org/pricing]. Exactly 10 means zero headroom; unclear whether that cap is the cloud trial or the self-hosted licence.
7. **LiveKit Cloud Build (free).** The 5-concurrent-agent cap applies only to LiveKit-hosted agents; 100 participants, 1,000 third-party SIP minutes, 50 US-inbound minutes, hard caps with no overage [V: docs.livekit.io/deploy/admin/quotas-and-limits]. LiveKit Phone Numbers are US only [S: livekit.com/products/livekit-phone-numbers].
8. **Daily.** Numbers +1 (US/CA) only; static SIP URI + pinless dial-in webhook; ~$0.018–0.03/min [S: docs.daily.co/guides/products/dial-in-dial-out].

### F2. Media-stream API: codec to the WebSocket, barge-in, DTMF
- **Twilio**: `audio/x-mulaw` 8 kHz only, both directions; `clear` and `mark`; Media Streams available in IE1 Dublin [S: twilio.com/docs/voice/media-streams/websocket-messages].
- **Telnyx**: bidirectional RTP mode with PCMU, PCMA, G722, OPUS 8/16k, AMR-WB 8/16k, L16 16k via `stream_bidirectional_mode:"rtp"` + `stream_bidirectional_codec`; events connected/start/media/stop/mark/dtmf/clear/error; chunks 20 ms–30 s; one bidirectional stream per call; DTMF may arrive out of order [V: developers.telnyx.com/docs/voice/programmable-voice/media-streaming].
- **SignalWire** cXML `<Stream codec=...>`: PCMU@8000h (default), L16@16000h, L16@24000h; Twilio-compatible messages, outbound media/mark/clear/dtmf; `realtime` attribute; wss only, mono only [V: signalwire.com/docs/compatibility-api/cxml/reference/voice/stream.md].
- **Plivo** `<Stream bidirectional="true" contentType=...>`: audio/x-l16 at 8k/16k (page also lists 24k), audio/x-mulaw 8k [V: plivo.com/docs/voice/xml/audio-streaming]. Events in: start, media, dtmf, playedStream, clearedAudio; out: playAudio, checkpoint, clearAudio, sendDTMF [S: plivo.com/docs/voice-agents/audio-streaming/concepts/audio-streaming-guide].
- **Vonage**: raw BINARY L16 frames at 8/16/24 kHz (~20 ms), JSON text for control; `clear` flushes, `notify` marks; DTMF as `websocket:dtmf`; buffer ~60 s [V: developer.vonage.com/en/voice/voice-api/concepts/websockets].
- **jambonz** `listen`: L16 binary at 8/16/24/48/64 kHz, `bidirectionalAudio{enabled,streaming,sampleRate}`, `playAudio` (max 10 queued), `killAudio`, `mark`/`clearMarks`, `passDtmf` [V: docs.jambonz.org/verbs/verbs/listen].
- **Asterisk `chan_websocket`**: codec-agnostic (slin16, G.722, Opus), in 20.16 / 21.11 / 22.6 / 23.0+, JSON control from 20.18 / 22.8 / 23.2 [S: docs.asterisk.org/Configuration/Channel-Drivers/WebSocket].
- Sinch `connectStream` is closed beta; Infobip Calls API and Bandwidth BXML offer bidirectional WS streaming but onboarding is enterprise-style [S/I].

### F3. Wideband: what it really buys
[I] PSTN legs are G.711 narrowband. L16 16/24 kHz on the WebSocket is upsampled 8 kHz audio: no new information for STT, but no mu-law or resampling code and no extra quantization on our side. True wideband exists only when the caller arrives over SIP/WebRTC with G.722/Opus (cases b/d, browser demo). Telnyx, jambonz, Asterisk and LiveKit carry it end to end; Twilio Media Streams always collapses to mu-law 8k.

### F4. Bridging to Gemini Live and OpenAI Realtime from Node
- **Gemini Live**: raw PCM16 little-endian, natively 16 kHz, but "any sample rate can be sent" when declared in the MIME type (`audio/pcm;rate=24000`); output always 24 kHz; languages include es, ca, gl, eu; VAD interruption cancels generation and notifies; audio sessions 15 min [V: ai.google.dev/gemini-api/docs/live-guide]. Model ids shown there today, as extracted by the fetch tool (confirm with the model probe): `gemini-3.8-live`, `gemini-3.1-flash-live-preview` (legacy).
- **Zero-DSP pattern** [I from V facts]: choose a 24 kHz L16 ingress (SignalWire `L16@24000h`, Vonage `rate=24000`, jambonz `sampleRate: 24000`), forward caller audio as `audio/pcm;rate=24000`, pipe Gemini's 24 kHz output straight back. With 16 kHz ingress (Telnyx, Plivo) input is direct and output needs 24k to 16k (3:2). With Twilio: mu-law decode, send as `audio/pcm;rate=8000`, output 24k to 8k + mu-law encode.
- **Node DSP when needed** [I]: mu-law via a 256-entry lookup table or `alawmulaw`; streaming resampler `@alexanderolsen/libsamplerate-js` or `speex-resampler` (WASM). Always low-pass before 3:1 decimation; dropping samples aliases and the jury will hear it. `wavefile` resamples offline only; `@tw2gem/audio-converter` is a small Twilio-to-Gemini helper [S: npm]. TS reference bridge: github.com/rohitcoding1991/twilio-gemini-caller [S].
- **Barge-in wiring** [I]: Gemini `serverContent.interrupted` triggers the provider flush (`clear` / `clearAudio` / `killAudio`). Use `mark` / `checkpoint` / `notify` acks to know what the caller actually heard and truncate agent state to that point; this matters for literal scoring.
- **OpenAI Realtime over WS** accepts `audio/pcmu`, `audio/pcma`, or `audio/pcm` at 24 kHz only [S: OpenAI API reference]. Twilio mu-law passes untouched; 24 kHz L16 ingress passes untouched too.
- **OpenAI native SIP**: `sip:$PROJECT_ID@sip.api.openai.com;transport=tls`, webhook `realtime.call.incoming`, REST accept/reject/refer/hangup, sideband `wss://.../v1/realtime?call_id=` for tools [S: developers.openai.com/api/docs/guides/realtime-sip returned 404 to the fetcher; V on the Azure mirror learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-sip, which adds EU endpoint `swedencentral.sip.ai.azure.com` and models up to `gpt-realtime-2` 2026-05-07]. Counter-evidence: inbound SIP rejected with 400 "Invalid SDP offer" before webhook dispatch for ~9 h on 2026-05-13, similar ~1-day incident in late March 2026 [V: community.openai.com/t/1380763]; open thread on calls cut at ~30 s with a silent sideband [S: community.openai.com/t/1393596].
- Gemini Live native SIP/PSTN ingress: not found [I]. Voximplant ships native Gemini Live and OpenAI Realtime clients inside VoxEngine (serverless JS) [S: voximplant.com/products/gemini-client]; orchestration would live in their runtime; numbers/KYC not checked.

### F5. How the frameworks plug in
- **Pipecat** (v1.5.0, Python only): serializers for Twilio, Telnyx, Plivo, Vonage, Exotel, Genesys, plus Daily PSTN/SIP and SmallWebRTC [S: docs.pipecat.ai/pipecat-cloud/guides/telephony/overview, GitHub releases]. Recent serializer bugs: Telnyx drops OutputTransportMessageFrame (#5840), malformed WS message crashes the call (#5816), Telnyx L16 unsupported (#3383). Not a fit for a TS team.
- **LiveKit**: SIP bridge accepts any trunk (Twilio, Telnyx, Plivo, Wavix); agents-js (Node) has `@livekit/agents-plugin-google` realtime [S]. Counter-evidence: 5–8 s latency report for Gemini realtime over SIP (self-hosted) and a Telnyx to LiveKit Cloud Frankfurt trunk-match 404 thread [S: community.livekit.io/t/238, /t/1164].
- **jambonz**: BYO carrier or direct SIP; first-class Node SDKs; it packages drachtio + FreeSWITCH + rtpengine, so assembling those raw in 36 h is wasted effort [I].
- **Cloudflare Realtime / RealtimeKit**: no SIP or PSTN; a phone call needs Twilio/Telnyx in front [S]. Useful as host (Workers + Durable Objects WS) or `cloudflared` tunnel only.

### F6. Spanish +34 numbers are not a weekend item
- Telnyx: ID/passport (any EU state) + address matching the DID area code + proof of address under 3 months; end user physically in Spain; ~72 h validation [V: support.telnyx.com/en/articles/1311073].
- Twilio: Spanish fiscal ID (DNI/NIF/NIE/CIF) + ID + address in Spain (local: inside the prefix region); review time unstated [V: twilio.com/en-us/guidelines/es/regulatory]. UK numbers also need ID + a UK address [V: twilio.com/en-us/guidelines/gb/regulatory]. DIDWW lists Spain as registration-required [S]. Zadarma, DIDWW and Voxbone (now Bandwidth) sell SIP DIDs with no media-stream API, so they still need jambonz/Asterisk behind them [I].
- [I] A +34 number is not needed for scoring; the harness can dial any E.164 number, or none. It matters only if jurors dial from Spanish mobiles; cover that with the browser path plus a US number.

### F7. EU media PoPs
Telnyx anchors media in Frankfurt, Amsterdam, Paris, London [S: telnyx.com/europe]; Twilio Media Streams run in IE1 Dublin [S]; LiveKit Cloud has Frankfurt and SIP region pinning [S]; Azure OpenAI SIP in swedencentral [V]. Regions for OpenAI SIP, SignalWire, Plivo, Vonage, jambonz cloud: not found. [I] Madrid to FRA/PAR/DUB is ~25–40 ms RTT, Madrid to US-East ~90–110 ms; the harness location is unknown and may dominate.

### F8. "Terrible line": causes and what transport can do
[I] Causes: G.711 band-limit 300–3400 Hz (fricatives, names, digits suffer); low-bitrate mobile AMR-NB; tandem transcoding (AMR/EVS to G.711 to L16/Opus); G.729 on cheap international transit; packet loss and jitter on Wi-Fi-calling or internet SIP legs (20 ms frames; PLC hides up to ~60 ms, bursts eat syllables); speakerphone echo causing false barge-in. The harness most likely bakes noise, band-limit and dropouts into the source audio, so transport cannot undo it.
What we control: (1) add no damage: one transcode at most, bridge server in the provider's media region, 20 ms pacing; (2) provider WebSockets are TCP and the provider already ran jitter buffer + PLC on the RTP leg, so we see delay bursts, not gaps; time out on silence, not on frame gaps; (3) barge-in gate: require 200–300 ms of speech before flushing, tune Live API activity-detection sensitivity; (4) comfort noise or a short filler while tools run, because dead air on a bad line reads as a dropped call; (5) DTMF fallback for digits, since every shortlisted provider delivers DTMF on the WS; (6) denoise (RNNoise WASM) only after an A/B on practice cases, it can hurt narrowband STT; (7) rehearse with a line simulator: `ffmpeg -af "highpass=f=300,lowpass=f=3400" -ar 8000 -c:a pcm_mulaw` plus random 20–60 ms frame drops and babble noise. On SIP/WebRTC paths (jambonz, Asterisk, LiveKit) jitter buffer, PLC and Opus FEC come with the media server; do not hand-roll RTP in Node.

### F9. Transfer and recording
Transfer: OpenAI `POST /v1/realtime/calls/{id}/refer` with a `tel:` or `sip:` target [V, Azure mirror]; Telnyx transfer/REFER, Twilio/SignalWire/Plivo `<Dial>`, Vonage NCCO transfer, jambonz `dial` / `sip:refer`, LiveKit TransferSIPParticipant [I]. Scoring probably reads the reported outcome, not a real transfer; a warm transfer is a jury nicety. Recording [I]: both PCM directions already pass through our Node bridge, so write a stereo WAV + JSONL event log ourselves (provider-agnostic, feeds the observability criterion); provider dual-channel recording as backup.

## Comparison table

| Option | Number this weekend | New-account gate / 10 concurrent | Codec to our WS (bidirectional) | Barge-in / DTMF | EU media | Node fit | Verdict |
|---|---|---|---|---|---|---|---|
| Twilio (baseline) | US instant after upgrade; ES/UK need docs [V] | limited concurrency until Primary Customer Profile approved [V] | mu-law 8k only [S] | clear, mark, dtmf [S] | IE1 Dublin [S] | official SDK, most TS examples | only with an aged, profile-approved account |
| Telnyx | blocked for new non-US L1 accounts until L2, up to 48 h [V] | inbound cap undocumented; outbound 2 then 10 [V] | PCMU, PCMA, G722, OPUS, AMR-WB, L16 16k [V] | clear, mark, dtmf [V] | FRA/AMS/PAR/LON [S] | official SDK + WebRTC softphone SDK | technically best; gated by L2, apply tonight |
| SignalWire | US instant after $5 [S] | post-trial cap not found | PCMU 8k, L16 16k/24k [V] | clear, mark, dtmf both ways [V] | not found | Twilio-compatible cXML, Twilio TS examples port | runner-up; 24k means zero DSP |
| Plivo | US after upgrade [I] | "No limit" concurrent, 10 CPS inbound [V] | L16 8/16k (24k listed), mu-law [V] | clearAudio, checkpoint, dtmf [S] | not verified | official SDK | first choice for PSTN on a new account |
| Vonage | after upgrade; trial has no inbound [S] | no cap, 3 CPS [S] | raw binary L16 8/16/24k [V] | clear, notify, dtmf [V] | regional endpoints [I] | official SDK, cleanest WS framing | runner-up alternative |
| jambonz cloud | none needed (SIP URI) or BYO carrier | trial "up to 10 sessions"; $8/session [V] | L16 8–64k binary [V] | killAudio, mark, passDtmf [V] | region not stated | first-class Node SDKs | first choice for SIP |
| LiveKit SIP + agents-js | US number only [S]; SIP URI free | self-hosted agents uncapped; 1,000 SIP min hard cap [V] | Opus inside the framework | framework-managed | Frankfurt [S] | Node agents SDK + Google realtime plugin | runner-up for SIP; pick for LiveKit-based contracts |
| OpenAI native SIP | none (SIP URI); trunk for PSTN | session limits not checked | PCMU/PCMA on SIP leg [S] | model VAD; refer/hangup REST [V mirror] | US; Azure swedencentral [V] | webhook + WS, trivial | 30-minute emergency path; outages Mar + May 2026 [V] |
| Daily PSTN/SIP | +1 only [S] | hundreds of calls per number [S] | WebRTC | n/a | n/a | server side is Python | avoid for a TS team |
| Asterisk 22.6+/23 self-host | none (SIP URI) | your own VM | slin16, G.722, Opus [S] | app-controlled | any EU VM | plain `ws` | zero-KYC fallback; 2–4 h ops cost [I] |
| Voximplant | not checked | not checked | native Gemini/OpenAI clients [S] | n/a | not checked | VoxEngine JS, their runtime | conflicts with owning orchestration |
| Bandwidth (+Voxbone), Sinch, Infobip | enterprise onboarding [I]; Sinch streaming closed beta [S] | n/a | n/a | n/a | n/a | n/a | avoid this weekend |
| Zadarma, DIDWW | ES docs required [S/I] | n/a | SIP only, no WS API [I] | n/a | EU | needs jambonz/Asterisk | only if someone already owns a number there |
| Cloudflare Realtime | no SIP/PSTN [S] | n/a | n/a | n/a | n/a | n/a | hosting or tunnel only |
| drachtio / FreeSWITCH raw | n/a | n/a | n/a | n/a | n/a | drachtio-srf | avoid; jambonz packages it |

## Recommendation per harness-contract case

Architecture for all cases [I]: one Node `CallSession` core (PCM16 in at a declared rate, Gemini Live, PCM16 24 kHz out, flush + heard-position events) with thin ingress adapters (~60 lines each): Twilio-dialect JSON/base64, Plivo dialect, raw binary PCM (Vonage, jambonz, browser), and whatever the starter kit defines. This makes the unknown contract cheap.

**(a) PSTN number**
- Step 0: ask the team for any EXISTING verified CPaaS account (aged Twilio with approved profile, Telnyx L2). Account age beats provider choice [I].
- First choice on new accounts: **Plivo**. It is the only shortlisted provider documenting no concurrency cap plus 10 CPS inbound [V], with L16 16 kHz bidirectional, clearAudio/checkpoint and an official Node SDK.
- Runner-up: **SignalWire** (Twilio-compatible cXML, `L16@24000h` is zero-DSP with Gemini and OpenAI, $5 exits trial) or **Vonage** (binary 24 kHz, no cap after upgrade). Open both; keep one as a hot spare.
- In parallel: submit **Telnyx L2** tonight. If it clears, move: EU PoPs, cheapest, real wideband on SIP legs.
- Avoid: a fresh Twilio account for the 10-call case (documented limited concurrency, trial banner, blocked verbs); Twilio ConversationRelay (managed STT/TTS with its own concurrency error 64109) since the team owns orchestration; any +34 plan; Daily or LiveKit numbers (US only, and they add a framework).
- Must do the same night: a 10-parallel inbound test originated from a DIFFERENT account, because own-account outbound legs count toward the same cap and are CPS-limited.

**(b) SIP URI**
- First choice: **jambonz cloud**. Hand the harness the account SIP realm; `listen` at 24 kHz L16 binary into the same Node bridge; G.722/Opus if the harness offers it; no number, no KYC. Check the trial session cap at signup; buy 12 sessions (~$96) if capped at 10.
- Runner-up: the SIP domain of whichever CPaaS account is already live (Telnyx SIP subdomain is best: G722/OPUS/L16; a Twilio SIP Domain still yields mu-law only) [I], or **LiveKit Cloud SIP + agents-js** if the team accepts a framework for transport.
- Emergency, checkpoint in 30 minutes: **OpenAI native SIP** URI + webhook + sideband WS tools. Costs: not Gemini, US media, TLS-only, two outages in 2026.
- Zero-KYC fallback: Asterisk 22.6+/23 `chan_websocket` on an EU VM, SIP locked to the harness IPs.
- Avoid: a raw drachtio/FreeSWITCH build; Daily (Python).

**(c) WebSocket audio endpoint**
- First choice: no telephony vendor. One Node process (`ws` + `@google/genai`), wire adapter written after reading the starter kit (expect a Twilio-Media-Streams-like JSON/base64 mu-law 8k dialect [I]). Host in the harness's region; `cloudflared tunnel` for the dev loop.
- Runner-up host: Cloudflare Workers + Durable Objects (sponsor) once the plain Node version works.
- Avoid: serverless functions that cannot hold long-lived WebSockets; inserting a CPaaS; assuming 10 parallel Gemini Live sessions are allowed on the key (quota check belongs to the model probe).

**(d) WebRTC**
- If the starter kit is built on LiveKit: agents-js (Node). Here the platform is dictated, so this is evidence, not a popularity default. If built on Daily: server SDKs are Python in practice; keep a thin Python transport that calls the Node orchestrator, or use Pipecat for transport only.
- If raw SDP offer/answer: `werift` (pure TS) or `@roamhq/wrtc` [I, not verified today]; timebox 3 h, then terminate WebRTC on LiveKit Cloud instead.
- Avoid: a hand-rolled jitter buffer or Opus pipeline in Node.

**Jury-demo fallback (all cases)**
1. Browser "Call the clinic" page: getUserMedia, AudioWorklet, PCM16 16 kHz over WSS into the same bridge. True wideband, no carrier, works on any juror laptop or phone; add the line-simulator toggle to show robustness.
2. The provider's browser softphone SDK (Telnyx WebRTC, Plivo Browser, SignalWire, Twilio Voice JS) to exercise the real telephony path without PSTN cost [I].
3. A US PSTN number for a literal phone call, printed on the demo page. Keep two ingress paths live on Sunday.

## Hackathon fast-path: working inbound call in under 2 hours
- 0:00 (person B, parallel): open Plivo, SignalWire, jambonz cloud and Telnyx accounts; add a card; submit Telnyx L2; buy a US number on the first account that allows it. Ask the organizers whether a number is needed at all.
- 0:00–0:40 (person A): Node 22 + `ws` + `@google/genai`. `CallSession`: `ai.live.connect`, `sendRealtimeInput({audio:{data, mimeType:"audio/pcm;rate=N"}})`, stream `inlineData` audio out, emit `flush` on `serverContent.interrupted` [I]. Browser test page with an AudioWorklet. This alone covers cases (c), (d) partially, the dev loop and the jury fallback, with no account gating.
- 0:40–1:10: provider adapter. Answer webhook returns XML, e.g. Plivo `<Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-l16;rate=16000">wss://host/plivo</Stream>`, SignalWire `<Connect><Stream url="wss://host/sw" codec="L16@24000h" realtime="true"/></Connect>`, jambonz `{"verb":"listen","url":"wss://host/jb","sampleRate":24000,"bidirectionalAudio":{"enabled":true,"streaming":true,"sampleRate":24000},"passDtmf":true}`. Map media in, audio out, `flush` to clearAudio/clear/killAudio, checkpoint/mark acks to heard-position, DTMF to an event.
- 1:10–1:30: expose with `cloudflared tunnel --url http://localhost:8080` (WebSockets supported) or an EU VM; set the number's answer URL.
- 1:30–1:45: first call from a mobile; test barge-in and an es/ca switch.
- 1:45–2:00: 10-parallel smoke test from a second account (or `sipp`/baresip against the SIP domain); stereo WAV + JSONL log per call.

## Gaps
- The harness contract itself, its hosting region, and whether the ten calls arrive in one burst (CPS) or staggered.
- Twilio's exact limited-concurrency number and Primary Customer Profile approval time; Telnyx inbound cap, whether a non-US L1 account may receive SIP/Voice API traffic at all, and real L2 turnaround on a weekend.
- Plivo trial inbound rules; EU media regions for Plivo, SignalWire, Vonage; SignalWire post-trial concurrency; Vonage upgrade KYC.
- jambonz cloud trial session cap and hosting region.
- Which EU-country numbers are instant (no regulatory bundle) per provider; check the console at purchase time.
- Per-minute prices were not verified on primary pages (Telnyx ~$0.0032 + $0.002/min, Daily $0.018–0.03, LiveKit SIP $0.003–0.004 are secondary); immaterial for one weekend.
- OpenAI's SIP guide returned 404 to the fetcher; SIP-leg codec list (G.722/Opus), DTMF handling and concurrent realtime-session limits on a low-tier key are unverified.
- Gemini Live concurrent-session quota, regional endpoints and the current model id: for the model probe.
- Maintenance status of `werift`, `@roamhq/wrtc`, `@alexanderolsen/libsamplerate-js`, `speex-resampler` not checked today.
- Voximplant, Infobip, Bandwidth, Sinch, Zadarma, DIDWW were only surface-checked.
