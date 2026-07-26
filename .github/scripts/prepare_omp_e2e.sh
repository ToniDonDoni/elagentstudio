#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

workdir="$RUNNER_TEMP/omp-sddtdd-arkanoid"
rm -rf "$workdir"
mkdir -p "$workdir/skills"
cp -R "$GITHUB_WORKSPACE/skills/spec-driven-tdd" "$workdir/skills/spec-driven-tdd"

cat > "$workdir/AGENTS.md" <<'EOF'
@skills/spec-driven-tdd/AGENTS.md
EOF

cat > "$workdir/WATCHDOG.md" <<'EOF'
@skills/spec-driven-tdd/WATCHDOG.md
EOF

git -C "$workdir" init -b main
git -C "$workdir" config user.name "OMP E2E"
git -C "$workdir" config user.email "omp-e2e@example.invalid"
git -C "$workdir" add .
git -C "$workdir" commit -m "Initialize OMP SDDTDD E2E fixture"

printf 'OMP_E2E_WORKDIR=%s\n' "$workdir" >> "$GITHUB_ENV"
printf 'Prepared isolated OMP repository at %s\n' "$workdir"
