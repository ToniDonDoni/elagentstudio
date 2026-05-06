set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  src/triagent-driven-development/opencode_install.sh [--override]

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
   { [ -f ~/.config/opencode/skills/triagent-driven-development/SKILL.md ] || \
     ls ~/.config/opencode/agents/trdd-*.md >/dev/null 2>&1; }; then
  echo "ERROR: TRIAGENT-DRIVEN DEVELOPMENT DIRECTORY IS NOT CLEAN. RE-RUN WITH --override TO REPLACE EXISTING FILES." >&2
  exit 1
fi

mkdir -p ~/.config/opencode/agents
mkdir -p ~/.config/opencode/skills/triagent-driven-development
cp src/triagent-driven-development/trdd-*.md ~/.config/opencode/agents/
cp src/triagent-driven-development/SKILL.md ~/.config/opencode/skills/triagent-driven-development/

echo "DONE"
