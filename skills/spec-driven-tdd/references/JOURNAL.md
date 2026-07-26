# JOURNAL.md — Spec-Driven TDD Journal Specification

This document defines the committed audit trail at:

```text
<repo_root>/.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log
```

## File rules

- file name is exactly `JOURNAL_SDD_TDD_SKILL.log`;
- file path is under `.sddtdd_skill/`;
- every entry is append-only and committed before it counts as proof;
- OMP session, advisor, `agent://`, and `history://` records are runtime evidence, not substitutes for required committed journal events.

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
AGENT_ID: {OMP_AGENT_ID | --}            (optional)
JOB_ID: {OMP_JOB_ID | --}                (optional)
COMMIT: {COMMIT_SHA | --}                (optional)
DETAIL: {description}
```

Blank lines separate entries.

## JID rules

Format:

```text
J-YYYYMMDD-HHMMSS-NNN
```

Every JID is unique. Parent JIDs already exist and are copied exactly.

## TYPE values

| TYPE | Meaning |
|---|---|
| `USER_INPUT` | exact user request or append-only user addition captured |
| `SPEC_SPEC` | `SPEC.md` created or revised |
| `SPEC_REVIEW` | review verdict for `SPEC.md` |
| `ARCHITECTURE` | `ARCHITECTURE.md` created or revised |
| `ARCHITECTURE_REVIEW` | architecture review verdict |
| `DECOMPOSE` | `TASKS.md` created or revised |
| `TASK_REVIEW` | task decomposition review verdict |
| `RED` | committed failing test and RED evidence |
| `RED_REVIEW` | RED review verdict |
| `GREEN` | committed implementation and GREEN evidence |
| `GREEN_REVIEW` | GREEN review verdict |
| `MERGE` | one reviewed worker result integrated and tested |
| `MERGE_REVIEW` | review verdict for the integrated result |
| `TASKS_COMPLETE` | all required task branches converged |
| `REGRESSION` | committed regression evidence |
| `REGRESSION_REVIEW` | regression review verdict |
| `FINAL` | committed final evidence |
| `FINAL_REVIEW` | final review verdict |
| `ORCHESTRATOR_GATE` | native OMP process-gate decision for one completed work/review event |
| `ESCALATION` | workflow escalated to user |
| `DONE` | pipeline completed |

Use `TASK_REVIEW` consistently. `TASKS_REVIEW` is not a valid event name.

## STATUS values

| STATUS | Use |
|---|---|
| `COMPLETED` | work events |
| `PASS` | review or process-gate approval |
| `FAIL` | review or process-gate failure |
| `NEEDS_CLARIFICATION` | user input is required |
| `BLOCKED` | an external or repository condition prevents progress |
| `ERROR` | trustworthy verification was impossible |
| `ESCALATED` | escalation entry |
| `CANCELLED` | cancelled task or branch |

Rules:

- `DONE` uses `STATUS: COMPLETED`;
- `ORCHESTRATOR_GATE` may use `PASS`, `FAIL`, `NEEDS_CLARIFICATION`, `BLOCKED`, or `ERROR`;
- non-PASS review/gate entries are not approvals.

## Journal lineage

`PARENT` and `ROOT` describe journal-event lineage, not task hierarchy.

Root user input:

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

Task hierarchy uses only `TASK_ID`, `PARENT_TASK_ID`, and
`ROOT_USER_INPUT_ID`.

- when `TASK_ID` exists, the other two fields are mandatory;
- a root task uses `PARENT_TASK_ID: --` and `ROOT_USER_INPUT_ID == TASK_ID`;
- child tasks store the direct parent task id;
- all entries for one logical task reuse the same task-tree fields.

## Workflow transitions

Top level:

```text
USER_INPUT
→ SPEC_SPEC
→ SPEC_REVIEW
→ ORCHESTRATOR_GATE
→ ARCHITECTURE
→ ARCHITECTURE_REVIEW
→ ORCHESTRATOR_GATE
→ DECOMPOSE
→ TASK_REVIEW
→ ORCHESTRATOR_GATE
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
→ ORCHESTRATOR_GATE
→ GREEN
→ GREEN_REVIEW
→ ORCHESTRATOR_GATE
→ MERGE
→ optional MERGE_REVIEW
```

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
plus replanning/re-review. `BLOCKED` stops dependent work until the named
condition is resolved.

## ORCHESTRATOR_GATE

This entry records the primary OMP orchestrator's process check after a work or
review result. It is distinct from semantic reviewer `*_REVIEW` events.

The gate is based on native evidence:

- actual OMP agent id and job id;
- exact delegated prompt in `.sddtdd_skill/orchestrator.log`;
- returned `agent://` output and `history://` transcript when needed;
- exact branch and commit;
- clean-worktree evidence;
- required independent review verdict;
- required RED/GREEN or integrated-test evidence;
- absence of unresolved watchdog blockers.

Rules:

- when independent review is required, `PARENT` is the committed review JID;
- otherwise, `PARENT` is the committed work JID;
- `TASK_ID` identifies the business task being validated;
- `AGENT_ID`, `JOB_ID`, and `COMMIT` contain actual values when available;
- `DETAIL` summarizes the checked evidence, findings, and next legal transition.

Meaning:

- `PASS`: process evidence is complete and downstream work may begin;
- `FAIL`: a process gap must be corrected first;
- `NEEDS_CLARIFICATION`: user questions must be answered and recorded;
- `BLOCKED`: the named blocker prevents legal progress;
- `ERROR`: trustworthy process verification was not possible.

## DEPENDS

`DEPENDS` records extra journal-entry dependencies, not task hierarchy. Use it
when one event depends on several completed branches.

## Invariants

1. every JID is unique;
2. every derived entry points to an existing direct parent;
3. every entry preserves the root JID of its delivery tree;
4. task hierarchy is represented only by task-tree fields;
5. sibling tasks share a parent rather than being chained by execution order;
6. review PASS cannot exist truthfully without the corresponding committed work entry;
7. `ORCHESTRATOR_GATE: PASS` cannot exist truthfully without matching native OMP runtime and committed evidence;
8. no implementation result is integrated before independent review PASS;
9. downstream work does not depend on upstream work lacking required approval proof.
