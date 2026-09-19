# plan — initiatives

One folder per initiative: `docs/planning/active/<slug>/`

- `contract.md` — goal, scope in and out, success criteria, approvals.
  Owns intent. Changes only with the user's renewed agreement.
- `work.md` — the plan, current status, exact next action. The only
  place status lives, ever.
- `decisions.md` — dated decisions with the why, newest first.
- `research/` — probe findings feeding this work.

Rules: one job per file; status only in `work.md`; every item carries a
human-readable title, never a bare ID. Small work never opens an
initiative — the worklog entry is enough.

Opening one: understand the domain before drafting — the things
involved, how they relate, their lifecycle, and what must always or
never be true; ask only what cannot be inferred from the code or the
conversation. Then draft `contract.md`, ask only the highest-impact
unanswered questions, get the user's explicit scope agreement, and keep
`work.md` current as execution moves — status updates are part of doing
the work, not a separate chore.

The plan in `work.md` breaks the work into pieces small enough to hold:
each piece has a clear done, sequenced dependencies-first and
risk-early. A piece is ready to build when you can say what done looks
like, what the approach is, and how it will be verified — if you
cannot, the thinking is not finished.

## Scope borders — plans stay finite

A material change to an agreed contract is named out loud: stop, say
"this changes the agreed scope," record it, and get renewed agreement
before continuing. Silent scope drift is a defect.

The plan is a ratchet: it only shrinks toward done, and grows only
through renewed agreement. Ideas discovered mid-build default to OUT —
they go under a "Follow-ups" heading at the bottom of `work.md`, never
into the plan. Review findings follow the same border: only blockers
and material findings enter scope automatically.

When the user asks for unrelated work mid-initiative, size that
request on its own — it never silently joins the active plan. Small:
do it as its own work with its own worklog entry, and leave a one-line
park note in the active initiative's `work.md`. Big: open its own
initiative folder; each `work.md` state note says which initiative is
currently in motion.

## Done has a definition

Done is the contract's success criteria — verified and accepted — not
the absence of further ideas. Completing an initiative: verify against
the contract (`verify.md`), write the acceptance note and final status
in `work.md`, list which follow-ups survive so the user can decide if
any becomes a new initiative, move the folder to
`docs/planning/archive/<year>/`, and append the worklog entry. The
folder leaving `active/` is the border made physical — and the move is
automatic: acceptance and archiving are one motion, never a separate
request.
