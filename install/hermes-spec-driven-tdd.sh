#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL_NAME="spec-driven-tdd"
DEST="$HOME/.hermes/skills/software-development/$SKILL_NAME"
SOURCE="$ROOT_DIR/skills/$SKILL_NAME"

usage() {
  cat <<'EOF'
Usage:
  install/hermes-spec-driven-tdd.sh [--override]

Install Spec-Driven TDD skill for Hermes Agent.

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

# Check source exists
if [ ! -d "$SOURCE" ]; then
  echo "ERROR: Source directory not found: $SOURCE" >&2
  echo "Make sure you are running this from the repository root." >&2
  exit 1
fi

if [ ! -f "$SOURCE/SKILL.md" ]; then
  echo "ERROR: SKILL.md not found in $SOURCE" >&2
  exit 1
fi

# Check if already installed
if [ -d "$DEST" ] && [ "$override" != true ]; then
  echo "ERROR: $SKILL_NAME is already installed at $DEST" >&2
  echo "Re-run with --override to replace it." >&2
  exit 1
fi

# Remove existing if override
if [ "$override" = true ] && [ -d "$DEST" ]; then
  rm -rf "$DEST"
  echo "Removed existing installation."
fi

# Install
mkdir -p "$DEST/references"
cp "$SOURCE/SKILL.md" "$DEST/"
if [ -d "$SOURCE/references" ] && [ -n "$(ls -A "$SOURCE/references" 2>/dev/null)" ]; then
  cp "$SOURCE/references/"* "$DEST/references/"
fi

echo "SUCCESS: Installed $SKILL_NAME for Hermes Agent."
echo "Location: $DEST"
echo ""
echo "Files installed:"
find "$DEST" -type f | sort | sed 's|^|  |'
