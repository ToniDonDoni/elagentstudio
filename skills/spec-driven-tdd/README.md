# Spec-Driven TDD

## Quick start from an empty project

Assume this skill is already present in the project (e.g. under `skills/spec-driven-tdd/`).

### 1. Prerequisites

- git (with worktree support)
- the language/runtime toolchain your product needs (e.g. Node, Python)
- an agent runtime that can delegate self-contained tasks to background worker
  agents, return a runtime identity per delegation, deliver completion
  notifications, and accept a structured final result (a JSON object) per worker.

### 2. Create a project and copy the skill

```bash
PROJECT_DIR="../my-project"
mkdir -p "$PROJECT_DIR/skills"
cp -R skills/spec-driven-tdd "$PROJECT_DIR/skills/"
cd "$PROJECT_DIR"
git init -b main
```

`AGENTS.md` loads the orchestrator workflow for the primary agent; if your
agent runtime does not read `AGENTS.md`, load the role files it lists directly
(`SKILL.md`, `SKILL-ORCHESTRATOR.md`, `references/JOURNAL.md`,
`references/STAGES.md`).

### 3. Write the task

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

### 4. Commit the initial project

Worktrees and review evidence require a git repository with a committed
starting point.

```bash
git add AGENTS.md TASK.md .gitignore skills
git commit -m "Initialize Spec Driven TDD project"
```

### 5. Run

Launch your agent runtime with the orchestrator prompt: "Use the Spec-Driven TDD
workflow and run as the primary orchestrator" plus the TASK.md content. The
orchestrator delegates every artifact and task to worker agents, launches
independent reviewers, and drives the workflow to DONE.

After completion, inspect:

```bash
find .sddtdd_skill -maxdepth 2 -type f -print
git log --oneline --all --graph --decorate
```

The workflow should leave the specification, architecture, tasks, journal,
reviewed commits, tests, and final implementation in the project repository.

## Documentation set

- `SKILL.md` — the workflow.
- `SKILL-ORCHESTRATOR.md` — orchestration policy.
- `SKILL-IMPLEMENTER.md` — implementer policy.
- `SKILL-REVIEWER.md` — reviewer policy.
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md` — acceptance criteria and test boundaries.
- `references/JOURNAL.md` — journal specification.
- `references/STAGES.md` — stage-by-stage procedure.