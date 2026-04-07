#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT/.job-agent"
mkdir -p "$STATE_DIR"

nohup bash -lc "cd \"$ROOT/web\" && npm run build && npm run start -- --hostname 127.0.0.1 --port 3001" > "$STATE_DIR/web-dashboard.log" 2>&1 &
echo $! > "$STATE_DIR/web-dashboard.pid"
echo "started web pid $(cat "$STATE_DIR/web-dashboard.pid")"
