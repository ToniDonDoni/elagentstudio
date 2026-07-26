#!/usr/bin/env bash
set -euo pipefail

bun install -g @oh-my-pi/pi-coding-agent
omp --version

if [[ -z "${OPENCODE_API_KEY:-}" ]]; then
  echo "Repository secret OPENCODE_GO_API_KEY is required" >&2
  exit 1
fi
