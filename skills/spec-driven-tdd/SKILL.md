---
name: spec-driven-tdd
version: 7.0.0
description: "Spec-Driven TDD workflow with asynchronous worker agents, independent review, and worktree isolation."
author: GPT-5.6
license: MIT
---

# Spec-Driven TDD

## Purpose

Turn a user request into committed software through a strict artifact chain,
independent review, a reviewed RED/GREEN TDD cycle, parallel worktree
implementation, and committed evidence.

## Roles

There are three strictly separated roles:

- Orchestrator: the primary agent. It delegates, monitors, applies process gates, and records handoffs. It does not implement or review.
- Implementer: a delegated worker agent that creates one assigned artifact, test, code change, correction, or merge result.
- Reviewer: a separate delegated worker agent that reviews an exact committed result and never fixes or writes files.

## Runtime assumptions

The workflow is platform-agnostic. It assumes the agent runtime provides:

- delegating self-contained tasks to worker agents, run in the background by default;
- a runtime identity (agent id / job id) returned for every delegation, recorded verbatim;
- a completion notification when a background worker settles;
- a structured final result (e.g. a JSON object) returned by each worker;
- the ability to continue the same worker's conversation for follow-up work (corrections by the same implementer, re-reviews by the same reviewer, when possible);
- git with worktree support for isolated implementation.

The orchestrator waits for completion notifications and never busy-polls: it stays
responsive to the user between delegations.

## Entrypoints

- `SKILL.md` — this file.
- `SKILL-ORCHESTRATOR.md` — delegation and process gates.
- `SKILL-IMPLEMENTER.md` — artifact, RED/GREEN, correction, and merge work.
- `SKILL-REVIEWER.md` — independent committed-state review.
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md` — acceptance criteria and test boundaries.
- `references/JOURNAL.md` — journal specification.
- `references/STAGES.md` — stage-by-stage procedure.

## Runtime evidence

Use:

- delegation records with the runtime-provided identity (agent id / job id) for every worker;
- completion notifications and the worker's structured final result;
- dedicated git worktree branches for implementation isolation;
- session transcripts and worker outputs as raw execution evidence where available.

Runtime handoff evidence is recorded in `.sddtdd_skill/orchestrator.log`. The
committed journal keeps its original compact schema and records the resulting
workflow verdicts.

## Workflow artifacts

The workflow state lives under `.sddtdd_skill/`:

- `SPEC-DRAFT.md`: exact user input and later append-only additions;
- `SPEC.md`: reviewed requirements and acceptance criteria;
- `ARCHITECTURE.md`: reviewed design and test boundaries;
- `TASKS.md`: reviewed task graph and dependencies. It is the schedule source: waves, parallelism, and write scopes are derived from its `DEPENDS_ON` and `WRITE-AREA` notes at delegation time. It must also preserve an explicit end-to-end path from the original business task in the root user request and reviewed SPEC to an accepted task outcome that resolves that business task; a graph that only schedules technical scaffolding, tests, fixtures, placeholders, or traceability without resolving the original business task is invalid;
- `JOURNAL_SDD_TDD_SKILL.log`: committed workflow evidence;
- `orchestrator.log`: append-only primary-agent handoff/check records;
- `reviewer.log`: append-only copies of immutable reviewer results, recorded by the orchestrator.

## Hard rules

1. Every agent-generated artifact receives independent review before downstream work depends on it.
2. Every automatically testable behavior passes through reviewed RED and reviewed GREEN.
3. Review only committed evidence. Mutable working-tree state is not evidence.
4. The orchestrator never implements, resolves conflicts, or performs independent review.
5. The reviewer never modifies files, writes logs, authors fixes, merges, or advances the workflow.
6. Commit messages are ASCII-only.
7. No RED, GREEN, or implementation delegation may begin before `TASK_REVIEW: PASS` and its process gate.
8. Every RED or GREEN delegation covers exactly one reviewed `TASKS.md` task node.
9. Parallel implementation is allowed only for dependency-ready tasks with safe, non-overlapping write scopes (from the TASKS.md `WRITE-AREA` notes).
10. Implementation branches are not integrated before independent review passes.
11. Every integration commit receives mandatory `MERGE_REVIEW: PASS` before downstream use.
12. Merge results are tested after integration, not only in the worker worktree.
13. RED is valid only when it fails for the target missing behavior or target bug. Unrelated failures are invalid RED evidence.
14. The orchestrator maintains the canonical journal on the integration branch; worker-appended entries are mirrored identically there and deduplicated.
15. Corrections after FAIL are delegated to the same implementer, and re-reviews after FAIL to the same reviewer, when the agent runtime allows continuing the same agent.
16. Reviewers are launched with a read-only role when the agent runtime supports one; otherwise read-only is enforced by instruction plus the orchestrator's post-check that the reviewer made no commits.
17. The orchestrator waits for completion notifications and never busy-polls; it stays responsive to the user.

## User scope changes

`SPEC-DRAFT.md` is append-only after its first commit.

When the user adds or changes a product requirement during work:

1. append the exact wording under an `ADDITION:` label;
2. journal and commit the addition before acting on it;
3. pause affected downstream work;
4. return to the earliest affected stage;
5. revise and re-review SPEC, architecture, tasks, and RED/GREEN evidence as needed.

## Required flow

1. Capture and commit `SPEC-DRAFT.md`.
2. Delegate SPEC creation; commit it; launch an independent `SPEC_REVIEW`.
3. Repeat correction and review until SPEC passes, then record `ORCHESTRATOR_TASK_REVIEW`.
4. Repeat the same cycle for ARCHITECTURE and TASKS, using `TASK_REVIEW` consistently.
5. Launch only dependency-ready RED delegations. Each covers exactly one `TASKS.md` task id and uses a dedicated git worktree branch when it writes tests or code.
6. When one worker completes, inspect its runtime identity, output, branch, commit, tests, and clean-state evidence.
7. Immediately launch a separate reviewer against that exact commit.
8. On `PASS`, advance only to the next legal transition. On `FAIL`, delegate correction to the same implementer. On `NEEDS_CLARIFICATION`, ask the user and pause affected work. On `BLOCKED`, record and surface the blocker.
9. Delegate one synchronous MERGE implementer for one reviewed branch at a time. Resolve conflicts there and run required tests on the integrated tree.
10. Immediately launch mandatory `MERGE_REVIEW` against the exact integration commit. No downstream work may use it before `PASS` and the following process gate.
11. Run and review regression evidence on the final integrated candidate.
12. Run final traceability review and record DONE only after every gate passes.

## Delegation context

Every implementer and reviewer receives:

- exact role and role-file path;
- task id and task kind;
- allowed write scope;
- required output and evidence;
- repository, integration base, worktree, and branch context where relevant;
- relevant committed ancestry, including the reviewed `TASKS.md` node (dependencies, `WRITE-AREA`, acceptance condition) for RED/GREEN work;
- relevant prior verdicts and corrections;
- the ASCII-only commit-message rule;
- a structured output contract when useful.

Child sessions do not inherit the parent conversation. Pass all required context
in the delegation prompt.
