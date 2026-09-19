# Hosting, latency and sponsor-infrastructure fit — research probe (2026-09-18)

**Question.** Where and how do we deploy the real-time voice server (Node/TS, long-lived WebSocket, maybe small ONNX VAD) and the web/data layer for lowest latency at 10–20 concurrent calls — and which sponsor infrastructure genuinely fits?
**Decision it informs.** Deployment topology, region, data layer, sponsor products adopted.
**Constraints folded in (team lead, mid-probe).** Google Cloud credits (largest) + OpenAI key + $100 cash; Gemini/Google preferred; TypeScript/Node, own orchestration; APIs only (no GPU hosting — Modal/Cerebrium dropped); sponsor wins ties.
**Legend.** [V] verified, primary source seen today · [S] strong, primary page seen only via search summary or several secondary sources · [I] inferred (my reasoning / memory) · [NF] not found.

## Findings

### A. Hosting platforms (September 2026 state)
- [V] **Fly.io has no Madrid region any more**: 18 regions; EU = ams, arn, cdg, fra, lhr; US-East = iad, ewr. https://fly.io/docs/reference/regions/ — Pricing: shared-cpu-2x/2GB $11–14/mo, performance-2x/4GB $62–81/mo (per-second billing), IPv4 $2/mo, card required. https://fly.io/docs/about/pricing/
- [V] Railway: 4 regions, EU = Amsterdam only. https://docs.railway.com/reference/regions · [V] Render: EU = Frankfurt only. https://render.com/docs/regions
- [S] Koyeb was bought by Mistral AI (announced 2026-02-17; team folded into Mistral Compute). Platform direction uncertain; docs host did not resolve today. https://techcrunch.com/2026/02/17/mistral-ai-buys-koyeb-in-first-acquisition-to-back-its-cloud-ambitions/
- [S] Pipecat Cloud has `eu-central` (`--region eu-central`) but is Python/Pipecat-only — conflicts with Node + own orchestration. https://docs.pipecat.ai/cli/cloud/regions
- [S] LiveKit Cloud agents: us-east, eu-central (Frankfurt), ap-south; region fixed at creation; open issue on higher latency in the EU region. Only useful if we adopt LiveKit rooms as transport. https://docs.livekit.io/deploy/admin/regions/agent-deployment/ · https://github.com/livekit/agents/issues/4053
- [V] Cloudflare Containers: Workers Paid plan required; instance types up to 4 vCPU / 12 GiB; default placement = closest to the incoming request, pinnable to `WEUR`/`EEUR` or jurisdiction `eu`. [S] GA (Containers + Sandboxes). [NF] cold-start numbers, explicit WebSocket guidance. https://developers.cloudflare.com/containers/platform-details/placement/ · https://developers.cloudflare.com/containers/platform-details/limits/ · https://developers.cloudflare.com/changelog/post/2026-04-05-regional-placement/
- [V] **Vercel Functions now serve WebSockets (public beta since 2026-06-22)**: connection pinned to one instance, closes at the function max duration, state not shared between instances. [S] default cap 5 min, 30 min ceiling on Pro/Enterprise. https://vercel.com/docs/functions/websockets · https://ably.com/vercel/websockets-on-vercel
- [S] Hetzner raised prices twice in 2026 (CCX13 €0.069/h, CCX23 €0.138/h); EU sites FSN/NBG/HEL, none in Spain. https://costgoat.com/pricing/hetzner · https://northflank.com/blog/hetzner-cloud-server-price-increases
- [I] AWS eu-south-2 (Aragón) and Azure Spain Central (Madrid) exist but bring no credits and no co-located voice vendors. [S] **Azure Speech is NOT offered in Spain Central.** https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions
- [NF] Northflank, OVH (Madrid Local Zone), Scaleway: not checked within the timebox.

### B. Google Cloud as host (deep dive)
- [V] Cloud Run supports WebSockets with no extra config; they are long-running HTTP requests: **timeout default 5 min, max 60 min**; session affinity is best-effort; up to 1000 concurrent connections per container; an instance with any open WebSocket is "active" and **billed as instance-based**; do not enable end-to-end HTTP/2; clients must reconnect on timeout; cross-instance state needs an external store. https://docs.cloud.google.com/run/docs/triggering/websockets · https://docs.cloud.google.com/run/docs/configuring/request-timeout
- [V] **europe-southwest1 (Madrid) is a Cloud Run Tier 1 region**, as are europe-west1 (Belgium), europe-west4 (Netherlands), europe-west9 (Paris); Frankfurt/London are Tier 2. https://docs.cloud.google.com/run/docs/locations
- [I] Cloud Run is HTTP/WebSocket/gRPC only — **no UDP ingress**, so no raw SIP/RTP/WebRTC media. If the harness needs that, use a Compute Engine VM (or Fly.io, which supports UDP).
- [I] Tier 1 instance-based price ≈ $0.000018/vCPU-s + $0.000002/GiB-s (from memory; pricing page fetch was truncated): 4 vCPU/4 GiB ≈ $0.29/h.
- [I] GKE Autopilot: cluster + ingress + managed cert ≈ 1 h of yak-shaving for zero benefit at this scale — avoid. GCE e2-standard-4 ≈ $0.15–0.17/h in EU: no cold starts, UDP OK, but TLS/domain/deploys are manual (≈30–45 min setup vs ≈10–15 min for Cloud Run).
- [S] **Vertex AI Live API in EU regions is the weak spot**: as of May 2026 only `gemini-live-2.5-flash-native-audio` was reachable in europe-west1/west4, with reports of the model going silent after turn 1 and crackling audio; `gemini-3.1-flash-live-preview` was not on Vertex at all (AI Studio, global routing only). No Google reply in the threads. https://discuss.ai.google.dev/t/vertex-ai-live-api-only-native-audio-reachable-in-eu-and-it-breaks-on-turn-2-cascade-models-return/144760 · https://discuss.ai.google.dev/t/gemini-3-1-flash-live-preview-on-vertex-ai-eu-region-availability/144429 · https://discuss.ai.google.dev/t/gemini-live-api-on-vertex-ai-europe-west4-irregular-audio-chunk-delivery-causing-crackling-mid-call/183450
- [V*] Gemini Developer API model list today: Live = `gemini-3.8-live` (stable), `gemini-3.8-live-extended-thinking`, `gemini-3.1-flash-live-preview` (legacy), `gemini-2.5-flash-native-audio-preview-12-2025`; text = `gemini-3.8-flash`, `gemini-3.5-flash-lite`; TTS = `gemini-3.1-flash-tts-preview`. (*page read through a summarising fetch — confirm IDs in AI Studio.) https://ai.google.dev/gemini-api/docs/models
- [S] Gemini 3.8 Flash (released 2026-09-02) is served on the **global endpoint only**; Gemini 3.5 Flash is the newest with EU residency; us/eu multi-region endpoints carry a 10% premium. https://innfactory.ai/en/ai-models/google-gemini/ · https://discuss.google.dev/t/gemini-3-x-models-in-european-locations/333038
- [S] AI Studio endpoint is not slower than Vertex: Gemini 2.5 Flash TTFT 0.49 s (AI Studio) vs 0.59 s (Vertex). Regional Vertex endpoints buy residency, not speed. https://artificialanalysis.ai/models/gemini-2-5-flash/providers
- [V] **Chirp 3 STT**: GA in `us` and `eu` multi-regions (`eu-speech.googleapis.com`), StreamingRecognize supported; es-ES and **ca-ES GA; eu-ES (Basque) and gl-ES (Galician) Preview**. No Madrid-regional serving. https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3
- [S] Chirp 3 HD TTS: `global`/`eu`/`us` endpoints, `streaming_synthesize` supported; no SSML, no rate/pitch, no A-law. https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd
- [NF] Whether any Gemini model is served from europe-southwest1 on Vertex (docs pages returned navigation only).

### C. Network
- [V] RTT from Madrid (WonderNetwork): Paris 16 ms, Milan 26, Amsterdam 28, Frankfurt 28, Brussels 30, Dublin 32, Helsinki 51, Stockholm 57, New York 81, Chicago 96, Dallas 117, US-West ≈142–147. (London 118 / Washington 141 look like dataset outliers; expect ≈28 / ≈90.) https://wondernetwork.com/pings/Madrid
- [V-own, indicative] From the team laptop (Spain; Cloudflare colo LIS; TCP-connect times implausibly low → some local relay, so only TTFB deltas and resolved IPs are used): `api.eu.deepgram.com` → AWS eu-central-1 IP, TTFB 124 ms vs `api.deepgram.com` → US (Cogent) IP, **448 ms**; `eu.rt.speechmatics.com` → AWS eu-west-3 (Paris), 101 ms; AssemblyAI default and `.eu` streaming hosts both → AWS eu-north-1 (Stockholm), ≈170–190 ms; Gladia → OVH France; Google endpoints 75–95 ms; OpenAI/Groq/Cerebras/Soniox/Cartesia terminate on anycast CDNs (backend location not observable).
- [I] Per-turn network overhead ≈ RTT(harness↔server) + Σ RTT(server↔vendor) — three vendor legs for a cascade (STT, LLM, TTS), one for speech-to-speech. **Vendor co-location therefore outweighs caller proximity ~3:1.**

| Server region (cascade) | Harness in EU / Madrid caller | Harness in US-East |
|---|---|---|
| europe-southwest1 Madrid | 5 + 3×28 ≈ **90 ms** | 85 + 84 ≈ 170 ms |
| europe-west1 Belgium | 30 + 3×(2–8) ≈ **45 ms** | 90 + 15 ≈ 105 ms |
| us-east4 Virginia (US vendor endpoints) | 90 + 3×(2–10) ≈ 110 ms | 5 + 15 ≈ **20 ms** |

Madrid is dominated in both scenarios: nothing we would call is served from Madrid. Wrong-continent regret is one transatlantic RTT (≈65–85 ms per turn) — audible but not fatal.

### D. Dev tunnels
- [I] ngrok / Cloudflare Tunnel / Tailscale Funnel all carry WebSockets and are fine for rehearsal. For scored runs a laptop on venue Wi-Fi adds a tunnel hop plus shared-AP jitter, captive-portal/DHCP drops and lid-close risk; bandwidth is not the issue (20 calls < 5 Mbps). With literal pass/fail scoring, one dropped call = one failed case. **Never serve scored calls from a laptop.**

## Comparison table — voice server host

| Option | Nearest region | WS / UDP | Cold start risk | Deploy speed | Weekend cost | Verdict |
|---|---|---|---|---|---|---|
| **Cloud Run** (min-instances, no CPU throttling) | Belgium / NL / Madrid / Paris | WS yes (60 min cap) / no UDP | none with min≥1; scale-out only | `gcloud run deploy --source`, instant rollback | ≈$8–32, credits | **First choice** |
| Compute Engine VM | same | WS + UDP | none | manual TLS + deploy | ≈$9, credits | Fallback if UDP/SIP needed |
| GKE Autopilot | same | both | none | slowest | credits | Avoid |
| Fly.io | cdg / fra / ams, iad | WS + UDP, no timeout, one anycast hostname multi-region | none (always-on VM) | `fly deploy`, ≈10 min first time | ≈$5–8 cash | **Runner-up** |
| Railway / Render | ams / fra | WS | none on paid | very fast | ≈$5–10 cash | Fine, no edge over the above |
| Cloudflare Containers (+DO) | WEUR pin | WS via Worker/DO proxy | on-demand start [NF numbers] | Worker + DO + image wiring | $5 + usage | Sponsor, but not competitive in 36 h |
| Vercel Functions WS (beta) | fra1/cdg1 etc. | WS, cut at max duration | yes | trivial | $0–20 | Dashboard only, not scored calls |
| Pipecat Cloud / LiveKit Cloud | eu-central | managed transports | low | fast if on their framework | usage | Conflicts with own Node orchestration |
| Hetzner / OVH / Scaleway VPS | DE/FI/FR | WS + UDP | none | manual | ≈€4–8 cash | No advantage over a GCE VM with credits |
| Laptop + tunnel | venue Wi-Fi | WS | n/a | instant | $0 | Dev only |

## Vendor-endpoint region table

| Vendor | EU endpoint? | Evidence |
|---|---|---|
| Gemini Developer API (text + Live) | Global routing only, newest models | [S] B above |
| Vertex AI Gemini | Regional EU for ≤3.5 Flash; 3.8 Flash global only; Live in west1/west4 = old 2.5 native-audio, buggy | [S] |
| Google STT Chirp 3 / TTS Chirp 3 HD | `eu` multi-region, streaming | [V] / [S] |
| OpenAI (text + Realtime) | `eu.api.openai.com` only for eligibility-gated EU-residency projects; Realtime tracing not EU-compliant; default backend location undisclosed | [S] https://developers.openai.com/api/docs/guides/your-data |
| Deepgram | `api.eu.deepgram.com` GA: STT, TTS, Voice Agent, same keys, AWS EU | [S] https://deepgram.com/learn/deepgram-eu-endpoint-now-generally-available + own measurement |
| Speechmatics | `eu.rt.speechmatics.com`; `global.rt` auto-routes | [S] https://docs.speechmatics.com/api-ref/realtime-transcription-websocket |
| AssemblyAI | EU data-zone streaming host; resolves to Stockholm | [S] + own measurement |
| Gladia | French, OVH-hosted | [I] from resolved IP |
| Soniox | EU endpoint [NF]; defaults reported as US | [NF] |
| ElevenLabs | EU residency host is Enterprise-only; default is a global anycast LB | [S] https://elevenlabs.io/docs/overview/administration/data-residency |
| Cartesia | Routes by origin to US/EU/APAC; dedicated EU endpoint | [S, secondary] https://docs.cartesia.ai/changelog/2026 |
| Azure Speech | Many EU regions, **not Spain Central** | [S] |
| Groq | Helsinki DC since 07-2025; no public region selector | [S] https://community.groq.com/t/european-api-endpoints/431 |
| Cerebras | First EU capacity "by end-2026" → US today | [S] https://investors.cerebras.ai/news-releases/news-release-details/cerebras-systems-accelerates-european-expansion-200mw-ai-compute |
| Anthropic | Not checked (outside the team's stack) | [NF] |
| Twilio | Edges `dublin`, `frankfurt` (old `ie1`/`de1` API hostnames retired 2026-04-28) | [S] https://www.twilio.com/docs/global-infrastructure/edge-locations |
| Telnyx | Media anchorsites Frankfurt, Amsterdam, London, Paris; no Madrid | [S] https://telnyx.com/resources/choose-point-of-presence-anchorsite |
| Vonage / SignalWire / Plivo | Not checked | [NF] |

## Sponsor-fit table

| Sponsor | What it is | Verdict for this product |
|---|---|---|
| **Convex** | Reactive DB + functions, serializable transactions. [V] Regions: US East and **EU West (Ireland)**, all plans incl. free, region fixed at creation. https://docs.convex.dev/production/regions | **Use it**: call/session state, tool-call trace, live call console (browser subscribes directly), and booking writes as one mutation (check-then-write without slot locks). [I] ≈15–20 ms RTT from Belgium per function call; keep it to a few round trips per turn. If the organizers' API owns clinic records, Convex is our mirror + audit trail, not the source of truth. The HackSpain platform itself runs on Convex. |
| **Vercel** | Frontend cloud, AI Gateway, Functions | **Use it** for the Next.js dashboard. Do not host the voice socket (beta, max-duration cut). AI Gateway: do not force into the hot path — extra hop, unmeasured. |
| **Cloudflare** | Workers, DO, Containers, Tunnel, Workers AI (Deepgram Nova-3, Flux, Aura-1, Whisper), Realtime SFU/TURN | **Use Tunnel** for dev. Containers/DO per-call actor: do not force (extra wiring, isolate CPU limits, no native ONNX). Workers AI speech and Realtime: only if the harness turns out to be WebRTC or we want Flux on sponsor credits — measure first. https://blog.cloudflare.com/cloudflare-realtime-voice-ai/ |
| **Tinybird** | Real-time analytics (ClickHouse) with SQL-to-API; Madrid company. [S] Free: 1000 API req/day, 10 GB. https://www.tinybird.co/docs/forward/pricing/limits | **Use it** for post-call analytics: fire-and-forget events (turn latencies, tool calls, outcomes, per-case pass/fail) → pipes → charts. Never in the hot path; cache dashboard queries under the daily cap. |
| **fal.ai** | Generative-media inference; TTS/STT catalogue, realtime WebSocket infra | Do not force into the live loop (region and telephony latency unknown). Optional: synthesize multilingual/noisy test-caller audio for our eval suite. https://fal.ai/explore/text-to-speech-apis |
| **Helmcode** | Spanish firm: EU-hosted private inference on open models + DevOps-as-a-service. https://helmcode.com/ | Do not force. Ask at the booth for TTFT and tool-calling support; possible EU LLM fallback. |
| **Exa** | Neural web-search API | No fit for a closed-domain booking agent. Do not force. |
| **QuiverAI** | Text/image-to-SVG models (Arrow). https://docs.quiver.ai/developers | No runtime fit; at most demo illustrations. |
| **Cognition / Cursor** | Devin/Windsurf; IDE | Build-time tooling only. |
| Perk amounts | [NF] — `seed.ts` in the HackSpain repo holds demo values only (it lists non-sponsors). Run `hackspain perk`. | |

Non-sponsor data options [I]: Neon/Supabase Postgres (Frankfurt), Turso, Upstash Redis slot locks — all workable, none beats Convex here; Convex's transactional mutations remove the need for Redis locks.

## Recommendation

**First choice — Cloud Run in `europe-west1` (Belgium), not Madrid.** One Node container, `min-instances 2`, 4 vCPU / 4 GiB, concurrency 20, timeout 3600, `--no-cpu-throttling`, `--cpu-boost`, session affinity, gen2. Paid by credits, one-command deploy, instant revision rollback at checkpoints, Google's backbone carries the harness leg from the nearest PoP, and Gemini/Chirp are in-network. It is **not materially worse** than Fly.io on latency (a few ms of front-end hop) or deploy speed (≈10–15 min first deploy vs ≈10). Deploy the same image to `us-east4` and pick by measurement once the harness location is known. Data: Convex EU West. Dashboard: Vercel. Analytics: Tinybird. Dev: Cloudflare Tunnel.
- Use the **Gemini Developer API / global endpoint** for the newest models; do not build on Vertex regional Live in the EU.
- Prefer speech vendors with a real EU endpoint (Chirp 3 `eu`, Deepgram EU, Speechmatics EU, Cartesia EU). Setting the EU host is a one-line change; on Deepgram it measured ≈300 ms less connection setup, i.e. roughly 100 ms per round trip [V-own, indicative].

**Runner-up — Fly.io** (`cdg` or `fra`, plus `iad` behind the same anycast hostname): always-on VMs, UDP, no request timeout, automatic nearest-region routing — the better hedge if the harness location stays unknown or needs UDP. ≈$5–8 from the $100.

**Fallback** — GCE e2-standard-4 in europe-west1 running the same image behind Caddy or cloudflared.

**Avoid**: Madrid region (nothing co-located), GKE, Vercel/Cloudflare for the scored socket, Pipecat/LiveKit Cloud (framework lock vs own orchestration), Koyeb (post-acquisition uncertainty), laptop + tunnel for scored runs, autoscaling from zero.

**Sizing, 10–20 calls** [I]: audio < 5 Mbps total; Node relay ≈2–5% of a core per call, local Silero VAD ≈+2–4% (run it in `worker_threads`, or use vendor-side turn detection and skip ONNX). 2 warm instances × 4 vCPU leaves >3× headroom. Keep per-call state in memory on the socket's instance; mirror to Convex.
**Weekend cost** [I]: Cloud Run EU ≈$32 + US hedge ≈$8–16 + optional VM ≈$9, all credits; Convex/Vercel/Tinybird free tiers; Cloudflare $0–5. Cash spend on hosting ≈$0–8 → keep the $100 for speech APIs.

## Hackathon fast-path
1. Tonight: `gcloud run deploy voice --source . --region europe-west1 --allow-unauthenticated --cpu 4 --memory 4Gi --concurrency 20 --min-instances 2 --max-instances 4 --timeout 3600 --no-cpu-throttling --cpu-boost --session-affinity --execution-environment gen2`. Server listens on `$PORT`, sends WS pings every 20 s, handles SIGTERM.
2. Register that URL with the organizers before the first checkpoint; iterate locally through Cloudflare Tunnel against practice cases.
3. Log the source IP of the first harness call → geolocate → if US, deploy the same image to `us-east4` and re-register.
4. Create the Convex project in EU West (irreversible choice), the Vercel dashboard, the Tinybird workspace.
5. Before every scored run: 10 parallel replayed calls against the deployed URL; never deploy a revision mid-run.

## Gaps
- Harness transport and location (decides Cloud Run vs VM/Fly, EU vs US). Biggest open item.
- Vendor **concurrency ceilings** for the ten-at-once case (Gemini Live sessions, STT/TTS streams per plan) — not checked here.
- Cloud Run behaviour of open sockets during a revision rollout; exact current Cloud Run/GCE prices; a separate "Cloud Run instances" resource the locations page says cannot be created in Tier 1 regions (not investigated, irrelevant to services).
- Gemini availability in europe-southwest1; where the global Gemini endpoint actually serves EU traffic; `gemini-3.8-live` on Vertex.
- Cloudflare Containers cold-start and WebSocket behaviour; Tinybird EU regions; Soniox/Anthropic/Vonage/SignalWire/Plivo regions; Northflank, OVH, Scaleway.
- Real sponsor perk amounts.
