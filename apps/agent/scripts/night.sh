#!/usr/bin/env bash
# Everything the scored lane needs, in one terminal that outlives any other session: the server, a tunnel of
# its own, the registered endpoint and the scored loop, all kept awake. Run it in a terminal tab and leave it:
#   apps/agent/scripts/night.sh
# It takes over politely: the loop is paused and no call is in flight while the tunnel is swapped.
set -euo pipefail
cd "$(dirname "$0")/../../.."  # the repo root: .venv, logs and .env live there
mkdir -p logs && touch logs/.hold
trap 'rm -f logs/.hold' EXIT
pkill -f "scripts/scored.py loop" || true
for i in $(seq 1 200); do
  active=$(curl -s -m 2 http://127.0.0.1:7860/health | python3 -c "import sys,json; print(json.load(sys.stdin)['active_calls'])" 2>/dev/null || echo down)
  busy=$(.venv/bin/python apps/agent/scripts/scored.py status | grep -c "active run: True" || true)
  if [ "$busy" = "0" ] && { [ "$active" = "0" ] || [ "$active" = "down" ]; }; then break; fi
  echo "waiting for the call in flight to finish…"; sleep 5
done
rm -f logs/.run-in-flight
[ "${active:-down}" = "down" ] && bash apps/agent/scripts/restart.sh && touch logs/.hold
pkill -x ngrok || true
nohup ngrok http 7860 --log=stdout --log-format=json > logs/ngrok.log 2>&1 &
for i in $(seq 1 20); do curl -s -m 2 http://127.0.0.1:4040/api/tunnels | grep -q "https://" && break; sleep 1; done
.venv/bin/python apps/agent/scripts/practice.py endpoint
rm -f logs/.hold
caffeinate -dims .venv/bin/python -u apps/agent/scripts/scored.py loop 2>&1 | tee -a logs/scored-loop.log
