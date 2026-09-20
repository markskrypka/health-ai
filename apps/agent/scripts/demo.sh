#!/usr/bin/env bash
# Everything the jury demo needs besides the phone line, in one terminal:
#   the dry-run call server the caller's page dials (7861), the events service behind both screens (7870),
#   and the web app (3100). The phone line (7860) is not touched: start or restart it with restart.sh / night.sh.
#
#   apps/agent/scripts/demo.sh        then open  http://localhost:3100
#
# Ctrl-C stops all three. Logs: logs/demo-server-7861.log, logs/events-service.log, logs/web-dev.log
set -euo pipefail
cd "$(dirname "$0")/../../.."  # the repo root: .venv, logs and .env live there
mkdir -p logs

# Whatever of the three is already running (an earlier demo.sh, the assistant's session) makes way.
pkill -f "uvicorn clinic_agent.server:app --host 127.0.0.1 --port 7861" 2>/dev/null || true
pkill -f "uvicorn clinic_agent.console:app" 2>/dev/null || true
lsof -ti tcp:3100 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1

pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

DRY_RUN_SUBMIT=1 .venv/bin/python -m uvicorn clinic_agent.server:app --host 127.0.0.1 --port 7861 >> logs/demo-server-7861.log 2>&1 &
pids+=($!)
.venv/bin/python -m uvicorn clinic_agent.console:app --host 127.0.0.1 --port 7870 >> logs/events-service.log 2>&1 &
pids+=($!)
pnpm --filter web dev >> logs/web-dev.log 2>&1 &
pids+=($!)

for port in 7861 7870 3100; do
  for _ in $(seq 1 60); do
    if curl -s -o /dev/null -m 1 "http://127.0.0.1:$port/"; then echo "up: $port"; break; fi
    sleep 0.5
  done
done
phone=$(curl -s -m 2 http://127.0.0.1:7860/health || echo "not running")
echo "phone line (7860): $phone"
echo
echo "  the caller's screen   http://localhost:3100/call"
echo "  the front desk        http://localhost:3100/desk"
echo
wait
