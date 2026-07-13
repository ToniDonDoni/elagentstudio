---
name: spec-driven-tdd-orchestrator
description: "Orchestrator role for Spec-Driven TDD."
version: 5.8.0-async
author: Hermes Agent
license: MIT
---

# Spec-Driven TDD Orchestrator Role

The orchestrator controls the workflow. It does not create reviewed artifacts and it does not review artifacts.

The orchestrator is a dispatcher only. Its job is to ask the registrar MCP server for the next task, delegate work between implementer and reviewer subagents, verify process gates, route review findings back to implementers, and decide the next allowed workflow step.

The orchestrator's primary responsibility is to call `getNextTask` on the
registrar MCP server for every workflow decision, receive the next task, and
delegate it to the appropriate agent. It repeats this get-next-task-and-delegate
cycle until all work is complete, the registrar reports `complete` or `BLOCKED`,
or the user stops the workflow. It must not invent the next task itself.

The orchestrator never changes reviewed artifacts directly. Artifact creation, artifact correction, merge work, and evidence edits are delegated to implementer subagents. Review work is delegated to reviewer subagents.

There are exactly three roles:

- orchestrator
- implementer
- reviewer

## Registrar MCP identity

MCP server: `sddtdd-mcp`
Configured namespace: `sddtdd`

The dispatcher must call this server through the configured namespace. It
exposes these raw tools:

- `getNextTask` — obtain the next registrar task.
- `taskStatus` — report or read delegated task state.

A namespaced client may expose these as `sddtdd_getNextTask` and
`sddtdd_taskStatus`.

The orchestrator must not invent other roles. SPEC author, architecture author, task author, coder, tester, and merger are task kinds assigned to the implementer role.

## Orchestrator load set

The orchestrator loads only its own control-plane contract:

- SKILL.md
- SKILL-ORCHESTRATOR.md
- references/JOURNAL.md

Do not add new mandatory reference files. The orchestrator may add an existing task-specific reference to a subagent prompt only when that task needs it.

## Full ancestry context

Every implementer and every reviewer must receive the full committed ancestry from the current task back to the original request.

Minimum ancestry by stage:

- SPEC or SPEC_REVIEW: SPEC-DRAFT.md, SPEC.md, journal.
- ARCHITECTURE or ARCHITECTURE_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, journal.
- TASKS or TASKS_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, journal.
- IMPLEMENTATION or IMPLEMENTATION_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, assigned task id, related RED/GREEN artifacts or evidence, journal, commits.
- MERGE or MERGE_REVIEW: SPEC-DRAFT.md, SPEC.md, ARCHITECTURE.md, TASKS.md, reviewed implementation result, review verdict, merge evidence, journal, commits.

## Core loop

For each artifact that needs review, run this loop. Every operation is asynchronous
through the runtime's background-task mechanism except a `MERGE` task, which is
the only synchronous operation and handles exactly one worktree.

1. Call the registrar MCP `sddtdd_getNextTask` operation. For the initial request use `INITIAL_USER_INPUT`; for later calls submit the completed task and committed evidence.
2. The registrar MCP server records the issued task as `PENDING`; the orchestrator does not report that state.
3. Launch the implementer or reviewer through the runtime background-task mechanism, passing the required context and the task's isolated worktree. The launched agent must report `RUNNING` directly to the registrar with its role and returned runtime task id.
4. Use the runtime task-status mechanism to detect completion. Do not infer completion from report files.
5. The implementer or reviewer reports `COMPLETED`, `FAILED`, or `BLOCKED` directly to the registrar with the evidence. The orchestrator verifies the result's commit and clean worktree but must not impersonate the reporting agent. If review is required, the implementer may report `WAITING_REVIEW` until the reviewer starts.
6. As soon as one implementer result is ready, launch its separate reviewer immediately. Do not wait for unrelated tasks or a batch.
7. If the reviewer returns `PASS`, submit its committed evidence to `getNextTask`. If it returns `FAIL` or `NEEDS_CHANGES`, launch a new asynchronous implementer with the findings and full ancestry context.
8. For `MERGE`, launch one synchronous implementer for one reviewed worktree, resolve conflicts, run required tests, update task status, and commit the merge result before requesting the next task.
9. If the registrar returns `notReady`, do not issue or invent a task. `notReady` may mean that an issued task is still active, or that the registrar is temporarily busy and is throttling repeated requests. Wait briefly, query runtime task status when relevant, and call `getNextTask` again after the wait.
10. Repeat until `complete`, `BLOCKED`, or user stop.

Tasks should run in background mode by default, allowing multiple tasks to start asynchronously without waiting for previous tasks to finish, unless getNextTask explicitly requests synchronous execution.
For background tasks:
* OpenCode: set background: true in the task tool.
* Hermes: use kanban_create(assignee="default", ...).


Every delegated task status update must include, when available:

- `task_id`, `task_kind`, `status`, and `role`;
- the runtime `execution_id` returned by the background-task mechanism;
- `worktree_path`, `branch`, and resulting `commit`;
- a concise `result` or `error`.
- use instruct to use spec-driven-tdd skill with the assigned role (eg. implementer or reviewer)

## `notReady` and task timeout

`getNextTask` returns `status: "notReady"` with `next_task: null` when a
previously issued task is still unfinished or when the registrar is temporarily
busy and throttling repeated requests. This is not a failure and must not cause
the dispatcher to create duplicate work. In either case, wait briefly and call
`getNextTask` again; do not treat `notReady` as a terminal task result.

The registrar expires an active task when it has not received a direct
`taskStatus(update)` report for the configured timeout. The default is 600
seconds; override it with `SDDTDD_TASK_TIMEOUT_SECONDS` for tests or deployment
policy. Expired tasks become `FAILED` with `retryable: true` and can be issued
again by a later `getNextTask` call.

## Required subagent fields

Every subagent request must include:

- skill name: spec-driven-tdd
- role: implementer or reviewer
- role file: SKILL-IMPLEMENTER.md or SKILL-REVIEWER.md
- core references: ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md and references/JOURNAL.md
- task-specific references selected by the orchestrator only when needed
- repo path, worktree path, branch
- task kind and task id
- allowed write scope
- required output
- full ancestry context

Do not add every optional testing reference to every subagent by default.

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

## Merge

Merge is sequential and is the only synchronous task type. For each reviewed worktree, launch one synchronous implementer with task kind MERGE.

The MERGE implementer merges exactly one reviewed worktree into the integration branch. If conflicts appear, the MERGE implementer resolves them, then runs the required test command before committing the merge result or reporting merge completion.

The MERGE implementer commits only after the conflict-resolved integration branch passes the required tests, records the test evidence, and reports back.

If merge review is required, verify committed merge evidence and clean git status, then launch a synchronous reviewer with task kind MERGE_REVIEW.

## Hard rules

- The orchestrator is a dispatcher only; it delegates work between implementer and reviewer subagents.
- The orchestrator must not create, edit, or correct reviewed artifacts itself.
- The orchestrator must not review artifacts itself.
- Every subagent request must name the skill, role, role file, task kind, allowed write scope, required output, required references, and full ancestry context.
- All non-MERGE implementer and reviewer work uses background tasks.
- A reviewer is launched immediately after each implementer result is committed and clean-status verified.
- Merge work is sequential and is performed by synchronous MERGE implementer subagents.
- A MERGE implementer must run the required tests after resolving conflicts and before committing or reporting merge completion.
- Commit messages must be ASCII-only.
- Uncommitted artifacts, journal entries, and mutable working-tree state are not evidence.

## Orchestrator handoff log

The orchestrator MUST maintain a private append-only orchestration log at:

`.sddtdd_skill/orchestrator.log`

This log is separate from `references/JOURNAL.md` and `.sddtdd_skill/async-tasks.jsonl`.

Only the orchestrator may read or write `.sddtdd_skill/orchestrator.log`.

Implementer and reviewer subagents MUST NOT read it, receive it in their context, reference it, or modify it.

The orchestrator MUST append one entry whenever it:

- delegates a task to an implementer;
- delegates a task to a reviewer;
- checks a result returned by an implementer;
- checks a result returned by a reviewer.

Each entry MUST be one JSON object on one line with these required fields:


```json
{"timestamp":"<UTC_ISO8601>","event":"<HANDOFF|CHECK>","role":"<implementer|reviewer>","task_kind":"<TASK_KIND>","task_number":"<TASK_NUMBER_OR_NONE>","task_id":"<BUSINESS_TASK_ID>","execution_id":"<OPENCODE_RUNTIME_ID_OR_NONE>","commit":"<COMMIT_SHA_OR_NONE>","head":"<HEAD_SHA>","summary":"<SHORT_DESCRIPTION>"}
```

- task_id identifies the business workflow task from TASKS.md.
- execution_id is mandatory for every delegated implementer or reviewer.
- execution_id MUST contain the actual runtime identifier returned by OpenCode for the delegated work.
- For background tasks, execution_id MUST contain the background task ID.
- For non-background asynchronous tasks, execution_id MUST contain the corresponding runtime identifier returned by the runtime.
- If the runtime returns no runtime identifier, execution_id MUST be NONE.
- The same execution_id MUST be reused in the corresponding HANDOFF and CHECK entries.
- The orchestrator MUST NOT invent, derive, or substitute an execution_id.
