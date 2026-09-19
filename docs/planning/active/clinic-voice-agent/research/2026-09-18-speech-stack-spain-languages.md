# Speech stack for en / es / ca / gl / eu on a terrible phone line

Date: 2026-09-18 · Probe timebox: ~20 min of web research · Status: recommendation with open spikes (see Gaps).

Labels: **[V]** verified — primary source read this session (through a summarising fetch tool: spot-check a number before betting on it) · **[S]** strong — vendor-published claim or several secondary sources · **[I]** inferred — my reasoning · **[NF]** looked, not found.

Team constraints folded in (lead's two updates): Google credits + OpenAI key preferred, any other vendor must clearly beat Google for a language; $100 for all other APIs including eval runs; APIs only (no self-hosted GPU models; small CPU/ONNX models inside the Node server are fine); TypeScript/Node; team owns orchestration; leaderboard-first — names, dates and language ID beat voice beauty.

## Question
Which STT, TTS, turn-detection/VAD and noise-suppression components best handle English, Spanish, Catalan, Galician and Basque on an 8 kHz μ-law line with noise and packet loss, at conversational latency, with automatic language identification and mid-call switching?

## Decision it informs
The speech components of the pipeline, the per-language routing/fallback table, and whether any non-Google account is worth opening.

## Findings

### A. Google path (preferred vendor)
1. [V] **Chirp 3 STT** (`chirp_3`, Speech-to-Text v2) supports `StreamingRecognize`. en-US GA, es-ES GA, ca-ES GA, **gl-ES Preview, eu-ES Preview**. Regions: `us` and `eu` multi-region, both GA. Speech adaptation (phrase biasing) GA; built-in denoiser (`denoiser_config`); `endpointing_sensitivity` STANDARD / SHORT / SUPERSHORT; utterance-level timestamps only. https://docs.cloud.google.com/speech-to-text/v2/docs/chirp_3-model · https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3
2. [V] STT v2 accepts `MULAW` / `ALAW`, `sample_rate_hertz` 8000–48000 ("16000 is optimal") → send the line's μ-law 8 kHz natively. https://docs.cloud.google.com/speech-to-text/v2/docs/reference/rpc/google.cloud.speech.v2
3. [V] No telephony-tuned model for ca-ES / gl-ES / eu-ES (only chirp, chirp_2, chirp_3). `telephony` and `telephony_short` exist for es-ES and en-US. https://docs.cloud.google.com/speech-to-text/v2/docs/speech-to-text-supported-languages
4. [V, ambiguous] Language auto-detect: docs show `language_codes=["auto"]` and restricted lists (`["en-US","fr-FR"]`), described as "transcribes in the most prevalent language". The streaming sample uses one code and `interim_results=False`. Two reads of the docs disagreed on whether auto-detect applies to streaming. Treat **streaming LID and interim results as UNCONFIRMED**; sync `Recognize` with `"auto"` is confirmed. Streaming latency: Google publishes none [NF].
5. [S] Price $0.016/min (~$0.96/h), Chirp 3 at the standard rate (credits cover it). Concurrent-stream quota [NF]. https://cloud.google.com/speech-to-text/pricing
6. [V] **Chirp 3 HD TTS**: en-US, en-GB, es-ES, es-US yes; **ca / gl / eu NOT supported**. Streaming synthesis with ALAW / MULAW / OGG_OPUS / PCM output; `eu` GA. https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd
7. [V] For ca/gl/eu Google has exactly one legacy **Standard** voice each — `ca-ES-Standard-B`, `gl-ES-Standard-B`, `eu-ES-Standard-B` (female); no WaveNet / Neural2 / Chirp. https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types
8. [V] **Gemini-TTS** (`gemini-3.1-flash-tts-preview`, `gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`): en-US, es-ES GA; ca-ES, gl-ES, eu-ES **Preview**; streaming on paper. https://docs.cloud.google.com/text-to-speech/docs/gemini-tts — [S] counter-evidence: forum reports Jul–Aug 2026 of 10–20 s to first chunk and "one long silent wait, then a burst" (not incremental). https://discuss.ai.google.dev/t/3-1-flash-tts-preview-streaming-latency/176050 → not safe inside a live call.
9. [V] **Gemini Live** (`gemini-3.8-live`, `gemini-3.8-live-extended-thinking`; older `gemini-2.5-flash-native-audio-preview-12-2025`): language list (99) includes ca, gl, eu, es, en; auto-detects and switches language; input raw PCM16 (16 kHz native, resamples), output PCM 24 kHz — no μ-law; 15-min audio session cap. [S] Tier 1 = 50 concurrent sessions. Quality in ca/gl/eu: [NF]. https://ai.google.dev/gemini-api/docs/live-api/capabilities · https://ai.google.dev/gemini-api/docs/models

### B. Other STT (streaming)
10. [V] **Soniox `stt-rt-v5`**: one unified model, 60+ languages, **all five in the supported-languages table**; per-token language ID (`language` field on each token), language hints, built-in endpoint detection, `context` for domain terms/custom vocabulary, raw `mulaw` / `alaw` input. https://soniox.com/docs/stt/concepts/supported-languages · https://soniox.com/docs/stt/rt/real-time-transcription
11. [V] Soniox price **$0.12/h** real-time ($2 per 1M audio tokens). https://soniox.com/pricing — [V] default limits: **10 concurrent WebSocket connections per project**, 100 req/min, 300 min/stream; increases requested in the Console. https://soniox.com/docs/stt/rt/limits-and-quotas → exactly the ten-call case with zero headroom.
12. [S, vendor benchmark, biased] Soniox claims Catalan WER 10.7% vs Google 21.7% and OpenAI 15.4%; Galician 11.1%; Basque number [NF]. Seen only in search snippets of soniox.com/compare pages (direct fetch returned 404); Google model and mode not stated. A hypothesis to test, not a fact.
13. [V] **Gladia Solaria-1**: all five, with "auto-discovery and code-switch"; ca/gl/eu are Solaria-1 only (not Solaria-3). Live concurrency: free 1, paid 30. $0.75/h Starter, EUR 50 free credit. https://docs.gladia.io/chapters/language/supported-languages · https://docs.gladia.io/chapters/limits-and-specifications/concurrency · https://www.gladia.io/pricing
14. [V] **Speechmatics**: all five as separate language packs; es+en bilingual pack; **automatic language ID is batch only** — a realtime session must know its language up front. Concurrency: Free 2, Pro 50. `additional_vocab` up to 20,000 entries. https://docs.speechmatics.com/speech-to-text/languages · https://docs.speechmatics.com/speech-to-text/realtime/limits
15. [V] **Azure Speech**: real-time STT for ca-ES, eu-ES, gl-ES, es-ES, en-*. Phrase list: ca-ES yes, **eu-ES / gl-ES no**. LID: up to 4 candidates at-start (<5 s), up to 10 continuous (JavaScript SDK supported), no intra-sentence switching; whether ca/gl/eu are eligible LID candidates [NF]. [S] $1/h, 100 concurrent on S0. https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt · https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-identification
16. [V] **ElevenLabs Scribe v2 Realtime**: "90+ languages", ~150 ms, `ulaw_8000` input, `include_language_detection`, VAD commit strategy, keyterms (50), EU residency endpoint. Batch accuracy tiers: Catalan and Galician "Excellent (<=5% WER)"; **Basque absent from the tier list**. Concurrency Free 6 / Starter 9 / Creator 15. [S] $0.39/h. https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime · https://elevenlabs.io/docs/overview/capabilities/speech-to-text · https://elevenlabs.io/docs/overview/models
17. [V] **Deepgram**: Nova-3 has `ca`; **no `gl`, no `eu` in any model**; `multi` and `flux-general-multi` cover en, es, fr, de, hi, ru, pt, ja, it, nl — no ca. https://developers.deepgram.com/docs/models-languages-overview
18. [V] **OpenAI**: current models `gpt-transcribe`, `gpt-live-transcribe` (realtime), `whisper-1`; `languages`, `prompt`, `keywords` biasing; ca/gl/eu not explicitly listed. https://developers.openai.com/api/docs/guides/speech-to-text — [S] HiTZ needed a fine-tune to reach 10.62% WER on Common Voice Basque → stock Whisper-lineage Basque is weak [I]. https://huggingface.co/HiTZ/whisper-large-v3-eu
19. [S] Open models (AINA/BSC Catalan, Proxecto Nós Galician, HiTZ Basque, Parakeet/Canary, Voxtral, Whisper fine-tunes): **self-host only — out of scope**. HiTZ model page: "isn't deployed by any Inference Provider"; Proxecto Nós ships a Dockerized HTTP API (you host it). Groq/fal Whisper is stock Whisper, no Basque advantage [I].
20. AssemblyAI streaming (`universal-3-5-pro`) language list, Cartesia Ink, Voxtral realtime: [NF] within the timebox.

### C. Other TTS (streaming)
21. [V] **Azure Neural**: ca-ES Joana / Enric / Alba; eu-ES Ainhoa / Ander; gl-ES Sabela / Roi (standard neural only; no HD or multilingual voices for these locales). [S] $15 per 1M chars, 0.5M free on F0. The only mainstream vendor verified with proper neural voices in all three.
22. [V] **Soniox `tts-rt-v2`**: all five languages listed, `pcm_mulaw` output. [S] default **3 concurrent TTS streams** → fails ten calls until raised. Price and ca/gl/eu quality [NF]. https://soniox.com/docs/tts/concepts/supported-languages
23. [V] **ElevenLabs**: v3 / v3 Conversational (~280 ms) include Catalan and Galician, **not Basque**; Flash v2.5 (~75 ms, 32 languages) has none of ca/gl/eu. TTS concurrency Free 2 / Starter 3 / Creator 5 / **Pro 10** → ten calls needs Pro, which eats the $100.
24. [V] **Cartesia `sonic-3.6`**: 44 languages, **no ca / gl / eu**. https://docs.cartesia.ai/build-with-cartesia/tts-models/latest
25. OpenAI TTS languages for ca/gl/eu: not re-verified [NF]; historically the Whisper list (ca, gl yes; eu no) [I]. Matxa, Nós-TTS, HiTZ TTS, Kokoro, Chatterbox, XTTS, F5: self-host only — out of scope.

### D. Turn detection / VAD
26. [S] **Pipecat Smart Turn v3 / v3.1**: audio-based, 23 languages (en, es yes; **ca / gl / eu no**), ONNX, ~12 ms CPU. `onnx-community/smart-turn-v3-ONNX` exists → runnable in Node via `onnxruntime-node` / transformers.js, but you must reproduce the Whisper log-mel front-end; Python is the supported path [I]. https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/
27. [S] **LiveKit MultilingualModel**: text-based, 14 languages (en, es yes; ca/gl/eu no), in Agents JS 1.0.19 but tied to the LiveKit Agents framework → conflicts with owning orchestration. https://docs.livekit.io/agents/logic/turns/turn-detector/
28. [V] Deepgram Flux end-of-turn: en, es only of our five. [V] Soniox endpointing is inside the multilingual model → same behaviour for all five. [V] Chirp 3 endpointing sensitivity is language-independent config. [V] ElevenLabs: VAD-silence commit only.
29. [I] Silero VAD is language-agnostic, ONNX, natively supports 8 kHz and 16 kHz → the barge-in trigger for every language, in-process in Node. Krisp VIVA, TEN (en/zh), AssemblyAI and Speechmatics turn detection: not researched [NF].

### E. Noise suppression
30. [S] arXiv 2512.17562 "When De-noising Hurts": enhancement before ASR made **all 40 tested configurations worse** (Whisper, Parakeet, Gemini Flash 2.0, Parrotlet; +1.1 to +46.6 points semantic WER). arXiv 2603.04710 reports the same for Whisper. https://arxiv.org/abs/2512.17562
31. [S, vendor claim] ai-coustics Quail is tuned for STT rather than perception: 10–25% relative WER reduction, 8/16 kHz, CPU, ~30 ms, **Node.js wrapper**. https://ai-coustics.com/blog/quail-stt-asr-transcription
32. [I] RNNoise and DeepFilterNet are 48 kHz full-band models — mismatched to 8 kHz narrowband. Maxine needs a GPU (out of scope). Krisp and Koala not researched [NF]. Chirp 3's server-side denoiser is the only "free" option tuned with its own recogniser.

## Language-support matrix — STT, streaming
| Vendor / model | en | es | ca | gl | eu | In-stream LID / switch | μ-law 8k | Entry concurrency | Price |
|---|---|---|---|---|---|---|---|---|---|
| Google `chirp_3` | GA | GA | GA | Preview | Preview | unconfirmed (sync: yes) | yes | NF | $0.96/h, credits |
| Google `telephony` | yes | yes | no | no | no | no | yes | NF | $0.96/h, credits |
| Soniox `stt-rt-v5` | yes | yes | yes | yes | yes | per-token, one model | yes | 10/project, raisable | $0.12/h |
| Gladia Solaria-1 | yes | yes | yes | yes | yes | auto-detect + code-switch | NF | free 1 / paid 30 | $0.75/h |
| Azure Speech | yes | yes | yes | yes | yes | 4 at-start / 10 continuous; ca/gl/eu eligibility NF | yes [I] | S0 100 | $1/h |
| Speechmatics | yes | yes | yes | yes | yes | **none in realtime** | NF | free 2 / Pro 50 | NF |
| ElevenLabs Scribe v2 RT | yes | yes | yes | yes | **unlisted** | yes (on commit) | yes | 6 / 9 / 15 | $0.39/h |
| Deepgram Nova-3 | yes | yes | yes | **no** | **no** | `multi` excludes ca | yes [I] | — | — |
| Deepgram Flux multi | yes | yes | no | no | no | yes | — | — | — |
| OpenAI `gpt-live-transcribe` | yes | yes | ? | ? | weak [I] | `languages` hint | NF | — | team key |
| Gemini Live `gemini-3.8-live` | yes | yes | listed | listed | listed | automatic | no, PCM16 | Tier 1: 50 | credits |
| AINA / Nós / HiTZ / Parakeet / Voxtral | self-host only — out of scope |

## Language-support matrix — TTS, streaming
| Vendor / model | en | es | ca | gl | eu | Notes |
|---|---|---|---|---|---|---|
| Google Chirp 3 HD | yes | yes | no | no | no | streaming, MULAW out, `eu` region |
| Google Standard | yes | yes | Standard-B | Standard-B | Standard-B | one robotic female voice each; fast, cheap, intelligible |
| Gemini-TTS | GA | GA | Preview | Preview | Preview | first-chunk latency reports of 10–20 s |
| Azure Neural | yes | yes | 3 voices | 2 voices | 2 voices | $15/1M chars; Node SDK; μ-law 8k output [I] |
| Soniox `tts-rt-v2` | yes | yes | yes | yes | yes | 3 concurrent streams default; price and quality NF |
| ElevenLabs v3 Conversational | yes | yes | yes | yes | no | ~280 ms; 10 concurrent needs Pro |
| ElevenLabs Flash v2.5 | yes | yes | no | no | no | ~75 ms |
| Cartesia `sonic-3.6` | yes | yes | no | no | no | 44 languages |
| Matxa / Nós-TTS / HiTZ / Kokoro / Chatterbox | self-host only — out of scope |

## Recommendation
**First choice — Google-centred, plus one cheap front-end STT, decided by a 2-hour A/B.**
- **Front STT (always on, all languages): Soniox `stt-rt-v5`**, `language_hints: [en, es, ca, gl, eu]`, language ID on, endpoint detection on, `context` filled with doctor names, site names and the candidate patient names returned by the records lookup. The justification for a non-Google account is **not one language — it is the routing problem**: you cannot route by language until you know it, and Soniox is the only option verified to give per-token LID, all five languages, partials and endpointing in a single stream. At $0.12/h the $100 is irrelevant.
- **Google as verifier: `chirp_3` sync `Recognize`** (eu endpoint, detected language code, phrase-set adaptation, denoiser on) re-transcribes the buffered audio of slot-critical turns only (name, DOB, date/time, phone). Two independent transcripts; agreement → proceed, disagreement → the agent asks again or reads back. This aims straight at the literal scorer and uses the credits where Google is confirmed to work.
- **TTS: Google Chirp 3 HD streaming, MULAW 8 kHz output, for en and es.** For ca/gl/eu: start with Google Standard-B (zero new accounts, good enough for the leaderboard — the caller only has to understand it), and move to **Azure Neural** voices before Sunday because the jury judges how it sounds.
- **Turn-taking: Silero VAD in-process (ONNX, 8 kHz) for barge-in + the STT's endpoint event + an adaptive silence timeout** (long, ~1.0–1.2 s, after the agent asked for a name, DOB or number; short, ~0.5 s, after yes/no questions). Works identically in all five languages.
- **No denoiser in front of STT.** Feed raw audio. If false barge-ins from line noise hurt, denoise only the VAD branch; test ai-coustics Quail only if the A/B shows noise-driven slot errors.
- **LLM:** Gemini (credits), replying in the locked language.

**Decision rule that can flip this to all-Google (run in the first 2 hours):** replay the same recorded practice calls through `chirp_3` StreamingRecognize (eu endpoint, MULAW) and through Soniox. Go all-Google for STT if Chirp 3 streaming (a) identifies the language among the five within the first utterance, (b) returns finals within ~800 ms of end of speech, and (c) matches Soniox on slot accuracy in ca/gl/eu. If (a) fails but (b) and (c) pass, all-Google still works with the sync-`Recognize("auto")` trick in the routing section.

**Runner-up — all Google speech (no new accounts):** `chirp_3` streaming for everything; first-utterance sync `Recognize` for LID; Chirp 3 HD for en/es; Standard-B for ca/gl/eu. Risks: gl-ES and eu-ES are Preview; no confirmed partials (barge-in rests on VAD alone); latency unpublished; robotic regional voices in front of the jury.
**Second runner-up — Azure as the single extra account:** real-time STT in all five plus the only verified neural ca/gl/eu voices, 100 concurrent, official JS SDK. Weaker than Soniox on LID (five languages exceed the 4-candidate at-start limit; continuous mode needed; ca/gl/eu eligibility unverified) and no phrase list for eu/gl.

**Avoid, and why**
- Deepgram Nova-3 / Flux as primary: no Galician or Basque in any model; Flux multi has no Catalan [V]. Adds an account and beats Google nowhere.
- ElevenLabs as the single speech vendor: Basque missing in both STT tiers and TTS; ten concurrent TTS streams needs Pro.
- Cartesia Sonic: no ca/gl/eu. Gemini-TTS in the live loop: latency reports. Speechmatics as front STT: no realtime LID, free tier 2 sessions.
- Smart Turn or LiveKit turn detector as the only end-of-turn logic: ca/gl/eu unsupported; LiveKit's also drags in a framework.
- Gemini Live as the whole pipeline: no evidence for ca/gl/eu, less deterministic slot handling under a literal scorer, PCM-only. Worth a 30-minute probe as a Basque/Galician comprehension benchmark, nothing more.
- Upsampling 8 kHz to 16 kHz before engines that accept 8 kHz μ-law natively: adds CPU and artefacts, no information.
- Self-hosting AINA / Nós / HiTZ models this weekend.

## Per-language routing table
| Language | STT | TTS | Is Google good enough? |
|---|---|---|---|
| English | Soniox front (or `chirp_3` / `telephony` if all-Google) + `chirp_3` verifier | Chirp 3 HD en-US | **Yes.** No vendor justified by English alone. |
| Spanish | same, es-ES | Chirp 3 HD es-ES | **Yes.** Same. |
| Catalan | Soniox front + `chirp_3` ca-ES (GA) verifier | Standard-B → Azure `ca-ES-JoanaNeural` | STT: **probably** — GA, but the only comparative number found (vendor, biased) has Google at twice Soniox's WER; A/B it. TTS: good enough for the leaderboard, **not for the jury**. |
| Galician | Soniox front + `chirp_3` gl-ES (Preview) verifier | Standard-B → Azure `gl-ES-SabelaNeural` | STT: **unproven** — Preview, no streaming-LID guarantee; alternatives are GA-listed (ElevenLabs rates Galician <=5% WER in batch). No independent proof anyone is more accurate. TTS: as Catalan. |
| Basque | Soniox front + `chirp_3` eu-ES (Preview) verifier; Azure eu-ES as third opinion if needed | Standard-B → Azure `eu-ES-AinhoaNeural` | STT: **unproven, highest risk** — Preview at Google; ElevenLabs, Deepgram and OpenAI drop out entirely; only Soniox, Gladia, Speechmatics, Azure and Google remain. TTS: Azure is **materially better** — the only verified mainstream neural Basque voice. |

**Detecting the language in the first seconds**
1. Short greeting (under 2 s) with barge-in enabled, so the caller talks early.
2. Primary signal: majority of per-token language tags over the first utterance of 3+ words, restricted to the five hints.
3. Text check by the LLM on the transcript — function words separate the classic confusions (gl vs es vs pt; ca vs es): "unha / quero / bos días" gl, "vull / amb / bon dia" ca, "nahi dut / bat / egun on" eu.
4. Tiebreak, and the all-Google route: send the buffered first utterance to `chirp_3` sync `Recognize` with `["auto"]` or the five-code list. It returns language and transcript in one call, so nothing the caller said is lost; then open the streaming session in that language.

**Switching mid-call:** lock the language after the first valid utterance; switch only after two consecutive turns in another language or an explicit request. A switch swaps the TTS voice, the STT hint (or Google stream) and the LLM reply language; captured slots live in language-neutral state (ISO dates, record IDs), so nothing is re-asked.
**Numbers, dates, names [I]:** expect ca/gl/eu numbers as words, not digits — normalise in the LLM's structured output, resolve relative dates in code against the scenario's "today", fuzzy-match names against the records returned by the lookup rather than trusting raw STT, and read back DOB and phone digit by digit.

## Hackathon fast-path (Node / TypeScript)
- **Hour 0–1:** Node WebSocket server; μ-law decode table → PCM16 8 kHz for VAD; pass the original μ-law bytes straight to Soniox (WebSocket JSON protocol; a Node SDK exists in their docs) and log tokens with language tags; stream Google TTS back as MULAW (`@google-cloud/text-to-speech` streaming synthesis) — no resampling anywhere.
- **Hour 1–2:** replay harness — record your own practice calls in all five languages, degrade them (μ-law 8 kHz, noise, 5–10% packet loss), run Soniox vs `chirp_3` streaming vs `chirp_3` sync, score **slot accuracy against the published practice answers**, not WER. Apply the decision rule. Request the Soniox concurrency increase now (or create a second project/key).
- **Hour 2–4:** Silero VAD via `onnxruntime-node` for barge-in (cancel TTS after ~200–300 ms of speech); endpoint event + adaptive timeout; language lock/switch state machine.
- **Then:** critical-slot verifier; Azure TTS for ca/gl/eu (`microsoft-cognitiveservices-speech-sdk` or REST, raw 8 kHz μ-law output); a ten-call load test against every quota (Soniox 10 connections, Google streams, TTS concurrency).
- **Python needed?** No. Silero and Smart Turn are ONNX and run in Node; Smart Turn costs a log-mel port, so skip it unless en/es turn-taking feels bad to a human. ai-coustics ships a Node wrapper.
- **Budget:** 18 cases x ~3 min x 40 full eval runs is ~36 audio hours → Soniox ~$4, Gladia ~$27, Azure STT ~$36, ElevenLabs ~$14 (+$22 plan for concurrency), Google ~$35 on credits. Azure TTS at ~1,500 agent chars per call is ~$0.02 per call. **$100 survives the weekend with any single choice; with Soniox it is barely touched.**

## Gaps
- **Chirp 3 streaming behaviour** — interim results, LID in streaming, real time-to-final, concurrent-stream quota: undocumented or ambiguous. Settle with the hour-1 spike.
- **No independent accuracy benchmark** for ca/gl/eu on narrowband noisy audio from any vendor. Soniox's numbers are vendor-run, seen only in search snippets, Google model unstated. Only the team's A/B settles it.
- [I] The leaderboard callers are probably synthetic voices (mainstream TTS barely covers Basque), so regional-language cases may lean to Catalan and Galician, and synthetic speech is easier for STT than real speech. Unverified — do not drop Basque on this basis.
- Azure: whether ca-ES / gl-ES / eu-ES are valid LID candidates. Soniox: EU endpoint, TTS price, TTS quality in ca/gl/eu. Gladia: μ-law input and live LID latency.
- Not researched in the timebox: AssemblyAI streaming languages, Cartesia Ink, Voxtral realtime, OpenAI TTS and `gpt-live-transcribe` language lists for ca/gl/eu, Krisp VIVA, TEN, Picovoice Koala, Speechmatics turn detection and per-hour price, Inworld / Rime / Hume / MiniMax / Fish / Resemble (none known to cover Basque [I]).
- Harness transport still unknown (brief gap): if audio arrives as WebRTC or wideband PCM rather than μ-law, the "send native 8 kHz" advice changes and Gemini Live becomes cheaper to try.
