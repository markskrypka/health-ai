"""Drive the organizers' practice lane from the terminal: what the dashboard's buttons do, scripted.

  practice.py endpoint                 register the current ngrok tunnel as our endpoint
  practice.py list                     open problems and their published cases (today's accepted answers)
  practice.py call <problem> [n|all]   dial published case n (1-based, default 1) or every case of a problem
  practice.py batch <problem>[:n] ...  dial several, one after another (no n = every case), then a summary

Practice calls score nothing. The platform enforces its own limits (30 s between calls, one run at a time);
this script just waits and retries. Credentials come from .env.
"""

import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
BASE = os.environ["PROSPER_BASE_URL"].rstrip("/") + "/leaderboard/api"
DONE = {"completed", "failed", "cancelled", "canceled", "voided", "error"}


def _sign_in(http: httpx.Client) -> None:
    r = http.post(f"{BASE}/session", json={"email": os.environ["PROSPER_DASHBOARD_EMAIL"],
                                           "password": os.environ["PROSPER_DASHBOARD_PASSWORD"]})
    r.raise_for_status()


def login() -> httpx.Client:
    http = httpx.Client(timeout=30)
    _sign_in(http)
    return http


def fetch(http: httpx.Client, method: str, path: str, want: str | None = None, **kw) -> httpx.Response:
    """The platform has bad minutes (invalid JSON, dropped TLS, error bodies, an expired session).
    A batch of calls must ride them out, not die: retry for up to five minutes."""
    for _ in range(50):
        try:
            r = http.request(method, f"{BASE}{path}", **kw)
            if r.status_code == 401:
                _sign_in(http)
                problem = "session expired, signed in again"
            elif r.status_code >= 500 or r.status_code == 429:
                problem = f"HTTP {r.status_code}"
            elif want and want not in r.json():
                problem = f"no {want!r} in the answer: {r.text[:120]}"
            else:
                r.json()
                return r
        except (httpx.HTTPError, ValueError) as err:
            problem = type(err).__name__
        print(f"    platform hiccup ({problem}) — retrying in 6 s")
        time.sleep(6)
    raise SystemExit(f"platform unreachable: {method} {path}")


def tunnel_url() -> str:
    tunnels = httpx.get("http://127.0.0.1:4040/api/tunnels", timeout=5).json()["tunnels"]
    https = next(t["public_url"] for t in tunnels if t["public_url"].startswith("https"))
    return https.replace("https://", "wss://") + "/ws"


def set_endpoint(http: httpx.Client) -> str:
    url = tunnel_url()
    r = http.put(f"{BASE}/endpoint", json={"endpoint": url, "headers": ""})
    r.raise_for_status()
    return r.json()["endpoint"]


def fmt_action(a: dict) -> str:
    rest = {k: v for k, v in a.items() if k != "action"}
    return f'{a.get("action")} ' + " ".join(f"{k}={v}" for k, v in rest.items())


def dial(http: httpx.Client, problem: str, case: dict) -> dict:
    """Trigger one practice call and wait for its verdict."""
    for attempt in range(40):
        r = fetch(http, "POST", f"/problems/{problem}/runs", json={"case_id": case["case_id"]})
        if r.status_code < 300:
            break
        msg = (r.json().get("message") or r.json().get("detail") or r.text) if r.content else r.status_code
        print(f"    platform says: {msg} — waiting 10 s")
        time.sleep(10)
    else:
        raise SystemExit("could not start a practice call")
    run_id = r.json()["run_id"]
    t0 = time.monotonic()
    while time.monotonic() - t0 < 360:
        time.sleep(5)
        attempts = fetch(http, "GET", f"/problems/{problem}/submissions", want="attempts").json()["attempts"]
        mine = next((a for a in attempts if a["run_id"] == run_id), None)
        if mine and mine.get("state") in DONE and mine.get("case", {}).get("status") not in (None, "pending", "running"):
            return mine
    raise SystemExit(f"run {run_id} did not settle in 6 minutes")


def report(attempt: dict, verbose: bool) -> bool:
    c = attempt["case"]
    ok = c["status"] == "passed"
    print(f'  {"PASS" if ok else "FAIL"}  call_id={c["call_id"]}  attribution={c.get("attribution")}  signals={c.get("signal_codes")}')
    for f in c.get("fields", []):
        if not f["matched"]:
            print(f'      ✗ {f["field"]}: expected {f["expected"]!r}, submitted {f["submitted"]!r}')
    if verbose or not ok:
        for t in c.get("transcript", []):
            print(f'      [{t["seconds"]:5.1f}s] {t["speaker"]:8} {t["text"]}')
        print(f'      our event log: logs/calls/{c["call_id"]}.jsonl')
    return ok


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    http = login()
    if cmd == "endpoint":
        print("endpoint registered:", set_endpoint(http))
        return
    if cmd == "list":
        for p in fetch(http, "GET", "/problems", want="problems").json()["problems"]:
            detail = fetch(http, "GET", f'/problems/{p["id"]}').json()
            print(f'\n{p["number"]:>2}. {p["title"]} ({p["id"]}, weight {p["weight"]})')
            for i, ex in enumerate(detail.get("examples", []), 1):
                answers = " || ".join(" + ".join(fmt_action(a) for a in acc["actions"]) for acc in ex["accepted"])
                print(f'    {i}. {ex["caller"]}: {ex["summary"][:110]}\n       → {answers}')
        return
    if cmd in ("call", "batch"):
        specs = [(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "1")] if cmd == "call" else \
                [(a.split(":") + ["all"])[:2] for a in sys.argv[2:]]
        results = []
        for problem, which in specs:
            examples = fetch(http, "GET", f"/problems/{problem}", want="examples").json()["examples"]
            chosen = list(enumerate(examples, 1)) if which == "all" else [(int(which), examples[int(which) - 1])]
            for i, case in chosen:
                print(f'\n{problem} #{i} — {case["caller"]}: {case["summary"][:120]}', flush=True)
                results.append((problem, i, report(dial(http, problem, case), verbose=cmd == "call" and len(chosen) == 1)))
        print()
        for problem in dict.fromkeys(p for p, _, _ in results):
            mine = [(i, ok) for p, i, ok in results if p == problem]
            failed = [f"#{i}" for i, ok in mine if not ok]
            print(f'{problem}: {sum(ok for _, ok in mine)}/{len(mine)} passed' + (f'  — failed {", ".join(failed)}' if failed else ""))
        return
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
