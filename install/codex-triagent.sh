#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL_NAME="triagent-driven-development"
SKILL_DEST="$HOME/.codex/skills/$SKILL_NAME"
AGENTS_DEST="$HOME/.codex/agents"
SOURCE="$ROOT_DIR/skills/$SKILL_NAME"

usage() {
  cat <<'EOF'
Usage:
  install/codex-triagent.sh [--override]

Install TriAgent-Driven Development skill for Codex.

Options:
  --override   Replace existing installed files.
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
if [ -d "$SKILL_DEST" ] && [ "$override" != true ]; then
  echo "ERROR: $SKILL_NAME is already installed at $SKILL_DEST" >&2
  echo "Re-run with --override to replace it." >&2
  exit 1
fi

# Remove existing if override
if [ "$override" = true ]; then
  if [ -d "$SKILL_DEST" ]; then
    rm -rf "$SKILL_DEST"
    echo "Removed existing skill installation."
  fi
  # Remove old agent files
  for agent in trdd-orchestrator.md trdd-planner.md trdd-builder.md trdd-reviewer.md; do
    if [ -f "$AGENTS_DEST/$agent" ]; then
      rm -f "$AGENTS_DEST/$agent"
      echo "Removed existing agent: $agent"
    fi
  done
fi

# Install skill
mkdir -p "$SKILL_DEST"
cp "$SOURCE/SKILL.md" "$SKILL_DEST/"
cp "$SOURCE/README.md" "$SKILL_DEST/"

# Install agents
mkdir -p "$AGENTS_DEST"
if [ -d "$SOURCE/agents" ]; then
  for agent_file in "$SOURCE/agents"/*.md; do
    if [ -f "$agent_file" ]; then
      cp "$agent_file" "$AGENTS_DEST/"
    fi
  done
fi

echo "SUCCESS: Installed $SKILL_NAME for Codex."
echo "Skill location: $SKILL_DEST"
echo "Agents location: $AGENTS_DEST"
echo ""
echo "Files installed:"
echo "  Skill:"
find "$SKILL_DEST" -type f | sort | sed 's|^|    |'
echo "  Agents:"
find "$AGENTS_DEST" -name "trdd-*.md" -type f | sort | sed 's|^|    |'
