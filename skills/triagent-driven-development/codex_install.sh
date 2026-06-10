set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  skills/triagent-driven-development/codex_install.sh [--override]

Options:
  --override   Replace existing installed TriDD files.
  -h, --help   Show this help message.
EOF
}

override=false

for arg in "$@"; do
  case "$arg" in
    --override)
      override=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: INVALID ARGUMENT: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ "$override" != true ] && \
   { [ -f ~/.codex/skills/triagent-driven-development/SKILL.md ] || \
     ls ~/.codex/agents/trdd-*.md >/dev/null 2>&1; }; then
  echo "ERROR: TRIAGENT-DRIVEN DEVELOPMENT DIRECTORY IS NOT CLEAN. RE-RUN WITH --override TO REPLACE EXISTING FILES." >&2
  exit 1
fi

mkdir -p ~/.codex/agents
mkdir -p ~/.codex/skills/triagent-driven-development
cp skills/triagent-driven-development/agents/trdd-*.md ~/.codex/agents/
cp skills/triagent-driven-development/SKILL.md ~/.codex/skills/triagent-driven-development/

echo "DONE"
