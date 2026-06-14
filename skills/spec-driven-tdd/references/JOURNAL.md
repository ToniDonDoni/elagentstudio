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
TASK_PARENT: {TASK_PARENT_ID}    (required for subtask entries)
DETAIL: {free-form description}
```

Blank lines separate entries. Fields MUST appear in the order shown above.
Optional fields (DEPENDS, TASK, TASK_PARENT) are omitted when not applicable.

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
| `DECOMPOSE` | Spec decomposed into tasks |
| `TASK_REVIEW` | Task decomposition review |
| `AGENT_DECISION` | Agent selects which task to work on |
| `RED` | Writing + running test (failure expected) |
| `RED_REVIEW` | RED result review |
| `GREEN` | Writing minimal implementation |
| `GREEN_REVIEW` | GREEN review |
| `REGRESSION` | Regression test run |
| `REGRESSION_REVIEW` | Regression review |
| `FINAL_REVIEW` | Final implementation review |
| `ESCALATION` | User escalation (review limit exceeded) |
| `DONE` | Pipeline completion |

### 2.3 STATUS — Entry status

- `COMPLETED` — work step finished (USER_INPUT, SPEC_SPEC, DECOMPOSE, RED, GREEN, DONE, etc.)
- `PASS` — review passed (SPEC_REVIEW, TASK_REVIEW, RED_REVIEW, GREEN_REVIEW, etc.)
- `FAIL` — review failed
- `NEEDS_CLARIFICATION` — review needs more info
- `CANCELLED` — step was cancelled
- `FIXED` — used in fix commits after a failed review

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

Required for task-level entries: `RED`, `RED_REVIEW`, `GREEN`, `GREEN_REVIEW`.

Format: `T-{SPEC_ID}-{NNN}`

Examples: `T-S-TETRIS-01-001`, `T-S-TETRIS-01-002`

### 2.8 TASK_PARENT — Parent task (optional)

Required for subtask entries. Points to the TASK ID of the parent task.

Example: If task `T-S-TETRIS-01-001` is decomposed into subtasks:
```
TASK: T-S-TETRIS-01-001.001
TASK_PARENT: T-S-TETRIS-01-001
```

### 2.9 DETAIL — Free-form description

Human-readable note about what happened in this step. Should include key
decisions, test output summaries, and reviewer verdicts.

---

## 3. Mandatory Fields per Entry Type

| TYPE | SPEC | STATUS | PARENT | ROOT | TASK |
|------|------|--------|--------|------|------|
| USER_INPUT | required | required | `--` | self JID | — |
| SPEC_SPEC | required | required | required | required | — |
| SPEC_REVIEW | required | required | required | required | — |
| DECOMPOSE | required | required | required | required | — |
| TASK_REVIEW | required | required | required | required | — |
| AGENT_DECISION | required | required | required | required | optional |
| RED | required | required | required | required | required |
| RED_REVIEW | required | required | required | required | required |
| GREEN | required | required | required | required | required |
| GREEN_REVIEW | required | required | required | required | required |
| REGRESSION | required | required | required | required | — |
| REGRESSION_REVIEW | required | required | required | required | — |
| FINAL_REVIEW | required | required | required | required | — |
| ESCALATION | required | required | required | required | optional |
| DONE | required | required | required | required | — |

---

## 4. Validation Rules

### 4.0 Universal Requirements

- Every entry MUST have a `TYPE` from the valid enum (section 2.2)
- Every entry MUST have a `SPEC` field with a non-empty value
- Every entry MUST have a `ROOT` field
- Every entry MUST have a `STATUS` field
- All JIDs in a journal MUST be unique
- At minimum, a completed pipeline MUST have at least one `USER_INPUT` and one `DONE`

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

### 4.3 Branching

The journal forms a **forest of trees**, not a single linear chain.

```ascii
USER_INPUT                         (root, PARENT: --, ROOT=self)
  └─ SPEC_SPEC → SPEC_REVIEW
       └─ DECOMPOSE → TASK_REVIEW
            ├─ TASK-001 → RED → RED_REVIEW → GREEN → GREEN_REVIEW → REGRESSION
            ├─ TASK-002 → RED → RED_REVIEW → GREEN → GREEN_REVIEW → REGRESSION
            └─ TASK-003 → ... → REGRESSION → FINAL_REVIEW → DONE
```

Branching (a node having multiple children) is PERMITTED at:
- `USER_INPUT` — may have multiple spec pipelines
- `DECOMPOSE` — may have multiple child entries leading to TASK_REVIEW
- `TASK_REVIEW` — may have multiple RED entries (one per task)
- `DECOMPOSE` within a task — may have multiple child tasks (subtasks)

Linearity (max one child per node) is REQUIRED within each task lifecycle:
```
RED → RED_REVIEW → GREEN → GREEN_REVIEW
```
No entry in this chain MAY have more than one child pointing to it.

**Key branching rules:**

1. **Multiple USER_INPUTs** are allowed (one per feature request). Each is a separate tree root with `PARENT: --` and `ROOT` = its own JID.
2. **Tasks are siblings, not a chain.** RED(T1) and RED(T2) both have `PARENT=JID_of_TASK_REVIEW`. RED(T2) does NOT have `PARENT=JID_of_REGRESSION(T1)`. Chaining tasks creates false causal relationships and violates the definition of PARENT as "the triggering entry."
3. **ROOT must match the reached USER_INPUT** — for any entry, tracing PARENT backwards must reach a USER_INPUT whose JID equals the entry's ROOT field.

### 4.4 TASK Fields

1. Entries of type `RED`, `RED_REVIEW`, `GREEN`, `GREEN_REVIEW` MUST have a TASK field
2. TASK values MUST match the pattern `T-{SPEC_ID}-{NNN}` where `{SPEC_ID}` is
   the id of the parent spec
3. If a TASK value contains a dot suffix (e.g., `T-S-X-01.001`), it is a subtask
   and MUST have a `TASK_PARENT` field pointing to the parent task ID

### 4.5 Task Parent Traceability

From any task or subtask entry:
1. `TASK` field → identifies the task
2. If `TASK_PARENT` present → parent task → recurse until no parent
3. `PARENT` field → follow chain to `USER_INPUT`
4. The reached `USER_INPUT` MUST match `ROOT`

### 4.6 DONE Validation

Before writing a `DONE` entry, the agent MUST:
1. Parse the complete journal
2. Verify all rules 4.0–4.5 pass
3. Verify the PARENT chain from DONE reaches a USER_INPUT
4. If any check fails, DO NOT write DONE — fix the chain first

---

## 5. Examples

### 5.1 Correct Journal (tree structure)

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

=== J-20260614-100000-005 ===
TYPE: TASK_REVIEW
SPEC: S-TETRIS-01
STATUS: PASS
PARENT: J-20260614-100000-004
ROOT: J-20260614-100000-001
DETAIL: 4 tasks approved

=== J-20260614-100000-006 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 RED — board tests fail

=== J-20260614-100000-011 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 RED — piece tests fail
```

Note: entries 006 and 011 are both children of 005 (TASK_REVIEW).
This is valid branching.

### 5.2 Incorrect Journal (linear chain — WRONG)

```
=== J-20260614-100000-006 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-001
DETAIL: T1 RED

=== J-20260614-100000-007 ===
TYPE: RED
SPEC: S-TETRIS-01
STATUS: COMPLETED
PARENT: J-20260614-100000-006     ← WRONG: T2 RED should not be child of T1 RED
ROOT: J-20260614-100000-001
TASK: T-S-TETRIS-01-002
DETAIL: T2 RED
```

### 5.3 Incorrect Journal (cycle)

```
=== J-A-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-B-001
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: A

=== J-B-001 ===
TYPE: GREEN
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-A-001
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: B
```

### 5.4 Incorrect Journal (orphan PARENT)

```
=== J-CHILD-001 ===
TYPE: RED
SPEC: S-TEST
STATUS: COMPLETED
PARENT: J-NONEXISTENT
ROOT: J-UID-001
TASK: T-S-TEST-001
DETAIL: Orphan
```

---

## 6. Validation Algorithm (for automated checks)

```
function validate_journal(journal_text):
    entries = parse(journal_text)
    errors = []

    for entry in entries:
        # Every entry must have TYPE, SPEC, STATUS, ROOT
        if missing_any(entry, ["type", "spec", "status", "root"]):
            errors.append(...)

        # TYPE must be valid
        if entry.type not in VALID_TYPES:
            errors.append(...)

        # ROOT must be valid for USER_INPUT
        if entry.type == USER_INPUT:
            if entry.parent != "--": errors.append(...)
            if entry.root != entry.jid: errors.append(...)
        else:
            if missing(entry, "parent"): errors.append(...)
            if entry.parent == entry.jid: errors.append(...)  # self-ref
            if entry.parent not in entries and entry.parent != "--":
                errors.append(...)  # orphan

        # TASK field for task-level entries
        if entry.type in TASK_TYPES:
            if missing(entry, "task"): errors.append(...)
            elif invalid_format(entry.task): errors.append(...)

    # Unique JIDs
    if duplicate_jids(entries): errors.append(...)

    # No cycles
    for entry in entries:
        if has_cycle(entry, entries): errors.append(...)

    # Every chain reaches USER_INPUT
    for entry in entries:
        reached = follow_parent_chain(entry, entries)
        if reached is None: error(...)  # broken chain
        elif reached.root != reached.jid: error(...)  # bad USER_INPUT
        elif entry.root != reached.jid: error(...)  # ROOT mismatch

    # Branching limits
    for parent_jid, children in group_by_parent(entries):
        if len(children) > 1:
            parent = entries[parent_jid]
            if parent.type not in BRANCHING_ALLOWED:
                error(...)  # illegal branching

    return errors
```

---

## 7. References

- SKILL.md — SDD workflow definition (uses this journal format)
- spec-driven-tdd skill — the pipeline that produces this journal
