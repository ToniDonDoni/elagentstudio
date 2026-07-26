#!/usr/bin/env bash
set -Eeuo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

script_path="$(readlink -f "$0")"
raw_events="$RUNNER_TEMP/omp-events.jsonl"
live_log="$RUNNER_TEMP/omp-live.log"
stderr_log="$RUNNER_TEMP/omp-stderr.log"
pipeline_status_file="$RUNNER_TEMP/omp-pipeline-status.txt"
heartbeat_stop="$RUNNER_TEMP/omp-heartbeat.stop"

run_pipeline() {
  cd "$OMP_E2E_WORKDIR"
  local prompt
  local stderr_fifo="$RUNNER_TEMP/omp-stderr.fifo"
  local stderr_tee_pid
  local stderr_status
  local pipeline_status
  local statuses

  prompt="$(cat "$GITHUB_WORKSPACE/.github/omp-e2e-prompt.md")"
  rm -f "$stderr_fifo" "$pipeline_status_file"
  mkfifo "$stderr_fifo"

  stdbuf -oL tee "$stderr_log" < "$stderr_fifo" >&2 &
  stderr_tee_pid=$!

  set +e
  timeout "${OMP_E2E_TIMEOUT:-60m}" stdbuf -oL -eL omp \
    --mode json \
    --advisor \
    --no-pty \
    --yolo \
    --model opencode-go/deepseek-v4-flash \
    --config "$GITHUB_WORKSPACE/.github/omp-e2e-config.yml" \
    "$prompt" \
    2> "$stderr_fifo" \
    | stdbuf -oL tee "$raw_events" \
    | python3 -u "$GITHUB_WORKSPACE/.github/scripts/render_omp_events.py" \
    | stdbuf -oL tee "$live_log"
  statuses=("${PIPESTATUS[@]}")
  wait "$stderr_tee_pid"
  stderr_status=$?
  set -e

  rm -f "$stderr_fifo"
  pipeline_status=0
  for status in "${statuses[@]}" "$stderr_status"; do
    if (( status != 0 )); then
      pipeline_status=$status
      break
    fi
  done

  printf '%s\n' "${statuses[*]} $stderr_status" > "$pipeline_status_file"
  exit "$pipeline_status"
}

if [[ "${1:-}" == "--pipeline" ]]; then
  run_pipeline
fi

echo "[script run_omp_e2e] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
cd "$OMP_E2E_WORKDIR"
rm -f "$heartbeat_stop" "$pipeline_status_file"

echo "[script run_omp_e2e] Workdir: $OMP_E2E_WORKDIR"
echo "[script run_omp_e2e] Model: opencode-go/deepseek-v4-flash"
echo "[script run_omp_e2e] Raw JSONL: $raw_events"
echo "[script run_omp_e2e] Readable log: $live_log"
echo "[script run_omp_e2e] OMP stderr: $stderr_log"
echo "[script run_omp_e2e] Starting foreground OMP process group now"

heartbeat() {
  echo "[script run_omp_e2e] Heartbeat process started"
  while [[ ! -e "$heartbeat_stop" ]]; do
    sleep 10
    [[ -e "$heartbeat_stop" ]] && break
    echo "[OMP heartbeat] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ -f .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log ]]; then
      echo "[OMP heartbeat] latest journal lines:"
      tail -n 12 .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log || true
    else
      echo "[OMP heartbeat] journal not created yet"
    fi
    echo "[OMP heartbeat] git status:"
    git status --short || true
  done
  echo "[script run_omp_e2e] Heartbeat process stopped"
}

heartbeat &
heartbeat_pid=$!
pipeline_pid=""

cleanup() {
  touch "$heartbeat_stop"
  kill "$heartbeat_pid" 2>/dev/null || true
  wait "$heartbeat_pid" 2>/dev/null || true
  echo "[script run_omp_e2e] Cleanup complete"
}
trap cleanup EXIT

forward_signal() {
  local signal="$1"
  local exit_code="$2"
  trap - INT TERM
  if [[ -n "$pipeline_pid" ]] && kill -0 "$pipeline_pid" 2>/dev/null; then
    kill -"$signal" -- -"$pipeline_pid" 2>/dev/null || true
    wait "$pipeline_pid" 2>/dev/null || true
  fi
  exit "$exit_code"
}
trap 'forward_signal INT 130' INT
trap 'forward_signal TERM 143' TERM

setsid bash "$script_path" --pipeline &
pipeline_pid=$!

set +e
wait "$pipeline_pid"
pipeline_status=$?
set -e

if [[ -f "$pipeline_status_file" ]]; then
  echo "[script run_omp_e2e] Pipeline statuses: $(cat "$pipeline_status_file")"
else
  echo "[script run_omp_e2e] Pipeline status file was not produced"
fi

echo "[script run_omp_e2e] DONE status=$pipeline_status $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit "$pipeline_status"
