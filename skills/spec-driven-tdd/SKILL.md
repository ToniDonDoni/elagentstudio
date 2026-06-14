---
name: spec-driven-tdd
description: "Spec-driven TDD with review at every step. Spec -> REVIEW -> tasks -> TEST -> REVIEW -> RED -> REVIEW -> GREEN -> REVIEW -> REFACTOR -> REVIEW. The test is end-to-end and targets the acceptance criterion from the spec."
version: 1.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, specification, testing, quality, workflow, code-review]
    related_skills: [writing-plans, test-driven-development, requesting-code-review, systematic-debugging, subagent-driven-development]
---

# Spec-Driven TDD

## Overview

Take a specification (formal or informal) and produce production-ready code through a pipeline with review at every step:

**parse spec -> REVIEW SPEC -> decompose into tasks -> for each task: WRITE TEST -> REVIEW TEST -> RED -> REVIEW RED -> GREEN -> REVIEW GREEN -> next task**

Every line of production code passes through:
1. Spec -> reviewed
2. Task -> reviewed
3. Test (failing, end-to-end, targets the acceptance criterion) -> reviewed
4. RED (test fails) -> reviewed
5. GREEN (minimal impl, test passes) -> reviewed

**Core principle:** Reviewer at every stage. A fresh perspective -- every time. No shared memory with the author.

## Core Idea (read this first)

Three stages. One rigid cycle. Every artifact goes through the same loop:

  CREATE -> COMMIT -> REVIEW (via delegate_task)
                           |
                     PASS or FAIL?
                     |-- PASS -> next stage
                     |-- FAIL -> FIX artifact -> COMMIT fix
                               -> REVIEW again (same loop)

Stage 1: SPEC-DRAFT.md -> REVIEW -> PASS -> next stage
Stage 2: Tests -> REVIEW -> PASS -> next stage
Stage 3: Code  -> REVIEW -> PASS -> next stage

Every `-> REVIEW ->` means a SEPARATE delegate_task call - a fresh reviewer agent, no shared memory with the author.
Every `-> COMMIT ->` means review always runs on committed changes (Rule 1: commit before review).
Every stage produces two types of artifacts - the work output (spec/test/code) and updated JOURNAL_SDD_TDD_SKILL.log file with a new entry with the step result. Both exist in the project tree when the step is done. A step is not done until both are committed.

**The #1 rule:** Never proceed to the next step without REVIEW = PASS
on the current artifact. Ever. No exceptions.

### Why Per-Stage Commits + Journal Are Required (Audit Trail)

Commit after every completed stage and journal every stage result — this is not ceremony. It exists to make the process **analyzable and improvable over time**:

```
git log --oneline --reverse

abc1234 SPEC COMPLETED                                    # spec/ + journal
def5678 SPEC REVIEW PASSED                                # journal only
7890123 RED COMPLETED                                    # tests/ + test output + journal
3456789 RED REVIEW FAILED                                 # journal only
5678901 RED COMPLETED FIXED                              # test fix + journal
9012345 RED REVIEW PASSED                                 # journal only
1234567 GREEN COMPLETED                                   # src/ + journal
3456779 GREEN REVIEW PASSED                               # journal only
...
```

Each REVIEW commit (`SPEC REVIEW PASSED`, `SPEC REVIEW FAILED`, `RED REVIEW PASSED`, `RED REVIEW FAILED`, `GREEN REVIEW PASSED`, `GREEN REVIEW FAILED`) contains **only the journal update** — the reviewer verdict is appended to `JOURNAL_SDD_TDD_SKILL.log`. No test changes, no code changes. This is how you verify that review happened independently of any implementation work.

If review verdict is FAIL → fix the artifact (test or code), commit with `COMPLETED FIXED` (includes the fix + journal update) → re-review → new review verdict commit (journal only).

Each commit is a permanent record of what existed at each stage. This is needed to understand how to improve the solution of the task — and for that we need a full log of the process by steps, to understand when and what happened. Without per-stage commits, there is no data to learn from: you cannot tell why the solution turned out the way it did, where the bottlenecks were, or what to change next time.

Three purposes:
1. **Audit** — `git log` documents the sequence: tests → RED → GREEN. Makes every run reproducible and reviewable.
2. **Analysis** — when a solution fails, the commit chain shows exactly which stage introduced the issue (test gap? RED missed something? GREEN overcomplicated?), making debugging reproducible.
3. **Skill improvement** — pattern-matching across past runs reveals where agents most often shortcut the process (skipped RED, skipped REVIEW, batched commits), driving targeted fixes to this SKILL.md itself.

### Target State

The cycle is complete when:
- The goal from the spec is fully solved
- All code passes all tests
- Every commit along the chain has a **PASS** verdict from review
- The journal file `JOURNAL_SDD_TDD_SKILL.log` exists, is updated for every completed step and review result, and contains:
  - An unbroken `PARENT` chain from `USER_INPUT` to `DONE`
  - Every journal entry has a `ROOT` field identifying the originating `USER_INPUT`
  - Per-task entries (`RED`, `GREEN`, `RED_REVIEW`, `GREEN_REVIEW`) carry a `TASK` field with the task ID

## When to Use

- Building a feature from requirements (ticket, user story, verbal spec)
- Implementing against a formal spec document (SpecKit, OpenAPI, ADR)
- Refactoring legacy code with spec coverage (specify behavior -> test -> refactor -> verify)
- Delegating to subagents: give them spec + TDD instructions for autonomous execution

**Skip for:** throwaway prototypes, single-line changes, or when user explicitly says "no tests needed".

## Relationship to Other Skills

This skill **orchestrates** three existing Hermes skills:

| Skill | Role |
|-------|------|
| `writing-plans` | Plan decomposition -- break spec into bite-sized tasks |
| `test-driven-development` | RED-GREEN-REFACTOR cycle per task |
| `requesting-code-review` | Independent review after each task |

It does NOT replace them. It sequences them into a pipeline.

## Pipeline

**Reviewer at every step.** Every artifact undergoes independent verification before the next stage begins.

```
SPEC
  │
  ├── REVIEW SPEC
  │     ├── PASS -> decompose into tasks
  │     └── FAIL -> ask user -> re-review
  │
  ▼
TASK N (from spec decomposition)
  │
  ├── 1. RED (write test + run, expect failure)
  ├── 2. REVIEW RED -> PASS?
  │     ├── PASS -> proceed
  │     └── FAIL -> fix test -> re-run RED -> re-review
  │
  ├── 3. GREEN (minimal implementation)
  ├── 4. REVIEW GREEN -> PASS?
  │     ├── PASS -> proceed to next task or done
  │     └── FAIL -> fix code -> re-review
  │
  └── NEXT TASK or DONE

=== After each review ===
PASS -> next stage
FAIL -> fix -> re-review of the same artifact
```

In the pipeline above, each completed stage still requires a committed journal file `JOURNAL_SDD_TDD_SKILL.log` entry before the next stage starts.

### Key Principles

1. **Test targets the spec, not the code.** The test is end-to-end (end-to-end for one of the acceptance criteria from the spec). It verifies the SPEC is satisfied, not that function X returns Y. The test reviewer checks: "Does this test prove that the spec is satisfied?"

2. **Reviewer = separate context.** No shared memory with the author. A fresh perspective every iteration.

3. **Every artifact is reviewed before the next one is built on top of it.** Test -- before RED. RED -- before GREEN. GREEN -- before completion.

4. **RED must fail.** If the test passes during RED, you are testing existing behavior. The test must be fixed.

5. **Spec Draft -- immutable input.** SPEC-DRAFT.md (or TASK-DRAFT.md) is written once and never edited again. All discussion, clarifications, and reviewer comments go only into JOURNAL_SDD_TDD_SKILL.log. If the spec is incomplete -- ask the user rather than editing the spec yourself. This preserves traceability: you can always find the original statement and track which decisions led to what.

## Global Rules

### Rule 1 -- Commit before review

Every artifact must be committed before it can be reviewed. Reviews always inspect a commit, never a dirty working tree.

Artifacts include:
- spec files
- task files
- test files
- implementation files
- generated documentation
- review notes
- journal updates
- regression evidence
- retry/fix artifacts

### Rule 2 -- Review request format

Every review request must include:
- commit hash
- artifact path
- spec ID
- task ID (if applicable)
- expected review scope

### Rule 3 -- Every completed step updates the journal

Every completed step and every review result appends a record to the journal file `JOURNAL_SDD_TDD_SKILL.log`.

Review outcomes: PASS, FAIL, NEEDS_CLARIFICATION, CANCELLED.

### Rule 4 -- Journal updates are committed

After appending to JOURNAL_SDD_TDD_SKILL.log, commit the journal change. The journal commit becomes part of the audit trail.

### Rule 5 -- Every fix is a new commit

If review fails, do not amend history. Default behavior:
- create a fix commit
- review the new commit
- append review result to journal
- commit journal update

### Rule 6 -- No silent mutation of immutable input

SPEC-DRAFT.md is immutable after initial commit. If the user clarifies or changes requirements, write it to JOURNAL_SDD_TDD_SKILL.log and create a derived spec amendment artifact (SPEC-AMENDMENT-001.md) if needed. Original input stays preserved.

### Rule 7 -- SPEC-AMENDMENT mechanism

When spec review fails or the user provides clarification after SPEC-DRAFT.md is committed:
1. Create SPEC-AMENDMENT-001.md with the amendment details, OR update a non-immutable derived spec artifact (e.g. a child spec or derived document)
2. Link it to the original spec ID
3. Commit the amendment
4. Review the amendment
5. Journal the result

Amendment format:
```markdown
# SPEC-AMENDMENT-001
**Spec:** S-SDT-01
**Date:** YYYY-MM-DD
**Reason:** Clarification / Revision / Rejection
**Change:** Description of what changed and why
```

### Rule 8 -- Maximum review iterations per artifact

Each artifact has a review counter that resets when moving to the next artifact.

Maximum **21 review attempts** per artifact total (including all PASS, FAIL, NEEDS_CLARIFICATION, and CANCELLED outcomes combined). After the 21st attempt:
- If the review has not passed -- the process escalates to the user
- The user decides: force-pass (review bypassed, proceeds to next stage), cancel (abort the artifact), revise the spec/amendment, or split/redefine the artifact
- Escalation is recorded in JOURNAL_SDD_TDD_SKILL.log with TYPE=ESCALATION
- On force-pass: proceed to the next stage as if PASS, but note in DETAIL that review was force-passed
- On cancel: entry TYPE=CANCELLED, abort this artifact, move to next or stop
- On revise: entry TYPE=SPEC_REVIEW STATUS=FAIL with detail "escalated for revision"
- On split: create new artifact, new counter starts at 1

Counter resets when work starts on a new artifact (next spec, next task, next test, etc.). Each artifact starts its own counter at 1.

### Rule 9 -- English-only artifacts

All artifacts in the project must be written in English. This includes:
- spec files (SPEC-DRAFT.md, SPEC-EXAMPLE.md, etc.)
- task files (TASKS.md)
- tests and implementation code
- JOURNAL_SDD_TDD_SKILL.log entries
- SKILL.md, README.md, and any other documentation
- commit messages
- review requests and responses
- inline comments in code

Non-English content is only allowed in:
- **User input** -- recorded as-is in Phase 0 (then translated before committing)
- **Intentionally bilingual reference documents** -- e.g. translation glossaries that map between languages (SPEC-ENGLISH.md-style translation references)
- **Historical/excluded artifacts** -- files explicitly excluded from active development (e.g. SKILL.current.md)

If the user provides a spec or clarification in another language, translate it before committing or record it as a USER_INPUT entry and create an English artifact.

Rationale: traceability, reviewer independence (reviewers may not speak the user's language), and tooling compatibility (grep, linters, CI checks).

## Journaling & Audit Trail

Every transition between stages, review results, and returns for rework is journaled to the `JOURNAL_SDD_TDD_SKILL.log` file at the project root.

### JID Format

```
J-{YYYYMMDD}-{HHMMSS}-{NNN}
```

Example: `J-20260608-204500-001`. Uniqueness when multiple events happen in the same second is provided by the `{NNN}` counter.

### Record Format (serialized)

```
=== {JID} ===
TYPE: {TYPE}
SPEC: {SPEC}
STATUS: {STATUS}
PARENT: {PARENT_JID}
ROOT: {ROOT_JID}        (optional — JID of root USER_INPUT for this spec tree)
DEPENDS: {DEPENDS_JID}   (optional — JID of previous step in the chain)
TASK: {TASK_ID}          (optional — Task ID for per-task entries)
DETAIL: {detail text}
```

Blank line between entries. Fields are strictly in this order. Empty optional fields are omitted.
`PARENT` = ` -- ` and `ROOT` = ` -- ` for root USER_INPUT. Entry is created post-factum AFTER completing the step.

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| JID | yes | Unique entry ID |
| TYPE | yes | Stage type (enum) |
| SPEC | yes | Spec ID — always a Spec ID, not a Task ID |
| STATUS | yes | PASS, FAIL, NEEDS_CLARIFICATION, COMPLETED, CANCELLED |
| PARENT | yes | JID of the trigger entry (` -- ` for root USER_INPUT) |
| ROOT | no | JID of the originating USER_INPUT entry for this spec tree |
| DEPENDS | no | JID of the previous step in the chain |
| TASK | no | Task ID (`T-{SPEC_ID}-{NNN}`) for per-task entries (RED, GREEN, RED_REVIEW, GREEN_REVIEW) |
| DETAIL | no | Description of what happened |

### TYPE Enum

| TYPE | When created |
|------|----------------|
| USER_INPUT | Recording incoming feature request (Phase 0) |
| PROJECT_INIT | Project creation |
| SPEC_SPEC | Capture of the initial spec (creation only) |
| SPEC_REVIEW | Spec review |
| DECOMPOSE | Decomposition into tasks |
| TASK_REVIEW | Task decomposition review (Phase 2) |
| AGENT_DECISION | Agent selects which task to work on next |
| RED | Writing + running the test (failure expected) |
| RED_REVIEW | RED result review |
| GREEN | Writing the minimal implementation |
| GREEN_REVIEW | GREEN review |
| REGRESSION | Regression verification |
| REGRESSION_REVIEW | Regression review (Phase 4) |
| FINAL_REVIEW | Final implementation review (Phase 5) |
| ESCALATION | User escalation when review limit exceeded (Rule 8) |
| CODEX_REVIEW | Review by Codex CLI |
| DONE | Completion |

### Lifecycle Rules

1. **One entry per step** -- created after the step is completed.
2. **STATUS** = outcome: COMPLETED (work), PASS/FAIL/NEEDS_CLARIFICATION (review), CANCELLED (interrupted).
3. **APPEND only** -- entries are only added to the end of the file.
4. **Chronological** -- entry order = event order.
5. **PARENT** = JID of the step that triggered this one (SPEC_REVIEW -> preceding SPEC_SPEC). ROOT is the JID of the originating USER_INPUT entry for the spec tree; it is copied from the USER_INPUT entry to all derived entries. TASK is the Task ID for per-task entries.
6. **PARENT chain validation** — Before writing a DONE entry, verify the complete unbroken PARENT chain by iteratively following PARENT links from DONE until `PARENT: --` is found. The entry with `PARENT: --` MUST have TYPE=USER_INPUT. If the chain breaks (referenced JID does not exist) or the root is not USER_INPUT, the DONE entry MUST NOT be written until the chain is fixed.

### Example

```journal
=== J-20260608-204500-001 ===
TYPE: USER_INPUT
SPEC: S-SDT-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260608-204500-001
DETAIL: Initial feature request received.

=== J-20260608-204500-002 ===
TYPE: SPEC_SPEC
SPEC: S-SDT-01
STATUS: COMPLETED
PARENT: J-20260608-204500-001
ROOT: J-20260608-204500-001
DETAIL: Initial spec draft created with 6 subspecs

=== J-20260608-204500-003 ===
TYPE: SPEC_REVIEW
SPEC: S-SDT-01
STATUS: FAIL
PARENT: J-20260608-204500-002
ROOT: J-20260608-204500-001
DETAIL: Spec review FAIL -- acceptance criteria too vague

=== J-20260608-204500-004 ===
TYPE: RED
SPEC: S-SDT-01.01
STATUS: COMPLETED
PARENT: J-20260608-204500-003
ROOT: J-20260608-204500-001
TASK: T-S-SDT-01.01-001
DETAIL: Test written for TodoItem model. RED: ImportError expected.
```

### Spec ID Scheme

Spec IDs follow a hierarchical format for parent-child relationships:

```
S-[A-Z]{2,6}-\d{2}(\.\d{2})*
```

Examples:
- `S-SDT-01` -- root spec (parent: ` -- `)
- `S-SDT-01.01` -- child spec (parent: `S-SDT-01`)
- `S-SDT-01.01.01` -- sub-spec (parent: `S-SDT-01.01`)

**Rules:**
1. Child spec ID = parent spec ID + `.NN`
2. The spec body must contain a `parent:` field (lowercase)
3. Find children: `grep "^parent: S-SDT-01" *.md`

### Traceability

| Direction | Mechanism |
|-------------|----------|
| Spec -> Journal entries | `grep "S-SDT-01.01" JOURNAL_SDD_TDD_SKILL.log` |
| Journal -> Spec | SPEC field in the entry -> find the spec file by ID |
| Child -> Parent | In the child spec, `parent:` -> find the parent spec |
| Parent -> Children | `grep "parent: S-SDT-01" *.md` |
| Task -> Spec | Extract SPEC_ID from TASK ID (`T-{SPEC_ID}-{NNN}`) -> find spec |
| Entry -> Root User Input | `grep "^ROOT: <JID>" JOURNAL_SDD_TDD_SKILL.log` shows all entries from that input |

### Task ID Scheme

Task IDs follow a hierarchical format that encodes the parent spec relationship:

```
T-{SPEC_ID}-{NNN}
```

Where:
- `{SPEC_ID}` is the Spec ID the task belongs to (e.g. `S-SDT-01`)
- `{NNN}` is a zero-padded 3-digit sequence number (001, 002, ...)

Examples:
- `T-S-SDT-01-001` — Task 1 of root spec S-SDT-01
- `T-S-SDT-01.01-001` — Task 1 of child spec S-SDT-01.01
- `T-S-SDT-01.01-002` — Task 2 of child spec S-SDT-01.01

**Rules:**
1. Task ID = `T-` + parent spec ID + `-` + zero-padded sequence number
2. Sequence numbers restart per spec ID (`S-SDT-01-001`, `S-SDT-01.01-001` — both have `-001`)
3. Every per-task journal entry (RED, GREEN, RED_REVIEW, GREEN_REVIEW) carries the Task ID in the `TASK` field
4. The `SPEC` field in per-task entries still holds the Spec ID (not the Task ID)

**Traceability from a Task ID:**
1. Extract `{SPEC_ID}` from the Task ID: `T-{SPEC_ID}-{NNN}`
2. Find the spec file by `{SPEC_ID}` (e.g. `S-SDT-01.01`)
3. From the spec's `parent:` field, find the parent spec
4. Recurse until `parent: --` (root spec)
5. The root spec's USER_INPUT is the journal entry with `TYPE=USER_INPUT` for that SPEC

### SPEC/TASK Field Usage by TYPE

The following table specifies what value goes in the `SPEC` and `TASK` fields for each journal entry TYPE:

| TYPE | SPEC value | TASK value |
|------|-----------|------------|
| USER_INPUT | Assigned spec ID | — (absent) |
| PROJECT_INIT | Project spec ID | — |
| SPEC_SPEC | The spec ID being created | — |
| SPEC_REVIEW | The spec ID being reviewed | — |
| DECOMPOSE | The spec ID being decomposed | — |
| TASK_REVIEW | The spec ID | — (or absent) |
| AGENT_DECISION | The spec ID | Task ID if selecting a specific task |
| RED | The parent spec ID | Task ID |
| RED_REVIEW | The parent spec ID | Task ID |
| GREEN | The parent spec ID | Task ID |
| GREEN_REVIEW | The parent spec ID | Task ID |
| REGRESSION | The spec ID | — |
| REGRESSION_REVIEW | The spec ID | — |
| FINAL_REVIEW | The spec ID | — |
| ESCALATION | The spec ID | Task ID if applicable |
| CODEX_REVIEW | The spec ID | — |
| DONE | The spec ID | — |

## Phase 0 -- User Input Recording

Before any spec work, record the incoming feature request in the journal.

The user provides the initial request (text description, bullet points, user story, or formal spec).

**Action:** Create a journal entry with TYPE=USER_INPUT.

```journal
TYPE: USER_INPUT
SPEC: <assigned spec ID>
STATUS: COMPLETED
PARENT: --
ROOT: <JID of this entry — same as the JID in === JID ===>
DETAIL: Initial feature request received.
```

**Commit:** `spec-driven-tdd: record initial user input for <spec ID>`

No feature review yet. This only records incoming context.

** ->  JOURNAL:** `USER_INPUT`, STATUS=COMPLETED, PARENT= -- , ROOT=<JID of this entry>.

Then commit the journal update.

## Phase 1 -- Spec Parsing + Review

Accept spec in any format:
- Text description ("build a todo list API with CRUD endpoints")
- Bullet-point requirements
- Formal spec (SpecKit `.spec.md`, OpenAPI YAML, ADR)
- User story ("As a user, I want to...")

Extract:
- **Entities** -- what data structures exist
- **Behaviors** -- what operations are permitted
- **Constraints** -- validation rules, edge cases
- **Acceptance criteria** -- how to verify it's done

** ->  REVIEW SPEC.** An independent reviewer checks:
- Are all acceptance criteria unambiguous?
- Are there any contradictions in the spec?
- Can a test be written from the spec?
- Are any edge cases missing?

```python
delegate_task(
    goal="Review this specification for completeness and testability.",
    context="Spec:\n" + spec_text,
    toolsets=[]
)
```

PASS -> decompose. FAIL -> clarify with the user + record in JOURNAL_SDD_TDD_SKILL.log -> re-review.

## Phase 2 -- Task Decomposition + Review (from the spec)

Use `writing-plans` skill to break spec into tasks. Each task = one acceptance criterion from the spec.

```markdown
### Task 1: TodoItem model -- id, title, completed_at fields

**Spec ref:** §2.1
**Acceptance:** TodoItem has all 3 fields; id is auto-generated UUID
```

Tasks build on each other. The first task is the most basic entity, the last one is integration of everything.

** ->  REVIEW TASKS.** Independent reviewer checks:
- Does every task map to exactly one acceptance criterion?
- Are task IDs linked to spec IDs?
- Is task order reasonable?
- Are tasks small enough for TDD?
- Is traceability preserved?

** ->  JOURNAL:** `TASK_REVIEW`, STATUS=PASS or FAIL, PARENT=JID of the DECOMPOSE entry.

PASS -> proceed to per-task loop (Phase 3).
FAIL -> fix TASKS.md -> re-review -> journal -> commit journal.

### Task Grouping for Review

If task decomposition produces many tasks, request the spec reviewer to also evaluate task granularity:

```python
delegate_task(
    goal="Review task decomposition for appropriate granularity.",
    context=f"Spec:\n{spec_text}\n\nTasks:\n{tasks_text}",
    toolsets=[]
)
```

Reviewer should check:
- Are tasks too granular (e.g., "import module" as separate task)?
- Can related tasks be grouped (e.g., "CSV loading + parsing" as one task)?
- Does each task map to exactly ONE acceptance criterion (not multiple, not partial)?

Grouping tasks reduces total pipeline complexity. Grouped tasks share a single GREEN_REVIEW but still have individual RED -> GREEN cycles.
Journal entries use combined spec IDs: `S-SAM-01.03-06` for tasks 3-6.

## Phase 3 -- Per-Task Loop (review at every step)

For EVERY task from Phase 2:

---

### Step 3.1 -- RED (write test + run, expect failure)

Write a failing test on RED stage targeting the acceptance criterion from the spec, not the implementation. The test is end-to-end — it checks system behavior, not function internals.

```python
def test_todo_has_id_title_and_completed_at():
    """Spec §2.1: TodoItem has id (UUID), title (str), completed_at (None|datetime)."""
    item = TodoItem(title="Buy milk")
    assert item.id is not None
    assert isinstance(item.title, str)
    assert item.completed_at is None
```

**Then run the test immediately.** It must fail — we have not written the code yet.

**Commit RED artifact: test file + RED evidence (test output) + journal entry.**

```bash
pytest tests/test_todo.py::test_todo_has_id_title_and_completed_at -v
```

Expected: `FAILED` (class is not defined, method is missing, import does not work).

If the test passes — you are testing existing behavior. The test must be rewritten.

** ->  JOURNAL:** After writing and running — create a `RED` entry, STATUS=COMPLETED, SPEC=current spec ID, PARENT=JID of the decomposition step. Include test output in DETAIL.

```journal
TYPE: RED
SPEC: S-SDT-01.01
STATUS: COMPLETED
PARENT: J-<decomp jid>
DETAIL: Tests written and RED: FAILED (ImportError: cannot import name 'TodoItem')
```

### Step 3.2 -- REVIEW RED

Reviewer checks **both** the test code and the RED output:

**Test quality:**
1. **Test targets the spec, not the code** — the test checks the acceptance criterion, not implementation details
2. **End-to-end approach** — the test checks system behavior as a whole (or at minimum the module's public API), not internal functions
3. **One test = one acceptance criterion**
4. **Wording is clear** — from the name and docstring it is clear what is being verified

**RED result:**
- Did the test fail for the right reason (missing feature, not a test bug)?
- Are edge cases covered?

```python
delegate_task(
    goal="""Review the test and RED result:
    1. Does the test correctly cover the acceptance criterion from the spec?
    2. Did it fail for the right reason (missing feature, not a test bug)?
    3. Is it end-to-end (behavioral, not implementation-coupled)?
    4. Are edge cases covered?
    5. Is wording clear?

    Return a verdict (PASS or FAIL) with reasoning for each criterion.""",
    context=f"Spec section:\n{spec_section}\n\nTest:\n{test_code}\n\nRED output:\n{terminal_output}",
    toolsets=[]
)
```

**PASS** -> proceed to GREEN. Journal: `RED_REVIEW`, STATUS=PASS, PARENT=JID of RED.
**FAIL** (test is broken, failed for wrong reason, or doesn't cover the spec) -> fix the test -> re-run RED -> journal `RED` entry with DETAIL="FIXED" -> re-review RED.

### Step 3.3 -- GREEN (write minimal implementation)

Write the minimal code needed to make the test pass. Nothing extra.

```python
from dataclasses import dataclass, field
from uuid import uuid4

@dataclass
class TodoItem:
    title: str
    id: str = field(default_factory=lambda: str(uuid4()))
    completed_at: None = None
```

Run the test again:

```bash
pytest tests/test_todo.py::test_todo_has_id_title_and_completed_at -v
```

Expected: `PASSED`.

** ->  JOURNAL:** After GREEN — entry `GREEN`, STATUS=COMPLETED, PARENT=JID of RED_REVIEW.

### Step 3.4 -- REVIEW GREEN

Reviewer checks:
- The test passed (there is evidence)
- The implementation is minimal (does nothing extra, does not violate YAGNI)
- Whether there are bugs, security issues, or logic errors in the implementation
- The implementation matches the spec (covers the acceptance criterion)

```python
delegate_task(
    goal="Review the GREEN implementation. Is it minimal, correct, spec-compliant?",
    context=f"Spec ref: {spec_ref}\nTest output:\n{terminal_output}\n\nNew code:\n{implementation_code}",
    toolsets=["terminal"]
)
```

**PASS** -> proceed to next task or done. Journal: `GREEN_REVIEW`, STATUS=PASS, PARENT=JID of GREEN.
**FAIL** -> fix -> re-review GREEN. Journal: `GREEN_REVIEW`, STATUS=FAIL.

## Phase 4 -- Inter-Task Regression Check + Review

After completing each task -- run ALL tests (including all previous tasks):

```bash
pytest tests/ -q
```

All must be green. If there are regressions -- fix them before moving to the next task.

** ->  JOURNAL:** `REGRESSION`, STATUS=PASS (all tests are green) or FAIL (regressions exist), PARENT=JID of the previous step.

** ->  REVIEW REGRESSION (optional but recommended).** Independent reviewer checks:
- All tests are green (evidence from terminal output)
- No regressions introduced by the latest task
- The regression evidence is recorded in the journal

** ->  JOURNAL:** `REGRESSION_REVIEW`, STATUS=PASS or FAIL, PARENT=JID of the REGRESSION entry.

If FAIL -> fix regression -> re-run tests -> re-review -> journal -> commit journal.

## Phase 5 -- Final Review + Done

**MANDATORY: Git clean check before FINAL_REVIEW.**

After each commit -- including journal updates, spec files, tests, and implementation -- verify no important artifacts are left uncommitted:

```bash
git status --porcelain
```

If uncommitted files exist:
- **Add and commit them** if they are part of the task solution or the solution workflow requirements (spec files, tests, implementation, journal updates, documentation)
- **Or explicitly exclude them** if they are temporary artifacts (e.g. `__pycache__/`, `.env`, `.pytest_cache/`)

Uncommitted solution artifacts = pipeline incomplete. Do not proceed to FINAL_REVIEW until git is clean.

---

Run a final independent review of the complete implementation.

**Review scope:**
- Are all acceptance criteria from the original spec covered by tests?
- Are all tests green?
- Is there a complete audit trail in JOURNAL_SDD_TDD_SKILL.log?
- Are there any regressions or uncovered edge cases?
- Is documentation aligned with implementation?
- Is git clean (no uncommitted artifacts)?

** ->  JOURNAL:** `FINAL_REVIEW`, STATUS=PASS or FAIL, PARENT=JID of the last REGRESSION.

If FAIL -> fix -> re-review -> journal -> commit journal.

All tasks are completed. Final verification:
- All acceptance criteria from the spec are covered by tests
- All tests are green
- Every stage was reviewed
- No regressions
- Journal file `JOURNAL_SDD_TDD_SKILL.log` exists, is updated for every completed step and review result, and contains an unbroken `PARENT` chain from `USER_INPUT` to `DONE`

** ->  JOURNAL:** `DONE`, STATUS=COMPLETED, PARENT=JID of the last FINAL_REVIEW.

## Hermes Agent Integration

### Local execution (single agent)

```python
# 1. Load skills
from hermes_tools import skill_view
skill_view("spec-driven-tdd")
skill_view("writing-plans")
skill_view("test-driven-development")
skill_view("requesting-code-review")

# 1b. Initialize journal
import os, datetime
JOURNAL_PATH = "JOURNAL_SDD_TDD_SKILL.log"
_jid_seq = [0]  # mutable counter for JID uniqueness
def jlog(type_, spec, status, parent=" -- ", depends="", detail=""):
    _jid_seq[0] += 1
    now = datetime.datetime.now()
    jid = f"J-{now.strftime('%Y%m%d-%H%M%S')}-{_jid_seq[0]:03d}"
    entry = f"\n=== {jid} ===\nTYPE: {type_}\nSPEC: {spec}\nSTATUS: {status}\nPARENT: {parent}\n"
    if depends:
        entry += f"DEPENDS: {depends}\n"
    entry += f"DETAIL: {detail}\n"
    with open(JOURNAL_PATH, "a") as f:
        f.write(entry)
    return jid

# 2. Parse spec
spec = """..."""
spec_jid = jlog("SPEC_SPEC", "S-SDT-01", "COMPLETED", detail="Parsed spec from user input")

# 3. REVIEW SPEC (Phase 1)
review = delegate_task(
    goal="Review this specification for completeness and testability.",
    context="Spec:\n" + spec,
    toolsets=[]
)
review_jid = jlog("SPEC_REVIEW", "S-SDT-01", "PASS", parent=spec_jid, detail="Spec review passed")

# 4. Decompose into tasks (Phase 2)
tasks = [
    {"id": "task-1", "spec_ref": "S-SDT-01.01", "description": "TodoItem model"},
]
decomp_jid = jlog("DECOMPOSE", "S-SDT-01", "COMPLETED", parent=review_jid, detail="Decomposed into 3 tasks")

# 5. For each task (Phase 3)
for task in tasks:
    # Step 3.1: RED (write test + run, expect failure) + REVIEW RED
    test = write_failing_test(task)
    red_output = run_test(test)  # expected: FAIL — confirms test works
    red_jid = jlog("RED", task["spec_ref"], "COMPLETED", parent=decomp_jid,
                   detail=f"Tests written and RED: {red_output.strip()}")
    review_red = delegate_task(
        goal="Review test and RED result. Does the test cover the spec? "
             "Did it fail for the right reason (missing feature, not a test bug)?",
        context=f"Spec ref: {task['spec_ref']}\nTest:\n{test}\nRED output:\n{red_output}",
        toolsets=[]
    )
    jlog("RED_REVIEW", task["spec_ref"], review_red["verdict"], parent=red_jid,
         detail=review_red.get("detail", ""))
    # If FAIL → fix test → jlog("RED", ..., detail="FIXED") → re-review

    # Step 3.3-3.4: GREEN + REVIEW GREEN
    impl = write_minimal_implementation(task, test)
    green_output = run_test(test)  # expected: PASS
    green_jid = jlog("GREEN", task["spec_ref"], "COMPLETED", parent=red_jid,
                     detail=f"Implementation done and tests: {green_output.strip()}")
    review_green = delegate_task(
        goal="Review GREEN implementation. Is it minimal, correct, spec-compliant?",
        context=f"Spec ref: {task['spec_ref']}\nTest output:\n{green_output}\n\nNew code:\n{impl}",
        toolsets=["terminal"]
    )
    jlog("GREEN_REVIEW", task["spec_ref"], review_green["verdict"], parent=green_jid,
         detail=review_green.get("detail", ""))
    # If FAIL → fix impl → jlog("GREEN", ..., detail="FIXED") → re-review

    # Phase 4: regression check
    run_all_tests()
    jlog("REGRESSION", task["spec_ref"], "PASS", parent=green_jid)

# Phase 5: Done
jlog("DONE", "S-SDT-01", "COMPLETED", detail="All tasks completed")
```

### Subagent delegation (autonomous worker)

For full automation -- delegate to a subagent while passing the path to JOURNAL_SDD_TDD_SKILL.log:

```python
delegate_task(
    goal="""Implement the following spec via spec-driven-tdd.

    Full pipeline:
    1. REVIEW SPEC -- verify acceptance criteria are unambiguous
    2. Decompose into tasks -- each task = one acceptance criterion
    3. For each task (review at every step):
       a. WRITE TEST (failing, end-to-end, on spec) -> REVIEW TEST
       b. RED (verify fail) -> REVIEW RED
       c. GREEN (minimal impl) -> REVIEW GREEN
    4. Inter-task regression check (all tests green)
    5. Done

    IMPORTANT: Journal every step into JOURNAL_PATH.
    Create entry AFTER completing each step.
    Use the jlog() helper from the integration example.

    Spec:
    [INSERT SPEC TEXT]

    Test framework: pytest
    """,
    context=f"JOURNAL_PATH={journal_path}. Full pipeline autonomous. Each step -- delegate_task for review.",
    toolsets=["terminal", "file", "skills"]
)
```

### Important for subagent delegation

When delegating to a subagent -- every `delegate_task` for review must be a separate call, not part of one goal. Each time, the reviewer receives fresh context, with no memory of previous steps. That is exactly what gives review its independence.

```python
# Correct: separate call per review
review_test = delegate_task(goal="Review test", context=test_context, toolsets=[])
# ... different context, different agent ...

review_red = delegate_task(goal="Verify RED", context=red_context, toolsets=[])
# ... fresh context again ...
```

### Codex CLI Code Review (additional review)

For external, independent review of the skill or documentation -- use Codex CLI directly:

```bash
# In the project root with SKILL.md and SPEC-DRAFT.md
codex exec --skip-git-repo-check --sandbox danger-full-access \
  "Review the skill SKILL.md against SPEC-DRAFT.md requirements. \
   Check: journaling section, spec ID hierarchy, traceability, \
   journal entries in all Phase 3 steps, pitfalls >=12. PASS/FAIL per item."
```

If the sandbox (bwrap) blocks local files -- pass the content through stdin:

```bash
cat SKILL.md SPEC-DRAFT.md | codex exec --skip-git-repo-check \
  --sandbox danger-full-access - "Review..."
```

> **Note:** Codex CLI does not support `--acp`. Use `codex exec` or `codex review --uncommitted`. For ACP review -- `opencode acp` or `copilot --acp --stdio`.

## Spec Format Example

> **Full reference:** See [SPEC-EXAMPLE.md](references/SPEC-EXAMPLE.md) for a complete, end-to-end walkthrough of the pipeline (Counter API demo). The examples below are quick inline references.

### Structured spec (recommended)

```markdown
# Todo API -- Specification

## §1 Entities

### TodoItem
- `id: str` -- UUID, auto-generated
- `title: str` -- required, max 200 chars
- `completed_at: datetime | None` -- set when toggled done

## §2 Operations

### Create todo
- Input: `title: str` (required, 1-200 chars, trimmed)
- Output: `TodoItem`
- Errors: `ValueError` if title empty or >200 chars

### List todos
- Returns: `list[TodoItem]` ordered by creation (newest first)

### Toggle todo
- Input: `id: str`
- Flips `completed_at` between None and now
- Errors: `KeyError` if id not found
```

### Free-form spec (still works)

```
Build a counter component:
- Starts at 0
- increment() -> +1
- decrement() -> -1
- Can't go below 0
- get_value() returns current
```

## Pitfalls

- **Spec too vague** -- escalate to user for clarification before writing code
- **Existing-codebase spec trap** -- spec-driven-tdd assumes greenfield, but the user may say "go to repo X and update the spec." Before writing SPEC-DRAFT.md: (1) read the existing code to understand what's already implemented, (2) create the spec from requirements BUT mark each AC's implementation status (Already works / Partial / Missing), (3) distinguish net-new features from behavior that only needs a bugfix pass. The existing code is NOT the spec -- the spec describes what SHOULD happen, but the AC table helps the reviewer and implementer know what's starting from scratch vs. what's already there.
- **Ambiguous user terminology** -- when a user uses an unclear term ("юрист" = lawyer in this session), don't guess. Flag it in the spec as an open question (§Open Questions), ask the user with concrete multiple-choice options, and create a SPEC-AMENDMENT once clarified. Never silently interpret ambiguous requirements.
- **Tests too coupled to implementation** -- test behavior, not internals
- **Skipping RED verification** -- if you didn't see it fail, you're testing existing behavior
- **Skipping review** -- independent reviewer catches things you normalized
- **Large tasks** -- if a task takes more than 5 minutes, split it further
- **Reviewer has no spec context** -- always pass the relevant spec section to the reviewer
- **SpecKit compatibility** -- SpecKit `.spec.md` files can be parsed as-is; extract requirements from the "Specification" section
- **Journal not initialized** -- create JOURNAL_SDD_TDD_SKILL.log at project start. No journal = no traceability.
- **PARENT chain broken** -- always pass the previous JID to the next journal entry. Without PARENT, traceability across steps is lost.
- **Journal entries not post-factum** -- write entries AFTER completing the step, not before. STATUS must reflect the actual outcome.
- **Spec ID collision** -- use unique hierarchical spec IDs (`S-SDT-01.01`, not just "task1"). Flat IDs break parent-child traceability.
- **Mixed-language artifacts** -- non-English content in spec files, journal entries, or code breaks traceability and reviewer independence. Keep all artifacts in English. Translate user input before committing.
- **README self-consistency** -- after modifying the skill's file structure (adding/removing references, templates, or core files), the README's "What's Included" table and result directory tree must be updated to match. The table must list ALL R1 files (including README.md itself -- it is easy to forget self-reference). Stale directory entries (e.g. a `templates/` line in the tree after templates were removed) silently mislead users.
- **Cross-reference staleness** -- every local `references/` link in SKILL.md must point to an existing file in the installed skill. After adding or removing reference files, verify all SKILL.md references resolve. Unused files (installed but not referenced) and broken links (referenced but not installed) both degrade the skill. Use `scripts/verify-install.py` to automate this check.

## Self-Consistency Checks

After modifying the skill's file structure (references, README, core files), run a clean-install verification to catch cross-reference staleness and README mismatches:

```bash
# From the repo root
cp scripts/verify-install.py /tmp/ && python3 /tmp/verify-install.py
```

The script performs all checks from SPEC-MINIMAL-INSTALL.md (S-SDT-01.03):

| Check | What it verifies |
|-------|-----------------|
| AC1 | Installed dir contains exactly the R1 file set (no more, no less) |
| AC2 | No git repo artifacts leaked (JOURNAL_SDD_TDD_SKILL.log, SPEC-*.md, tests/, etc.) |
| AC3 | README "What's Included" table and tree match the actual installed layout |
| AC4 | README install commands (`cp SKILL.md`, `cp references/*`) produce the R1 set |
| XREF | Every local `references/` link in SKILL.md resolves to an existing installed file |
| XREF | No non-EXAMPLE files linked in SKILL.md's references (unless intentional) |

To run the verification against a fresh install:

```bash
# Wipe and clean-install from repo
rm -rf ~/.hermes/skills/software-development/spec-driven-tdd/
mkdir -p ~/.hermes/skills/software-development/spec-driven-tdd/references
cp SKILL.md README.md ~/.hermes/skills/software-development/spec-driven-tdd/
cp references/* ~/.hermes/skills/software-development/spec-driven-tdd/references/

# Verify
python3 /tmp/verify-install.py
```

The script operates on the installed Hermes skill directory, not the repo. This catches cases where files were committed to the repo but never synced, or where old files lingered in the installed dir after removal.

## References

- [SPEC-EXAMPLE.md](references/SPEC-EXAMPLE.md) -- **Canonical reference artifact.** Full Counter API demo walkthrough showing every stage of the pipeline from user input to DONE. Ships with this skill. Read it to see the complete workflow including commit-before-review, journal-commit loop, SPEC-AMENDMENT mechanism, and review scopes per stage.
- [SpecKit](https://github.com/github/spec-kit) -- GitHub's spec-driven development tooling. Write `.spec.md` files, generate tests, scaffold code.
- [Hermes Skills Catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) -- complete list of available Hermes skills
- Hermes skills used by this pipeline:
  - `writing-plans` -- task decomposition
  - `test-driven-development` -- RED-GREEN cycle
  - `requesting-code-review` -- independent verification
  - `systematic-debugging` -- when RED fails unexpectedly
  - `subagent-driven-development` -- multi-task subagent orchestration
