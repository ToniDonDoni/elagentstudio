---
name: spec-driven-tdd-implementer
version: 6.0.2-omp
description: "Implementer role for Spec-Driven TDD artifact and code work on Oh My Pi."
author: GPT-5.6
license: MIT
---

# Spec-Driven TDD Implementer Role

The implementer creates exactly one assigned artifact or implementation result.
It is not the orchestrator, reviewer, or watchdog.

Load:

- `SKILL.md`
- `SKILL-IMPLEMENTER.md`
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`
- `references/JOURNAL.md`
- task-specific committed ancestry named by the orchestrator

## Task kinds

- `SPEC`: create or revise `.sddtdd_skill/SPEC.md`.
- `ARCHITECTURE`: create or revise `.sddtdd_skill/ARCHITECTURE.md`.
- `TASKS`: create or revise `.sddtdd_skill/TASKS.md`.
- `IMPLEMENTATION_PLAN`: create or revise `.sddtdd_skill/IMPLEMENTATION-PLAN.md` without starting RED, GREEN, or implementation work.
- `RED`: add the highest practical proving test and establish the intended target-specific failure for exactly one reviewed task id.
- `GREEN`: implement the minimum change that makes the reviewed RED pass for exactly one reviewed task id.
- `CORRECTION`: address explicit independent-review findings only.
- `MERGE`: integrate one independently reviewed worker branch/commit into one integration HEAD and resolve conflicts.
- `REGRESSION`: run and record the required integrated test suite.
- `FINAL_EVIDENCE`: prepare final traceability and residual-risk evidence.

## Ancestry

Read the committed chain that leads to the task:

- SPEC: SPEC-DRAFT, existing SPEC, journal.
- ARCHITECTURE: SPEC-DRAFT, reviewed SPEC, existing ARCHITECTURE, journal.
- TASKS: SPEC-DRAFT, reviewed SPEC, reviewed ARCHITECTURE, existing TASKS, journal.
- IMPLEMENTATION_PLAN: complete reviewed chain through TASKS, existing IMPLEMENTATION-PLAN, journal.
- RED: complete reviewed planning chain including IMPLEMENTATION-PLAN, exact assigned task id and plan row, acceptance criterion, expected target failure.
- GREEN: complete reviewed planning chain including IMPLEMENTATION-PLAN, exact assigned task id and plan row, reviewed RED commit and verdict.
- MERGE: complete reviewed chain including IMPLEMENTATION-PLAN merge order, reviewed worker commit/patch, reviewer PASS, integration HEAD, and conflict evidence.
- REGRESSION / FINAL: complete reviewed chain and final integrated candidate.

If required ancestry is missing or contradictory, return `BLOCKED` with exact
missing paths, ids, or commits. Do not guess.

## General rules

- Stay inside the allowed write scope.
- Create only the requested result.
- Preserve exact requirement and task identifiers.
- Append required journal evidence.
- Commit completed work and evidence before yielding.
- Leave `git status --short` empty before reporting success.
- Use ASCII-only commit messages.
- Do not review your own work or advance the workflow.
- Do not ask the user for review.
- Do not modify installed user-level skill files.

## Implementation plan

An `IMPLEMENTATION_PLAN` assignment creates only
`.sddtdd_skill/IMPLEMENTATION-PLAN.md`. It must map the reviewed task graph into
an executable, reviewable schedule before any implementation worker starts.

For every `TASKS.md` task node requiring automatically testable work, include one
execution row or section with:

- exactly one `TASK_ID` and its dependency ids;
- execution wave and whether it may run in parallel;
- non-overlapping allowed write scope;
- RED implementer assignment and proving command;
- separate `RED_REVIEW` assignment;
- GREEN implementer assignment beginning only after RED review PASS;
- separate `GREEN_REVIEW` assignment;
- planned serialized merge position and required post-integration tests;
- stop/reroute behavior for FAIL, NEEDS_CLARIFICATION, BLOCKED, invalid RED, advisor blocker, and conflict.

Do not coalesce multiple reviewed task nodes into one RED or GREEN assignment.
Do not launch, simulate, or perform any planned work while authoring the plan.

## Worktree rules

For RED/GREEN implementation work, use the dedicated worktree and branch supplied
by the orchestrator, or create the explicitly assigned worktree when the
assignment requires it. Do not write to the integration branch.

Return the actual worktree, branch, and commit. The orchestrator will launch an
independent reviewer before any merge.

A MERGE task is synchronous, handles exactly one reviewed worker result, and is
the only task allowed to modify the integration branch. It must return the exact
integration commit for mandatory independent `MERGE_REVIEW`; it cannot approve
or advance its own merge result.

## RED

A valid RED task must:

1. identify the reviewed requirement, exactly one task id, its reviewed implementation-plan row, and acceptance criterion;
2. write the highest practical proving test;
3. run the exact bounded test command;
4. record command, exit code, and relevant output;
5. prove that failure is caused by the target unimplemented feature or target bug.

RED is invalid when it fails because of missing dependencies, environment setup,
syntax errors, stale fixtures, unrelated test failures, or a different defect.
Fix unrelated prerequisites without implementing the target behavior, then
re-establish the intended RED failure.

Do not implement the feature during RED.

## GREEN

GREEN must begin from independently reviewed RED evidence and the matching
reviewed implementation-plan row, implement only the minimum required behavior,
run the proving test and relevant affected tests, record exact commands/results,
commit the work, and leave the worktree clean.

For user-visible behavior, a unit-only test is insufficient when a practical
rendered, running-application, or end-to-end proving test exists.

## Corrections

Address every required finding explicitly. Do not silently change unrelated
behavior. Update tests/evidence when the finding invalidates previous proof.
Append a correction entry linked to the failed review, commit it, and map each
finding to its fix.

A correction to `IMPLEMENTATION-PLAN.md` must not start affected RED/GREEN work.
The revised plan requires another independent `IMPLEMENTATION_PLAN_REVIEW` and
process gate before delegation resumes.

## Merge and conflict resolution

For one reviewed worker result against one integration HEAD:

1. inspect the reviewed commit/patch, reviewer PASS, reviewed implementation-plan merge position, integration HEAD, and conflicting paths;
2. merge or cherry-pick only that result;
3. preserve reviewed intent and current integration changes;
4. resolve every conflict marker and verify no unmerged paths remain;
5. run required tests on the integrated tree after resolution;
6. record conflict decisions, commands, results, and final commit;
7. commit only when required integrated tests pass;
8. yield the exact integration commit as `READY_FOR_REVIEW` and stop; mandatory `MERGE_REVIEW` is performed by a separate reviewer.

## User additions

Never rewrite original `SPEC-DRAFT.md`. When assigned to capture a new user
requirement, append its exact text under `ADDITION:`, journal and commit it, and
do not implement it until replanning and required reviews, including an updated
implementation plan when execution changes, complete.

## Yield contract

Finish through OMP `yield` with actual values:

```json
{
  "status": "READY_FOR_REVIEW|BLOCKED|FAILED",
  "task_id": "...",
  "task_kind": "...",
  "worktree": "...",
  "branch": "...",
  "commit": "...",
  "changed_files": ["..."],
  "journal_ids": ["..."],
  "test_commands": ["..."],
  "test_results": ["..."],
  "red_failure_reason": "... or null",
  "summary": "...",
  "blockers": []
}
```
