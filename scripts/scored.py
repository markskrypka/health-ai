"""The scored lane on a clock: one scored call the moment the cooldown allows, practice calls in the gaps.

  scored.py status                        credited cases per problem, cooldown, rank
  scored.py loop [<problem>…]             bank four passes at every open scored problem (or only those named);
                                          each scored call goes where weight x observed pass rate is highest,
                                          and the gaps go to practising the problem with the least evidence

Rules 2.1 (19 Sep): a scored run is one private case of one problem; 12 minutes between scored runs, counted
from when the last one finished; one queued or active run per team in either lane; a problem credits the first
four passes; scored calls pool and can only raise the score. So the loop never stops to ask.

It stands down while logs/.hold exists (scripts/restart.sh makes it while the server restarts), and it keeps
logs/.run-in-flight from the moment a run is requested until its verdict, so a restart never lands on a call.
"""

import sys
import time
from pathlib import Path

import practice
from practice import DONE, fetch

LOGS = Path(practice.ROOT) / "logs"
HOLD, IN_FLIGHT = LOGS / ".hold", LOGS / ".run-in-flight"
CREDITED_PER_PROBLEM = 4
PRACTICE_NEEDS_SECS = 210  # a practice call must be over before the cooldown is, or it delays the scored call


def team(http) -> dict:
    if not hasattr(http, "team_id"):
        http.team_id = fetch(http, "GET", "/session", want="viewer").json()["viewer"]["team_id"]
    return fetch(http, "GET", f"/teams/{http.team_id}", want="progress").json()


def status(http) -> None:
    t = team(http)
    weights = {p["id"]: p["weight"] for p in fetch(http, "GET", "/problems", want="problems").json()["problems"]}
    credited = {p["problem_id"]: p for p in t["progress"]}
    print(f'{t["name"]}: rank {t["stats"]["rank"]}, {t["stats"]["best_points"]} points')
    for pid, weight in weights.items():
        if weight:
            p = credited.get(pid, {"credited": 0, "passed": 0})
            print(f'  {pid:<20} weight {weight}   credited {p["credited"]}/{CREDITED_PER_PROBLEM}')
    e = t["eligibility"]
    print(f'active run: {e["active_run"]}   scored cooldown: {e["private_wait"]} s   practice cooldown: {e["public_wait"]} s')


def scored_call(http, problem: str) -> dict:
    """Request one scored call and wait for its verdict. The case and its answer stay hidden until the reveal."""
    r = fetch(http, "POST", f"/problems/{problem}/scored-runs")
    if r.status_code >= 300:
        return {"status": f"not started: {r.text[:160]}"}
    run_id = r.json()["run_id"]
    IN_FLIGHT.write_text(run_id)
    try:
        while True:
            time.sleep(10)
            run = next((x for x in team(http)["runs"] if x["run_id"] == run_id), None)
            if run and run["state"] in DONE:
                return run["cases"][0] if run["cases"] else {"status": run["state"]}
    finally:
        IN_FLIGHT.unlink(missing_ok=True)


def practice_call(http, problem: str, case: dict) -> bool:
    IN_FLIGHT.write_text("practice")
    try:
        print(f'  practice {problem} — {case["caller"]}: {case["summary"][:90]}', flush=True)
        return practice.report(practice.dial(http, problem, case), verbose=False)
    except SystemExit as gave_up:  # the platform's queue can sit on a call for minutes; the loop must outlive that
        print(f"    practice call abandoned: {gave_up}", flush=True)
        return False
    finally:
        IN_FLIGHT.unlink(missing_ok=True)


def worth(problem: str, weights: dict, evidence: dict) -> float:
    """What the next scored call at a problem is worth: its weight times the pass rate seen so far on this
    build, practice and scored calls alike. Unknown counts as one in two, so a new problem is tried."""
    passes, calls = evidence.get(problem, (0, 0))
    return weights[problem] * (passes + 1) / (calls + 2)


def loop(http, only: list[str]) -> None:
    evidence: dict[str, tuple[int, int]] = {}  # problem -> (passes, calls) seen by this loop
    rehearsed: dict[str, int] = {}             # problem -> index of the next published case to practise

    def saw(problem: str, passed: bool) -> None:
        passes, calls = evidence.get(problem, (0, 0))
        evidence[problem] = (passes + passed, calls + 1)

    while True:
        if HOLD.exists():
            time.sleep(5)
            continue
        t = team(http)
        wait = t["eligibility"]
        if not wait["active_run"]:
            IN_FLIGHT.unlink(missing_ok=True)  # left behind if an earlier loop was killed mid-run
        # Problems open through the weekend: read the list every time, so a new one is dialled without a restart.
        weights = {p["id"]: p["weight"] for p in fetch(http, "GET", "/problems", want="problems").json()["problems"]
                   if p["weight"] and (not only or p["id"] in only)}
        credited = {p["problem_id"]: p["credited"] for p in t["progress"]}
        owed = [p for p in weights if credited.get(p, 0) < CREDITED_PER_PROBLEM]
        if wait["active_run"] or not owed:
            time.sleep(10 if wait["active_run"] else 120)
        elif wait["private_wait"] <= 0:
            problem = max(owed, key=lambda p: worth(p, weights, evidence))
            print(f'{time.strftime("%H:%M:%S")} SCORED {problem} (credited {credited.get(problem, 0)}/4) …', flush=True)
            case = scored_call(http, problem)
            if case.get("status") in ("passed", "failed") and case.get("attribution") not in ("harness_issue", "mixed"):
                saw(problem, case["status"] == "passed")
            print(f'{time.strftime("%H:%M:%S")}   → {str(case.get("status")).upper()}  attribution={case.get("attribution")}  '
                  f'signals={case.get("signal_codes")}  call_id={case.get("call_id")}', flush=True)
        elif wait["private_wait"] >= PRACTICE_NEEDS_SECS and wait["public_wait"] <= 0:
            problem = min(owed, key=lambda p: (evidence.get(p, (0, 0))[1], -weights[p]))  # least evidence first
            cases = fetch(http, "GET", f"/problems/{problem}", want="examples").json()["examples"]
            case = cases[rehearsed.get(problem, 0) % len(cases)]
            rehearsed[problem] = rehearsed.get(problem, 0) + 1
            saw(problem, practice_call(http, problem, case))
        else:
            time.sleep(min(max(wait["private_wait"], wait["public_wait"], 1), 15))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    http = practice.login()
    if cmd == "status":
        status(http)
    elif cmd == "loop":
        loop(http, sys.argv[2:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
