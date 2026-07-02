# Spec-Driven TDD — usage

This skill turns a user request into working software through a chain of
explicit, traceable, committed, and independently reviewed artifacts, with
RED-GREEN TDD for every behavior that can be tested automatically. Every
step is journaled so the work can be reconstructed and audited.

There are two operating modes. Artifacts, journal, and principles are
identical in both.

- **Standalone mode** — no broker. The implementer walks the artifact chain
  stage by stage, reading `SKILL-IMPLEMENTER.md` and `references/STAGES.md`.
- **Broker mode** — an MCP task broker decides the next task. The
  implementer asks the broker for the next task and executes only what it
  returns. The broker's policy lives in `SKILL-ORCHESTRATOR.md` and is
  loaded only by the broker, not by the implementer.

## File layout (project side)

In every project that uses the skill, all SDDTDD artifacts and runtime
logs live under a single directory `<project-dir>/.sddtdd_skill/`:

- **Committed** (in git): `SPEC-DRAFT.md`, `SPEC.md`, `ARCHITECTURE.md`,
  `TASKS.md`, `JOURNAL_SDD_TDD_SKILL.log`.
- **Runtime** (NOT in git): `review-access.jsonl`, `broker-access.jsonl`.

The implementer creates `.sddtdd_skill/` (via the broker's first
task) on the first run; you do not need to `mkdir` it manually.

The rest of this README is mostly about broker mode, because that is the
mode that needs a user prompt. Standalone mode is straightforward:
read `SKILL.md`, read `SKILL-IMPLEMENTER.md`, walk the chain.

## What you do in broker mode (short version)

1. Pick a clean working directory (e.g. `/work/my-app`).
2. Make sure the broker MCP and reviewer MCP are reachable
   (`mcp_sddtdd_broker_*`, `mcp_sddtdd_review_review`).
3. Make sure the skill is preloaded. The skill is at
   `skills/spec-driven-tdd/`. If you are running inside an installed
   agent, the skill is usually preloaded by the harness. If you are
   running a fresh agent, load it explicitly with `skill_view`.
4. Send the agent a prompt like the one below.
5. The agent does the work, journals every step, commits, calls the
   broker after each task, and stops when the broker says `complete`.
6. Inspect the result (see "What to check afterwards" below).

## Example user prompt — broker mode

This is the exact prompt shape that works. Replace `<project-dir>` with
an empty directory, and replace the **Task** section with what you
actually want built. Keep the **Process** section as is — that is the
contract.

```text
You are running inside `<project-dir>`. The `spec-driven-tdd` skill is
preloaded. Operate in **broker mode**: the implementer role file is
`SKILL-IMPLEMENTER.md`. Do not read `SKILL-ORCHESTRATOR.md` — that is
for the broker MCP server.

## Task

<describe what to build, including:

- the user-visible behavior you want
- any constraints (language, framework, file layout, no-build vs build)
- what the tests must cover, with concrete scenarios
- the test framework and the test command (e.g. `npm test`)

Be specific. The implementer will not invent requirements.>

## Process — non-negotiable

1. Run the entire pipeline through the broker MCP
   (`mcp_sddtdd_broker_*`). **Do not** walk the chain yourself; the
   broker decides the next task.
2. The first call is `getNextTask` with `user_input` set to the full
   task description above.
3. For every task the broker issues, do the work, commit (every
   artifact AND every journal entry must be committed before
   `reviewTask`), and call `reviewTask` with the matching
   `work_journal_id`.
4. When `reviewTask` returns `PASS`, append a `BROKER_TASK_REVIEW`
   journal entry with `TASK_ID: <broker task id>`,
   `STATUS: PASS`, and `PARENT` set to the reviewer verdict (or the
   work entry for capture tasks), then commit, then call
   `getNextTask` for the next task.
5. The independent reviewer verdict comes from
   `mcp_sddtdd_review_review` (use `review_type` from the broker
   task).
6. When `getNextTask` returns `complete`, write a short final report
   listing every commit, every JID, and the contents of
   `.sddtdd_skill/broker-access.jsonl`.

## What I will check afterwards

- `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` is committed and shows the full chain.
- `.sddtdd_skill/broker-access.jsonl` shows broker activity
  (`task_issued` + `task_review_started` + `task_review_completed`
  events).
- The tests you specified actually run via the command you specified
  and they pass.
- `git log --oneline` shows a clean commit history.
- The whole thing lives in `<project-dir>`.

## Style

- <your style rules, e.g. "vanilla, no framework",
  "ASCII-only commits", "one commit per task",
  "no sleeping in tests, use Playwright auto-waiting">.
```

### What each section does

- **Task** is what the implementer builds. Be concrete: file layout,
  inputs, outputs, test scenarios. If you want Playwright, say so and
  say which scenarios. If you want a CLI, say so and say which flags.
  Vague tasks produce vague specs.
- **Process — non-negotiable** is the contract. The six points enforce
  the broker loop, the commit-before-review rule, the
  `BROKER_TASK_REVIEW` journal entry, and the final report. Do not
  rewrite them. If you do, the broker will not be able to verify
  anything.
- **What I will check afterwards** is your acceptance test. It tells
  the implementer what evidence to produce. List the files, the
  commands, and the broker access log; the implementer will show all
  of them in the final report.
- **Style** is free-form. Use it for "vanilla only", "no external
  deps", "ASCII commits", "deterministic tests" and similar.

### Minimal variant

If you do not care about a heavy spec, you can shrink the prompt to
just the **Task** and **Process** sections. The **What I will check
afterwards** and **Style** sections are optional but recommended;
without them, the implementer is more likely to cut corners on tests
or commit hygiene.

## Worked example

The skill ships a canonical worked example at
[`references/SPEC-EXAMPLE.md`](references/SPEC-EXAMPLE.md). It shows a
real `.sddtdd_skill/SPEC.md`, `.sddtdd_skill/ARCHITECTURE.md`, `.sddtdd_skill/TASKS.md`, journal, and commits for
a small in-memory counter API. Read it before writing your first
prompt — it shows the shape of a good spec.

## What to check afterwards (broker mode)

After the implementer reports `complete`, verify all of the following
in `<project-dir>`:

1. **Journal is committed and complete.** `git log --oneline` includes
   a commit for `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` and the journal shows the
   full chain: `SPEC_DRAFT` → `SPEC` → `ARCHITECTURE` → `TASKS` → per-
   task `WORK` / `TEST` / `RED` / `GREEN` / `REVIEW` → `REGRESSION` →
   `FINAL_REVIEW` → `DONE`. No gaps.
2. **Broker access log exists and is sane.** Run
   `cat .sddtdd_skill/broker-access.jsonl | jq .` (or
   `python3 -m json.tool` if you do not have `jq`). Every broker task
   should appear as three events: `task_issued`,
   `task_review_started`, `task_review_completed`. Every
   `task_review_completed` should have a `verdict` matching the
   corresponding `BROKER_TASK_REVIEW` journal entry.
3. **Tests run and pass.** Run the exact command from the prompt
   (e.g. `npm test`). It must exit 0. If it requires a server, the
   test command must start the server itself; the implementer must
   not be relying on a process the agent started in the background
   and forgot.
4. **Commits are clean and per-task.** `git log --oneline` should
   show roughly one commit per broker task, with no fixup-style
   "oops forgot to commit" commits and no amend-style history
   rewriting.
5. **Final report is in the journal or as a final commit.** The
   implementer should have produced a short summary listing every
   commit, every JID, and the contents of
   `.sddtdd_skill/broker-access.jsonl`.
6. **No unreviewed artifacts.** Every `*_REVIEW` journal entry must
   have `STATUS: PASS` and a `PARENT` pointing to the matching work
   entry.

If any of those are missing, do not trust the result. Send the
implementer back to fix it; the journal is the audit trail.

## Common failure modes

These are the corners agents cut when they ignore the skill:

- **Skipping RED.** Writing production code and tests at the same
  time, then "reviewing" the combined artifact. The broker will catch
  this if the journal is missing a `TEST` / `RED` / `RED_REVIEW: PASS`
  sequence before `WORK`.
- **Inline file contents in the reviewer prompt.** Passing the full
  file as the `prompt` argument to the reviewer MCP. The reviewer
  should read files from `repo_path`; the `prompt` is the review
  question, not the artifact content.
- **Self-issuing the next task.** Skipping `getNextTask` and just
  walking the chain. The implementer does not decide the order in
  broker mode; the broker does.
- **Forgetting to journal a `BROKER_TASK_REVIEW` for a non-PASS
  verdict.** On `FAIL` or `NEEDS_CLARIFICATION`, the implementer
  must still record the verdict, fix, retry. Hiding a non-PASS
  verdict breaks the audit trail.
- **Inferring `task_id` or `request_id`.** These come from the broker
  and the reviewer, not from the implementer. Copy them, do not
  invent them.
- **Tests that pass only because the agent kept a process running.**
  e.g. Playwright tests that need a static server the agent started
  in a background terminal. Configure the test runner to start the
  server itself (`playwright.config.js` `webServer`,
  `pytest-postgresql`, etc.).

## File map

- [`SKILL.md`](SKILL.md) — overview, principles, roles, invariants.
- [`SKILL-IMPLEMENTER.md`](SKILL-IMPLEMENTER.md) — implementer loop.
  Loaded by the implementer in both modes.
- [`SKILL-ORCHESTRATOR.md`](SKILL-ORCHESTRATOR.md) — broker policy.
  Loaded by the broker MCP, **not** by the implementer.
- [`references/JOURNAL.md`](references/JOURNAL.md) — journal format,
  entry types, task-tree rules, invariants.
- [`references/STAGES.md`](references/STAGES.md) — stage-by-stage
  procedure for standalone mode.
- [`references/SPEC-EXAMPLE.md`](references/SPEC-EXAMPLE.md) — worked
  example.
