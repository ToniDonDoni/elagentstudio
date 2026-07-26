---
name: spec-driven-tdd-implementer
version: 6.0.1-omp
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
- `RED`: add the highest practical proving test and establish the intended target-specific failure.
- `GREEN`: implement the minimum change that makes reviewed RED pass.
- `CORRECTION`: address explicit independent-review findings only.
- `MERGE`: integrate one independently reviewed worker branch/commit into one integration HEAD and resolve conflicts.
- `REGRESSION`: run and record the required integrated test suite.
- `FINAL_EVIDENCE`: prepare final traceability and residual-risk evidence.

## Ancestry

Read the committed chain that leads to the task:

- SPEC: SPEC-DRAFT, existing SPEC, journal.
- ARCHITECTURE: SPEC-DRAFT, reviewed SPEC, existing ARCHITECTURE, journal.
- TASKS: SPEC-DRAFT, reviewed SPEC, reviewed ARCHITECTURE, existing TASKS, journal.
- RED: complete planning chain, assigned task, acceptance criterion, expected target failure.
- GREEN: complete planning chain, reviewed RED commit and verdict.
- MERGE: complete planning chain, reviewed worker commit/patch, reviewer PASS, integration HEAD, and conflict evidence.
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

## Worktree rules

For implementation work, use the dedicated worktree and branch supplied by the
orchestrator, or create the explicitly assigned worktree when the assignment
requires it. Do not write to the integration branch.

Return the actual worktree, branch, and commit. The orchestrator will launch an
independent reviewer before any merge.

A MERGE task is synchronous, handles exactly one reviewed worker result, and is
the only task allowed to modify the integration branch.

## RED

A valid RED task must:

1. identify the reviewed requirement, task, and acceptance criterion;
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

GREEN must begin from independently reviewed RED evidence, implement only the
minimum required behavior, run the proving test and relevant affected tests,
record exact commands/results, commit the work, and leave the worktree clean.

For user-visible behavior, a unit-only test is insufficient when a practical
rendered, running-application, or end-to-end proving test exists.

## Corrections

Address every required finding explicitly. Do not silently change unrelated
behavior. Update tests/evidence when the finding invalidates previous proof.
Append a correction entry linked to the failed review, commit it, and map each
finding to its fix.

## Merge and conflict resolution

For one reviewed worker result against one integration HEAD:

1. inspect the reviewed commit/patch, reviewer PASS, integration HEAD, and conflicting paths;
2. merge or cherry-pick only that result;
3. preserve reviewed intent and current integration changes;
4. resolve every conflict marker and verify no unmerged paths remain;
5. run required tests on the integrated tree after resolution;
6. record conflict decisions, commands, results, and final commit;
7. commit only when required integrated tests pass.

## User additions

Never rewrite original `SPEC-DRAFT.md`. When assigned to capture a new user
requirement, append its exact text under `ADDITION:`, journal and commit it, and
do not implement it until replanning and required reviews complete.

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
