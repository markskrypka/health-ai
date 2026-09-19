# debug — no fixes without understanding

Reproduce before touching anything. If it cannot be reproduced, say so
plainly and stop — guessing at fixes is how bugs multiply.

Trace from the symptom to the cause: read the failing path, hold one
hypothesis at a time, test it, discard it honestly. The fix addresses
the cause, never just the symptom, and stays minimal — no drive-by
refactors riding along.

## No workarounds while the cause is findable

A fix without understanding is a band-aid. Never implement — or
suggest — a workaround while the root cause is still findable. When a
workaround is genuinely unavoidable (time, access, a dependency you
cannot touch), say so out loud, mark the worklog entry as a workaround,
and record the follow-up that removes it. A workaround without a
removal plan is a defect with better manners.

## When the normal pass does not find it

Escalate the way research escalates — unprompted, stated in one line.
Send a trace brief to the probe agent: read the failing path end to
end, the git history of the files it touches, and any similar past
fixes. If competing hypotheses remain, run several probes in parallel,
one hypothesis each, and reconcile what comes back. Never downgrade to
"probably fixed" — either the cause is understood or the investigation
is honestly stuck, and you say which.

## When it is live and burning

Contain first: stop the damage and restore service before
understanding it — record the facts as they happen (what, when, what
was tried), and do the full root-cause work after the fire is out.
If the same issue returns, the root cause was missed the first time —
say so and dig again.

Add the regression test that fails before the fix and passes after it.
No test, no done.

Several related bugs are a pattern, not a coincidence — name it, and
let the user decide whether to widen scope.

Worklog entry: Why is the root cause; How is the fix plus the test.
