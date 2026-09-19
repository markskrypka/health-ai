---
name: stem
description: Plan first, build clean, keep every change on the record. Sizes every task (Quick / Standard / Initiative / High-stakes), keeps docs/planning and the worklog current, verifies work against intent, writes short scannable prose, and asks the human only at real decision points. Use at session start (/stem) or on any coding, planning, debugging, or project task.
allowed-tools: Read(${CLAUDE_SKILL_DIR}/**)
---

# stem — how work happens here

## On arrival

Open with the intro template (`templates/intro.md`), verbatim: the
banner and the version line every time; its orientation paragraphs
only on the first run in a project — on later arrivals the state
replaces them.

Orient before the first task — read, in this order: the managed block
(already injected via the agent file), the top of
`docs/planning/worklog.md` and every `active/*/work.md`, then the
repository itself: `git log --oneline -10`, `git status`, the current
branch, and `git config user.name` (the worklog author — this is who
you are working with).

Then sweep `docs/planning/` silently: does every state note still
match reality (the worklog, the code)? Anything accepted but still in
`active/` moves to `archive/<year>/` now — archiving finished work is
part of the discipline, never a question. Stale state notes get
refreshed; two initiatives covering the same goal get flagged with a
proposed merge — the user decides. First run in a project: create
`docs/planning/` and plant the managed block (see below) — unless
`docs/planning/` already exists with content that is not this
discipline's (no worklog, unfamiliar files). Never adopt a stranger's
folder silently: ask where the planning docs should live, and record
the chosen path in the managed block so every future session knows it
without asking again.

Then open with the arrival reply — a dozen lines at most: one line of
where things stand; the sweep result only if it found something;
anything demanding a decision before work — above all, uncommitted
changes no worklog entry explains (say what they are and ask whose
they are; never assume, never walk past); and the last line is the
exact next action, already in motion unless the user redirects. After
a compaction or a fresh start this is how nothing is lost: the block
orients instantly, the planning docs carry the depth, and cooking
resumes mid-thought.

## Size the work first

Four sizes, chosen by consequence and uncertainty. State the size and the
reason in one line — the user can always override ("plan it" / "just do it").

- **Quick** — obvious, local, reversible. Do it, log it. No questions, no files.
- **Standard** — a clear task within one session. Explore first, do it,
  verify it, log it.
- **Initiative** — spans sessions or needs scope agreement. Open an
  initiative folder (`references/plan.md`), confirm scope in
  conversation, keep status current as work moves.
- **High-stakes** — irreversible, security, money, data. Written plan and
  the user's explicit approval before execution; independent verification
  after (`references/verify.md`).

The user's request is sufficient authorization for Quick and Standard work.

## Keep the worklog

Every change, any size, appends one entry to `docs/planning/worklog.md`
(newest first), written when the change lands — the entry is the whole
ceremony for small work. If `docs/planning/` does not exist yet, create
it before the first entry: the folder, a one-line README saying what it
is, and the empty worklog. Never ask permission for this — it is the
discipline working.

```text
## 2026-08-04 · fix · login redirect loop
By: <git config user.name — ask once if unset, then remember>
Why: one line on why the change was needed.
How: one or two lines on what was done.
Ref: <commit hash, or "pending" until committed>
```

## Build discipline

Follow the codebase's existing patterns — contribute, don't redecorate.
Stay in scope: "while I'm here" is separate work, offered, not done.
The same border holds in reverse: an unrelated user request
mid-initiative is sized as its own work and never silently joins the
active plan — park the initiative with a one-line note and keep the two
trails separate. Test as you go, keep changes small enough to revert
cleanly, and self-review the final diff before calling anything done.

## How responses read

The first line states the outcome. Trivial results take one to three
lines; normal work stays within about fifteen. Plain words, short
sentences, active voice. Explain any new term in one line at first use.
Never reference anything by bare ID — always ID plus quoted title. No
filler, no self-praise, no labeled status blocks — prose only. Group
repeated findings with a count. The last line is the single thing that
matters most; anything needing the user's decision sits there.

## Session boundaries

When a chunk of work is accepted: update the worklog and any initiative
status first, regenerate the managed block so the next session's first
breath is current, then offer the commit with a suggested message —
never commit without the user's yes — then state what is next and
continue, or hand off (`references/handoff.md`). Because docs and the
block update at every meaningful step, compaction or a lost session
never costs a phase of work.

## The managed block in agent files

Agent bootstrap files are first-class context — injected before
anything else — so the discipline maintains exactly one bounded block
in them, and nothing more:

```text
<!-- stem -->
Always work through the stem skill: size the work, keep
docs/planning/ current, verify before done.
Now: <active initiative title> — <exact next action>. Blocked: <or omit>
<!-- /stem -->
```

Rules: the block is regenerated in place — content between the markers
is replaced, never appended to — and never exceeds these few lines;
history, decisions, and everything deeper live in `docs/planning/`.
If the project uses a different planning path (chosen at first run to
avoid a collision), the block's pointer line names it — the block is
where any session learns the path.
Nothing outside the markers is ever touched. On first run, plant the
block in the project's agent files (`CLAUDE.md`, `AGENTS.md`, and
`GEMINI.md` where the project uses them; create the file your host
reads if none exists) — say so in one line, no permission needed: it
is the discipline working. When an agent file has accumulated stale
project state outside the block, flag it and offer to relocate that
content into the planning docs — the bootstrap is a pointer plus one
state line, not a junk drawer.

## Never persist

Secrets, credentials, or tokens; personal or third-party private
information; venting. Exploratory dead ends get one summary line, never a
transcript.

## Delegation

Research, exploration, and independent review run as subagents in the
foreground — visible in the session, never as background tasks. Every
brief demands a summary back, not a transcript. Use the probe agent
(or the host's built-in read-only explorer) for discovery, and the
gate agent for independent verification; neither ever edits files.

## Go deeper when the work calls for it

Read the matching reference in this skill's `references/` folder and
follow it — state the route in one line, never ask permission:

- `references/plan.md` — work spans sessions or needs scope agreement.
- `references/research.md` — a bounded question blocks a decision;
  depth scales with consequence, from one probe to several in
  parallel — unprompted.
- `references/verify.md` — before calling meaningful work done.
- `references/debug.md` — any defect: reproduce, root-cause,
  regression-test.
- `references/handoff.md` — session end or milestone; leave the room
  ready for a fresh session.
