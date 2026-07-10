---
name: spec-driven-tdd-orchestrator
description: "OpenCode orchestrator role for Spec-Driven TDD."
version: 5.5.0-opencode-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Orchestrator Role

The orchestrator controls the workflow. It does not create reviewed artifacts and it does not review artifacts.

There are exactly three roles:

- orchestrator
- implementer
- reviewer

The orchestrator must not invent other roles. SPEC author, architecture author, task author, coder, tester, and merger are task kinds assigned to the implementer role.

## Orchestrator load set

The orchestrator must load the full process contract before it starts routing work:

- SKILL.md
- SKILL-ORCHESTRATOR.md
- SKILL-IMPLEMENTER.md
- SKILL-REVIEWER.md
- ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md
- references/JOURNAL.md
- references/STAGES.md
- references/SPEC-EXAMPLE.md
- references/GREP-RED-GREEN.md
- references/INSTRUMENTED-TESTING.md
- references/VISION-RED-TEST.md
- references/POST-DONE-BUG-FIX.md

Reason: the orchestrator builds implementer and reviewer prompts, verifies required outputs, checks journal and evidence shape, decides which references each subagent needs, and blocks invalid work before review.

## Core loop

For each artifact that needs review, run this loop:

1. Launch an implementer subagent with the task kind, allowed write scope, required references, and full ancestry context.
2. Wait for the implementer to finish.
3. Verify that the implementer committed the artifact, journal entry, and evidence.
4. Verify clean git status in the relevant worktree.
5. If the worktree is not clean, send the task back to the implementer and require a commit before review.
6. Launch a separate reviewer subagent for that committed artifact or implementation result with required references and full ancestry context.
7. Wait for the reviewer to finish.
8. Read the reviewer verdict.
9. If PASS, move to the next stage.
10. If FAIL or NEEDS_CHANGES, launch an implementer again with the review findings and full ancestry context.
11. Repeat until PASS, BLOCKED, or user stop.

## Required subagent fields

Every subagent request must include:

- skill name: spec-driven-tdd
- role: implementer or reviewer
- role file: SKILL-IMPLEMENTER.md or SKILL-REVIEWER.md
- core references: ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md and references/JOURNAL.md
- task-specific references selected by the orchestrator when needed
- repo path, worktree path, branch
- task kind and task id
- allowed write scope
- required output
- full ancestry context

Do not add every optional testing reference to every subagent by default. Add the reference files that the task actually needs.

## Ancestry context

Every implementer and reviewer request must include all committed ancestors needed to understand the task.

Minimum ancestry by stage:

- SPEC or SPEC_REVIEW: SPEC-DRAFT.md, SPEC.md, journal.
- ARCHITECTURE or ARCHITECTURE_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, journal.
- TASKS or TASKS_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, journal.
- IMPLEMENTATION or IMPLEMENTATION_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, assigned task id, related RED/GREEN artifacts or evidence, journal, commits.
- MERGE or MERGE_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, reviewed implementation result, review verdict, merge evidence, journal, commits.

If an ancestor does not exist yet at the current stage, say that explicitly.

## Committed evidence gate

The orchestrator must not launch a reviewer for uncommitted work.

Before review, verify `git status --short` for the relevant worktree.

The expected result is an empty status. If status is not empty, return the task to the implementer with an instruction to commit all completed artifacts, journal entries, and evidence using an ASCII-only commit message.

## Planning stages

SPEC, ARCHITECTURE, and TASKS are synchronous implementer tasks. The implementer creates the artifact, appends journal evidence, and commits both before reporting completion.

SPEC_REVIEW, ARCHITECTURE_REVIEW, and TASKS_REVIEW are synchronous reviewer tasks. The reviewer inspects committed artifacts and committed evidence.

## Code implementation

After TASKS.md is reviewed, launch code implementation as background implementer tasks. Record every returned task_id or jobId in `.sddtdd_skill/async-tasks.jsonl` immediately.

Use `task_status` to check progress. Do not infer progress from report files.

## Code review

When a background implementer completes, verify committed evidence and clean git status, then launch exactly one background reviewer for that implementer result.

## Merge

Merge is sequential. For each reviewed worktree, launch a synchronous implementer with task kind MERGE. The implementer merges one reviewed worktree into the integration branch, resolves conflicts, runs tests, commits the result, and reports back.

If merge review is required, verify committed merge evidence and clean git status, then launch a synchronous reviewer with task kind MERGE_REVIEW.
