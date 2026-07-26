#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

cd "$OMP_E2E_WORKDIR"
prompt="$(cat "$GITHUB_WORKSPACE/.github/omp-e2e-prompt.md")"
raw_events="$RUNNER_TEMP/omp-events.jsonl"
live_log="$RUNNER_TEMP/omp-live.log"
stderr_log="$RUNNER_TEMP/omp-stderr.log"

echo "Starting OMP JSON event stream at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Raw events: $raw_events"

timeout 60m stdbuf -oL -eL omp \
  --mode json \
  --advisor \
  --no-pty \
  --yolo \
  --model opencode-go/deepseek-v4-flash \
  --config "$GITHUB_WORKSPACE/.github/omp-e2e-config.yml" \
  "$prompt" \
  2> >(tee "$stderr_log" >&2) \
  | tee "$raw_events" \
  | python3 -u "$GITHUB_WORKSPACE/.github/scripts/render_omp_events.py" \
  | tee "$live_log" &
pipeline_pid=$!

heartbeat() {
  while kill -0 "$pipeline_pid" 2>/dev/null; do
    sleep 15
    kill -0 "$pipeline_pid" 2>/dev/null || break
    echo "[OMP heartbeat] $(date -u +%Y-%m-%dT%H:%M:%SZ) pid=$pipeline_pid"
    if [[ -f .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log ]]; then
      echo "[OMP heartbeat] latest journal lines:"
      tail -n 12 .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log || true
    fi
    echo "[OMP heartbeat] git status:"
    git status --short || true
  done
}

heartbeat &
heartbeat_pid=$!

set +e
wait "$pipeline_pid"
omp_status=$?
set -e

kill "$heartbeat_pid" 2>/dev/null || true
wait "$heartbeat_pid" 2>/dev/null || true

echo "OMP pipeline exited with status $omp_status at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit "$omp_status"
