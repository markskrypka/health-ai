#!/usr/bin/env bash
# The way back, if the phone line was restarted on the demo's build and anything about a call looks different:
# the agent exactly as it ran until the restart (commit a7c0062, before the move to apps/agent), unpacked beside
# the repo's own files and started by the same restart.sh — it waits for the line to be idle, as always.
#
#   apps/agent/scripts/old-build.sh            prepare the old build and restart the phone line on it
#   apps/agent/scripts/old-build.sh --check    prepare it and only prove that it starts (port 7862, no calls)
#
# To come forward again: apps/agent/scripts/restart.sh (without PYTHONPATH the phone line runs this checkout).
set -euo pipefail
cd "$(dirname "$0")/../../.."  # the repo root
commit=a7c0062
old="${TMPDIR:-/tmp}/health-ai-$commit"
rm -rf "$old" && mkdir -p "$old"
git archive "$commit" src | tar -x -C "$old"
# The old code finds its files relative to itself: give it the repo's keys, logs (the desk keeps reading them) and docs.
ln -s "$PWD/.env" "$old/.env"; ln -s "$PWD/logs" "$old/logs"; ln -s "$PWD/docs" "$old/docs"
echo "old build ($commit) unpacked at $old"

if [ "${1:-}" = "--check" ]; then
  PYTHONPATH="$old/src" .venv/bin/python -c "import clinic_agent, clinic_agent.config as c; print('code from:', clinic_agent.__file__); print('keys:', bool(c.GOOGLE_API_KEY and c.DEEPGRAM_API_KEY and c.PROSPER_API_KEY), '| logs:', c.CALL_LOG_DIR.resolve())" 2>&1 | grep -v Pipecat
  DRY_RUN_SUBMIT=1 PYTHONPATH="$old/src" .venv/bin/python -m uvicorn clinic_agent.server:app --host 127.0.0.1 --port 7862 > /dev/null 2>&1 &
  pid=$!
  for _ in $(seq 1 40); do curl -s -m 1 http://127.0.0.1:7862/health && break; sleep 0.5; done; echo
  kill "$pid"
  exit 0
fi
PYTHONPATH="$old/src" bash apps/agent/scripts/restart.sh
