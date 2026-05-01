set -euo pipefail

if [ -f ~/.config/opencode/skills/triagent-driven-development/SKILL.md ] || \
   ls ~/.config/opencode/agents/trdd-*.md >/dev/null 2>&1; then
  echo "TriAgent-Driven Development directory is not clean."
  exit 1
fi

mkdir -p ~/.config/opencode/agents
mkdir -p ~/.config/opencode/skills/triagent-driven-development
cp src/triagent-driven-development/trdd-*.md ~/.config/opencode/agents/
cp src/triagent-driven-development/SKILL.md ~/.config/opencode/skills/triagent-driven-development/
