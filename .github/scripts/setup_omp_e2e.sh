#!/usr/bin/env bash
set -euo pipefail

echo "[script setup_omp_e2e] START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[script setup_omp_e2e] Installing @oh-my-pi/pi-coding-agent"
bun install -g @oh-my-pi/pi-coding-agent

echo "[script setup_omp_e2e] Checking omp version"
omp --version

if [[ -z "${OPENCODE_API_KEY:-}" ]]; then
  echo "Repository secret OPENCODE_GO_API_KEY is required" >&2
  exit 1
fi

echo "[script setup_omp_e2e] API key is present"
echo "[script setup_omp_e2e] DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
