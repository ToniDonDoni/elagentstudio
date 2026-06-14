---
name: spec-driven-tdd
description: "Spec-driven TDD with review at every step. Spec -> REVIEW -> tasks -> TEST -> REVIEW -> RED -> REVIEW -> GREEN -> REVIEW -> REFACTOR -> REVIEW. The test is end-to-end and targets the acceptance criterion from the spec."
version: 1.4.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, specification, testing, quality, workflow, code-review]
    related_skills: [writing-plans, test-driven-development, requesting-code-review, systematic-debugging]
---

# Spec-Driven TDD

## Overview

Take a specification (formal or informal) and produce production-ready code through a pipeline with review at every step:

**capture raw input in SPEC-DRAFT.md -> derive SPEC.md -> REVIEW SPEC.md until PASS -> decompose into tasks -> RED -> REVIEW RED -> GREEN -> REVIEW GREEN -> next task**

Every line of production code passes through:
1. Spec -> reviewed
2. Task -> reviewed
3. Test (failing, end-to-end, targets the acceptance criterion) -> reviewed
4. RED (test fails) -> reviewed
5. GREEN (minimal impl, test passes) -> reviewed

**Core principle:** Reviewer at every stage. A fresh perspective -- every time. No shared memory with the author.

**Delegation boundary:** `delegate_task` is used for review only.

The primary agent MUST create and fix artifacts, run the workflow, update the journal, and move between stages.
A delegated agent MUST only inspect an already-created, committed artifact and return a review verdict.
A delegated agent MUST NOT implement the feature, modify files, fix the artifact, run the full pipeline,
or continue to another workflow stage.

## Specification Artifacts

The workflow uses two specification artifacts with different responsibilities.

### `SPEC-DRAFT.md` — immutable raw user input

`SPEC-DRAFT.md` is the exact user input as received.

It MUST:
- preserve the original wording and language;
- be created before interpretation or normalization;
- be committed once;
- never be edited, reviewed, corrected, translated, normalized, or replaced.

Later clarifications or requirement changes are recorded in the journal and
incorporated into `SPEC.md`. They do not rewrite `SPEC-DRAFT.md`.

### `SPEC.md` — editable working specification

`SPEC.md` is derived from `SPEC-DRAFT.md`.

It MUST:
- convert raw input into structured requirements and acceptance criteria;
- remain traceable to `SPEC-DRAFT.md`;
- identify ambiguities, constraints, entities, and observable behavior;
- be committed before every review;
- be reviewed by a separate review-only agent;
- be edited by the primary agent after `FAIL` or `NEEDS_CLARIFICATION`;
- repeat the commit and review cycle until the verdict is `PASS`.

Only reviewed `SPEC.md` is used for task decomposition, test design,
implementation, regression checks, and final acceptance.

## Core Idea (read this first)

Three stages. One rigid cycle. Every artifact goes through the same loop:

  CREATE -> COMMIT -> REVIEW (via delegate_task)
                           |
                     PASS or FAIL?
                     |-- PASS -> next stage
                     |-- FAIL -> FIX artifact -> COMMIT fix
                               -> REVIEW again (same loop)

Input capture: user input -> `SPEC-DRAFT.md` -> COMMIT -> never edit or review

Stage 1: derive `SPEC.md` from `SPEC-DRAFT.md`
         -> COMMIT -> REVIEW
         -> PASS: decompose into tasks
         -> FAIL / NEEDS_CLARIFICATION:
              primary agent edits `SPEC.md`
              -> COMMIT -> fresh REVIEW

Stage 2: Tests -> REVIEW -> PASS -> next stage
Stage 3: Code  -> REVIEW -> PASS -> next stage

Every `-> REVIEW ->` means a SEPARATE review-only `delegate_task` call — a fresh reviewer agent, no shared memory with the author. The delegated agent returns a verdict and MUST NOT modify the artifact.
Every `-> COMMIT ->` means review always runs on committed changes (Rule 1: commit before review).
Every stage produces two types of artifacts - the work output (spec/test/code) and updated JOURNAL_SDD_TDD_SKILL.log file with a new entry with the step result. Both exist in the project tree when the step is done. A step is not done until both are committed.

**The #1 rule:** Never proceed to the next step without REVIEW = PASS
on the current artifact. Ever. No exceptions.

### Why Per-Stage Commits + Journal Are Required (Audit Trail)

Commit after every completed stage and journal every stage result — this is not ceremony. It exists to make the process **analyzable and improvable over time**:

```
git log --oneline --reverse

abc0001 SPEC-DRAFT CAPTURED                              # raw user input + journal
abc1234 SPEC COMPLETED                                    # SPEC.md + journal
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
- `SPEC-DRAFT.md` still contains the original user input unchanged
- `SPEC.md` has a PASS review verdict
- The goal from reviewed `SPEC.md` is fully solved
- All code passes all tests
- Every commit along the chain has a **PASS** verdict from review
- The journal file `JOURNAL_SDD_TDD_SKILL.log` exists, is updated for every completed step and review result. All content rules are defined in [references/JOURNAL.md](references/JOURNAL.md).

## When to Use

- Building a feature from requirements (ticket, user story, verbal spec)
- Implementing against a formal spec document (SpecKit, OpenAPI, ADR)
- Refactoring legacy code with spec coverage (specify behavior -> test -> refactor -> verify)

**Skip for:** throwaway prototypes, single-line changes, or when user explicitly says "no tests needed".

## Relationship to Other Skills

This skill may reference three supporting Hermes skills:

| Skill | Role |
|-------|------|
| `writing-plans` | Plan decomposition -- break spec into bite-sized tasks |
| `test-driven-development` | RED-GREEN-REFACTOR cycle per task |
| `requesting-code-review` | Independent review after each task |

The primary agent executes the pipeline. Delegated agents are used only as independent reviewers.

## Pipeline

**Reviewer at every step.** Every artifact undergoes independent verification before the next stage begins.

```
USER INPUT
  │
  ├── capture exactly in SPEC-DRAFT.md
  │     └── immutable after commit; not reviewed
  │
  ├── derive editable SPEC.md
  │     └── REVIEW SPEC.md
  │           ├── PASS -> decompose into tasks
  │           └── FAIL / NEEDS_CLARIFICATION
  │                 -> primary agent edits SPEC.md
  │                 -> commit
  │                 -> fresh review
  │
  ▼
TASK N (decomposed from reviewed SPEC.md)
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

5. **Draft and working spec are different artifacts.** `SPEC-DRAFT.md` preserves raw user input and is never edited or reviewed. `SPEC.md` is derived from it, reviewed, corrected, and re-reviewed until PASS. Clarifications update `SPEC.md`, never `SPEC-DRAFT.md`.

## Global Rules

### Rule 1 -- Commit before review

Every artifact must be committed before it can be reviewed. Reviews always inspect a commit, never a dirty working tree.

Artifacts include:
- `SPEC-DRAFT.md` (initial immutable capture)
- `SPEC.md` and its reviewed corrections
- other spec files
- task files
- test files
- implementation files
- generated documentation
- review notes
- journal updates
- regression evidence
- retry/fix artifacts

### Rule 2 -- Review-only delegation

Every `delegate_task` call MUST request review of one already-created, committed artifact.

The delegated reviewer may:
- inspect the supplied artifact and evidence;
- compare them with the relevant specification;
- return `PASS`, `FAIL`, or `NEEDS_CLARIFICATION`;
- explain the findings.

The delegated reviewer MUST NOT:
- create or modify implementation, tests, specifications, tasks, or journal entries;
- fix a failed artifact;
- execute the complete spec-driven TDD workflow;
- advance to another stage;
- delegate implementation work to another agent.

The primary agent remains responsible for all creation, fixes, commits, journal updates,
test execution, and workflow progression.

Every review request must include:
- commit hash;
- artifact path;
- spec ID;
- task ID, when applicable;
- expected review scope;
- an explicit instruction to review only and not modify files.

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

### Rule 6 -- Preserve raw user input

`SPEC-DRAFT.md` is a permanent snapshot of the original request.

The primary agent MUST:
- create it before deriving requirements;
- preserve the original wording and language;
- commit it once;
- never modify it after the first commit.

User clarifications and later requirement changes MUST be recorded in the journal
and incorporated into `SPEC.md`. They MUST NOT rewrite historical raw input.

### Rule 7 -- Review and revise SPEC.md

`SPEC.md` is the editable working specification derived from `SPEC-DRAFT.md`.

The primary agent creates and edits `SPEC.md`.
A delegated agent reviews only the committed `SPEC.md`.

The required cycle is:

```text
create or edit SPEC.md
-> commit SPEC.md and journal update
-> review-only delegate_task
-> PASS: proceed to task decomposition
-> FAIL or NEEDS_CLARIFICATION:
     primary agent edits SPEC.md
     -> commit
     -> fresh review-only delegate_task
```

Task decomposition MUST NOT begin until `SPEC.md` receives `PASS`.

Ordinary review corrections and clarifications are made directly in `SPEC.md`.
Commit history and the journal preserve the evolution of the working specification.

### Rule 8 -- Maximum review iterations per artifact

Each artifact has a review counter that resets when moving to the next artifact.

Maximum **21 review attempts** per artifact total (including all PASS, FAIL, NEEDS_CLARIFICATION, and CANCELLED outcomes combined). After the 21st attempt:
- If the review has not passed -- the process escalates to the user
- The user decides: force-pass (review bypassed, proceeds to next stage), cancel (abort the artifact), revise `SPEC.md`, or split/redefine the artifact
- Escalation is recorded in JOURNAL_SDD_TDD_SKILL.log with TYPE=ESCALATION
- On force-pass: proceed to the next stage as if PASS, but note in DETAIL that review was force-passed
- On cancel: entry TYPE=CANCELLED, abort this artifact, move to next or stop
- On revise: update `SPEC.md`, commit it, and start a new review attempt
- On split: create new artifact, new counter starts at 1

Counter resets when work starts on a new artifact (next spec, next task, next test, etc.). Each artifact starts its own counter at 1.

### Rule 9 -- Artifact language

`SPEC-DRAFT.md` preserves raw user input exactly and MAY use any language.

All derived active artifacts MUST be written in English, including:
- `SPEC.md`;
- task files;
- tests and implementation code;
- journal entries except verbatim quoted user input;
- documentation;
- commit messages;
- review requests and responses;
- inline comments in code.

If the user input is not English, keep it unchanged in `SPEC-DRAFT.md` and create
the English working specification in `SPEC.md`.

Rationale: the raw input remains historically accurate, while derived artifacts
remain accessible to reviewers and tooling.

## Journaling & Audit Trail

The pipeline MUST maintain a journal file `JOURNAL_SDD_TDD_SKILL.log` at the project root,
updated for every completed step and every review result.

All rules governing journal content — entry format, required fields, branching model,
validation — are defined in [references/JOURNAL.md](references/JOURNAL.md).

### Spec ID Scheme

Spec IDs follow a hierarchical format for parent-child relationships:

```
S-[A-Z]{2,6}-\d{2}(\.\d{2})*
```

Examples:
- `S-SDT-01` — root spec (parent: ` -- `)
- `S-SDT-01.01` — child spec (parent: `S-SDT-01`)
- `S-SDT-01.01.01` — sub-spec (parent: `S-SDT-01.01`)

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

## Phase 0 -- Capture Raw User Input

Before interpretation or specification work:

1. Create `SPEC-DRAFT.md`.
2. Copy the user input into it exactly as received.
3. Do not normalize wording, translate it, resolve ambiguities, or add inferred requirements.
4. Create the `USER_INPUT` journal entry according to `references/JOURNAL.md`.
5. Commit `SPEC-DRAFT.md` and the journal update.

Example:

```markdown
# Raw User Input

Build a todo list API with CRUD endpoints.
```

Commit:

```text
spec-driven-tdd: capture raw user input for <spec ID>
```

`SPEC-DRAFT.md` is now immutable. It is not reviewed.

## Phase 1 -- Derive, Review, and Correct SPEC.md

Create `SPEC.md` from `SPEC-DRAFT.md`.

`SPEC.md` is the normalized working specification. It may add structure, but it
MUST NOT invent requirements unsupported by the raw input or recorded clarification.

`SPEC.md` should contain:
- a reference to `SPEC-DRAFT.md`;
- entities;
- behaviors;
- constraints;
- acceptance criteria;
- open questions;
- resolved clarifications.

Commit `SPEC.md` and record the completed specification step in the journal.

Then request an independent review of the committed `SPEC.md`.

The reviewer checks:
- Are all acceptance criteria unambiguous and observable?
- Does `SPEC.md` remain faithful to `SPEC-DRAFT.md` and recorded clarifications?
- Are there contradictions?
- Can tests be written from the acceptance criteria?
- Are constraints and edge cases sufficient?
- Are unsupported assumptions present?

```python
delegate_task(
    goal="Review only: assess the committed SPEC.md for fidelity, completeness, consistency, and testability. Do not modify files or implement changes.",
    context="Artifact: SPEC.md
Source: SPEC-DRAFT.md
Commit: <hash>

" + spec_text,
    toolsets=[]
)
```

If the verdict is `PASS`, proceed to task decomposition.

If the verdict is `FAIL`:
1. the delegated reviewer stops;
2. the primary agent edits `SPEC.md`;
3. commit the corrected `SPEC.md`;
4. update and commit the journal;
5. request a fresh review of `SPEC.md`.

If the verdict is `NEEDS_CLARIFICATION`:
1. ask the user;
2. preserve the clarification in the journal;
3. update `SPEC.md`;
4. commit it;
5. request a fresh review.

Never modify `SPEC-DRAFT.md`.

## Phase 2 -- Task Decomposition + Review (from reviewed SPEC.md)

Use reviewed `SPEC.md` to break the work into tasks. Each task maps to one acceptance criterion from `SPEC.md`.

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
    goal="Review only: assess this committed task decomposition for appropriate granularity. Do not modify files or implement changes.",
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
    goal="""Review only. Do not modify files, fix the test, or advance the workflow. Review the test and RED result:
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
    goal="Review only: assess the committed GREEN implementation for minimality, correctness, and spec compliance. Do not modify files or implement fixes.",
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
- Are all acceptance criteria from reviewed `SPEC.md` covered by tests?
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
- Journal file `JOURNAL_SDD_TDD_SKILL.log` exists, is updated for every completed step and review result

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

# 2. Capture immutable raw input, then derive editable SPEC.md
raw_user_input = """..."""
working_spec = derive_spec(raw_user_input)
spec_jid = jlog(
    "SPEC_SPEC",
    "S-SDT-01",
    "COMPLETED",
    detail="Created editable SPEC.md from immutable SPEC-DRAFT.md",
)

# 3. REVIEW SPEC (Phase 1)
review = delegate_task(
    goal="Review only: assess this committed specification for completeness and testability. Do not modify files or implement changes.",
    context="Artifact: SPEC.md\nSource: SPEC-DRAFT.md\n\n" + working_spec,
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

### Review Delegation

Each review MUST use a separate `delegate_task` call with fresh context.

A review request MUST identify exactly one artifact and one review scope.
It MUST explicitly say:

```text
Review only. Do not modify files, implement fixes, execute later stages,
or run the complete workflow. Return a verdict and findings.
```

If the verdict is `FAIL` or `NEEDS_CLARIFICATION`, the delegated reviewer stops.
The primary agent applies the fix, commits it, updates the journal, and submits
the corrected artifact through a new review-only `delegate_task` call.

## SPEC.md Format Example

> **Full reference:** See [SPEC-EXAMPLE.md](references/SPEC-EXAMPLE.md) for a complete, end-to-end walkthrough of the pipeline (Counter API demo). The examples below are quick inline references.

### Structured `SPEC.md` (recommended)

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

### Raw input accepted in `SPEC-DRAFT.md`

```
Build a counter component:
- Starts at 0
- increment() -> +1
- decrement() -> -1
- Can't go below 0
- get_value() returns current
```

## Pitfalls

- **Spec too vague** -- ask the user, record the clarification, update `SPEC.md`, commit, and re-review. Never edit `SPEC-DRAFT.md`.
- **Existing-codebase spec trap** -- first capture the raw request in `SPEC-DRAFT.md`. Then inspect the codebase while deriving `SPEC.md`. In `SPEC.md`, mark each acceptance criterion as Already works, Partial, or Missing. Existing code is evidence, not the specification.
- **Ambiguous user terminology** -- preserve the original wording in `SPEC-DRAFT.md`, add an open question to `SPEC.md`, ask the user, record the answer, update `SPEC.md`, and re-review it. Never silently interpret ambiguous requirements.
- **Tests too coupled to implementation** -- test behavior, not internals
- **Skipping RED verification** -- if you didn't see it fail, you're testing existing behavior
- **Skipping review** -- independent reviewer catches things you normalized
- **Large tasks** -- if a task takes more than 5 minutes, split it further
- **Reviewer has no spec context** -- always pass the relevant `SPEC.md` section to the reviewer
- **SpecKit compatibility** -- SpecKit `.spec.md` files can be parsed as-is; extract requirements from the "Specification" section
- **Journal not initialized** -- create JOURNAL_SDD_TDD_SKILL.log at project start. No journal = no traceability.
- **PARENT chain broken** -- always pass the previous JID to the next journal entry. Without PARENT, traceability across steps is lost.
- **Journal entries not post-factum** -- write entries AFTER completing the step, not before. STATUS must reflect the actual outcome.
- **Spec ID collision** -- use unique hierarchical spec IDs (`S-SDT-01.01`, not just "task1"). Flat IDs break parent-child traceability.
- **Mixed-language artifacts** -- preserve raw input in its original language in `SPEC-DRAFT.md`; write `SPEC.md` and all other derived active artifacts in English.
- **README self-consistency** -- after modifying the skill's file structure (adding/removing references, templates, or core files), the README's "What's Included" table and result directory tree must be updated to match. The table must list ALL R1 files (including README.md itself -- it is easy to forget self-reference). Stale directory entries (e.g. a `templates/` line in the tree after templates were removed) silently mislead users.
- **Cross-reference staleness** -- every local `references/` link in SKILL.md must point to an existing file in the installed skill. After adding or removing reference files, verify all SKILL.md references resolve. Unused files (installed but not referenced) and broken links (referenced but not installed) both degrade the skill.

## References

- [JOURNAL.md](references/JOURNAL.md) -- **Complete journal specification.** Entry format, mandatory fields, validation rules, branching model, examples of correct/incorrect journals. Required reading before writing or validating a journal.
- [SPEC-EXAMPLE.md](references/SPEC-EXAMPLE.md) -- **Canonical reference artifact.** Full Counter API demo walkthrough showing every stage of the pipeline from user input to DONE. Ships with this skill. Read it to see the complete workflow including immutable input capture, editable `SPEC.md`, commit-before-review, the journal loop, and review scopes per stage.
