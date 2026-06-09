#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEST="$HOME/.hermes/skills/software-development/spec-driven-tdd"

usage() {
  cat <<'EOF'
Usage:
  install/hermes-spec-driven-tdd.sh [--override]

Options:
  --override   Replace existing installed spec-driven-tdd files.
  -h, --help   Show this help message.
EOF
}

override=false
for arg in "$@"; do
  case "$arg" in
    --override) override=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: invalid argument: $arg" >&2; usage >&2; exit 1 ;;
  esac
done

if [ -d "$DEST" ] && [ "$override" != true ]; then
  echo "ERROR: spec-driven-tdd is already installed. Re-run with --override to replace it." >&2
  exit 1
fi

if [ "$override" = true ]; then
  rm -rf "$DEST"
fi

mkdir -p "$DEST/references"
cp "$ROOT_DIR/src/spec-driven-tdd/SKILL.md" "$DEST/"
cp "$ROOT_DIR/src/spec-driven-tdd/README.md" "$DEST/"
cp "$ROOT_DIR/src/spec-driven-tdd/references/"* "$DEST/references/"

echo "Installed spec-driven-tdd for Hermes Agent."
