---
name: spec-driven-tdd
version: 6.0.2-omp
description: "Spec-Driven TDD workflow for Oh My Pi with asynchronous subagents, independent review, worktree isolation, and advisor supervision."
author: GPT-5.6
license: MIT
---

# Spec-Driven TDD for Oh My Pi

## Purpose

Turn a user request into committed software through a strict artifact chain,
independent review, a reviewed implementation plan, reviewed RED/GREEN TDD,
parallel worktree implementation, and committed evidence.

## Roles

There are four strictly separated roles:

- Orchestrator: the primary OMP agent. It delegates, monitors, applies process gates, and records handoffs. It does not implement or review.
- Implementer: an OMP `task` subagent that creates one assigned artifact, test, code change, correction, or merge result.
- Reviewer: a separate OMP `task` subagent that reviews an exact committed result and never fixes or writes files.
- Watchdog: the OMP advisor attached to the primary session. It checks the orchestrator process and emits `nit`, `concern`, or `blocker` advice. It does not replace independent review.

## OMP entrypoints

- `AGENTS.md` imports the shared and orchestrator policies for the primary agent.
- `WATCHDOG.md` imports advisor-only policy and is discovered separately by OMP.
- `SKILL-ORCHESTRATOR.md` defines delegation and process gates.
- `SKILL-IMPLEMENTER.md` defines artifact, RED/GREEN, correction, and merge work.
- `SKILL-REVIEWER.md` defines independent committed-state review.
- `SKILL-WATCHDOG.md` defines advisor process supervision.

## Native OMP evidence

Use:

- `task` for asynchronous subagents and batch fan-out;
- `hub` for status, follow-up, correction, and cancellation;
- `agent://<id>` for full subagent output;
- `history://<id>` for the subagent transcript;
- OMP agent/job ids and async-result delivery for runtime identity;
- dedicated git worktree branches for implementation isolation;
- session and advisor JSONL transcripts as raw execution evidence.

Runtime handoff evidence is recorded in `.sddtdd_skill/orchestrator.log`. The
committed journal keeps its original compact schema and records the resulting
workflow verdicts through `ORCHESTRATOR_TASK_REVIEW`.

## Workflow artifacts

The workflow state lives under `.sddtdd_skill/`:

- `SPEC-DRAFT.md`: exact user input and later append-only additions;
- `SPEC.md`: reviewed requirements and acceptance criteria;
- `ARCHITECTURE.md`: reviewed design and test boundaries;
- `TASKS.md`: reviewed task graph and dependencies;
- `IMPLEMENTATION-PLAN.md`: reviewed execution waves, per-task RED/review/GREEN/review assignments, parallelism, write scopes, and merge order;
- `JOURNAL_SDD_TDD_SKILL.log`: committed workflow evidence;
- `orchestrator.log`: append-only primary-agent handoff/check records;
- `reviewer.log`: append-only copies of immutable reviewer yields, recorded by the orchestrator after reviewers return.

## Hard rules

1. Every agent-generated artifact receives independent review before downstream work depends on it.
2. Every automatically testable behavior passes through reviewed RED and reviewed GREEN.
3. Review only committed evidence. Mutable working-tree state is not evidence.
4. The orchestrator never implements, resolves conflicts, or performs independent review.
5. The reviewer never modifies files, writes logs, authors fixes, merges, or advances the workflow.
6. Independent review and watchdog supervision are different controls; neither replaces the other.
7. Commit messages are ASCII-only.
8. No RED, GREEN, or implementation assignment may begin before `IMPLEMENTATION_PLAN_REVIEW: PASS` and its process gate.
9. Every RED or GREEN assignment covers exactly one reviewed `TASKS.md` task node and follows the reviewed implementation plan.
10. Parallel implementation is allowed only for dependency-ready tasks with safe, non-overlapping write scopes defined in the reviewed implementation plan.
11. Implementation branches are not integrated before independent review passes.
12. Every integration commit receives mandatory `MERGE_REVIEW: PASS` before downstream use.
13. Merge results are tested after integration, not only in the worker worktree.
14. RED is valid only when it fails for the target missing behavior or target bug. Unrelated failures are invalid RED evidence.

## User scope changes

`SPEC-DRAFT.md` is append-only after its first commit.

When the user adds or changes a product requirement during work:

1. append the exact wording under an `ADDITION:` label;
2. journal and commit the addition before acting on it;
3. pause affected downstream work;
4. return to the earliest affected stage;
5. revise and re-review SPEC, architecture, tasks, the implementation plan, RED, and GREEN evidence as needed.

## Required flow

1. Capture and commit `SPEC-DRAFT.md`.
2. Delegate SPEC creation; commit it; launch an independent `SPEC_REVIEW`.
3. Repeat correction and review until SPEC passes, then record `ORCHESTRATOR_TASK_REVIEW`.
4. Repeat the same cycle for ARCHITECTURE and TASKS, using `TASK_REVIEW` consistently.
5. Delegate creation of `.sddtdd_skill/IMPLEMENTATION-PLAN.md`; commit it; launch `IMPLEMENTATION_PLAN_REVIEW`; repeat until it passes; then record `ORCHESTRATOR_TASK_REVIEW`.
6. Launch only dependency-ready RED assignments named by the reviewed implementation plan. Each assignment covers exactly one `TASKS.md` task id and uses a dedicated git worktree branch when it writes tests or code.
7. When one worker completes, inspect its agent/job ids, output, transcript when needed, branch, commit, tests, and clean-state evidence.
8. Immediately launch a separate reviewer against that exact commit.
9. On `PASS`, advance only to the next transition defined by the reviewed implementation plan. On `FAIL`, delegate correction. On `NEEDS_CLARIFICATION`, ask the user and pause affected work. On `BLOCKED`, record and surface the blocker.
10. Delegate one synchronous MERGE implementer for one reviewed branch at a time. Resolve conflicts there and run required tests on the integrated tree.
11. Immediately launch mandatory `MERGE_REVIEW` against the exact integration commit. No downstream work may use it before `PASS` and the following process gate.
12. Run and review regression evidence on the final integrated candidate.
13. Run final traceability review and record DONE only after every gate passes.

## Delegation context

Every implementer and reviewer receives:

- exact role and role-file path;
- task id and task kind;
- allowed write scope;
- required output and evidence;
- repository, integration base, worktree, and branch context where relevant;
- relevant committed ancestry, including the reviewed implementation plan for RED/GREEN work;
- the exact implementation-plan assignment row or section governing the task when applicable;
- relevant prior verdicts and corrections;
- the ASCII-only commit-message rule;
- a structured output contract when useful.

Child sessions do not inherit the parent conversation. Pass all required context
in the `task` request.
