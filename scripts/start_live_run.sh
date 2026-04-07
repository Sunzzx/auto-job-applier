#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT/.job-agent"
mkdir -p "$STATE_DIR"

REQUEST="${1:-Find remote or hybrid AI/backend software engineering roles at product-focused companies. Prioritize Python, LLM systems, applied AI, platform, or infra-heavy roles. Avoid obvious recruiting spam and junior-only roles. Prefer companies with clear application forms and salary transparency.}"

bash "$ROOT/scripts/prepare_openclaw_profile.sh"

cat > "$STATE_DIR/live-run.json" <<EOF
{
  "startedAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "request": $(python3 - <<PY
import json
print(json.dumps("""$REQUEST"""))
PY
),
  "action": "submit",
  "profile": "examples/profile.openclaw.yaml",
  "policy": "examples/policy.openclaw.yaml"
}
EOF

nohup bash -lc "cd \"$ROOT\" && bash run-job-agent.sh autopilot --profile examples/profile.openclaw.yaml --policy examples/policy.openclaw.yaml --request $(python3 - <<PY
import json
print(json.dumps("""$REQUEST"""))
PY
) --max-jobs 8 --apply-limit 3 --action submit && bash run-job-agent.sh tracker-export --profile examples/profile.openclaw.yaml --policy examples/policy.openclaw.yaml" > "$STATE_DIR/live-run.log" 2>&1 &

echo $! > "$STATE_DIR/live-run.pid"
echo "started pid $(cat "$STATE_DIR/live-run.pid")"
