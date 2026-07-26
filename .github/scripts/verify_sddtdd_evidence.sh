#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${OMP_E2E_WORKDIR:?OMP_E2E_WORKDIR is required}"

cd "$OMP_E2E_WORKDIR"
python3 \
  "$GITHUB_WORKSPACE/skills/spec-driven-tdd/tests/verify_evidence.py" \
  .sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log \
  .sddtdd_skill/orchestrator.log

test -z "$(git status --porcelain)"
test "$(git rev-list --count HEAD)" -gt 1
