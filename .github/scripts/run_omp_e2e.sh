#!/usr/bin/env bash
set -Eeuo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

cd "$OMP_E2E_WORKDIR"
prompt="$(cat "$GITHUB_WORKSPACE/.github/omp-e2e-prompt.md")"
raw_events="$RUNNER_TEMP/omp-events.jsonl"
live_log="$RUNNER_TEMP/omp-live.log"
stderr_log="$RUNNER_TEMP/omp-stderr.log"
heartbeat_stop="$RUNNER_TEMP/omp-heartbeat.stop"
rm -f "$heartbeat_stop"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "::notice title=OMP E2E::Starting live OMP event stream at $started_at"
echo "Raw JSONL: $raw_events"
echo "Readable log: $live_log"
echo "OMP stderr: $stderr_log"
echo "::group::OMP live event stream"

heartbeat() {
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
}

heartbeat &
heartbeat_pid=$!

cleanup() {
  touch "$heartbeat_stop"
  kill "$heartbeat_pid" 2>/dev/null || true
  wait "$heartbeat_pid" 2>/dev/null || true
  echo "::endgroup::"
}
trap cleanup EXIT INT TERM

set +e
timeout 60m stdbuf -oL -eL omp \
  --mode json \
  --advisor \
  --no-pty \
  --yolo \
  --model opencode-go/deepseek-v4-flash \
  --config "$GITHUB_WORKSPACE/.github/omp-e2e-config.yml" \
  "$prompt" \
  2> >(stdbuf -oL tee "$stderr_log" >&2) \
  | stdbuf -oL tee "$raw_events" \
  | python3 -u "$GITHUB_WORKSPACE/.github/scripts/render_omp_events.py" \
  | stdbuf -oL tee "$live_log"
pipeline_statuses=("${PIPESTATUS[@]}")
set -e

pipeline_status=0
for status in "${pipeline_statuses[@]}"; do
  if (( status != 0 )); then
    pipeline_status=$status
    break
  fi
done

printf 'OMP pipeline statuses: %s\n' "${pipeline_statuses[*]}"
echo "OMP pipeline exited with status $pipeline_status at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit "$pipeline_status"
