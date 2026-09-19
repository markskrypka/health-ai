"""Evals without phoning: every published case, played in text against the real agent logic.

The caller is an LLM given the case's own published prompt. The agent is production's system prompt,
production's tools and production's model — only the audio is missing. The clock is pinned to the
case, submissions are captured instead of POSTed, and the verdict is the leaderboard's own rule
(evals/scoring.py): exact match after the published normalization. Repeats give a pass RATE, because
one green run of a stochastic agent proves little.

  .venv/bin/python -m evals.run                                  all 73 cases, once
  .venv/bin/python -m evals.run --problem simple_booking,the_rules --runs 5
  .venv/bin/python -m evals.run --case 14a8720 -v                one case, with the conversation
  .venv/bin/python -m evals.run --today                          accepted answers as the dashboard shows them today
"""

import argparse
import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime

import httpx
from google import genai
from google.genai import types

from clinic_agent import config, prompt, tools
from clinic_agent.bot import GREETING
from clinic_agent.clinic import ClinicClient
from clinic_agent.session import CallSession
from evals import scoring

HANGUP = "[HANGUP]"
_CALLER_RULES = """

You are the CALLER on a phone call to the clinic's receptionist. Stay in character.
- Say only what you would say aloud: one or two short sentences per turn, in {language}.
- Give a detail only when asked for it, unless your instructions say otherwise. Never invent details that are not above.
- If the receptionist reads something back wrong, correct them.
- Do not hang up the moment you agree to something: wait until the receptionist has CONFIRMED it is booked, moved, cancelled or registered — or has clearly told you it cannot be done. Then say goodbye and end that message with {hangup}.
"""
_LANG = {"en": "English", "es": "Spanish", "ca": "Catalan", "gl": "Galician", "eu": "Basque"}


def _declarations() -> list[types.Tool]:
    return [types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, description=desc,
                                  parameters_json_schema={"type": "object", "properties": props, "required": req})
        for name, (_, desc, props, req) in tools.TOOLS.items()])]


async def play(client: genai.Client, api: ClinicClient, catalogue: dict, case: dict, now: datetime) -> dict:
    phone = case["persona"].get("phone")
    session = CallSession(call_id=f'eval-{case["id"]}', from_number=f"+34{phone}" if phone else None,
                          now=now, dry_run=True, persist_log=False)
    agent_cfg = types.GenerateContentConfig(
        system_instruction=prompt.build(catalogue, now, bool(session.from_number)),
        tools=_declarations(),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level="minimal"))
    history: list[types.Content] = [types.Content(role="model", parts=[types.Part(text=GREETING)])]
    caller = client.aio.chats.create(model=config.LLM_MODEL, config=types.GenerateContentConfig(
        system_instruction=case["caller_prompt"] + _CALLER_RULES.format(
            language=_LANG.get(case["language"], "English"), hangup=HANGUP),
        thinking_config=types.ThinkingConfig(thinking_level="minimal")))

    transcript = [("agent", GREETING)]
    model_secs: list[float] = []
    agent_says = GREETING
    for _ in range(case["persona"].get("turn_cap", 28)):
        said = ((await caller.send_message(agent_says)).text or "").strip()
        transcript.append(("caller", said))
        if HANGUP in said:
            break
        session.heard.append(said)
        history.append(types.Content(role="user", parts=[types.Part(text=said.replace(HANGUP, "").strip())]))
        spoken: list[str] = []
        for _round in range(8):  # model rounds within one agent turn: speech, tool calls, speech
            t0 = time.monotonic()
            resp = await client.aio.models.generate_content(model=config.LLM_MODEL, contents=history, config=agent_cfg)
            model_secs.append(time.monotonic() - t0)
            content = resp.candidates[0].content if resp.candidates else None
            if content is None or not content.parts:
                break
            history.append(content)  # as returned: keeps the model's thought signatures intact
            spoken += [p.text for p in content.parts if p.text and not getattr(p, "thought", False)]
            calls = [p.function_call for p in content.parts if p.function_call]
            if not calls:
                break
            replies = []
            for fc in calls:
                args = dict(fc.args or {})
                try:
                    result = await tools.TOOLS[fc.name][0](session, api, **args)
                except Exception as err:  # same contract as the live handler: a tool never crashes the call
                    result = {"status": "error", "say": f"{fc.name} failed: {type(err).__name__}: {err}"}
                transcript.append(("tool", f"{fc.name}({json.dumps(args, ensure_ascii=False)}) → {json.dumps(result, ensure_ascii=False)[:400]}"))
                replies.append(types.Part.from_function_response(name=fc.name, response=result))
            history.append(types.Content(role="user", parts=replies))
        agent_says = " ".join(s.strip() for s in spoken if s.strip()) or "(silence)"
        session.said.append(agent_says)
        transcript.append(("agent", agent_says))

    await tools.finalize(session, api)  # production does the same when the socket closes
    acceptable = case["expected"]["acceptable"]
    return {"case": case["id"], "problem": case["problem_id"], "passed": scoring.passes(session.submissions, acceptable),
            "diff": scoring.diff(session.submissions, acceptable), "submitted": session.submissions,
            "transcript": transcript, "model_secs": model_secs,
            "caller_turns": sum(1 for who, _ in transcript if who == "caller")}


def todays_answers() -> dict[str, list[dict]]:
    """case_id → accepted answers as the dashboard shows them today (public cases re-anchor each morning)."""
    base = config.PROSPER_BASE_URL + "/leaderboard/api"
    with httpx.Client(timeout=30) as http:
        http.post(f"{base}/session", json={"email": os.environ["PROSPER_DASHBOARD_EMAIL"],
                                           "password": os.environ["PROSPER_DASHBOARD_PASSWORD"]}).raise_for_status()
        out = {}
        for p in http.get(f"{base}/problems").json()["problems"]:
            for ex in http.get(f'{base}/problems/{p["id"]}').json().get("examples", []):
                out[ex["case_id"]] = ex["accepted"]
        return out


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--problem", default="", help="comma-separated problem ids")
    ap.add_argument("--case", default="", help="substring of a case id")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--today", action="store_true", help="score against today's accepted answers from the dashboard")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every conversation, not only failures")
    args = ap.parse_args()

    cases = json.loads((config.ORGANIZERS_DIR / "public-cases.json").read_text())["cases"]
    wanted = {p for p in args.problem.split(",") if p}
    cases = [c for c in cases if (not wanted or c["problem_id"] in wanted) and args.case in c["id"]]
    now_for = lambda c: datetime.fromisoformat(c["reference_time"])  # noqa: E731
    if args.today:
        answers = todays_answers()
        cases = [c for c in cases if c["id"] in answers]  # only problems that are open today
        for c in cases:
            c["expected"] = {"acceptable": answers[c["id"]]}
        anchor = datetime.now(config.MADRID).replace(hour=9, minute=0, second=0, microsecond=0)
        now_for = lambda c: anchor  # noqa: E731
    if not cases:
        raise SystemExit("no cases match")

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    api = ClinicClient()
    catalogue = await api.catalogue()
    gate = asyncio.Semaphore(args.concurrency)

    async def one(case: dict) -> dict:
        async with gate:
            try:
                return await play(client, api, catalogue, case, now_for(case))
            except Exception as err:  # an eval that crashes is a failed run, reported as such
                return {"case": case["id"], "problem": case["problem_id"], "passed": False, "submitted": [],
                        "diff": [f"runner error: {type(err).__name__}: {err}"], "transcript": [], "model_secs": [], "caller_turns": 0}

    started = time.monotonic()
    results = await asyncio.gather(*(one(c) for c in cases for _ in range(args.runs)))
    await api.aclose()

    by_case: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_case[r["case"]].append(r)
    by_problem: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # passed runs, runs, cases with every run green
    for case_id, runs in by_case.items():
        ok = sum(r["passed"] for r in runs)
        tally = by_problem[runs[0]["problem"]]
        tally[0] += ok; tally[1] += len(runs); tally[2] += ok == len(runs)  # noqa: E702
        print(f'{"PASS" if ok == len(runs) else "FAIL"} {ok}/{len(runs)}  {case_id}')
        for r in runs:
            if not r["passed"] or args.verbose:
                for line in r["diff"]:
                    print(f"        ✗ {line}")
                if not r["submitted"]:
                    print("        ✗ nothing submitted")
                for who, text in r["transcript"]:
                    print(f"        {who:6} {text}")
                if not args.verbose:
                    break  # one failing conversation per case is enough to read
    print("\nproblem                  runs passed   cases green on every run")
    for problem, (ok, n, green) in by_problem.items():
        print(f"{problem:24} {ok:3}/{n:<3} {100 * ok / n:4.0f}%   {green}/{sum(1 for c in by_case if by_case[c][0]['problem'] == problem)}")
    secs = sorted(s for r in results for s in r["model_secs"])
    total_ok, total = sum(r["passed"] for r in results), len(results)
    print(f"\n{total_ok}/{total} runs passed ({100 * total_ok / total:.0f}%) in {time.monotonic() - started:.0f}s · "
          f"{len(secs)} model rounds, median {secs[len(secs) // 2]:.2f}s, p95 {secs[int(len(secs) * 0.95) - 1]:.2f}s · "
          f"median caller turns {sorted(r['caller_turns'] for r in results)[total // 2]}")

    out_dir = config.ROOT / "eval-runs"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f'{datetime.now().strftime("%m%d-%H%M%S")}.json'
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str))
    print(f"full results: {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
