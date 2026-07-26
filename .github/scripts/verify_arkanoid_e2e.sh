#!/usr/bin/env bash
set -euo pipefail

: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

cd "$OMP_E2E_WORKDIR"

test -f package.json
test -f app/index.html
test -f app/game.js
npm test

npm run start > "$RUNNER_TEMP/arkanoid-server.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

ready=0
for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:4173/ > "$RUNNER_TEMP/arkanoid-index.html"; then
    ready=1
    break
  fi
  sleep 1
done

test "$ready" -eq 1
grep -qi "canvas" "$RUNNER_TEMP/arkanoid-index.html"
