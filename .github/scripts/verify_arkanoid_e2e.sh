#!/usr/bin/env bash
set -euo pipefail

echo "[script verify_arkanoid_e2e] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"

: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

cd "$OMP_E2E_WORKDIR"

echo "[script verify_arkanoid_e2e] Checking generated files"
test -f package.json
test -f app/index.html
test -f app/game.js

echo "[script verify_arkanoid_e2e] Running npm test"
npm test

echo "[script verify_arkanoid_e2e] Starting application server"
npm run start > "$RUNNER_TEMP/arkanoid-server.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

ready=0
for attempt in $(seq 1 30); do
  echo "[script verify_arkanoid_e2e] Probe attempt $attempt/30"
  if curl --fail --silent http://127.0.0.1:4173/ > "$RUNNER_TEMP/arkanoid-index.html"; then
    ready=1
    break
  fi
  sleep 1
done

test "$ready" -eq 1
grep -qi "canvas" "$RUNNER_TEMP/arkanoid-index.html"
echo "[script verify_arkanoid_e2e] DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
