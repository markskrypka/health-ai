#!/usr/bin/env bash
# The real server, for your own terminal tab: answers the harness on :7860 and POSTs real submissions.
# caffeinate keeps the Mac awake for as long as the server runs. Tunnel, in another tab:
#   ngrok http --url="$NGROK_DOMAIN" 7860        ->  endpoint for the dashboard: wss://$NGROK_DOMAIN/ws
set -euo pipefail
cd "$(dirname "$0")/../../.."  # the repo root: .venv, logs and .env live there
unset DRY_RUN_SUBMIT
mkdir -p logs
exec caffeinate -dims .venv/bin/python -m uvicorn clinic_agent.server:app --host 0.0.0.0 --port 7860 2>&1 | tee -a logs/server.log
