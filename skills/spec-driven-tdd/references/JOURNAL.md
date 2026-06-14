# JOURNAL.md — SDD Workflow Journal Specification

This document defines the format, rules, and validation requirements for
`JOURNAL_SDD_TDD_SKILL.log` — the audit trail produced by every SDD pipeline run.

---

## 1. File Location

The journal file MUST be named `JOURNAL_SDD_TDD_SKILL.log` and placed at the
project root (same directory as the SDD pipeline entry point).

---

## 2. Entry Format

Each journal entry has the following structure:

```
=== {JID} ===
TYPE: {TYPE}
SPEC: {SPEC_ID}
STATUS: {STATUS}
PARENT: {PARENT_JID | --}
ROOT: {ROOT_JID}
DEPENDS: {DEPENDS_JID}           (optional)
TASK: {TASK_ID}                  (required for task-level entries)
PARENT_TASK_ID: {PARENT_TASK_ID}    (required for subtask entries)
ROOT_USER_INPUT_ID: {ROOT_USER_INPUT_ID}  (required when TASK is present)
DETAIL: {free-form description}
```

Blank lines separate entries. Fields MUST appear in the order shown above.
Optional fields (DEPENDS, TASK, PARENT_TASK_ID, ROOT_USER_INPUT_ID) are omitted when not applicable.

### 2.1 JID — Journal Entry ID

Format: `J-YYYYMMDD-HHMMSS-NNN`

- `YYYYMMDD` — date of entry creation
- `HHMMSS` — time of entry creation (24h UTC)
- `NNN` — zero-padded 3-digit sequence number for uniqueness within the same second

Example: `J-20260614-204500-001`

### 2.2 TYPE — Entry type

| TYPE | When created |
|------|-------------|
| `USER_INPUT` | Recording incoming feature request |
| `PROJECT_INIT` | Project creation |
| `SPEC_SPEC` | Initial spec draft creation |
| `SPEC_REVIEW` | Spec review result |
| `DECOMPOSE` | Spec decomposed into tasks (or task into subtasks) |
| `TASK_REVIEW` | Task decomposition review |
| `AGENT_DECISION` | Agent selects which task to work on |
| `RED` | Writing + running test (failure expected) |
| `RED_REVIEW` | RED result review |
| `GREEN` | Writing minimal implementation |
| `GREEN_REVIEW` | GREEN review |
| `TASKS_COMPLETE` | Barrier: all task branches finished, ready for regression |
| `REGRESSION` | Regression test run |
| `REGRESSION_REVIEW` | Regression review |
| `FINAL_REVIEW` | Final implementation review |
| `ESCALATION` | User escalation (review limit exceeded) |
| `DONE` | Pipeline completion |

### 2.3 STATUS — Entry status

| STATUS | Meaning | Valid on |
|--------|---------|----------|
| `COMPLETED` | Work step finished successfully | USER_INPUT, SPEC_SPEC, DECOMPOSE, RED, GREEN, TASKS_COMPLETE, REGRESSION, DONE |
| `PASS` | Review passed | SPEC_REVIEW, TASK_REVIEW, RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, FINAL_REVIEW |
| `FAIL` | Review failed | SPEC_REVIEW, TASK_REVIEW, RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, FINAL_REVIEW |
| `NEEDS_CLARIFICATION` | Review needs more info | SPEC_REVIEW, TASK_REVIEW, RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, FINAL_REVIEW |
| `CANCELLED` | Step was cancelled | Any TYPE |
| `FIXED` | Used in fix commits after a failed review | RED, GREEN |
| `ESCALATED` | Escalated to user after repeated FAIL | SPEC_REVIEW, TASK_REVIEW, RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, FINAL_REVIEW |

**Pipeline continuation rules:**
- After `FAIL` or `NEEDS_CLARIFICATION` on a review entry, the pipeline MUST NOT
  proceed to the next stage. Only `FIXED` (on RED/GREEN) or a new review with `PASS`
  unblocks the pipeline.
- `DONE` is only valid with STATUS=COMPLETED.
- `CANCELLED` on any entry terminates its branch. A cancelled task branch is
  excluded from TASKS_COMPLETE aggregation.

### 2.4 SPEC — Spec identifier

Each entry references a spec ID. Spec IDs follow the format:

```
S-[A-Z]{2,6}-\d{2}(\.\d{2})*
```

Examples: `S-SDT-01`, `S-TETRIS-01`, `S-TETRIS-01.01`

### 2.5 PARENT — Parent journal entry

Every entry except `USER_INPUT` MUST have a PARENT field pointing to the JID of
the entry that triggered this one.

- `USER_INPUT` has `PARENT: --` (sentinel meaning "no parent")
- All other entries have `PARENT: <JID>` pointing to an existing entry
- The PARENT chain from any entry MUST terminate at a `USER_INPUT` with `PARENT: --`

### 2.6 ROOT — Root journal entry

ROOT is **mandatory** for EVERY entry. It identifies the originating USER_INPUT
for this entry's spec tree.

- For `USER_INPUT`: `ROOT: <own JID>`
- For all derived entries: `ROOT` MUST match the USER_INPUT reached by following
  the PARENT chain from this entry

### 2.7 TASK — Task identifier (optional)

Required for entries of type: `RED`, `RED_REVIEW`, `GREEN`, `GREEN_REVIEW`.
Optional for entries of type: `DECOMPOSE`, `TASK_REVIEW` (required only when
decomposing or reviewing a specific task's subtasks; omitted for top-level
spec decomposition or task-set review).

**Task ID grammar (regex):**

```
^T-(S-[A-Z]{2,6}-\d{2}(?:\.\d{2})*)-\d{3}(?:\.\d{3})*$
```

Group 1 = SPEC_ID (e.g., `S-TETRIS-01`, `S-TETRIS-01.01`)
Group 2+ = task number + optional subtask suffix (e.g., `001`, `001.002`, `001.002.003`)

**Parsing rules (unambiguous):**

1. The full TASK string MUST match the regex
   `^T-(S-[A-Z]{2,6}-\d{2}(?:\.\d{2})*)-\d{3}(?:\.\d{3})*$`.
2. The SPEC_ID is everything between `T-` and the LAST `-NNN...` segment.
3. The task number is the segment AFTER the last `-`. If it contains dots
   (e.g., `001.002`), each dot-separated part is a subtask level:
   - `001` = task number
   - `001.002` = task 001, subtask 002
   - `001.002.003` = task 001, subtask 002, sub-subtask 003
4. Any dot INSIDE the SPEC_ID (before the task number) is part of the
   sub-spec reference and does NOT indicate a subtask.
5. Subtask depth is arbitrary: `001.002.003.004` is valid.

Examples:
| Value | SPEC_ID | Task | Is subtask? |
|-------|---------|------|-------------|
| `T-S-TETRIS-01-001` | `S-TETRIS-01` | `001` | No (top-level task) |
| `T-S-TETRIS-01-001.002` | `S-TETRIS-01` | `001.002` | Yes (subtask of 001) |
| `T-S-TETRIS-01.01-001` | `S-TETRIS-01.01` | `001` | No (sub-spec, not subtask) |
| `T-S-TETRIS-01.01-001.002.003` | `S-TETRIS-01.01` | `001.002.003` | Yes (sub-subtask) |

### 2.8 PARENT_TASK_ID — Parent task (optional)

Required for subtask entries. Points to the TASK ID of the parent task.

Example: If task `T-S-TETRIS-01-001` is decomposed into subtasks:
```
TASK: T-S-TETRIS-01-001.001
PARENT_TASK_ID: T-S-TETRIS-01-001
```

**PARENT_TASK_ID validation rules (see also §4.7):**
1. PARENT_TASK_ID MUST reference a TASK ID that exists on another entry in the journal
2. A task MUST NOT reference itself as PARENT_TASK_ID
3. The task-parent graph MUST NOT contain cycles
4. Parent task and child task MUST belong to the same ROOT
5. All entries with the same TASK value MUST have the same PARENT_TASK_ID value
6. Within one ROOT, a TASK ID identifies exactly one logical task and
   MUST always have the same SPEC and PARENT_TASK_ID across all entries.
   Multiple journal entries MAY reference the same TASK ID.

### 2.9 ROOT_USER_INPUT_ID — Root task identifier (required when TASK present)

The TASK_ID of the root task representing the originating user input.

**Rules:**
- For root tasks (tasks whose PARENT_TASK_ID is `--`):
  `ROOT_USER_INPUT_ID` MUST equal the entry's own `TASK`.
- For child tasks: `ROOT_USER_INPUT_ID` MUST match the root task's `TASK`,
  inherited from the parent task.
- All entries within the same task tree MUST have the same `ROOT_USER_INPUT_ID`.
- `ROOT_USER_INPUT_ID` is required on any entry that has a `TASK` field.
- The root task's `TASK` is typically created on the `USER_INPUT` entry
  (which carries an optional `TASK` field establishing the root task ID).

**Invariant:**
```
root_task.TASK == root_entry.ROOT_USER_INPUT_ID
root_task.PARENT_TASK_ID == "--"
root_task.ROOT_USER_INPUT_ID == root_task.TASK
```

### 2.10 DEPENDS — Dependency barrier (optional)

Used to express convergence when a single PARENT is insufficient.

- `DEPENDS` MAY list one or more JIDs (comma-separated) that the current entry
  depends on in addition to its PARENT.
- The entry is only reachable when ALL entries in DEPENDS exist.

Primary use case: `TASKS_COMPLETE` and `REGRESSION` entries that depend on
the completion of all task branches.

Example:
```
=== J-20260614-101500-001 ===
TYPE: TASKS_COMPLETE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005     ← TASK_REVIEW
ROOT: J-20260614-100000-001
DEPENDS: J-20260614-100000-010, J-20260614-100000-020, J-20260614-100000-030
                                  ← last entries of each task branch
DETAIL: All 3 tasks completed
```

### 2.10 DETAIL — Free-form description

Human-readable note about what happened in this step. Should include key
decisions, test output summaries, and reviewer verdicts.

---

## 3. Mandatory Fields per Entry Type

| TYPE | SPEC | STATUS | PARENT | ROOT | TASK | PARENT_TASK_ID | ROOT_USER_INPUT_ID | DEPENDS |
|------|------|--------|--------|------|------|-------------|-------------------|---------|
| USER_INPUT | required | required | `--` | self JID | optional* | — | optional* | — |
| SPEC_SPEC | required | required | required | required | — | — | — | — |
| SPEC_REVIEW | required | required | required | required | — | — | — | — |
| DECOMPOSE | required | required | required | required | optional | — | — | — |
| TASK_REVIEW | required | required | required | required | optional | — | — | — |
| AGENT_DECISION | required | required | required | required | optional | — | — | — |
| RED | required | required | required | required | required | optional | required | — |
| RED_REVIEW | required | required | required | required | required | optional | required | — |
| GREEN | required | required | required | required | required | optional | required | — |
| GREEN_REVIEW | required | required | required | required | required | optional | required | — |
| TASKS_COMPLETE | required | required | required | required | — | — | — | required |
| REGRESSION | required | required | required | required | — | — | — | optional |
| REGRESSION_REVIEW | required | required | required | required | — | — | — | — |
| FINAL_REVIEW | required | required | required | required | — | — | — | — |
| ESCALATION | required | required | required | required | optional | — | — | — |
| DONE | required | required | required | required | — | — | — | — |

Notes:
- `TASK` on DECOMPOSE is required when decomposing an existing task into
  subtasks (identifies the parent task being decomposed). Omitted for
  top-level spec decomposition.
- `TASK` on TASK_REVIEW is required when reviewing decomposition of a
  specific task. Omitted for top-level task set review.
- `PARENT_TASK_ID` on any entry with a subtask TASK (containing a dot after
  the task number) is required, regardless of TYPE. This ensures all entries
  for the same subtask have consistent PARENT_TASK_ID.
- `ROOT_USER_INPUT_ID` on RED/RED_REVIEW/GREEN/GREEN_REVIEW is required.
  On USER_INPUT it is required only when TASK is present (establishing the
  root task ID). Omitted for entries without TASK.
- `DEPENDS` on TASKS_COMPLETE lists the final JID of each task branch.
- `DEPENDS` on REGRESSION MAY list the TASKS_COMPLETE entry and/or individual
  task-final JIDs when there is no explicit TASKS_COMPLETE barrier.

---

## 4. Validation Rules

### 4.0 Universal Requirements

- Every entry MUST have a `TYPE` from the valid enum (section 2.2)
- Every entry MUST have a `SPEC` field with a non-empty value
- Every entry MUST have a `ROOT` field
- Every entry MUST have a `STATUS` field
- `STATUS` MUST be valid for the entry's `TYPE` (see §2.3)
- All JIDs in a journal MUST be unique

### 4.1 PARENT Chain

1. `USER_INPUT` MUST have `PARENT: --`
2. Every non-`USER_INPUT` entry MUST have a PARENT field
3. PARENT values MUST either be `--` or reference a JID that exists in the journal
4. No entry MAY have PARENT equal to its own JID (self-reference)
5. The PARENT relation MUST NOT contain cycles
6. From every entry, repeatedly following PARENT MUST eventually reach a
   `USER_INPUT` entry with `PARENT: --`

### 4.2 ROOT Consistency

1. ROOT is mandatory for every entry
2. For `USER_INPUT`: ROOT MUST equal the entry's own JID
3. For all other entries: ROOT MUST match the JID of the USER_INPUT reached by
   following the entry's PARENT chain

### 4.3 Allowed Transitions (parent TYPE/STATUS → child TYPE)

The following transitions are the ONLY valid parent/child relationships.
Any transition not listed here is a validation error.

| Parent TYPE | Parent STATUS | Allowed child TYPE(s) |
|-------------|---------------|----------------------|
| -- | -- | PROJECT_INIT |
| -- | -- | USER_INPUT |
| PROJECT_INIT | COMPLETED | SPEC_SPEC |
| USER_INPUT | COMPLETED | SPEC_SPEC |
| USER_INPUT | CANCELLED | (terminal) |
| SPEC_SPEC | COMPLETED | SPEC_REVIEW |
| SPEC_REVIEW | PASS | DECOMPOSE |
| SPEC_REVIEW | FAIL, NEEDS_CLARIFICATION | SPEC_SPEC (re-fix) |
| DECOMPOSE | COMPLETED | TASK_REVIEW |
| TASK_REVIEW | PASS | RED, TASKS_COMPLETE |
| TASK_REVIEW | FAIL, NEEDS_CLARIFICATION | DECOMPOSE (re-decompose) |
| AGENT_DECISION | COMPLETED | DECOMPOSE, RED |
| RED | COMPLETED | RED_REVIEW |
| RED | FIXED | RED_REVIEW |
| RED_REVIEW | PASS | GREEN |
| RED_REVIEW | FAIL, NEEDS_CLARIFICATION | RED (re-fix) |
| GREEN | COMPLETED | GREEN_REVIEW |
| GREEN | FIXED | GREEN_REVIEW |
|| GREEN_REVIEW | PASS | REGRESSION |
| GREEN_REVIEW | FAIL, NEEDS_CLARIFICATION | GREEN (re-fix) |
| TASKS_COMPLETE | COMPLETED | REGRESSION |
| REGRESSION | COMPLETED | REGRESSION_REVIEW |
| REGRESSION_REVIEW | PASS | FINAL_REVIEW |
| REGRESSION_REVIEW | FAIL | GREEN (re-fix) or REGRESSION (re-run) |
| FINAL_REVIEW | PASS | DONE |
| FINAL_REVIEW | FAIL | GREEN (re-fix) or REGRESSION (re-run) |
| SPEC_REVIEW | ESCALATED | ESCALATION |
| TASK_REVIEW | ESCALATED | ESCALATION |
| RED_REVIEW | ESCALATED | ESCALATION |
| GREEN_REVIEW | ESCALATED | ESCALATION |
| REGRESSION_REVIEW | ESCALATED | ESCALATION |
| FINAL_REVIEW | ESCALATED | ESCALATION |
| ESCALATION | COMPLETED | SPEC_SPEC, DECOMPOSE, RED, GREEN |
| ESCALATION | CANCELLED | (terminal) |
| any non-CANCELLED entry | (any active status) | child per transition rules |
| any | CANCELLED | (terminal — no children) |

**Transition constraints:**
- After `FAIL` on a review, the pipeline MUST return to the work step
  (SPEC_SPEC, DECOMPOSE, RED, GREEN, REGRESSION).
- After `PASS` on the final review of a branch, the next transition MUST be
  to TASKS_COMPLETE (if there are sibling branches) or REGRESSION (last/single branch).
- `CANCELLED` entries MUST NOT have children.

### 4.4 Branching (Divergence)

The journal forms a **forest of trees**, not a single linear chain.

```ascii
USER_INPUT                         (root, PARENT: --, ROOT=self)
  └─ SPEC_SPEC → SPEC_REVIEW(PASS)
       └─ DECOMPOSE → TASK_REVIEW(PASS)
            ├─ T1: RED → RED_REVIEW(PASS) → GREEN → GREEN_REVIEW(PASS)
            ├─ T2: RED → RED_REVIEW(PASS) → GREEN → GREEN_REVIEW(PASS)
            └─ T3: RED → RED_REVIEW(PASS) → GREEN → GREEN_REVIEW(PASS)
                 │
                 ▼
            TASKS_COMPLETE ←──── depends on T1, T2, T3 ────
                 │
                 ▼
            REGRESSION → REGRESSION_REVIEW(PASS) → FINAL_REVIEW(PASS) → DONE
```

Branching (a node having multiple children) is PERMITTED at:
- `USER_INPUT` — may have multiple spec pipelines
- `DECOMPOSE` — may have multiple child entries leading to TASK_REVIEW
- `TASK_REVIEW` — may have multiple RED entries (one per task)
- `DECOMPOSE` within a task — may have multiple child tasks (subtasks)

Linearity (max one child per node) is REQUIRED within each pipeline segment
that does not have branching listed above. Specifically: once inside a task
lifecycle (RED → RED_REVIEW → GREEN → GREEN_REVIEW), each entry has at most
one child.

**Key branching rules:**

1. **Multiple USER_INPUTs** are allowed (one per feature request). Each is a
   separate tree root with `PARENT: --` and `ROOT` = its own JID.
2. **Tasks are siblings, not a chain.** RED(T1) and RED(T2) both have
   `PARENT=JID_of_TASK_REVIEW`. RED(T2) does NOT have
   `PARENT=JID_of_REGRESSION(T1)`. Chaining tasks creates false causal
   relationships and violates the definition of PARENT.
3. **ROOT must match the reached USER_INPUT** — for any entry, tracing PARENT
   backwards must reach a USER_INPUT whose JID equals the entry's ROOT field.

### 4.5 Convergence (Join/Barrier)

After task branches diverge at TASK_REVIEW, they MUST converge to a shared
pipeline before DONE.

```ascii
TASK_REVIEW
  ├─ T1: ... → GREEN_REVIEW(PASS)
  ├─ T2: ... → GREEN_REVIEW(PASS)
  └─ T3: ... → GREEN_REVIEW(PASS)
       │
       ▼
  TASKS_COMPLETE                     ← barrier: depends on all branches
       │
       ▼
  REGRESSION → REGRESSION_REVIEW → FINAL_REVIEW → DONE
```

**Convergence rules:**

1. A single USER_INPUT MAY have multiple spec pipelines (multiple
   SPEC_SPEC children). Each pipeline is independent and MUST have
   its OWN convergence and completion.
2. When a pipeline has multiple task branches, the pipeline MUST NOT proceed
   directly from a single GREEN_REVIEW(PASS) to REGRESSION.
3. Instead, a `TASKS_COMPLETE` entry MUST be created with:
   - `PARENT` pointing to the common ancestor (TASK_REVIEW)
   - `DEPENDS` listing the JID of the LAST entry in EACH task branch
     (typically GREEN_REVIEW(PASS) for each task)
4. TASKS_COMPLETE MUST NOT list branches from a DIFFERENT spec pipeline
   in its DEPENDS, even within the same ROOT.
5. After TASKS_COMPLETE, the pipeline continues linearly:
   REGRESSION → REGRESSION_REVIEW → FINAL_REVIEW → DONE
6. A single-task pipeline (only one branch from TASK_REVIEW) MAY omit
   TASKS_COMPLETE and go directly to REGRESSION.
7. If any task branch has STATUS=CANCELLED, it is excluded from
   TASKS_COMPLETE DEPENDS.

### 4.6 TASK Fields

1. Entries of type `RED`, `RED_REVIEW`, `GREEN`, `GREEN_REVIEW`
   MUST have a TASK field.
   Entries of type `DECOMPOSE`, `TASK_REVIEW` MUST have a TASK field
   if they decompose or review a specific task's subtasks; they MUST NOT
   have a TASK field for top-level spec decomposition or task-set review.
   `USER_INPUT` MAY have a TASK field to establish the root task ID.
2. TASK values MUST match the grammar in §2.7.
3. If a TASK value is a subtask-id (contains a dot), it MUST have a
   `PARENT_TASK_ID` field.
4. All entries with the same TASK value MUST have the same PARENT_TASK_ID value
   (or all lack PARENT_TASK_ID for top-level tasks).
5. All entries with the same TASK value MUST have the same ROOT_USER_INPUT_ID
   value.
6. PARENT_TASK_ID and ROOT_USER_INPUT_ID on any entry with a subtask TASK
   are required, regardless of TYPE.

### 4.7 Task Tree Validation

The task tree is extracted from journal entries and validated independently
of journal event ordering. The tree is defined solely through three fields:
`TASK`, `PARENT_TASK_ID`, `ROOT_USER_INPUT_ID`.

**Extraction:** Collect all distinct TASK values from journal entries.
Each distinct TASK forms one task tree record. `PARENT_TASK_ID` and
`ROOT_USER_INPUT_ID` for that record are taken from any journal entry
bearing that TASK (all must agree — enforced by §4.6 rules 4–5).

**Validation rules (per task tree record):**

1. **Every TASK is unique** (across distinct task records).
   Multiple journal entries may share the same TASK (§2.8 rule 6),
   but they represent the same logical task.
2. **Root tasks** (tasks with `PARENT_TASK_ID: --`) MUST have
   `ROOT_USER_INPUT_ID` equal to their own `TASK`.
3. **Root invariant:** `root.PARENT_TASK_ID == "--"` and
   `root.ROOT_USER_INPUT_ID == root.TASK`.
4. **Every non-root task** MUST reference an existing parent task via
   `PARENT_TASK_ID`.
5. **ROOT_USER_INPUT_ID consistency:** Every child MUST have the same
   `ROOT_USER_INPUT_ID` as its parent.
6. **No self-reference:** No task MAY reference itself as `PARENT_TASK_ID`.
7. **No cycles:** The parent graph (`PARENT_TASK_ID` relations) MUST NOT
   contain cycles.
8. **Root reachability:** Following `PARENT_TASK_ID` from any task MUST
   eventually reach a root task (`PARENT_TASK_ID: "--"`).
9. **ROOT_USER_INPUT_ID invariant:** The reached root's `TASK` MUST equal
   the task's `ROOT_USER_INPUT_ID`.
10. **ROOT_USER_INPUT_ID existence:** Every `ROOT_USER_INPUT_ID` MUST
    reference an existing root task in the tree.

### 4.8 Per-Tree Completion Validation

The journal validation MUST be performed per ROOT, not globally.

1. Group all entries by ROOT.
2. For each ROOT group:
   a. The group MUST contain at least one `DONE` entry to be considered
      complete.
   b. A ROOT MAY be terminated without DONE via a root-level cancellation:
      an entry with TYPE=USER_INPUT and STATUS=CANCELLED, or a dedicated
      entry TYPE=ESCALATION STATUS=CANCELLED whose PARENT chain reaches
      the ROOT's USER_INPUT.
   c. A single CANCELLED entry on a task branch does NOT complete the ROOT.
      Other non-cancelled branches in the same ROOT must still reach DONE.
   d. If the group has a `DONE` entry: the DONE MUST belong to that ROOT
      (DONE.ROOT == ROOT).
   e. If the group has a `DONE` entry: every non-CANCELLED branch in the
      group MUST have reached a terminal state (completed its lifecycle
      through GREEN_REVIEW).
   f. The DONE entry's PARENT chain MUST terminate at a USER_INPUT whose
      JID matches the ROOT.
3. A ROOT group with BOTH `DONE` and `CANCELLED` is allowed: the CANCELLED
   branches are excluded from completion checks, but all non-CANCELLED
   branches must still be complete.

### 4.9 DONE Validation (per DONE entry)

Before writing a `DONE` entry, the agent MUST:

1. Verify all rules 4.0–4.8 pass for the DONE's ROOT tree
2. Verify the PARENT chain from DONE reaches the correct USER_INPUT
3. Verify all sibling task branches in the same ROOT are complete
   (have PASS on GREEN_REVIEW or are CANCELLED)
4. Verify DEPENDS on TASKS_COMPLETE (if present) covers all task branches
5. If any check fails, DO NOT write DONE — fix the chain first

---

## 5. Examples

### 5.1 Correct Journal (multi-task pipeline with convergence)

```
=== J-20260614-100000-001 ===
TYPE: USER_INPUT
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260614-100000-001
DETAIL: Implement Tetris game

=== J-20260614-100000-002 ===
TYPE: SPEC_SPEC
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-001
ROOT: J-20260614-100000-001
DETAIL: Tetris spec created

=== J-20260614-100000-003 ===
TYPE: SPEC_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-002
ROOT: J-20260614-100000-001
DETAIL: Spec approved

=== J-20260614-100000-004 ===
TYPE: DECOMPOSE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-003
ROOT: J-20260614-100000-001
DETAIL: 3 tasks identified

=== J-20260614-100000-005 ===
TYPE: TASK_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-004
ROOT: J-20260614-100000-001
DETAIL: All 3 tasks approved — Board, Pieces, Game

=== J-20260614-100000-006 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 RED — board tests fail

=== J-20260614-100000-007 ===
TYPE: RED_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-006
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 RED approved

=== J-20260614-100000-008 ===
TYPE: GREEN
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-007
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 GREEN — board impl done

=== J-20260614-100000-009 ===
TYPE: GREEN_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-008
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 GREEN approved

=== J-20260614-100000-010 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 RED — piece tests fail

=== J-20260614-100000-011 ===
TYPE: RED_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-010
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 RED approved

=== J-20260614-100000-012 ===
TYPE: GREEN
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-011
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 GREEN — piece impl done

=== J-20260614-100000-013 ===
TYPE: GREEN_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-012
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 GREEN approved

=== J-20260614-100000-014 ===
TYPE: TASKS_COMPLETE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
DEPENDS: J-20260614-100000-009, J-20260614-100000-013
DETAIL: All 2 tasks completed

=== J-20260614-100000-015 ===
TYPE: REGRESSION
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-014
ROOT: J-20260614-100000-001
DETAIL: All tests green

=== J-20260614-100000-016 ===
TYPE: REGRESSION_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-015
ROOT: J-20260614-100000-001
DETAIL: Regression passed

=== J-20260614-100000-017 ===
TYPE: FINAL_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-016
ROOT: J-20260614-100000-001
DETAIL: Final review passed

=== J-20260614-100000-018 ===
TYPE: DONE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-017
ROOT: J-20260614-100000-001
DETAIL: Tetris implementation complete
```

Key structural features:
- Entries 006 and 010 are siblings (both PARENT=005). Valid branching at TASK_REVIEW.
- TASKS_COMPLETE (014) depends on the last entry of each task branch via DEPENDS.
- After TASKS_COMPLETE the pipeline is linear: REGRESSION → ... → DONE.
- All entries share ROOT=J-20260614-100000-001, tracing back to USER_INPUT.

### 5.2 Incorrect Journal (missing convergence — WRONG)

```journal
=== J-20260614-100000-001 ===
TYPE: USER_INPUT
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260614-100000-001
DETAIL: Implement Tetris game

=== J-20260614-100000-002 ===
TYPE: SPEC_SPEC
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-001
ROOT: J-20260614-100000-001
DETAIL: Tetris spec created

=== J-20260614-100000-003 ===
TYPE: SPEC_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-002
ROOT: J-20260614-100000-001
DETAIL: Spec approved

=== J-20260614-100000-004 ===
TYPE: DECOMPOSE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-003
ROOT: J-20260614-100000-001
DETAIL: 2 tasks identified

=== J-20260614-100000-005 ===
TYPE: TASK_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-004
ROOT: J-20260614-100000-001
DETAIL: Both tasks approved

=== J-20260614-100000-006 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 RED

=== J-20260614-100000-007 ===
TYPE: RED_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-006
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 RED approved

=== J-20260614-100000-008 ===
TYPE: GREEN
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-007
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 GREEN

=== J-20260614-100000-009 ===
TYPE: GREEN_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-008
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 GREEN approved

=== J-20260614-100000-010 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 RED

=== J-20260614-100000-011 ===
TYPE: REGRESSION
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-009
ROOT: J-20260614-100000-001
DETAIL: Regression ← WRONG: went directly from T1 GREEN_REVIEW
                         to REGRESSION without TASKS_COMPLETE barrier.
                         T2 is incomplete.
```

Error: T1 GREEN_REVIEW(PASS) jumps directly to REGRESSION without
TASKS_COMPLETE. Task T2 exists (has RED entry) but is not included in
any barrier. The pipeline claims completion without waiting for all branches.
PARENT chains, transitions, and field formats are all valid — only
convergence is missing.

### 5.3 Incorrect Journal (cycle in PARENT — WRONG)

```
=== J-20260614-100000-020 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-021
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: A

=== J-20260614-100000-021 ===
TYPE: RED_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-020
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: B
```

Error: J-020 → J-021 and J-021 → J-020 form a cycle. Neither chain
reaches USER_INPUT. Types, transitions, SPEC, and ROOT are all valid —
only the PARENT cycle is wrong.

### 5.4 Incorrect Journal (orphan PARENT — WRONG)

```
=== J-20260614-100000-030 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-999
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: Orphan
```

Error: PARENT=J-20260614-100000-999 does not exist in the journal.
All other fields (JID, SPEC, ROOT, TASK) are valid.

### 5.5 Incorrect Journal (illegal transition — WRONG)

```
=== J-20260614-100000-040 ===
TYPE: SPEC_REVIEW
SPEC: S-TETRIS-01
STATUS: FAIL
PARENT: J-20260614-100000-002
ROOT: J-20260614-100000-001
DETAIL: Spec review failed

=== J-20260614-100000-041 ===
TYPE: DECOMPOSE
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-040
ROOT: J-20260614-100000-001
DETAIL: Decomposed after fail  ← WRONG: SPEC_REVIEW(FAIL) → DECOMPOSE
                                   is not a valid transition.
                                   After FAIL, must return to SPEC_SPEC.
```

---

## 6. Validation Algorithm (for automated checks)

```
function validate_journal(journal_text):
    entries = parse(journal_text)
    errors = []

    # --- Group by ROOT ---
    by_root = group_by(entries, "root")

    # --- Phase 1: structural validation per entry ---
    for entry in entries:
        if missing_any(entry, ["type", "spec", "status", "root"]):
            errors.append("Missing required field")

        if entry.type not in VALID_TYPES:
            errors.append(f"Invalid TYPE: {entry.type}")

        if entry.status not in VALID_STATUSES[entry.type]:
            errors.append(f"Invalid STATUS {entry.status} for TYPE {entry.type}")

        # JID format
        if not matches(entry.jid, r"^J-\d{8}-\d{6}-\d{3}$"):
            errors.append(f"Invalid JID format: {entry.jid}")

        # ROOT for USER_INPUT
        if entry.type == USER_INPUT:
            if entry.parent != "--": errors.append("USER_INPUT must have PARENT=--")
            if entry.root != entry.jid: errors.append("USER_INPUT ROOT must be self")
        else:
            if missing(entry, "parent"): errors.append("Non-USER_INPUT must have PARENT")
            if entry.parent == entry.jid: errors.append("Self-reference in PARENT")
            if entry.parent not in entries and entry.parent != "--":
                errors.append(f"Orphan PARENT: {entry.parent}")

        # TASK field for required types
        if entry.type in TASK_REQUIRED_TYPES:
            if missing(entry, "task"): errors.append(f"TYPE {entry.type} requires TASK")
            elif not valid_task_id(entry.task): errors.append(f"Invalid TASK: {entry.task}")

        # PARENT_TASK_ID validation
        if entry.task_parent:
            if entry.task_parent == entry.task:
                errors.append("PARENT_TASK_ID must not be self")
            if entry.task_parent not in all_task_ids(entries):
                errors.append(f"PARENT_TASK_ID references non-existent task: {entry.task_parent}")

        # SPEC consistency: a TASK ID must always have same SPEC
        if entry.task and entry.spec:
            for other in entries:
                if other.jid != entry.jid and other.task == entry.task:
                    if other.spec != entry.spec:
                        errors.append(
                            f"TASK {entry.task} has conflicting SPEC: "
                            f"{entry.jid}.spec={entry.spec} vs {other.jid}.spec={other.spec}"
                        )

        # PARENT_TASK_ID consistency: all entries with same TASK must have
        # same PARENT_TASK_ID
        if entry.task:
            for other in entries:
                if other.jid != entry.jid and other.task == entry.task:
                    tp_a = entry.task_parent or ""
                    tp_b = other.task_parent or ""
                    if tp_a != tp_b:
                        errors.append(
                            f"TASK {entry.task} has inconsistent PARENT_TASK_ID: "
                            f"{entry.jid}={tp_a} vs {other.jid}={tp_b}"
                        )

        # PARENT_TASK_ID ROOT consistency: parent and child must share ROOT
        if entry.task_parent:
            for other in entries:
                if other.task == entry.task_parent:
                    if other.root != entry.root:
                        errors.append(
                            f"PARENT_TASK_ID {entry.task_parent} ROOT mismatch: "
                            f"parent={other.root}, child={entry.root}"
                        )
                        break

    # --- Phase 2: duplicate JIDs ---
    if duplicate_jids(entries): errors.append("Duplicate JIDs found")

    # --- Phase 3: PARENT cycles ---
    for entry in entries:
        if has_parent_cycle(entry, entries): errors.append(f"Cycle at {entry.jid}")

    # --- Phase 4: PARENT chain termination ---
    for entry in entries:
        reached = follow_parent_chain(entry, entries)
        if reached is None:
            errors.append(f"Broken PARENT chain at {entry.jid}")
        elif reached.type != USER_INPUT or reached.parent != "--":
            errors.append(f"PARENT chain at {entry.jid} does not reach USER_INPUT")
        elif entry.root != reached.jid:
            errors.append(f"ROOT mismatch at {entry.jid}: {entry.root} != {reached.jid}")

    # --- Phase 5: Allowed transitions ---
    for entry in entries:
        if entry.parent != "--" and entry.parent in entries:
            parent = entries[entry.parent]
            if not is_valid_transition(parent.type, parent.status, entry.type):
                errors.append(
                    f"Illegal transition: {parent.type}({parent.status}) → {entry.type}"
                )

    # --- Phase 6: Branching limits ---
    for parent_jid, children in group_by_parent(entries):
        if len(children) > 1:
            parent = entries[parent_jid]
            if parent.type not in BRANCHING_ALLOWED_TYPES:
                errors.append(f"Illegal branching: {parent.type} has {len(children)} children")

    # --- Phase 7: DEPENDS validation ---
    for entry in entries:
        if not entry.depends:
            continue
        depends_list = split(entry.depends, ",")
        # Check uniqueness of DEPENDS values
        stripped_deps = [strip(j) for j in depends_list]
        if len(stripped_deps) != len(set(stripped_deps)):
            errors.append(f"Duplicate JIDs in DEPENDS at {entry.jid}")
        for dep_jid in stripped_deps:
            dep_jid = strip(dep_jid)
            if dep_jid not in entries:
                errors.append(f"DEPENDS references non-existent JID: {dep_jid}")
                continue
            dep = entries[dep_jid]
            if dep.root != entry.root:
                errors.append(
                    f"DEPENDS ROOT mismatch: {entry.jid} depends on "
                    f"{dep_jid} (root={dep.root}) but own root={entry.root}"
                )
            if dep_jid == entry.jid:
                errors.append(f"Self-dependency: {entry.jid} depends on itself")
            if has_depends_cycle(entry, entries):
                errors.append(f"Dependency cycle involving {entry.jid}")

    # TASKS_COMPLETE.DEPENDS must cover all active task branches
    for entry in entries:
        if entry.type != TASKS_COMPLETE:
            continue
        dep_jids = set(split(entry.depends, ","))
        task_jids = find_task_branch_terminals(entries, entry.root)
        active_terminals = {
            j for j in task_jids
            if entries[j].status != "CANCELLED"
        }
        if dep_jids != active_terminals:
            errors.append(
                f"TASKS_COMPLETE {entry.jid} DEPENDS missing or extra terminals: "
                f"expected={active_terminals}, got={dep_jids}"
            )
        # Each dependency must be a terminal entry (GREEN_REVIEW)
        for jid in dep_jids:
            if entries[jid].type not in ("GREEN_REVIEW", "CANCELLED"):
                errors.append(
                    f"TASKS_COMPLETE {entry.jid} DEPENDS on non-terminal {jid}: "
                    f"type={entries[jid].type}"
                )
            if entries[jid].status == "FAIL":
                errors.append(
                    f"TASKS_COMPLETE {entry.jid} DEPENDS on FAILED entry {jid}"
                )

    # --- Phase 8: Convergence check (per pipeline) ---
    # A pipeline is defined as: a SPEC_SPEC child of USER_INPUT and all
    # its descendants. Multiple pipelines may share a USER_INPUT root.
    for root_jid, root_entries in by_root.items():
        # Identify pipelines: each SPEC_SPEC that is a direct child of USER_INPUT
        user_input = next((e for e in root_entries if e.type == "USER_INPUT"), None)
        if not user_input:
            continue
        spec_specs = [
            e for e in root_entries
            if e.type == "SPEC_SPEC" and e.parent == user_input.jid
        ]
        # For each pipeline, collect its descendants
        for spec in spec_specs:
            pipeline_jids = collect_descendants(spec.jid, entries)
            pipeline_entries = [entries[j] for j in pipeline_jids]
            task_branches = count_task_branches(pipeline_entries)
            has_tasks_complete = any(e.type == "TASKS_COMPLETE" for e in pipeline_entries)
            has_done = any(e.type == "DONE" for e in pipeline_entries)
            if task_branches > 1 and has_done and not has_tasks_complete:
                errors.append(
                    f"Pipeline starting at {spec.jid}: multi-task pipeline "
                    f"with DONE but no TASKS_COMPLETE"
                )

    # --- Phase 9: Mandatory regression + final review path (with order check) ---
    for d in [e for e in entries if e.type == "DONE"]:
        # Verify exact order: DONE -> ... -> FINAL_REVIEW(PASS) -> REGRESSION_REVIEW(PASS) -> REGRESSION(COMPLETED)
        chain = parent_chain(d, entries)  # ordered from d up to root
        # Check mandatory presence
        chain_types = [entries[c].type for c in chain]
        if "FINAL_REVIEW" not in chain_types:
            errors.append(f"DONE {d.jid} PARENT chain does not include FINAL_REVIEW")
        if "REGRESSION_REVIEW" not in chain_types:
            errors.append(f"DONE {d.jid} PARENT chain does not include REGRESSION_REVIEW")
        if "REGRESSION" not in chain_types:
            errors.append(f"DONE {d.jid} PARENT chain does not include REGRESSION")
        # Check correct order: FINAL_REVIEW must appear AFTER REGRESSION_REVIEW
        # which must appear AFTER REGRESSION in the parent chain
        fr_pos = next((i for i, t in enumerate(chain_types) if t == "FINAL_REVIEW"), -1)
        rr_pos = next((i for i, t in enumerate(chain_types) if t == "REGRESSION_REVIEW"), -1)
        reg_pos = next((i for i, t in enumerate(chain_types) if t == "REGRESSION"), -1)
        # chain[0] = DONE, chain[-1] = USER_INPUT. Order: DONE -> ... -> REGRESSION -> ... -> USER_INPUT
        # FINAL_REVIEW should be before REGRESSION_REVIEW in the chain (closer to DONE)
        if fr_pos >= 0 and rr_pos >= 0 and fr_pos > rr_pos:
            errors.append(
                f"DONE {d.jid}: FINAL_REVIEW must be closer to DONE than REGRESSION_REVIEW"
            )
        if rr_pos >= 0 and reg_pos >= 0 and rr_pos > reg_pos:
            errors.append(
                f"DONE {d.jid}: REGRESSION_REVIEW must be closer to DONE than REGRESSION"
            )
        # Check statuses: REGRESSION_REVIEW must be PASS, FINAL_REVIEW must be PASS
        for j in chain:
            e = entries[j]
            if e.type == "FINAL_REVIEW" and e.status != "PASS":
                errors.append(f"DONE {d.jid}: FINAL_REVIEW has status {e.status}, expected PASS")
            if e.type == "REGRESSION_REVIEW" and e.status != "PASS":
                errors.append(
                    f"DONE {d.jid}: REGRESSION_REVIEW has status {e.status}, expected PASS"
                )
        # Check that all non-cancelled task branches are complete
        root_entries = entries_for_root(d.root, entries)
        task_branches = find_task_branches(root_entries)
        active_branches = [
            b for b in task_branches
            if not any(e.status == "CANCELLED" for e in b)
        ]
        for branch in active_branches:
            has_green_review_pass = any(
                e.type == "GREEN_REVIEW" and e.status == "PASS"
                for e in branch
            )
            if not has_green_review_pass:
                first = branch[0]
                errors.append(
                    f"DONE {d.jid}: active task branch starting at {first.jid} "
                    f"has no GREEN_REVIEW(PASS)"
                )

    # --- Phase 10: PARENT_TASK_ID cycles ---
    for entry in entries:
        if entry.task_parent:
            visited = set()
            current = entry.task
            while current:
                if current in visited:
                    errors.append(
                        f"PARENT_TASK_ID cycle involving {entry.task}"
                    )
                    break
                visited.add(current)
                # Find the parent task_id from any entry with this TASK
                parent_tasks = {
                    e.task_parent for e in entries
                    if e.task == current and e.task_parent
                }
                if not parent_tasks:
                    break
                current = next(iter(parent_tasks))

    # --- Phase 11: Per-tree completion ---
    for root_jid, root_entries in by_root.items():
        done_entries = [e for e in root_entries if e.type == DONE]
        cancelled_entries = [e for e in root_entries if e.status == "CANCELLED"]
        root_level_cancelled = any(
            e.type in ("USER_INPUT", "ESCALATION") and e.status == "CANCELLED"
            for e in root_entries
        )

        if not done_entries and not root_level_cancelled:
            # Check if ALL task branches are individually CANCELLED
            task_branches = find_task_branches(root_entries)
            all_cancelled = all(
                any(e.status == "CANCELLED" for e in branch)
                for branch in task_branches
            ) if task_branches else False
            if not all_cancelled:
                errors.append(f"ROOT {root_jid}: incomplete pipeline — no DONE")

        for d in done_entries:
            if d.root != root_jid:
                errors.append(
                    f"DONE ROOT mismatch: {d.jid} root={d.root} != {root_jid}"
                )

    return errors
```

---

## 7. References

- SKILL.md — SDD workflow definition (uses this journal format)
- spec-driven-tdd skill — the pipeline that produces this journal
