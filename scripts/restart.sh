#!/usr/bin/env bash
# Restart the server on the current code — but never in the middle of a call: a restart drops the socket,
# and a dropped socket is a failed case. Waits until /health reports no active calls.
set -euo pipefail
cd "$(dirname "$0")/.."
for i in $(seq 1 120); do
  active=$(curl -s -m 2 http://127.0.0.1:7860/health | python3 -c "import sys,json; print(json.load(sys.stdin)['active_calls'])" 2>/dev/null || echo down)
  [ "$active" = "0" ] || [ "$active" = "down" ] && break
  echo "waiting: $active call(s) in flight"; sleep 3
done
pid=$(lsof -nP -tiTCP:7860 -sTCP:LISTEN | head -1 || true)
[ -n "${pid:-}" ] && kill "$pid" && echo "stopped server pid $pid"
for i in $(seq 1 10); do lsof -nP -tiTCP:7860 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
unset DRY_RUN_SUBMIT
mkdir -p logs
nohup caffeinate -dims .venv/bin/python -m uvicorn clinic_agent.server:app --host 127.0.0.1 --port 7860 >> logs/server.log 2>&1 &
for i in $(seq 1 20); do [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:7860/health)" = "200" ] && echo "server up on the new code" && exit 0; sleep 1; done
echo "server did not come up — see logs/server.log"; exit 1
