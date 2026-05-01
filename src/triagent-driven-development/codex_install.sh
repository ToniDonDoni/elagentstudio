set -euo pipefail

if [ -f ~/.codex/skills/triagent-driven-development/SKILL.md ] || \
   ls ~/.codex/agents/trdd-*.md >/dev/null 2>&1; then
  echo "ERROR: TRIAGENT-DRIVEN DEVELOPMENT DIRECTORY IS NOT CLEAN." >&2
  exit 1
fi

mkdir -p ~/.codex/agents
mkdir -p ~/.codex/skills/triagent-driven-development
cp src/triagent-driven-development/trdd-*.md ~/.codex/agents/
cp src/triagent-driven-development/SKILL.md ~/.codex/skills/triagent-driven-development/

echo "DONE"
