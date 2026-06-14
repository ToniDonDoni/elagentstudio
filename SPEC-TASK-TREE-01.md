# SPEC-TASK-TREE-01 — Task Naming with Traceable Parent Chain

**Spec ID:** S-TASK-TREE-01
**Version:** 2
**Source:** User requirement to make every task traceable back to its USER_INPUT

## §1 Problem

The current SKILL.md has a PARENT field in journal entries and a Spec ID scheme (`S-SDT-01.01`), but:

1. **Task IDs are not specified** — tasks are named ad-hoc ("Task 1", "Task 2") with no encoded parent relationship
2. **PARENT chain is optional in practice** — entries can point to themselves, to non-existent JIDs, or the chain can be broken without detection
3. **No mechanism to trace from any task DONE entry back to USER_INPUT** — the skill says PARENT should point to the trigger entry, but doesn't enforce a complete chain

## §2 Requirements

### R1 — Task ID scheme

Task IDs must encode their full ancestry:

```
T-{SPEC_ID}-{NNN}
```

Where:
- `{SPEC_ID}` is the spec ID the task belongs to (e.g. `S-SDT-01`)
- `{NNN}` is a zero-padded 3-digit sequence number (001, 002, ...)

Examples:
- `T-S-SDT-01-001` — Task 1 of root spec S-SDT-01
- `T-S-SDT-01.01-001` — Task 1 of child spec S-SDT-01.01
- `T-S-SDT-01.01-002` — Task 2 of child spec S-SDT-01.01

A task ID directly encodes which spec it belongs to. From the task ID, you can:
1. Find the spec by the embedded `SPEC_ID`
2. From the spec's `parent:` field, find the parent spec
3. Recurse until `parent: --` (root spec)
4. The root spec's USER_INPUT is the journal entry with TYPE=USER_INPUT for that spec

### R2 — Mandatory unbroken PARENT chain

Every journal entry MUST have a correct PARENT JID that points to the actual triggering entry. The chain MUST be traceable from any entry back to USER_INPUT via iterative PARENT traversal until `PARENT: --` is found.

The full chain including review entries:

```
DONE → FINAL_REVIEW (if any) → REGRESSION → REGRESSION_REVIEW (if any)
       → GREEN → GREEN_REVIEW → RED → RED_REVIEW
       → TASK_REVIEW → DECOMPOSE → SPEC_REVIEW → SPEC_SPEC → USER_INPUT
```

**Guidelines:**
- PARENT MUST be a real JID that exists in the journal file
- PARENT of a review entry is the entry of the artifact being reviewed
- PARENT of a work entry (RED, GREEN) is the review entry that approved the previous stage
- PARENT of DECOMPOSE is SPEC_SPEC (or SPEC_REVIEW if SPEC was amended)
- PARENT of SPEC_SPEC is USER_INPUT
- USER_INPUT has `PARENT: --`
- The agent MUST create PARENT entries only AFTER the referenced JID exists (post-factum, after completing the step)

**Validation:** Before writing DONE, verify the complete unbroken PARENT chain by iteratively following PARENT links from DONE until `PARENT: --` is found. The entry with `PARENT: --` MUST have TYPE=USER_INPUT. If the chain breaks (missing JID) or the root is not USER_INPUT, the DONE entry MUST NOT be written until the chain is fixed.

### R3 — ROOT field in journal entries

Add an optional `ROOT` field to every journal entry. The ROOT is the JID of the root USER_INPUT for this spec tree. The field positions between PARENT and DEPENDS in the record format.

```
=== J-20260613-204500-001 ===
TYPE: USER_INPUT
SPEC: S-SDT-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260613-204500-001
DETAIL: Initial feature request received.
```

For all derived entries (SPEC_SPEC, REVIEW, DECOMPOSE, TASK, RED, GREEN, DONE), the ROOT is copied from the USER_INPUT entry:

```
=== J-20260613-204500-005 ===
TYPE: DONE
SPEC: S-TASK-TREE-01
STATUS: COMPLETED
PARENT: J-20260613-204500-004
ROOT: J-20260613-204500-001
DETAIL: Pipeline complete.
```

This enables instant grep: `grep "^ROOT: J-20260613-204500-001" JOURNAL_SDD_TDD_SKILL.log` shows ALL entries from that user input.

**How to determine ROOT:** When starting a new spec pipeline, create a USER_INPUT entry. Its JID becomes the ROOT for all subsequent entries in that spec tree. If the journal already contains multiple USER_INPUT entries, the agent determines the correct ROOT by finding the USER_INPUT entry whose SPEC matches the current spec's parent chain.

### R4 — TASK field for journal entries

Add an optional `TASK` field to journal entries. The SPEC field ALWAYS holds a Spec ID (backward compatible). The TASK field holds the Task ID when the entry is for a specific task.

```
=== J-20260613-204500-010 ===
TYPE: RED
SPEC: S-SDT-01.01
STATUS: COMPLETED
PARENT: J-20260613-204500-009
ROOT: J-20260613-204500-001
TASK: T-S-SDT-01-001
DETAIL: Test written for TodoItem model. RED: ImportError expected.
```

**SPEC field by TYPE:**

| TYPE | SPEC value | TASK value |
|------|-----------|------------|
| USER_INPUT | Assigned spec ID | — (absent) |
| SPEC_SPEC | The spec ID being created | — |
| SPEC_REVIEW | The spec ID being reviewed | — |
| DECOMPOSE | The spec ID being decomposed | — |
| TASK_REVIEW | The spec ID | — (or absent) |
| AGENT_DECISION | The spec ID | Task ID if applicable |
| RED | The spec ID | Task ID |
| RED_REVIEW | The spec ID | Task ID |
| GREEN | The spec ID | Task ID |
| GREEN_REVIEW | The spec ID | Task ID |
| REGRESSION | The spec ID | — |
| REGRESSION_REVIEW | The spec ID | — |
| FINAL_REVIEW | The spec ID | — |
| ESCALATION | The spec ID | Task ID if applicable |
| CODEX_REVIEW | The spec ID | — |
| DONE | The spec ID | — |

### R5 — Updated journal record format

The record format with the new ROOT and TASK fields:

```
=== {JID} ===
TYPE: {TYPE}
SPEC: {SPEC}
STATUS: {STATUS}
PARENT: {PARENT_JID}
ROOT: {ROOT_JID}           (optional — USER_INPUT JID for this spec tree)
DEPENDS: {DEPENDS_JID}      (optional — previous step in the chain)
TASK: {TASK_ID}             (optional — Task ID for per-task entries)
DETAIL: {detail text}
```

Fields are in this strict order. Omitted optional fields are skipped. ROOT before DEPENDS, TASK after DEPENDS.

### R6 — Updated Target State

The Target State section must add: "Every journal entry has an unbroken PARENT chain to its originating USER_INPUT. The ROOT field on any entry identifies the originating user input. Per-task entries (RED, GREEN, RED_REVIEW, GREEN_REVIEW) carry a TASK field with the task ID."

## §3 Acceptance Criteria

### AC1 — Task ID scheme documented in SKILL.md
- **Ref:** R1
- **Check:** SKILL.md contains a "### Task ID Scheme" section with format `T-{SPEC_ID}-{NNN}` and examples.

### AC2 — PARENT chain enforcement documented
- **Ref:** R2
- **Check:** SKILL.md has explicit rules for correct PARENT assignment. Includes the validation rule: before DONE, verify complete unbroken PARENT chain to USER_INPUT.

### AC3 — ROOT field documented
- **Ref:** R3
- **Check:** SKILL.md documents `ROOT: {JID}` field in the record format, positioned between PARENT and DEPENDS. Explains how to determine ROOT for a new spec tree.

### AC4 — TASK field documented with per-TYPE SPEC table
- **Ref:** R4
- **Check:** SKILL.md documents the `TASK: {TASK_ID}` optional field. Includes the TYPE→SPEC/TASK value table.

### AC5 — Updated record format
- **Ref:** R5
- **Check:** The Record Format section shows ROOT and TASK in the correct field order.

### AC6 — Updated Target State
- **Ref:** R6
- **Check:** Target State mentions traceable PARENT chain, ROOT field, and TASK field.

### AC7 — Example journal entries updated
- **Ref:** R1-R6
- **Check:** The journal examples in SKILL.md show entries with ROOT, TASK fields and Task IDs in the correct format.

## §4 Constraints

1. Backward compatible — all existing entries and IDs remain valid. The SPEC field continues to hold Spec IDs. New fields (ROOT, TASK) are optional and absent from old entries.
2. ROOT and TASK fields are optional (entries without them are valid)
3. Spec ID scheme (`S-[A-Z]{2,6}-\d{2}(\.\d{2})*`) remains unchanged
4. TYPE enum remains unchanged
5. Version bump to 1.3.0

## §5 Out of Scope

1. Automated validation scripts for PARENT chain
2. Migration of existing journal files
3. Changes to the SPEC ID scheme itself
4. Changes to the TYPE enum
