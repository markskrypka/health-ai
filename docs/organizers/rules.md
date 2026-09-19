# Scoring

**Version 2.2-draft · 19 September 2026 · HackSpain, 18–20 September 2026**

This page is the automatic score: what passes a case, how points are counted,
what the limits are, and what happens when a call fails. The jury's *final
boss* is scored separately and is described in
[what the challenge is](challenge.md#who-wins).

**Changed on Saturday 19 September: a scored run is now one problem and one
call.** Until this morning the scored lane was *Run All* — four private cases
of every open problem at once — and the board ranked each team's best one. It
is now a single call at a problem you choose, the cooldown between scored runs
is twelve minutes, a problem credits your first four passed cases, and your
scored calls **pool** instead of competing. Nothing was re-judged and **no
team's score fell**: a Run All dialled exactly four cases of each problem,
which is exactly what a problem now credits, so every case you have already
passed still counts. Teams who took more than one Run All gain, because those
runs now add up instead of one replacing another. The reason is capacity, and
it is spelled out under [the two lanes](#the-two-lanes).

**Updated later the same day: the cooldown between scored runs is five
minutes**, down from the twelve minutes above. It asks the harness for more
than it clears at full field size, so expect the run queue, not the cooldown,
to set how long a scored run actually takes once the field is busy.

## What passes a case

A case passes or it fails. There is no partial credit within a case — not for
a field, not for most of a name, not for an id that is one character out.

A case passes if the **list of actions** you submit matches one the case
accepts, after [normalization](scoring.md). What you submit and what each
action carries is in [the contract](contract.md).

**Doing nothing is not silence.** A call whose right answer is "this cannot be
booked" still submits a `NO_ACTION` carrying the reason. An empty list, or no
submission at all, is always wrong — otherwise an agent that crashed would
score the same as one that correctly refused.

**Nothing about the conversation is scored here.** Voice, manner, how personal
the call felt and how well the load was spread all belong to the jury. See
[the scheduling guidelines](clinic-api.md#scheduling-guidelines) for what to do
with them.

**More than one answer can be correct.** "The earliest appointment with a GP"
has three right answers when three GPs are free at the same minute. A case
carries the **set** of acceptable outcomes and your submission passes if it
matches any member. Scoring stays binary: it is membership, not partial credit.

Expected answers are computed through the same availability use case you call,
so a case can never expect an appointment the API would not have offered.

## The two lanes

**Practice** dials one published case, answer and all. You pick the problem
and you pick the case. As often as you like within the rate limit. It scores
nothing.

**Scored** is the lane the standings come from: **one private case of one
problem, one call.** You pick the problem. You do not pick the case, and its
answer is never published. Take as many as you like, one at a time, with a
cooldown between them. [The problem set](problems.md) says which problems are
open to dial now.

**One queued or active run at a time, in either lane**, and **5 minutes**
between scored runs, counted from the moment your last one *finished*. From
finished rather than requested, because timing it from the request would let a
busy harness pay its own queue wait out of your cooldown — the throttle would
slacken exactly when it is needed. That cooldown is **global**: it is one
clock for the team, so a scored run at any problem blocks a scored run at
every problem until it completes and the five minutes elapse. Practice is on
its own clock at 30 seconds, which exists only to stop a tight retry loop.

One call rather than a sweep of the whole open set because that is what the
wire can serve. The harness carries **ten calls at once for the entire field**
— one judge process on one event loop, a measured ceiling rather than a policy
— and a call holds a line for about three and a half minutes, so it clears
roughly 170 calls an hour in total. Sixty teams each taking a twenty-call
sweep every forty minutes asks for about ten times that, and the open set
would have grown to sixty-eight calls by Sunday. One call per scored run,
spaced by the cooldown, is the shape that fits.

At five minutes, sixty teams each asking every cycle add up to about 720
calls an hour against that same ~170-an-hour ceiling — more than the harness
clears on its own. The run queue, not the cooldown, carries the gap: at a
busy field a scored run can sit queued well past when its cooldown alone
would have allowed the next one.

Private cases are generated per call and their answers are never published.

While scoring is open, a private case tells you **whether it passed, whose
failure it was, and a failure signal** such as `missing_record` or
`record_mismatch`. It does not tell you which field lost, and it carries no
transcript and no audio. Those open at the **reveal — Monday 21 September,
00:00 Europe/Madrid** — after the event has ended. The expected values are never
published, before the reveal or after it.

Practice is the lane you debug in: a published case shows you its answer, the
fields your record lost, the transcript and the recording, straight away. See
[recordings](#recordings).

## Points

Every scored problem carries a **difficulty weight from 1 to 5**, published on
the problem list and in [the problem set](problems.md). Every private case you
pass is worth its problem's weight — a whole point at least, never a fraction
of one. **Your score is the sum of those. There is no percentage and no
denominator.**

```
points = sum over problems of (its passed cases × its weight)
```

**A problem credits your first four passed cases.** Passes beyond the fourth
at the same problem are worth nothing, so the sum above counts at most four
cases per problem however many you dial. Bank four cases of *The Real Call*
and 20 points go on the board; bank four of *The Simple Booking* and 4 do. The
most the full roster can give is **208** — the 52 weights, four times over.

Four rather than one because one binary call per run would make the board ask
only "did this agent ever pass this problem once", and at the ten or so
attempts per problem a weekend affords, an agent that is right well under half
the time clears that bar nearly every time. Two agents that are plainly not
the same would tie. Four passes is a sample rather than a coin flip.

A sum rather than a percentage because the set opens across the weekend. Under
a percentage, the same agent's score would fall every time we released a
problem it had not been built for — it would look like it was getting worse
while it sat there unchanged. A sum only ever grows as you solve more, and a
score from Friday means the same thing on Sunday.

**A problem nobody attempted scores nothing**, exactly like one that was
dialled and failed. There is no credit for what you did not get to. A call
that never produced a submission is an attempted, failed case: silence is
never cheaper than a wrong answer.

**Where you spend your calls is now a real decision.** Every credited case is
one call you chose to make, and the cooldown fixes how many you get. Dialling
only the problems you are already good at is allowed, and it caps you at what
those problems are worth: four cases of *The Simple Booking* is 4 points,
four of *The Real Call* is 20. Once a problem has credited its four, dialling
it again pays nothing at all, so the next call is better spent on a problem
that still owes you something.

**Your scored calls pool.** Every one the harness has judged counts, whenever
you made it — not your best run, not your latest. A scored call can only ever
raise your score, so an experiment on Sunday evening can never cost you what
you banked on Friday, and iterating is never punished. It is not free of luck
— four cases per problem is a sample — so the board shows how many scored runs
backed a score beside it.

**Your own page shows where you stand per problem**: how many of the four
credited cases you have banked there, and how many you have dialled. That is
what tells you a problem is finished and the next call belongs somewhere else.
A scored call itself still shows only whether it passed, whose failure it was
and a failure signal — no answer, no fields, no transcript and no audio before
the reveal.

Problem 2 scores nothing at all — it carries no weight and the scored lane
never dials it. Practice calls never score either.

**Problems open progressively.** The set is released as each problem is
verified end to end. What you have already earned is yours: whether a problem
is open decides what you may dial, never what a call you already made was
worth, and there is no denominator for a release to move.

[Attributed harness failures](#when-a-call-fails) are excluded rather than failed.

## Call limits

Every call is capped at **ten minutes** — an agent that cannot book in ten
minutes has failed. A call is also cut off if it takes too long to connect or
goes quiet, which means **no audible audio** from your agent: streaming silence
keeps the socket open but counts as saying nothing. Before cutting off, the
patient prompts a quiet agent twice, about ten seconds into each silence
("hello? are you still there?"), repeating what they had just asked; an agent
that stays silent after that is cut off and the call attributed to your agent.

A call cut off this way is still an attempt. Without an accepted record it
scores nothing.

## What is not scored

- Voice quality, accent, naturalness, politeness, conversational style.
- Transcription accuracy on its own, or spelling aloud.
- The number or order of questions, tool calls or confirmations.
- Model choice, architecture, token usage, provider cost.
- Speed. Limits apply and can stop a valid record arriving, but being fast
  earns nothing.

A good conversation does not rescue a wrong record, and a clumsy one does not
fail a right one. The one exception is
[problem 14](problems.md#14-adversarial-and-privacy), where the transcript
is checked for leaked patient data.

## Corrections and disputes

A rule change is announced to every team, with the old and new wording, the
reason and the effective time, before it takes effect. The wire and the
submission schema stay backward compatible for the weekend. A change to matching, eligibility, points
or deadlines is a scoring change even when it is a bug fix.

If a correction affects results already recorded, the decision on rejudging or
exclusion is published for all affected teams before the standings move.

For a dispute, give an organiser your team, run and call ids, the rules
version, the rule you expected and what you observed. See
[recordings](#recordings); scored-case evidence is not released while
scoring is open.

The wall freezes Sunday 20 September at 06:00 Europe/Madrid. Only runs
completed at or before that instant count. Equal scores are ordered by time:
the team that reached the score first places higher. The clock is the finish
of the last call that earned points, so calls made after that which earn
nothing do not move a team down.

Private-case detail opens to each team at the reveal, Monday 21 September at
00:00 Europe/Madrid — after the stage final, so nothing can leak into it.

## When a call fails

Attribution is deterministic. No LLM arbiter decides whether a failure counts.
Each settled case retains its comparison and observed failure signals.

| Evidence | Attribution | Run treatment |
| --- | --- | --- |
| Matching record, no failure signals | none | Case passes |
| Missing/mismatching record, no infrastructure signal | agent_issue | Case fails |
| Endpoint unreachable, malformed agent message, or clean early hang-up | agent_issue | Case fails |
| No audible audio from your agent for the silence window | agent_issue | Case fails |
| Wall-clock limit, turn cap, unexplained disconnect, unidentified pipeline error | inconclusive | Case fails; evidence is available for investigation |
| Identified harness STT/LLM/TTS error, or confirmed local socket defect | harness_issue | Case is voided: it leaves its problem's tally |
| Confirmed harness defect and independently observed agent failure | mixed | Case is voided: it leaves its problem's tally |

**A call our side spoiled is dialled again before it is judged.** If any
harness signal — an STT, LLM or TTS error, dropped agent audio on our line, or
an unidentified pipeline error — was raised during a call that did not pass,
whether it proved a lasting defect or was a blip the call rode out, the case
is dialled once more under a new call id. Your agent receives a second call
for the same case and submits a record against the new id; only that second
call is recorded and scored. A second spoiled call is recorded as it stands:
voided if the defect was confirmed, judged on its evidence otherwise. A case
that passed is never redialled, and a run you have cancelled keeps its first
attempt.

A harness verdict requires a concrete **component, problem, and fix** attached to
a recognised harness signal. An error label alone is not enough. A record
mismatch or missing record during a harness failure does not independently prove
an agent defect. TTS throttling reported through its error frames counts as a
provider defect; slow speech alone does not prove throttling. A socket disconnect
does not identify which host or network failed. `ENETDOWN` on the judge host does.

A run is voided only when every one of its calls was voided. A voided run
contributes no score and releases the cooldown for its own mode. Beyond the
single redial above, nothing is rerun on its own. The owning team's run API
response contains `status: "voided"`, a notification, and per-call attribution
and signal codes. Request a replacement run explicitly. A later run can still occupy the team's
active slot or start a new cooldown. Retrying delivery of an old settlement does
not reset that later cooldown.

**A scored run cannot be called off once its call is in the air.** Cancelling
one that has started never stopped a call already in flight — and a scored run
is now that one call, so there is nothing left for cancellation to stop. The
call runs to its end and is judged normally: you keep the result, because you
have already spent the cooldown on it and throwing away a case that passed
would make Cancel cost you a point for nothing. A run that recorded no call at
all settles as cancelled, which scores nothing and does not release its
cooldown — that is what stops an abandoned run being a way to skip the wait.

For evidence, organisers use the existing `X-Admin-Key` with
`GET /admin/teams/{team_id}/runs/{run_id}/evidence`. It returns retained error
details and concrete defects. This route is absent from the public OpenAPI
schema. Team responses expose only identifiers, attribution, and fixed signal
codes: raw provider errors, field names, private case contents and transcripts
are never included in attribution feedback.

## Recordings

By connecting an agent to El Turno, you agree that calls are recorded as audio
and timestamped transcripts for debugging, judging, dispute resolution and the
Sunday stage; all practice and scored recordings are retained after the weekend,
with no automatic deletion schedule.

Other teams can never read your recordings, and you can never read theirs.

### What you can read, and when

Which lane the call came from decides this, not who you are.

**Practice calls are open as soon as they end.** The case was published with its
answer, so there is nothing left to protect: the transcript, the fields your
record lost and the audio are all on your team page immediately.

**Scored calls stay closed until the reveal — Monday 21 September, 00:00
Europe/Madrid.** Until then a private case shows you whether it passed, whose
failure it was and a failure signal, and nothing else: no transcript, no audio,
no per-field comparison. At the reveal the transcript and the audio open to your
team.

**The expected answer to a private case is never published**, before the reveal
or after it. Which field you lost is feedback; the value it wanted is the answer
key.

Organisers are not on this clock — they can read any team's private-case detail
throughout the weekend, because they are who a verdict is disputed to and that
has to be answerable before Sunday rather than after it.

### Transcripts

Transcripts are machine-generated. Their timestamps mark when recognised or
spoken text reached the harness, not exact word boundaries. Audio is the source
to consult when a transcript mishears a name, number or other detail.

## Still to be decided

Organisers confirm these before scored calls open. Until then, nothing in
these docs implies an answer:

- How stage-final places are settled when qualifiers tie.
- The announcement channel for corrections, and who owns a dispute.
