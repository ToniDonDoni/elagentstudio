# JOURNAL.md — SDD Workflow Journal Specification

TODO update to the skill v2
TODO: Align JOURNAL.md with the new architecture stage.
- Add TYPE `ARCHITECTURE` for creation or revision of `ARCHITECTURE.md`.
- Add TYPE `ARCHITECTURE_REVIEW` for architecture review verdicts.
- Allow `ARCHITECTURE` to use STATUS `COMPLETED`.
- Allow `ARCHITECTURE_REVIEW` to use `PASS`, `FAIL`, or `NEEDS_CLARIFICATION`.
- Add both types to the required-fields-by-entry-type table.
- Update the top-level workflow to:
  USER_INPUT
  -> SPEC_SPEC
  -> SPEC_REVIEW
  -> ARCHITECTURE
  -> ARCHITECTURE_REVIEW
  -> DECOMPOSE
  -> TASK_REVIEW
  -> task branches
  -> TASKS_COMPLETE
  -> REGRESSION
  -> REGRESSION_REVIEW
  -> FINAL_REVIEW
  -> DONE
- Add the failure transition:
  ARCHITECTURE_REVIEW FAIL -> ARCHITECTURE
- Clarify that `SPEC_SPEC` records creation or revision of editable `SPEC.md`.
- Clarify that `SPEC_REVIEW` reviews committed `SPEC.md`, not immutable `SPEC-DRAFT.md`.
- Clarify that `DECOMPOSE` uses reviewed `SPEC.md` and reviewed `ARCHITECTURE.md`.
- Update the complete journal example to include `ARCHITECTURE` and `ARCHITECTURE_REVIEW`.
- Do not add new relationship fields. Continue using `JID`, `PARENT`, `ROOT`, `DEPENDS`, and the existing task-tree fields.
- Store artifact paths, reviewed commit hashes, and review evidence in `DETAIL` unless a separate structured-field change is explicitly approved.
- DONE: Added TYPE `BROKER_TASK_REVIEW` for the broker's process-gate verdict on whether a broker-issued task is process-complete. See section 10.


This document defines the required format and content of `JOURNAL_SDD_TDD_SKILL.log`.

The journal records:

1. workflow events;
2. relationships between journal entries;
3. relationships between tasks;
4. the originating user input for every derived task and journal entry.

---

## 1. File Location

The journal file MUST be named:

```text
JOURNAL_SDD_TDD_SKILL.log
```

It MUST be stored at the project root.

---

## 2. Journal Entry Format

Each journal entry MUST use the following field order:

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

Optional fields MUST be omitted when they are not applicable.

---

## 3. Journal Entry Fields

### 3.1 JID

Every journal entry MUST have a unique journal entry identifier.

Format:

```text
J-YYYYMMDD-HHMMSS-NNN
```

Example:

```text
J-20260614-204500-001
```

### 3.2 TYPE — Entry Type

| TYPE | When created |
|---|---|
| `USER_INPUT` | Recording an incoming user request |
| `PROJECT_INIT` | Project initialization |
| `SPEC_SPEC` | Initial specification or specification amendment created |
| `SPEC_REVIEW` | Specification review result |
| `DECOMPOSE` | Specification decomposed into tasks, or task decomposed into child tasks |
| `TASK_REVIEW` | Task decomposition review result |
| `AGENT_DECISION` | Agent records a workflow decision |
| `RED` | Test written and executed; failure expected |
| `RED_REVIEW` | RED stage review result |
| `GREEN` | Minimal implementation created |
| `GREEN_REVIEW` | GREEN stage review result |
| `TASKS_COMPLETE` | All active task branches for a specification are complete |
| `REGRESSION` | Regression test run |
| `REGRESSION_REVIEW` | Regression review result |
| `FINAL_REVIEW` | Final implementation review result |
| `BROKER_TASK_REVIEW` | MCP task broker process-gate verdict on whether a broker-issued task is process-complete |
| `ESCALATION` | Review limit exceeded or user decision required |
| `DONE` | Pipeline completed |

### 3.3 STATUS — Entry Status

| STATUS | Meaning | Typical entry types |
|---|---|---|
| `COMPLETED` | Work step completed | `USER_INPUT`, `PROJECT_INIT`, `SPEC_SPEC`, `DECOMPOSE`, `AGENT_DECISION`, `RED`, `GREEN`, `TASKS_COMPLETE`, `REGRESSION`, `DONE` |
| `PASS` | Review passed | `SPEC_REVIEW`, `TASK_REVIEW`, `RED_REVIEW`, `GREEN_REVIEW`, `REGRESSION_REVIEW`, `FINAL_REVIEW` |
| `FAIL` | Review failed | Review entries |
| `NEEDS_CLARIFICATION` | More information is required | Review entries |
| `FIXED` | A failed RED or GREEN artifact was corrected | `RED`, `GREEN` |
| `ESCALATED` | Review process escalated to the user | Review entries |
| `CANCELLED` | The entry or branch was cancelled | Any applicable type |

`DONE` MUST use:

```text
STATUS: COMPLETED
```

A review stage with `FAIL` or `NEEDS_CLARIFICATION` MUST NOT be treated as approved.

### 3.4 SPEC

Every entry MUST identify the relevant specification.

Recommended format:

```text
S-[A-Z]{2,6}-NN
```

Child specifications MAY extend the parent identifier:

```text
S-TETRIS-01
S-TETRIS-01.01
S-TETRIS-01.01.01
```

### 3.5 DETAIL

`DETAIL` contains a human-readable description of the event.

It SHOULD include:

- what was created or changed;
- test or review result;
- important reviewer findings;
- reason for failure, cancellation, or escalation;
- relevant evidence or summary.

---

## 4. Journal Entry Relationships

Journal entry relationships are represented by:

```text
PARENT
ROOT
```

These fields describe journal events, not task hierarchy.

### 4.1 USER_INPUT Journal Root

A `USER_INPUT` journal entry has:

```text
PARENT: --
ROOT: <its own JID>
```

### 4.2 Derived Journal Entry

Every derived journal entry has:

```text
PARENT: <exact JID of the direct parent journal entry>
ROOT: <originating USER_INPUT journal JID>
```

`PARENT` MUST be copied exactly from an existing journal entry.

A `PARENT` JID MUST NOT be generated, guessed, incremented, decremented,
reconstructed from another timestamp, or modified through string operations.

Before a derived entry is appended, its `PARENT` value MUST already exist in
the journal. If the direct parent cannot be identified unambiguously, the new
entry MUST NOT be written.

The exact JID created for a journal entry MUST be retained and reused by every
entry that directly descends from it.

`ROOT` is copied unchanged from the direct parent journal entry.

All journal entries originating from the same `USER_INPUT` share the same `ROOT`.

### 4.3 Multiple User Inputs

One journal file MAY contain multiple `USER_INPUT` roots.

Each `USER_INPUT` starts an independent journal tree.

---

## 5. Task Tree Fields

Task hierarchy is represented only by:

```text
TASK_ID
PARENT_TASK_ID
ROOT_USER_INPUT_ID
```

These fields describe task structure.

They MUST NOT be used to represent:

- journal event order;
- review order;
- execution order;
- commit order;
- workflow dependencies.

---

## 6. Root Task

Every `USER_INPUT` MUST establish a root task.

The root task fields are:

```text
TASK_ID: <new unique task ID>
PARENT_TASK_ID: --
ROOT_USER_INPUT_ID: <same TASK_ID>
```

Required root invariant:

```text
PARENT_TASK_ID == --
ROOT_USER_INPUT_ID == TASK_ID
```

---

## 7. Child Task

When a task is created from an existing task:

1. generate a new unique `TASK_ID`;
2. set `PARENT_TASK_ID` to the direct parent’s `TASK_ID`;
3. copy `ROOT_USER_INPUT_ID` from the parent unchanged.

The child MUST NOT copy the parent’s `PARENT_TASK_ID`.

It stores the parent’s own `TASK_ID`.

---

## 8. Task-Related Journal Entries

Every journal entry that describes work on a task MUST contain:

```text
TASK_ID
PARENT_TASK_ID
ROOT_USER_INPUT_ID
```

All entries referring to the same logical task MUST use identical values for these fields.

---

## 9. Required Fields by Entry Type

| TYPE | TASK_ID | PARENT_TASK_ID | ROOT_USER_INPUT_ID |
|---|---:|---:|---:|
| `USER_INPUT` | required | required (`--`) | required |
| `PROJECT_INIT` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `SPEC_SPEC` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `SPEC_REVIEW` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `DECOMPOSE` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `TASK_REVIEW` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `AGENT_DECISION` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `RED` | required | required | required |
| `RED_REVIEW` | required | required | required |
| `GREEN` | required | required | required |
| `GREEN_REVIEW` | required | required | required |
| `TASKS_COMPLETE` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `REGRESSION` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `REGRESSION_REVIEW` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `FINAL_REVIEW` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `BROKER_TASK_REVIEW` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `ESCALATION` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |
| `DONE` | optional | required when `TASK_ID` exists | required when `TASK_ID` exists |

Rule:

```text
If TASK_ID is present, PARENT_TASK_ID and ROOT_USER_INPUT_ID are mandatory.
```

---

## 10. Workflow Transitions

The normal top-level workflow is:

```text
USER_INPUT
→ SPEC_SPEC
→ SPEC_REVIEW
→ DECOMPOSE
→ TASK_REVIEW
→ task branches
→ TASKS_COMPLETE
→ REGRESSION
→ REGRESSION_REVIEW
→ FINAL_REVIEW
→ DONE
```

A task branch normally follows:

```text
RED
→ RED_REVIEW
→ GREEN
→ GREEN_REVIEW
```

A failed review returns to the corresponding work stage:

```text
SPEC_REVIEW FAIL → SPEC_SPEC
TASK_REVIEW FAIL → DECOMPOSE
RED_REVIEW FAIL → RED
GREEN_REVIEW FAIL → GREEN
REGRESSION_REVIEW FAIL → REGRESSION or affected task
FINAL_REVIEW FAIL → affected task or REGRESSION
```

In broker mode, the implementer produces this sequence in the journal
for every broker task. Capture tasks (`USER_INPUT_CAPTURE`) omit
the reviewer verdict step.

```text
work journal entry (e.g. SPEC_SPEC, RED, GREEN, REGRESSION, DONE)
   TYPE = the stage the task represents
   STATUS = COMPLETED

independent reviewer verdict (only when the task requires one)
   TYPE = <review_type>
   STATUS = PASS (or FAIL during rework)
   PARENT = work journal entry

broker.process-gate verification (reviewTask, no journal entry)

BROKER_TASK_REVIEW
   STATUS = PASS                       → implementer calls getNextTask
   STATUS = FAIL                       → implementer fixes the process gaps the
                                          broker listed, re-calls reviewTask
   STATUS = NEEDS_CLARIFICATION        → implementer asks the user
   STATUS = ERROR                      → implementer resolves state
```

`BROKER_TASK_REVIEW` is the broker's process-gate verdict. It is
distinct from the reviewer `*_REVIEW` entries, which record the
independent reviewer MCP's verdict on the artifact. Both chains must
exist and pass for the workflow to advance.

An escalation is recorded when the configured review limit is exceeded:

```text
review entry
→ ESCALATION
```

A cancelled entry or task branch does not continue.

---

## 11. Task Branching

Tasks created from the same parent are siblings.

Example:

```text
T-000001
├── T-000002
├── T-000003
└── T-000004
```

Sibling tasks MUST NOT be connected to each other merely because they are executed sequentially.

Incorrect:

```text
T-000002 → T-000003 → T-000004
```

Correct:

```text
T-000001
├── T-000002
├── T-000003
└── T-000004
```

---

## 12. Task Decomposition

Any task MAY be decomposed into child tasks.

Task depth is not encoded by ID syntax.

It is determined exclusively through `PARENT_TASK_ID`.

---

## 13. DEPENDS

`DEPENDS` represents additional journal-entry dependencies.

Format:

```text
DEPENDS: JID-1, JID-2, JID-3
```

It MAY be used when one workflow event requires several completed branches.

`DEPENDS` does not define task hierarchy.

Task hierarchy remains defined only by:

```text
TASK_ID
PARENT_TASK_ID
ROOT_USER_INPUT_ID
```

---

## 14. Required Journal Invariants

The journal MUST preserve these rules:

1. Every `JID` is unique.
2. Every `USER_INPUT` has `PARENT: --`.
3. Every `USER_INPUT` has `ROOT` equal to its own JID.
4. Every derived journal entry points to an existing direct journal parent.
5. Every `PARENT` JID is copied exactly from an existing journal entry.
6. A `PARENT` JID is never guessed, generated, incremented, decremented, or reconstructed.
7. Every derived journal entry preserves the originating journal `ROOT`.
8. Every `TASK_ID` identifies one logical task.
9. Every root task has `PARENT_TASK_ID: --`.
10. Every root task has `ROOT_USER_INPUT_ID` equal to its own `TASK_ID`.
11. Every child task points to its direct parent through `PARENT_TASK_ID`.
12. Every child task copies `ROOT_USER_INPUT_ID` from its parent.
13. All journal entries for one task use the same task-tree fields.
14. Sibling tasks share a parent; they are not chained by execution order.
15. Journal relationships and task relationships remain independent.

---

## 15. Complete Example

```text
=== J-20260614-100000-001 ===
TYPE: USER_INPUT
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260614-100000-001
TASK_ID: T-000001
PARENT_TASK_ID: --
ROOT_USER_INPUT_ID: T-000001
DETAIL: Implement a Tetris game.

=== J-20260614-100000-002 ===
TYPE: SPEC_SPEC
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-001
ROOT: J-20260614-100000-001
DETAIL: Tetris specification created.

=== J-20260614-100000-003 ===
TYPE: SPEC_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-002
ROOT: J-20260614-100000-001
DETAIL: Specification approved.

=== J-20260614-100000-004 ===
TYPE: DECOMPOSE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-003
ROOT: J-20260614-100000-001
DETAIL: Specification decomposed into Board and Piece tasks.

=== J-20260614-100000-005 ===
TYPE: TASK_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-004
ROOT: J-20260614-100000-001
DETAIL: Task decomposition approved.

=== J-20260614-100000-006 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-000002
PARENT_TASK_ID: T-000001
ROOT_USER_INPUT_ID: T-000001
DETAIL: Board tests fail because the board is not implemented.

=== J-20260614-100000-007 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-000003
PARENT_TASK_ID: T-000001
ROOT_USER_INPUT_ID: T-000001
DETAIL: Piece tests fail because tetrominoes are not implemented.
```

Entries `006` and `007` are sibling journal branches and sibling tasks.

Both tasks originate from the same user input task:

```text
ROOT_USER_INPUT_ID: T-000001
```
