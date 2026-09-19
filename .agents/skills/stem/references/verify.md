# verify — done means checked

Re-read the request (and `contract.md` if this is an initiative). List
what was actually asked. Check each item against what exists now: run
the tests, run the thing itself, read the final diff. Passing tests
alone never equal done.

Report findings by severity — and only the first two enter scope
automatically:

- **blocker** — violates what was agreed or breaks something real.
- **material** — plausible user-visible or reliability impact.
- **minor** — low impact; note it, never block on it.
- **speculative** — no concrete failure path; one line, move on.

For High-stakes work, delegate an independent pass to the gate agent
(foreground; reads and runs tests, never edits) and reconcile its
findings with your own before reporting. Brief the gate with the risk
lens as well as the intent lens: not only "does it do what was asked"
but "what is missing that nobody asked for" — unhandled errors,
security gaps, operational readiness before this meets reality.

Close with the verdict in one line — what was verified and what remains —
and append the worklog entry.
