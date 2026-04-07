#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Resolution order (first match wins):
# 1) JOB_AGENT_PYTHON env var for explicit control
# 2) Stable external venv at ~/.venvs/job-agent
# 3) Project-local .venv
# 4) System python3
if [[ -n "${JOB_AGENT_PYTHON:-}" ]]; then
  exec "$JOB_AGENT_PYTHON" -m job_agent.cli "$@"
fi

if [[ -x "$HOME/.venvs/job-agent/bin/python" ]]; then
  exec "$HOME/.venvs/job-agent/bin/python" -m job_agent.cli "$@"
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m job_agent.cli "$@"
fi

exec python3 -m job_agent.cli "$@"
