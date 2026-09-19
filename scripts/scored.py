"""The scored lane on a clock: one scored call the moment the cooldown allows, practice calls in the gaps.

  scored.py status                        credited cases per problem, cooldown, rank
  scored.py loop <problem> [<problem>…]   bank four passes per problem, highest weight first among those named;
                                          between scored calls, practise the same problems' published cases

Rules 2.1 (19 Sep): a scored run is one private case of one problem; 12 minutes between scored runs, counted
from when the last one finished; one queued or active run per team in either lane; a problem credits the first
four passes; scored calls pool and can only raise the score. So the loop never stops to ask.

It stands down while logs/.hold exists (scripts/restart.sh makes it while the server restarts), and it keeps
logs/.run-in-flight from the moment a run is requested until its verdict, so a restart never lands on a call.
"""

import sys
import time
from itertools import cycle
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


def practice_call(http, problem: str, case: dict) -> None:
    IN_FLIGHT.write_text("practice")
    try:
        print(f'  practice {problem} — {case["caller"]}: {case["summary"][:90]}', flush=True)
        practice.report(practice.dial(http, problem, case), verbose=False)
    except SystemExit as gave_up:  # the platform's queue can sit on a call for minutes; the loop must outlive that
        print(f"    practice call abandoned: {gave_up}", flush=True)
    finally:
        IN_FLIGHT.unlink(missing_ok=True)


def loop(http, problems: list[str]) -> None:
    listed = fetch(http, "GET", "/problems", want="problems").json()["problems"]
    weights = {p["id"]: p["weight"] for p in listed}
    rehearsals = cycle([(pid, case) for pid in problems
                        for case in fetch(http, "GET", f"/problems/{pid}", want="examples").json()["examples"]])
    dialled = dict.fromkeys(problems, 0)
    while True:
        if HOLD.exists():
            time.sleep(5)
            continue
        t = team(http)
        credited = {p["problem_id"]: p["credited"] for p in t["progress"]}
        owed = [p for p in problems if credited.get(p, 0) < CREDITED_PER_PROBLEM]
        wait = t["eligibility"]
        if not owed:
            print("every named problem has its four credited cases — nothing left to dial", flush=True)
            return
        if wait["active_run"]:
            time.sleep(10)
        elif wait["private_wait"] <= 0:
            problem = max(owed, key=lambda p: (weights[p], -dialled[p]))  # heaviest first; spread among equals
            dialled[problem] += 1
            print(f'{time.strftime("%H:%M:%S")} SCORED {problem} (credited {credited.get(problem, 0)}/4) …', flush=True)
            case = scored_call(http, problem)
            print(f'{time.strftime("%H:%M:%S")}   → {str(case.get("status")).upper()}  attribution={case.get("attribution")}  '
                  f'signals={case.get("signal_codes")}  call_id={case.get("call_id")}', flush=True)
        elif wait["private_wait"] >= PRACTICE_NEEDS_SECS and wait["public_wait"] <= 0:
            pid, case = next(rehearsals)
            if pid in owed:
                practice_call(http, pid, case)
            else:
                time.sleep(1)
        else:
            time.sleep(min(max(wait["private_wait"], wait["public_wait"], 1), 15))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    http = practice.login()
    if cmd == "status":
        status(http)
    elif cmd == "loop" and len(sys.argv) > 2:
        loop(http, sys.argv[2:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
