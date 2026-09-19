# Agent brain design for literal correctness (research probe)

Date: 2026-09-18 · Timebox ~20 min · Legend: **[V]** verified on a primary source today · **[T]** verified by a local test run today (versions given; throwaway scripts, not in the repo) · **[S]** strong (several credible secondary sources, or a search snippet of a primary doc not opened) · **[I]** inferred.
Team constraints folded in (coordinator update): TypeScript/Node-first (Python = short appendix) · Gemini preferred, OpenAI second · we OWN orchestration, so the state machine and rule enforcement live in our code · provenance of the clinic records API unknown → both cases covered. Transport/plumbing lives in `2026-09-18-orchestration-frameworks.md`; this note covers only the decision core.

## Question
How do we design the decision-making core so the recorded outcome of every call is exactly right?

## Decision it informs
Dialog-state architecture, tool design, rule enforcement, and the libraries behind date resolution, patient matching, booking safety and outcome reporting.

## Findings

### (a) Dialog state — "LLM proposes, code disposes"
- [V] τ²-bench airline: **"78% of observed failures are silent wrong-state failures with no tool error"**. Four deterministic, read-only, pre-execution gates `g(tool_name, args, db_state) → {allow, reject}` ("pure functions with no LLM calls and no writes"; first rejecting gate wins; the agent gets "a structured rejection message in place of the tool result") lifted success 29.6% → 42.0% (+12.4pp, P=0.0012; replicated +12.3pp) and gpt-5.2 61.2% → 71.6%. One gate is generic: `must_read_before_write`. https://arxiv.org/abs/2607.07405
- [V] "False success" (agent asserts completion, environment state says otherwise) = **45–48% of failures** in single-control τ²-bench domains; LLM judges cannot see it (AUROC ≤0.65 across 5 judges × 5 prompts). → the LLM must never be the source of "what happened". https://arxiv.org/abs/2606.09863
- [V] τ-Voice (ICML 2026): voice agents complete 31–51% of tasks on clean audio, 26–38% with noise/accents, vs 85% for text GPT-5 — "retain only 30–45% of text capability"; 79–90% of failures stem from agent behaviour, not audio. https://arxiv.org/abs/2603.13686
- [V] IHBench: post-interruption recovery (resume at the right step, answer the interjection, do not re-deliver) is "a largely distinct capability axis", depends strongly on interruption type; closed models degrade ~3.3x more slowly on long calls. https://arxiv.org/abs/2606.19595 → [I] keep workflow position in code, not in the model's memory.
- [S] Rasa CALM is the purest published form of the pattern: the LLM emits *commands* (set slot, start/cancel flow, correct slot); deterministic flows run the business logic. Python + licence key (free developer edition ≤1,000 conversations/month) → borrow the design, not the dependency. https://rasa.com/docs/learn/concepts/calm/
- [V] Pipecat Flows v1.4.0 (2026-07-05, moving into the `pipecat.flows` namespace): handlers return `(result, next_node)`, tools are per node. Python only. https://github.com/pipecat-ai/pipecat-flows/releases · [V] LiveKit `AgentTask` returns a typed result (Python + Node); `TaskGroup` is "currently experimental", lets callers regress to earlier steps; "Prebuilt tasks aren't available in Node.js". https://docs.livekit.io/agents/logic/tasks/
- [S] Parlant 3.3 (2026-03): guidelines + journeys + canned responses; Python; guideline matching costs extra LLM calls per turn (latency). https://github.com/emcie-co/parlant/releases · [I] LangGraph, OpenAI Agents SDK handoffs, NeMo Guardrails, Burr: they add LLM discretion, moderation rails or a Python runtime — none adds transactional correctness, none earns its learning curve for one six-phase flow.
- [S] XState 5.33.2 (npm, published this week): statecharts, actors, deep persistence, visualiser. https://www.npmjs.com/package/xstate

### (b) Date/time resolution in en/es/ca/gl/eu
Test setup [T]: reference = Fri 2026-09-18 09:00 Europe/Madrid, future-preferring options on.
- [T] **chrono-node 2.10.1** ships de en es fi fr it ja nl pt ru sv uk vi zh — **no ca/gl/eu**; README rates `es` partial [V]. https://github.com/wanasit/chrono · Correct: "next Thursday", "el próximo jueves", "el jueves que viene" → Thu 24; "mañana a las 10" → Sat 19 10:00. **Silently wrong**: "pasado mañana" → Sat 19 (matched only "mañana"); "day after tomorrow" → Sat 19; "el lunes por la mañana" and "first thing Monday" → Mon 12:00 (part of day dropped). Null: "the 25th", "el 25", "la semana que viene".
- [T] **dateparser 1.4.3** (Python): docs list es, ca, gl, eu [V] https://dateparser.readthedocs.io/en/latest/supported_locales.html — yet "next Thursday", "this Thursday", "Monday morning", "el jueves que viene", "pasado mañana", "dentro de dos semanas", "el 25 de septiembre a las 10:30" → `None`; ca/gl/eu resolve little beyond bare words (dijous, xoves, osteguna, demà, mañá, bihar; ca "demà passat" and "la setmana que ve" work; "etzi", "pasadomañá", "dijous que ve", "o vindeiro xoves", "datorren osteguna", "demà a les 10" → `None`); **"tomorrow at 15" / "mañana a las 15" → 09:00 (bare hour silently dropped)**.
- [V] Duckling Time has ES and CA, **no GL, no EU**; Haskell server = extra container. https://github.com/facebook/duckling/tree/main/Duckling/Time · [S] Microsoft Recognizers-Text: ES yes, no ca/gl/eu, Python packages alpha. https://github.com/microsoft/Recognizers-Text · SUTime/HeidelTime: not evaluated (JVM).
- [I] **No library covers the five languages; the LLM is the only multilingual parser.** So split the job: the LLM *extracts* a closed, language-neutral structure; code *computes* the date from an injected clock in `Europe/Madrid` (DST ends 2026-10-25 — never a fixed offset); the agent *reads back* weekday + day + month ("jueves 24 de septiembre") before any hold. Pitfalls: en "next Thursday" (nearest vs week after — one constant, calibrated on practice cases); es/gl "mañana/mañá" = tomorrow|morning; ca "demà passat", eu "etzi", gl "pasadomañá"; Catalan quarter-hours ("un quart de deu" = 9:15); "a las 7" (07 vs 19 — clinic hours decide, else ask); "first thing" = earliest free slot that day, not 00:00/12:00; `toISOString()` shifting a local date by a day.

### (c) Patient identification over the phone
- [T] fuzzball 2.2.6 + double-metaphone 2.0.1, 12 hand-made STT-error pairs: token-sort/-set scores **collapse when STT changes an initial letter**, because sorting reorders the tokens ("Begonia Bazquez"~"Begoña Vázquez" = 48; "Javier Jimenez"~"Xavier Giménez" = 43). A ~12-rule Iberian fold first (strip accents, tx→ch, x→s, v→b, h→∅, ll→y, z/ce/ci→s, ge/gi→j, qu/c→k, final -ig→ch, drop particles de/del/i) lifts them to 93–96; "John Echeverria"~"Jon Etxeberria" 76 → 100. **Different people still score 85–96** ("Ana Fernandez"~"Ana Hernández" 92–96; "Carlos Ruiz"~"Carla Ruiz" 86; "María García López"~"María García Pérez" 89). → fuzzy score = candidate generator only; an exact second factor decides identity.
- [V] Talisman (JS) has French and German phonetics, no Spanish (`spanish/fonetico` was dropped). https://yomguithereal.github.io/talisman/phonetics/ · [S] Python abydos has `SpanishMetaphone` and `PhoneticSpanish` (v0.5.0, old; install on 3.14 untested). https://abydos.readthedocs.io/en/latest/abydos.phonetic.html · [T] rapidfuzz 3.14.6 and jellyfish 1.2.1 install cleanly on Python 3.14.
- [I] Script: name → DOB (LLM extracts digits, code compares exactly) → if still >1: phone last digits or second surname. **Four-match case: never enumerate.** `find_patient` returns to the LLM only `{matchCount, askNext}` plus an opaque handle — the model cannot leak what it never sees. Unresolved after two discriminators → outcome `identity_unresolved`, no write. Small alias table (Pepe/José, Paco/Francisco, Maite, Txema; Jon/Juan/Joan/Xoán; Jordi/Jorge; Iñaki/Ignacio). Double surnames: callers give one, records hold two → token-subset match on folded tokens. Low confidence → ask to spell ("B de Barcelona": LLM extracts initials, code matches).
- [I] Unknown caller: before `register_patient`, re-query by DOB-only and phone-only so an STT-mangled name cannot create a duplicate; read the fields back; the report then carries register + book.
- [V] Proxy callers = FHIR `RelatedPerson` — "a person that is involved in the care for a patient, but who is not the target of healthcare"; `relationship` CodeableConcept; attorney/guardian are listed examples. https://hl7.org/fhir/R4/relatedperson.html [I] Model `caller ≠ patient`: find the *child's/father's* record (their name + DOB), store caller + relationship, honour any authorised-contact field the records expose; schedule on behalf, disclose nothing else. Whether the scorer accepts or refuses proxy booking is a practice-case fact.

### (d) Concurrency-safe booking (ten at once)
- [S] Convex mutations: serializable isolation + OCC + automatic retry. Two calls grabbing one slot: one commits, the other re-runs, reads `held|booked`, returns `SLOT_TAKEN`. https://docs.convex.dev/database/advanced/occ
- [V] Postgres: `CREATE EXTENSION btree_gist; … EXCLUDE USING GIST (room WITH =, during WITH &&)` rejects overlaps. https://www.postgresql.org/docs/current/rangetypes.html [I] For discrete slots, a partial unique index `(slot_id) WHERE status IN ('held','booked')` + `ON CONFLICT DO NOTHING` beats `SELECT FOR UPDATE` and SERIALIZABLE retry loops.
- [I] Hold protocol: hold on the caller's *selection* (before read-back), TTL 90–120 s, released on change of mind or hang-up, converted by `book`; `search_slots` hides live holds. Idempotency key `callId:actionSeq` on every write.
- [I] **External API**: we cannot lock. A 2xx is the only proof; conflict or any failure → re-query → re-offer; on timeout, read-after-write (list the patient's appointments) before retrying; keep an advisory hold in our own store so our ten calls do not race each other for "the soonest". Reschedule: native endpoint if one exists, else book new → cancel old, never the reverse.
- [I] FHIR-*shaped* tables (Slot.status, Appointment.status, RelatedPerson) cost nothing and read well to a Prosper jury; a FHIR server (Medplum) is overkill — hours of auth and search-parameter learning the scorer never reads.

### (e) Rules so refusals carry the right reason
- [I] Plain TS: `Rule = {id, reasonCode, applies(ctx), violated(ctx), say: {en,es,ca,gl,eu}}` in an ordered list, first violation wins (same semantics as the gates paper [V]). Vitest table tests built from the practice cases. Reason codes = closed enum copied verbatim from the harness contract.
- [V] json-rules-engine: rule events carry custom `params` (a reason code), async facts + almanac. https://github.com/CacheControl/json-rules-engine — useful only if organisers ship rules as data. · [S] GoRules Zen 0.54 (Rust core, Node/Python bindings, JSON decision tables): for rules edited by non-developers. https://github.com/gorules/zen · [I] OPA/Rego, Cedar: a second language and runtime built for authorisation; no payoff in 36 h.

### (f) Prompt injection / social engineering
- [S] "Design Patterns for Securing LLM Agents against Prompt Injections" (Google, Microsoft, IBM, ETH, EPFL): of six patterns, *action-selector* (LLM picks among predefined typed actions) and *context-minimisation* fit a phone agent. https://arxiv.org/abs/2506.08837 · [S] Practitioner audits: least-privilege tools, argument allow-lists, per-tool authorisation at dispatch; "omnibus tools accepting free-form input" = most common critical finding. https://hamming.ai/resources/voice-agent-prompt-injection-testing-guide
- [I] For us: authority comes only from session state written by code (verified identity), never from a claim in the transcript ("I am Dr X", "the manager approved it"); `patientId` and `callId` are injected by the dispatcher, never LLM arguments; tools exposed per phase; no tool can alter rules; free-text record fields (notes) stay out of the prompt (indirect injection). A talked-round model still hits the gate → rejection → **reported as a refusal with that reason**. Counter-risk: an over-defensive prompt refuses legitimate requests and fails those cases — put the "no" in gates, not in prose.

### (g) Outcome reporting
- [I] `deriveOutcome(events) → Report`: pure, synchronous, LLM-free function over the append-only call log (tool results + gate decisions), Zod-validated against the harness schema — it leaves within milliseconds of hang-up. The LLM has no free-text outcome tool, only `decline_request({reasonCode: enum})`, which code cross-checks (e.g. `no_availability` requires a zero-result search in this call). Nothing happened → explicit `no_action` + reason. Never silence.
- [V] Convex: "Scheduling functions from mutations is atomic with the rest of the mutation"; scheduled mutations are "executed exactly once"; actions "at most once" (not retried). https://docs.convex.dev/scheduling/scheduled-functions → `finalizeCall` mutation writes report + outbox row + schedules delivery; the delivery *action* reschedules itself through a mutation on failure; a watchdog scheduled at call start finalises crashed calls.
- [V] Cloudflare Durable Object alarms: "guaranteed at-least-once execution", exponential backoff from 2 s, up to 6 retries, one alarm per object. https://developers.cloudflare.com/durable-objects/api/alarms/ → DO-per-call is the equivalent shape.
- [I] Temporal, Restate, Inngest, Trigger.dev: correct but disproportionate — a second runtime to operate for one guaranteed POST. Outbox + watchdog gives the same guarantee. Delivery idempotent on `callId`.

### (h) Medical urgency
- [V] CARE-Bench (2026-08): patient-facing triage macro-F1 46.9–63.4 even when prompted; "only 33.5% of prompted outputs preserved" a needed clarification step; "not a simple prompting problem". https://arxiv.org/abs/2608.03731 · [S] Lay self-triage audits show persistent red-flag under-triage; one study reports 51.6% of clear emergencies under-triaged. https://pmc.ncbi.nlm.nih.gov/articles/PMC13109825/
- [I] Pattern, OR-ed for recall: (1) five-language red-flag lexicon on every user transcript (chest pain, cannot breathe, stroke signs, heavy bleeding, fainting, anaphylaxis, suicidal intent, bleeding in pregnancy, infant fever); (2) out-of-band text-model classifier per user turn, forced structured output `{acute, category, quote}` — it must not depend on the talking model choosing to call a tool. Fires → code enters `escalated`: write tools removed, 112 script, outcome `escalated_urgent`. Lexicon-only hit with past tense or negation ("had chest pain last year, need my follow-up") → one clarifying question, because a false escalation fails a booking case just as literally.

### Gemini function calling — what changes tool design
- [V] **`gemini-3.8-live` (stable, updated Sept 2026): "Async execution (`behavior: NON_BLOCKING`) is now the default function calling mode."** The model may keep talking — and claim success — while `book` is in flight. "Set `behavior: BLOCKING`" on every write and on every lookup that decides the next sentence. `thinking_level` is unsupported there. 3.1 Flash Live: sync only. https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live · https://ai.google.dev/gemini-api/docs/live-api/tools
- [V] Live API "doesn't support automatic tool response handling. You must handle tool responses manually" — consistent with owning the dispatcher.
- [V] Text API modes `auto | any | none | validated`: `validated` "ensures function schema adherence", `any` forces a call (use it for extraction and classifier side-calls; examples use `gemini-3.8-flash`). Parallel and compositional calls are on → the dispatcher serialises per call and rejects a turn carrying more than one write. https://ai.google.dev/gemini-api/docs/function-calling
- [S] Schemas are an OpenAPI subset (type, nullable, required, format, description, properties, items, enum, anyOf, $ref, $defs; nesting ≤32) and `anyOf` support has varied by model → flat objects, a `kind` enum + optional fields instead of unions. [I] Strip `$schema`/`additionalProperties` from Zod-generated JSON Schema.
- [V] Gemini 3 thought signatures: "SDKs automatically handle" them. [I] So keep history in `@google/genai` chat/session objects; a hand-rolled history that drops signatures degrades tool calling.
- [I] Given τ-Voice, run slot extraction as a text-model side-call on the transcript even when the voice is speech-to-speech, and compare with the live model's tool args before a write. OpenAI fallback: same design; strict function schemas are the analogue of `validated`.

## Recommended architecture

```
voice stack (other note) ── user transcript turns ──┐            ┌── agent text / tool results
                                                     ▼            │
┌──────────── CallSession — one object per callId, no module-level state ─────────────┐
│ LLM sees: persona + policy summary + STATE DIGEST rendered by code + only the tools  │
│   legal in this phase.  It proposes a tool call; it never computes or concludes.     │
│ Dispatcher: serialise → Zod-validate → inject callId/patientId → GATES → execute     │
│   gates (pure, read-only, first reject wins, each returns a reasonCode):             │
│   identity_verified · proxy_authorised · read_before_write (slot offered in THIS     │
│   call and still free) · confirmation_matches_args (hash) · clinic_rules ·           │
│   not_escalated · idempotent                                                         │
│ Reducer (state, event) → state: identity · intent · constraints · offered[] · hold · │
│   confirmation · outcome.  Any change to patient/service/doctor/site/slot            │
│   ⇒ confirmation = null and hold released (this is "state survives a mind change").  │
│ Side-channels per user turn (text model, forced structured output):                  │
│   urgency classifier · slot cross-check · TemporalExpr → resolveDate(expr, clock, tz)│
│ Event log (append-only): transcript, proposals, gate decisions, tool I/O,            │
│   transitions ──► live timeline UI = "why the agent said what it said"               │
└──────────────┬───────────────────────────────────────────────┬──────────────────────┘
               ▼                                               ▼
  ClinicPort (one interface, two adapters)      finalize on end | hang-up | watchdog
  ├ ExternalApiAdapter: 2xx = truth, conflict   deriveOutcome(events) → Zod Report → outbox
  │   → re-offer, read-after-write on timeout   → deliver with retry, idempotent on callId
  └ ConvexAdapter: our tables, OCC, TTL holds
```

Critical utterances (date read-back, success, refusal reason) are templated by code from state in five languages; the LLM is told to say them as given (Parlant's "canned responses" idea [S]). Success is only ever spoken from a 2xx tool result.

```ts
const TemporalExpr = z.object({            // flat on purpose (Gemini schema subset)
  kind: z.enum(['date','weekday','offset_days','offset_weeks','soonest','unclear']),
  weekday: z.number().int().min(1).max(7).optional(),          // ISO, Monday = 1
  weekModifier: z.enum(['bare','this','next']).optional(),
  day: z.number().int().optional(), month: z.number().int().optional(),
  offset: z.number().int().optional(),
  partOfDay: z.enum(['first_thing','morning','midday','afternoon','evening','any']).optional(),
  time: z.string().regex(/^\d{2}:\d{2}$/).optional(),
  verbatim: z.string(),                                         // for the log
});
type Gate = (tool: ToolName, args: unknown, s: CallState, db: ClinicPort) => Promise<{ok:true}|{ok:false; reasonCode: ReasonCode}>;
```

**TypeScript picks (primary)**
- State: hand-rolled reducer + discriminated-union events with an exhaustive `never` check. XState 5 only if someone already knows it (its visualiser is a jury asset). Model the *transaction*, not the conversation order — the LLM may collect slots in any order; code gates the writes.
- Validation: Zod 4 for tool args, the Report and the harness contract.
- LLM: `@google/genai`; live model to talk with `behavior: BLOCKING` tools; `gemini-3.8-flash` for side-channels in `any`/`validated` mode.
- Dates: own `resolveDate()` (~150 lines) on Luxon or a Temporal polyfill, zone `Europe/Madrid`, clock injected (harness "today" if supplied). chrono-node only as an en/es cross-check inside tests, never as the resolver [T].
- Names: own Iberian fold + fuzzball `token_set_ratio` on folded strings for candidates; exact DOB/phone compare for identity; `double-metaphone` at most as a tiebreak.
- Store, log, outbox, watchdog, live dashboard: Convex (sponsor; OCC; atomic scheduling; reactive queries give the live call timeline for free). Alternative: one Cloudflare Durable Object per call if the voice edge already runs on Workers.
- Rules: plain TS predicates + Vitest tables; json-rules-engine only if rules arrive as data.
- Self-test: text-mode caller simulator (LLM persona per problem) × 18 problems × k runs → pass^k (the τ-bench metric); assert on the derived Report, never on the transcript. Add a ten-parallel-calls run.

**Python appendix**: Pipecat core Flows (text-LLM pipeline only, see sibling note) or LiveKit Agents Python (prebuilt tasks exist there); Pydantic v2; identical reducer/gates/log; rapidfuzz 3.14 + the same fold (abydos `SpanishMetaphone` if it installs); dates = same LLM-extract + `zoneinfo` compute — **not dateparser** [T]; Postgres partial unique index or exclusion constraint, or Convex over HTTP; `try/finally` finaliser + outbox table + sweeper; Burr only if a state UI is wanted [I].

## Top failure modes against a literal scorer
1. Agent says "booked" but no write happened or it failed (false success, 45–48% of failures [V]). Fix: success spoken only from a 2xx; report from the log.
2. Write happened, report missing: hang-up, crash, exception in the finaliser. Fix: outbox + watchdog.
3. LLM-written summary diverges from the store (slot id, date, doctor). Fix: `deriveOutcome`.
4. Gemini 3.8 Live default NON_BLOCKING: model speaks before the tool result [V]. Fix: `BLOCKING`.
5. Wrong date: "next Thursday" off by a week; "pasado mañana" read as tomorrow [T]; bare hour dropped [T]; UTC shift; real clock used instead of the simulated "today".
6. Refusal with a paraphrased or wrong reason code, or a polite "sorry" and no report at all.
7. Wrong one of four matching patients; or booked for the caller instead of the child/father.
8. Mind changed after confirmation: stale args booked, both slots booked, or old cancelled and new not created. Fix: invalidation rule + args-hash gate + book-then-cancel.
9. Duplicate writes from retries, timeouts or parallel/duplicate function calls. Fix: idempotency key.
10. Ten at once: same "soonest" slot double-booked; module-level "current call" state shared across sessions; model/STT quota exhausted mid-run (sibling note: AI Studio concurrency not guaranteed).
11. Urgent caller gets a booking (or booking + escalation); or a historic symptom triggers a false escalation.
12. Talked into a forbidden action — or the inverse, an over-defensive refusal of a legal request.
13. Full diary: agent invents a slot, or books another doctor/site without consent, when the accepted outcome is "no availability".
14. ca/gl/eu: names or dates mangled in extraction; report enum/ID/date format not byte-exact.

## Hackathon fast-path
- H0–2: starter kit → freeze the Report schema and reason-code enum in Zod; write `deriveOutcome` and a replay test that feeds the published practice answers through it.
- H2–8: reducer, dispatcher, gates, rules, `ClinicPort` with the adapter we need; `resolveDate` with a 5-language × 15-phrase table test; fold + matcher + DOB verification.
- H8–14: wire to voice; `BLOCKING` tools; finaliser, outbox, watchdog; idempotency; ten-parallel run.
- H14–24: urgency side-channel, proxy callers, injection cases, unknown/four-match callers; text-mode simulator with pass^k per problem; run for score before the first checkpoint.
- H24+: live timeline UI from the event log, language polish, jury demo script.

## Gaps
- Harness contract: Report schema (net outcome vs action list), reason-code enum, simulated "today", caller ID, whether the records API exists and offers holds/idempotency/native reschedule.
- Scorer conventions only the practice cases reveal: "next Thursday", proxy booking, alternatives or waitlist on a full diary, register-then-book reporting.
- Not tested: Gemini's own extraction accuracy in ca/gl/eu (only libraries were tested); 3.8 Live `BLOCKING` under barge-in; abydos on Python 3.14; Zod → Gemini schema sanitising.
- Not opened (snippet only): Convex OCC page, the Design Patterns paper, Rasa/Parlant/XState/GoRules pages. Not evaluated: SUTime, HeidelTime, OPA, Cedar, Temporal, Restate, Inngest, Trigger.dev (judged by reasoning only).
- Not found: a validated es/ca/gl/eu red-flag symptom lexicon; Spanish phone-spelling conventions; any Prosper engineering post on how they score calls (their blog is buyer guides).
- The name-matching test is 12 hand-made pairs — indicative, not a benchmark; thresholds must be tuned on the real records.
