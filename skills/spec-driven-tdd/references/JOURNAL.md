# JOURNAL.md — Spec-Driven TDD Journal Specification

This document defines the required format and invariants for:

```text
<repo_root>/.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log
```

The journal is the committed audit trail of the workflow.

Runtime identities, prompts, transcripts, branches, commits, and task delivery
details stay in runtime JSONL logs such as `.sddtdd_skill/orchestrator.log`; they
are evidence used to justify journal verdicts, not new fields in every journal
entry.

## File rules

- file name must be exactly `JOURNAL_SDD_TDD_SKILL.log`;
- file path must be under `.sddtdd_skill/`;
- every appended entry must be committed before it counts as proof;
- session transcripts and `orchestrator.log`/`reviewer.log` are runtime evidence and are not substitutes for committed journal events.

## Entry format

```text
=== {JID} ===
TYPE: {TYPE}
SPEC: {SPEC_ID}
STATUS: {STATUS}
PARENT: {PARENT_JID | --}
ROOT: {ROOT_JID}
DEPENDS: {JID[, JID...]}                 (optional)
TASK_ID: {TASK_ID}                       (optional)
PARENT_TASK_ID: {TASK_ID | --}           (required when TASK_ID is present)
ROOT_USER_INPUT_ID: {TASK_ID}            (required when TASK_ID is present)
DETAIL: {description}
```

Blank lines separate entries.

## JID rules

Format:

```text
J-YYYYMMDD-HHMMSS-NNN
```

Rules:

- every JID is unique;
- parent JIDs must already exist;
- parent JIDs are copied exactly, never guessed or reconstructed.

## TYPE values

| TYPE | Meaning |
|---|---|
| `USER_INPUT` | raw user request or append-only user addition captured |
| `SPEC_SPEC` | `SPEC.md` created or revised |
| `SPEC_REVIEW` | review verdict for `SPEC.md` |
| `ARCHITECTURE` | `ARCHITECTURE.md` created or revised |
| `ARCHITECTURE_REVIEW` | architecture review verdict |
| `DECOMPOSE` | `TASKS.md` created or revised |
| `TASK_REVIEW` | task decomposition review verdict |
| `RED` | committed failing test and RED evidence |
| `RED_REVIEW` | RED review verdict |
| `GREEN` | committed minimal implementation and GREEN evidence |
| `GREEN_REVIEW` | GREEN review verdict |
| `MERGE` | one independently reviewed worker result integrated and tested |
| `MERGE_REVIEW` | independent review verdict for the exact integrated commit |
| `TASKS_COMPLETE` | required task branches converged after passing merge reviews |
| `REGRESSION` | committed regression evidence |
| `REGRESSION_REVIEW` | regression review verdict |
| `FINAL` | committed final evidence |
| `FINAL_REVIEW` | final review verdict |
| `ORCHESTRATOR_TASK_REVIEW` | process-gate verdict for one orchestrator task |
| `ESCALATION` | workflow escalated to user |
| `DONE` | pipeline completed |

Use `TASK_REVIEW` consistently. `TASKS_REVIEW` is not valid.

## STATUS values

| STATUS | Use |
|---|---|
| `COMPLETED` | work events |
| `PASS` | review or process-gate approvals |
| `FAIL` | review or process-gate failures |
| `NEEDS_CLARIFICATION` | missing information blocks approval |
| `BLOCKED` | external or repository condition prevents progress |
| `ERROR` | trustworthy verification was impossible |
| `ESCALATED` | escalation entry |
| `CANCELLED` | cancelled branch or delivery |

Rules:

- `DONE` must use `STATUS: COMPLETED`;
- `ORCHESTRATOR_TASK_REVIEW` may use `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, `BLOCKED`, or `ERROR`;
- non-PASS review entries are not approvals.

## Journal lineage

`PARENT` and `ROOT` describe journal-event lineage, not task hierarchy.

`USER_INPUT` root:

```text
PARENT: --
ROOT: <its own JID>
```

Derived entry:

```text
PARENT: <exact direct parent JID>
ROOT: <root USER_INPUT JID>
```

## Task-tree fields

Task hierarchy uses only:

```text
TASK_ID
PARENT_TASK_ID
ROOT_USER_INPUT_ID
```

Rules:

- if `TASK_ID` exists, `PARENT_TASK_ID` and `ROOT_USER_INPUT_ID` are mandatory;
- root task has `PARENT_TASK_ID: --`;
- root task has `ROOT_USER_INPUT_ID == TASK_ID`;
- child task stores the direct parent task id;
- all entries for one logical task reuse the same task-tree fields.

## Workflow transitions

Top level:

```text
USER_INPUT
→ SPEC_SPEC
→ SPEC_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ ARCHITECTURE
→ ARCHITECTURE_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ DECOMPOSE
→ TASK_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ task branches
→ TASKS_COMPLETE
→ REGRESSION
→ REGRESSION_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ FINAL
→ FINAL_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ DONE
```

No task branch may begin before `TASK_REVIEW: PASS` and the following
`ORCHESTRATOR_TASK_REVIEW: PASS` are committed.

Task branch:

```text
RED
→ RED_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ GREEN
→ GREEN_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
→ MERGE
→ MERGE_REVIEW
→ ORCHESTRATOR_TASK_REVIEW
```

Each task branch must correspond to exactly one reviewed `TASKS.md` task id.
Multiple reviewed task nodes may not be collapsed into one RED or GREEN event
chain.

`MERGE_REVIEW` is mandatory. No downstream task, `TASKS_COMPLETE`, regression,
or final work may consume an integrated commit until its exact merge result has
`MERGE_REVIEW: PASS` and a following `ORCHESTRATOR_TASK_REVIEW: PASS`.

Failure transitions:

```text
SPEC_REVIEW FAIL → SPEC_SPEC
ARCHITECTURE_REVIEW FAIL → ARCHITECTURE
TASK_REVIEW FAIL → DECOMPOSE
RED_REVIEW FAIL → RED
GREEN_REVIEW FAIL → GREEN
MERGE_REVIEW FAIL → MERGE or affected task
REGRESSION_REVIEW FAIL → REGRESSION or affected task
FINAL_REVIEW FAIL → FINAL or affected upstream artifact
```

`NEEDS_CLARIFICATION` pauses affected work and is followed by captured user input
plus replanning/re-review. `BLOCKED` stops dependent work until the named condition
is resolved.

Any change to task batching, dependency waves, parallel groups, write scopes, or
RED/GREEN assignment boundaries returns to `DECOMPOSE`, followed by a new
`TASK_REVIEW` and process gate before affected work resumes.

## ORCHESTRATOR_TASK_REVIEW

This entry records the primary orchestrator's process-gate verdict for one
completed work or review task. It is distinct from semantic reviewer `*_REVIEW`
entries.

The verdict must be grounded in actual runtime evidence recorded in the runtime
logs:

- delegated prompt and actual runtime identities;
- worker output and transcript when needed;
- exact branch and commit;
- clean-worktree evidence;
- independent reviewer verdict for the exact commit;
- RED/GREEN or post-integration test evidence.

Rules:

- if the submitted task required independent review, `PARENT` must be the committed review JID;
- otherwise, `PARENT` must be the committed work JID;
- `TASK_ID` identifies the orchestrator task being validated;
- `DETAIL` summarizes the task id, evidence checked, verdict, key findings, and next legal transition.

Meaning:

- `PASS` → submitted task is process-complete; downstream work may begin after this entry is committed;
- `FAIL` → process gap exists; fix it first;
- `NEEDS_CLARIFICATION` → user clarification or missing proof blocks legal progress;
- `BLOCKED` → the named blocker prevents legal progress;
- `ERROR` → trustworthy verification was not possible.

## DEPENDS

`DEPENDS` records extra journal-entry dependencies, not task hierarchy. Use it
when one event depends on several completed branches.

## Invariants

1. every JID is unique;
2. every derived entry points to an existing direct parent;
3. every entry preserves the root JID of its delivery tree;
4. task hierarchy is represented only by task-tree fields;
5. sibling tasks share a parent rather than being chained by execution order;
6. review PASS cannot truthfully exist without the corresponding reviewed work entry;
7. orchestrator PASS cannot truthfully exist without matching runtime evidence;
8. no RED/GREEN work begins before reviewed TASKS and its process gate;
9. each RED/GREEN assignment covers exactly one reviewed task node;
10. no implementation result is integrated before independent review PASS;
11. every integration commit receives `MERGE_REVIEW: PASS` before downstream use;
12. downstream work must not depend on upstream work lacking required approval proof.