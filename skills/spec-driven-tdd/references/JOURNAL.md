# JOURNAL.md — Spec-Driven TDD Journal Specification

This document defines the required format and invariants for:

```text
<repo_root>/.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log
```

The journal is the committed audit trail of the workflow.

## File rules

- file name must be exactly `JOURNAL_SDD_TDD_SKILL.log`;
- file path must be under `.sddtdd_skill/`;
- every appended entry must be committed before it counts as proof;
- `review-access.jsonl` and `orchestrator-access.jsonl` are runtime-only and not committed.

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
| `USER_INPUT` | raw user request captured |
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
| `TASKS_COMPLETE` | required task branches converged |
| `REGRESSION` | committed regression evidence |
| `REGRESSION_REVIEW` | regression review verdict |
| `FINAL` | committed final evidence |
| `FINAL_REVIEW` | final review verdict |
| `ORCHESTRATOR_TASK_REVIEW` | orchestrator process-gate verdict for one orchestrator task |
| `ESCALATION` | workflow escalated to user |
| `DONE` | pipeline completed |

## STATUS values

| STATUS | Use |
|---|---|
| `COMPLETED` | work events |
| `PASS` | review approvals |
| `FAIL` | review failures |
| `NEEDS_CLARIFICATION` | missing information blocks approval |
| `ERROR` | trustworthy process verification was impossible |
| `ESCALATED` | escalation entry |
| `CANCELLED` | cancelled branch or delivery |

Rules:

- `DONE` must use `STATUS: COMPLETED`;
- `ORCHESTRATOR_TASK_REVIEW` may use `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `ERROR`;
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
→ ARCHITECTURE
→ ARCHITECTURE_REVIEW
→ DECOMPOSE
→ TASK_REVIEW
→ task branches
→ TASKS_COMPLETE
→ REGRESSION
→ REGRESSION_REVIEW
→ FINAL
→ FINAL_REVIEW
→ DONE
```

Task branch:

```text
RED
→ RED_REVIEW
→ GREEN
→ GREEN_REVIEW
```

Failure transitions:

```text
SPEC_REVIEW FAIL → SPEC_SPEC
ARCHITECTURE_REVIEW FAIL → ARCHITECTURE
TASK_REVIEW FAIL → DECOMPOSE
RED_REVIEW FAIL → RED
GREEN_REVIEW FAIL → GREEN
REGRESSION_REVIEW FAIL → REGRESSION or affected task
FINAL_REVIEW FAIL → FINAL or affected upstream artifact
```

## ORCHESTRATOR_TASK_REVIEW

This entry records the verdict returned in `task_review` by
`mcp_sddtdd_getNextTask`. It is distinct from reviewer `*_REVIEW` entries.

Rules:

- if the submitted task required independent review, `PARENT` must be the committed review JID;
- otherwise, `PARENT` must be the committed work JID;
- in orchestrator mode, `TASK_ID` must be the orchestrator task id being validated;
- `DETAIL` should include the task id, verdict summary, key findings or fixes, and orchestrator request id when available.

Meaning:

- `PASS` → submitted task is process-complete; downstream work may begin after this entry is committed;
- `FAIL` → process gap exists; fix it first;
- `NEEDS_CLARIFICATION` → user clarification or missing proof blocks legal progress;
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
7. orchestrator PASS cannot truthfully exist without the corresponding orchestrator runtime verdict;
8. downstream work must not depend on upstream work lacking required approval proof.
