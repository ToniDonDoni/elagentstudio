# Spec-Driven TDD for Oh My Pi

## Quick start from an empty container

Assume this repository is already downloaded and the current directory is its
root.

### 1. Install prerequisites and OMP

Debian/Ubuntu example:

```bash
apt-get update && apt-get install -y curl git python3
curl -fsSL https://omp.sh/install | sh
omp --version
```

Open a new shell if the installer changed `PATH` and `omp` is not found.

### 2. Create a project and copy the skill

```bash
SOURCE_REPO="$(pwd)"
PROJECT_DIR="../my-omp-project"

mkdir -p "$PROJECT_DIR/skills" "$PROJECT_DIR/.omp"
cp -R "$SOURCE_REPO/skills/spec-driven-tdd" "$PROJECT_DIR/skills/"
cd "$PROJECT_DIR"
git init -b main

printf '@skills/spec-driven-tdd/AGENTS.md\n' > AGENTS.md
printf '@../skills/spec-driven-tdd/WATCHDOG.md\n' > .omp/WATCHDOG.md
cp skills/spec-driven-tdd/WATCHDOG.yml .omp/WATCHDOG.yml
```

`AGENTS.md` loads the orchestrator workflow. OMP loads `.omp/WATCHDOG.md` for the
advisor.

### 3. Configure the model and API key

This example uses OpenCode Go with DeepSeek V4 Flash:

```bash
cat > .omp/config.yml <<'EOF'
modelRoles:
  default: opencode-go/deepseek-v4-flash
  task: opencode-go/deepseek-v4-flash
  advisor: opencode-go/deepseek-v4-flash

async:
  enabled: true

advisor:
  enabled: true

task:
  maxConcurrency: 3
  isolation:
    mode: none
EOF

cat > .env <<'EOF'
OPENCODE_API_KEY=replace-with-your-key
EOF
printf '.env\n' >> .gitignore
```

Use another OMP provider/model by changing `modelRoles` and its credential.

### 4. Write the task

```bash
cat > TASK.md <<'EOF'
Use the Spec-Driven TDD workflow and run as the primary orchestrator.

Build a small HTTP service.

Requirements:
- GET /health returns HTTP 200 and JSON {"status":"ok"}.
- Add an end-to-end test against the running service.
- Keep unrelated behavior unchanged.
EOF
```

### 5. Commit the initial project

OMP worktrees and review evidence require a git repository with a committed
starting point.

```bash
git add AGENTS.md TASK.md .omp/config.yml .omp/WATCHDOG.md .omp/WATCHDOG.yml .gitignore skills
git commit -m "Initialize OMP Spec Driven TDD project"
```

### 6. Run with readable live output

```bash
set -o pipefail
omp \
  --mode json \
  --advisor \
  --no-pty \
  --yolo \
  --config .omp/config.yml \
  "$(cat TASK.md)" \
  | python3 -u "$SOURCE_REPO/.github/scripts/render_omp_events.py"
```

Remove the renderer pipe to see raw OMP JSON events. Run plain `omp` for the
interactive terminal UI. Remove `--yolo` when tool actions should require manual
approval.

After completion, inspect:

```bash
find .sddtdd_skill -maxdepth 2 -type f -print
git log --oneline --all --graph --decorate
```

The workflow should leave the specification, architecture, tasks, reviewed
implementation plan, journal, reviewed commits, tests, and final implementation
in the project repository.
