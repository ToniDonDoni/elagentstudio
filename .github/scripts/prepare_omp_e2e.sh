#!/usr/bin/env bash
set -euo pipefail

echo "[script prepare_omp_e2e] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

workdir="$RUNNER_TEMP/omp-sddtdd-arkanoid"
echo "[script prepare_omp_e2e] Creating fixture at $workdir"
rm -rf "$workdir"
mkdir -p "$workdir/skills"
cp -R "$GITHUB_WORKSPACE/skills/spec-driven-tdd" "$workdir/skills/spec-driven-tdd"

echo "[script prepare_omp_e2e] Writing OMP entrypoints"
cat > "$workdir/AGENTS.md" <<'EOF'
@skills/spec-driven-tdd/AGENTS.md
EOF

cat > "$workdir/WATCHDOG.md" <<'EOF'
@skills/spec-driven-tdd/WATCHDOG.md
EOF

cp "$workdir/skills/spec-driven-tdd/WATCHDOG.yml" "$workdir/WATCHDOG.yml"
echo "[script prepare_omp_e2e] Installed WATCHDOG.yml with bash grant"

echo "[script prepare_omp_e2e] Initializing git repository"
git -C "$workdir" init -b main
git -C "$workdir" config user.name "OMP E2E"
git -C "$workdir" config user.email "omp-e2e@example.invalid"
git -C "$workdir" add .
git -C "$workdir" commit -m "Initialize OMP SDDTDD E2E fixture"

printf 'OMP_E2E_WORKDIR=%s\n' "$workdir" >> "$GITHUB_ENV"
printf '[script prepare_omp_e2e] Prepared isolated OMP repository at %s\n' "$workdir"
echo "[script prepare_omp_e2e] DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
