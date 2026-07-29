#!/usr/bin/env bash
set -euo pipefail

echo "[script verify_sddtdd_evidence] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

cd "$OMP_E2E_WORKDIR"
echo "[script verify_sddtdd_evidence] Running evidence verifier"
python3 \
  "$GITHUB_WORKSPACE/skills/spec-driven-tdd/tests/verify_evidence.py" \
  .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log \
  .sddtdd_skill/orchestrator.log \
  "$RUNNER_TEMP/omp-events.jsonl"

echo "[script verify_sddtdd_evidence] Checking clean repository"
test -z "$(git status --porcelain)"

echo "[script verify_sddtdd_evidence] Checking commit history"
test "$(git rev-list --count HEAD)" -gt 1

echo "[script verify_sddtdd_evidence] DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
