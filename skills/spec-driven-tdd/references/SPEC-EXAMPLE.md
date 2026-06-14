# Demo Feature Case: Counter API with Commit-Based Spec-Driven TDD

## Purpose

This demo shows how spec-driven-tdd works when every artifact is treated declaratively and immutably.

Core idea:

Every meaningful change creates an artifact.  
Every artifact is committed.  
Every committed artifact is reviewed.  
Every review result is written to JOURNAL_SDD_TDD_SKILL.log.  
Every JOURNAL_SDD_TDD_SKILL.log update is also committed.  
Every fix after review is a new commit.

Nothing is silently edited.  
Nothing is reviewed from an uncommitted working tree.  
No stage moves forward without review evidence and journal evidence.

## Pipeline

Full pipeline:

User Input  
 ->  SPEC-DRAFT.md  
 ->  commit  
 ->  review spec  
 ->  JOURNAL_SDD_TDD_SKILL.log update  
 ->  commit journal  
 ->  TASKS.md  
 ->  commit  
 ->  review tasks  
 ->  JOURNAL_SDD_TDD_SKILL.log update  
 ->  commit journal  
 ->  RED (write test + run, expect failure)
 ->  commit
 ->  review RED
 ->  JOURNAL_SDD_TDD_SKILL.log update
 ->  commit journal
 ->  implementation code  
 ->  commit  
 ->  review GREEN  
 ->  JOURNAL_SDD_TDD_SKILL.log update  
 ->  commit journal  
 ->  optional refactor  
 ->  commit  
 ->  review refactor  
 ->  JOURNAL_SDD_TDD_SKILL.log update  
 ->  commit journal  
 ->  regression run  
 ->  JOURNAL_SDD_TDD_SKILL.log update  
 ->  commit journal  
 ->  DONE

## Global Rules

### Rule 1 -- Every artifact is committed

Any created or changed artifact must be committed before it can be reviewed.

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

### Rule 2 -- Review only committed state

Reviewer must review a commit, not a dirty working tree.

Every review request must include:

- commit hash
- artifact path
- spec ID
- task ID if applicable
- expected review scope

### Rule 3 -- Every review updates the journal

After every review result, append a record to JOURNAL_SDD_TDD_SKILL.log.

Review outcomes:

- PASS
- FAIL
- NEEDS_CLARIFICATION
- CANCELLED

### Rule 4 -- Journal updates are committed

After appending to JOURNAL_SDD_TDD_SKILL.log, commit the journal change.

The journal commit becomes part of the audit trail.

### Rule 5 -- Every fix is a new commit

If review fails, do not amend history unless explicitly allowed.

Default behavior:

- create a fix commit
- review the fix commit
- append review result to journal
- commit journal update

### Rule 6 -- No silent mutation of immutable input

SPEC-DRAFT.md is immutable after initial commit.

If the user clarifies or changes something, write it to JOURNAL_SDD_TDD_SKILL.log and create a derived spec amendment artifact if needed.

Original input stays preserved.

## Demo Feature: Counter API

Spec ID: S-DEMO-01  
Title: Counter API  
Status: Draft  
Parent: -- 

Build a simple in-memory counter.

Requirements:

S-DEMO-01.01 -- Initial value  
A new counter starts at 0.

S-DEMO-01.02 -- Increment  
Calling increment() increases the counter value by 1.

S-DEMO-01.03 -- Decrement  
Calling decrement() decreases the counter value by 1.

S-DEMO-01.04 -- Lower bound  
The counter must never go below 0.

S-DEMO-01.05 -- Read current value  
Calling get_value() returns the current counter value.

## Expected Files

SPEC-DRAFT.md  
Immutable original feature request.

TASKS.md  
Task decomposition. Each task maps to exactly one acceptance criterion.

JOURNAL_SDD_TDD_SKILL.log  
Append-only audit trail. Every event gets a JID.

tests/test_counter.py  
Acceptance-oriented tests.

counter.py  
Minimal production implementation.

## Stage 0 -- User Input

User provides the initial feature request:

"Build a simple counter. It starts at zero, can increment and decrement, never goes below zero, and exposes current value."

Action:

Create initial journal entry for external input.

Journal entry:

=== J-20260614-100000-001 ===
TYPE: USER_INPUT
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-000
PARENT_TASK_ID: --
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Initial feature request received.

Then commit:

Commit message:

spec-driven-tdd: record initial user input for S-DEMO-01

Review:

No feature review yet. This only records incoming context.

## Stage 1 -- Create Immutable Spec Draft

Action:

Create SPEC-DRAFT.md.

It contains:

- root spec ID
- child spec IDs
- requirements
- acceptance criteria
- parent-child structure

Important:

SPEC-DRAFT.md must not be edited after this stage.

Commit:

spec: add immutable counter API draft S-DEMO-01

Review request:

Review commit <hash>.

Scope:

- Is the spec testable?
- Are all acceptance criteria observable?
- Are requirements unambiguous?
- Are child spec IDs valid?
- Is the lower-bound behavior clear?

Expected review result:

PASS.

Journal update:

=== J-20260614-100000-002 ===
TYPE: SPEC_SPEC
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-001
ROOT: J-20260614-100000-001
DETAIL: Counter API spec draft created.

=== J-20260614-100000-003 ===
TYPE: SPEC_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-002
ROOT: J-20260614-100000-001
DETAIL: Spec is testable and decomposable. Reviewed commit <hash>.

Commit journal:

journal: record spec review for S-DEMO-01

If review fails:

- create SPEC-AMENDMENT-001.md or update a non-immutable derived spec artifact
- commit fix
- re-review
- journal FAIL and retry events
- commit journal

## Stage 2 -- Decompose Tasks

Action:

Create TASKS.md.

Task list:

T-DEMO-01-001  
Spec: S-DEMO-01.01  
Acceptance: a new counter returns 0 from get_value().

T-DEMO-01-002  
Spec: S-DEMO-01.02  
Acceptance: after one increment(), get_value() returns 1.

T-DEMO-01-003  
Spec: S-DEMO-01.03  
Acceptance: after two increments and one decrement, get_value() returns 1.

T-DEMO-01-004  
Spec: S-DEMO-01.04  
Acceptance: calling decrement() on a new counter keeps value at 0.

T-DEMO-01-005  
Spec: S-DEMO-01.05  
Acceptance: get_value() always returns current state after operations.

Commit:

tasks: decompose counter API spec into TDD tasks

Review request:

Review commit <hash>.

Scope:

- Does every task map to exactly one acceptance criterion?
- Are task IDs linked to spec IDs?
- Is task order reasonable?
- Are tasks small enough for TDD?
- Is traceability preserved?

Expected review result:

PASS.

Journal update:

=== J-20260614-100000-004 ===
TYPE: DECOMPOSE
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-003
ROOT: J-20260614-100000-001
DETAIL: Spec decomposed into 5 tasks (T-DEMO-01-001 through T-DEMO-01-005).

=== J-20260614-100000-005 ===
TYPE: TASK_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-004
ROOT: J-20260614-100000-001
DETAIL: TASKS.md maps five tasks to five acceptance criteria. Reviewed commit <hash>.

Commit journal:

journal: record task decomposition review for S-DEMO-01

## Stage 3 -- Implement Task T-DEMO-01-004

This walkthrough focuses on lower-bound behavior.

Task:

T-DEMO-01-004  
Spec: S-DEMO-01.04  
Acceptance: calling decrement() on a new counter keeps value at 0.

## Stage 3.1 -- Select Task (T-DEMO-01-004)

Action:

Agent chooses T-DEMO-01-004.

Journal update:

=== J-20260614-100000-006 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.04
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected lower-bound behavior task T-DEMO-01-004.

Commit journal:

journal: select lower-bound counter task

## Stage 3.2 -- RED (Write Test + Run, Expect Failure)

Action:

Write a failing test targeting the acceptance criterion, then run it immediately.

Test intent:

- create a new counter
- call decrement()
- verify current value is still 0
- test public behavior only
- do not inspect private fields

Expected result:

The test fails before implementation.

Valid failure reasons:

- Counter does not exist
- decrement() does not exist
- lower-bound behavior is missing

Invalid failure reasons:

- syntax error
- broken import unrelated to the feature
- bad fixture
- test cannot run
- environment failure

Commit RED artifact: test file + RED evidence (test output) + journal entry

```
test: add lower-bound acceptance test for counter
```

Then run the test and confirm FAIL.

Journal update:

=== J-20260614-100000-007 ===
TYPE: RED
SPEC: S-DEMO-01.04
STATUS: COMPLETED
PARENT: J-20260614-100000-006
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Test written and RED — failure confirms required behavior is missing.

Commit journal:

journal: record RED result for S-DEMO-01.04

Review request:

Review commit <hash> and RED evidence.

Scope:

- Does the test verify S-DEMO-01.04?
- Does it test behavior, not implementation details?
- Is it focused on exactly one acceptance criterion?
- Would it fail without lower-bound behavior?
- Did the test actually fail?
- Did it fail for the correct reason (missing behavior, not a broken test)?
- Is terminal evidence recorded?

Expected review result:

PASS.

Journal update:

=== J-20260614-100000-008 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.04
STATUS: PASS
PARENT: J-20260614-100000-007
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: RED is valid. Test matches acceptance criterion and failure proves behavior is not implemented. Reviewed commit <hash>.

Commit journal:

journal: record RED review for S-DEMO-01.04

If review fails:

- fix test/setup in a new commit
- re-run test
- journal retry
- commit journal
- re-review

## Stage 3.3 -- GREEN

Action:

Create or update counter.py.

Implementation rule:

Write the smallest code needed to pass the focused test.

Allowed:

- create Counter
- initialize value to 0
- implement decrement() with lower-bound behavior
- implement get_value() if needed by the test

Forbidden:

- implement unrelated future behavior unless required by current test
- refactor unrelated files
- change the test during GREEN unless the test has an obvious mechanical error

Run the focused test again.

Expected result:

PASS.

Commit:

impl: add minimal lower-bound counter behavior

Review request:

Review commit <hash>.

Scope:

- Does the focused test pass?
- Is implementation minimal?
- Does implementation satisfy S-DEMO-01.04?
- Were tests preserved during GREEN?
- Are there unrelated changes?

Expected review result:

PASS.

Journal update:

=== J-20260614-100000-009 ===
TYPE: GREEN
SPEC: S-DEMO-01.04
STATUS: COMPLETED
PARENT: J-20260614-100000-008
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Minimal lower-bound implementation complete.

=== J-20260614-100000-010 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.04
STATUS: PASS
PARENT: J-20260614-100000-009
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Minimal implementation satisfies lower-bound behavior. Reviewed commit <hash>.

Commit journal:

journal: record GREEN review for S-DEMO-01.04

If GREEN review fails:

- fix code in a new commit
- do not rewrite test unless review explicitly identifies a test defect
- run focused test again
- journal fix/retry
- commit journal
- re-review

## Stage 3.4 -- Refactor Decision

Action:

Agent decides whether refactor is needed.

For this demo:

No refactor is needed.

Journal update:

=== J-20260614-100000-011 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.04
STATUS: COMPLETED
PARENT: J-20260614-100000-010
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Refactor skipped; implementation is already minimal.

Commit journal:

journal: record refactor decision for S-DEMO-01.04

If refactor is needed:

- change code only, not behavior
- run focused and regression tests
- commit refactor
- review refactor commit
- append review result to journal
- commit journal

## Stage 3.5 -- Per-Task Regression

Action:

Run the focused test for T-DEMO-01-004 only.

Expected result:

PASS.

Journal update:

=== J-20260614-100000-012 ===
TYPE: REGRESSION
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-011
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-004
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Per-task regression for T-DEMO-01-004 — single-task test passes.

Commit journal:

journal: record per-task regression for T-DEMO-01-004

## Stage 3.6 -- Task Branch Complete

Completion criteria for T-DEMO-01-004:

- task selected and journaled
- RED completed and committed (test written + run, RED confirmed)
- RED reviewed (covers test quality + RED result)
- review result journaled and committed
- implementation committed
- GREEN reviewed
- GREEN review journaled and committed
- refactor decision journaled and committed
- per-task regression completed and journaled

Note:

There is no task-level DONE. Reaching GREEN_REVIEW(PASS) through the cycle
means the task branch is complete. All task branches converge at
TASKS_COMPLETE before proceeding to full REGRESSION.

## Stage 4 -- Implement Remaining Tasks

Each remaining task follows the same cycle as T-DEMO-01-004:
AGENT_DECISION → RED → RED_REVIEW → GREEN → GREEN_REVIEW.
All four task branches are siblings — each starts from the shared
TASK_REVIEW (J-005).

### T-DEMO-01-001 -- Initial value

=== J-20260614-100000-013 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected initial-value task T-DEMO-01-001.

=== J-20260614-100000-014 ===
TYPE: RED
SPEC: S-DEMO-01.01
STATUS: COMPLETED
PARENT: J-20260614-100000-013
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Test written and fails because initial value is not implemented.

=== J-20260614-100000-015 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.01
STATUS: PASS
PARENT: J-20260614-100000-014
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: RED valid. Test confirms initial value behaviour is absent.

=== J-20260614-100000-016 ===
TYPE: GREEN
SPEC: S-DEMO-01.01
STATUS: COMPLETED
PARENT: J-20260614-100000-015
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Initial value implementation complete.

=== J-20260614-100000-017 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.01
STATUS: PASS
PARENT: J-20260614-100000-016
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Initial value test passes. T-DEMO-01-001 complete.

### T-DEMO-01-002 -- Increment

=== J-20260614-100000-018 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.02
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected increment task T-DEMO-01-002.

=== J-20260614-100000-019 ===
TYPE: RED
SPEC: S-DEMO-01.02
STATUS: COMPLETED
PARENT: J-20260614-100000-018
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Increment test written and fails.

=== J-20260614-100000-020 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.02
STATUS: PASS
PARENT: J-20260614-100000-019
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Increment RED valid.

=== J-20260614-100000-021 ===
TYPE: GREEN
SPEC: S-DEMO-01.02
STATUS: COMPLETED
PARENT: J-20260614-100000-020
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Increment implementation complete.

=== J-20260614-100000-022 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.02
STATUS: PASS
PARENT: J-20260614-100000-021
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Increment test passes. T-DEMO-01-002 complete.

### T-DEMO-01-003 -- Decrement

=== J-20260614-100000-023 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.03
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-003
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected decrement task T-DEMO-01-003.

=== J-20260614-100000-024 ===
TYPE: RED
SPEC: S-DEMO-01.03
STATUS: COMPLETED
PARENT: J-20260614-100000-023
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-003
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Decrement test written and fails.

=== J-20260614-100000-025 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.03
STATUS: PASS
PARENT: J-20260614-100000-024
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-003
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Decrement RED valid.

=== J-20260614-100000-026 ===
TYPE: GREEN
SPEC: S-DEMO-01.03
STATUS: COMPLETED
PARENT: J-20260614-100000-025
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-003
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Decrement implementation complete.

=== J-20260614-100000-027 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.03
STATUS: PASS
PARENT: J-20260614-100000-026
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-003
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Decrement test passes. T-DEMO-01-003 complete.

### T-DEMO-01-005 -- Read current value

=== J-20260614-100000-028 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.05
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-005
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected read-value task T-DEMO-01-005.

=== J-20260614-100000-029 ===
TYPE: RED
SPEC: S-DEMO-01.05
STATUS: COMPLETED
PARENT: J-20260614-100000-028
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-005
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Get-value test written and fails.

=== J-20260614-100000-030 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.05
STATUS: PASS
PARENT: J-20260614-100000-029
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-005
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Get-value RED valid.

=== J-20260614-100000-031 ===
TYPE: GREEN
SPEC: S-DEMO-01.05
STATUS: COMPLETED
PARENT: J-20260614-100000-030
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-005
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Get-value implementation complete.

=== J-20260614-100000-032 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.05
STATUS: PASS
PARENT: J-20260614-100000-031
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-005
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Get-value test passes. T-DEMO-01-005 complete.

### Convergence -- All Tasks Complete

All five task branches have reached GREEN_REVIEW(PASS):

| Task | GREEN_REVIEW JID |
|------|-----------------|
| T-DEMO-01-004 | J-20260614-100000-010 |
| T-DEMO-01-001 | J-20260614-100000-017 |
| T-DEMO-01-002 | J-20260614-100000-022 |
| T-DEMO-01-003 | J-20260614-100000-027 |
| T-DEMO-01-005 | J-20260614-100000-032 |

Create the convergence barrier:

=== J-20260614-100000-033 ===
TYPE: TASKS_COMPLETE
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
DEPENDS: J-20260614-100000-010, J-20260614-100000-017, J-20260614-100000-022, J-20260614-100000-027, J-20260614-100000-032
DETAIL: All 5 task branches complete.

=== J-20260614-100000-034 ===
TYPE: REGRESSION
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-033
ROOT: J-20260614-100000-001
DETAIL: Full regression -- all 5 task tests pass.

=== J-20260614-100000-035 ===
TYPE: REGRESSION_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-034
ROOT: J-20260614-100000-001
DETAIL: Regression evidence accepted.

Commit journal:

journal: record convergence, regression, and regression review for S-DEMO-01


## Stage 5 -- Final Feature Review

Action:

After all tasks are complete, run full verification.

Checks:

- all acceptance criteria are covered
- every spec ID has at least one task
- every task has a test
- every RED was reviewed
- every GREEN was reviewed
- every refactor was reviewed or explicitly skipped
- every journal update was committed
- every artifact has a commit hash
- all tests pass
- traceability works from spec to journal to task to test to implementation

Commit:

verification: add final counter API completion evidence

Review request:

Review final feature commit <hash>.

Scope:

- Does implementation satisfy S-DEMO-01?
- Is traceability complete?
- Are all journal records present?
- Are commit boundaries clean?
- Is there any unreviewed artifact?

Expected result:

PASS.

Journal update:

=== J-20260614-100000-036 ===
TYPE: FINAL_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-035
ROOT: J-20260614-100000-001
DETAIL: Full feature review passed. All spec items implemented through committed TDD workflow.

Commit journal:

journal: record final feature review for S-DEMO-01

## Stage 6 -- Final Done

Journal update:

=== J-20260614-100000-037 ===
TYPE: DONE
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-036
ROOT: J-20260614-100000-001
DETAIL: Counter API completed through commit-based spec-driven TDD pipeline.

Commit journal:

journal: mark counter API feature complete

## Traceability Example

Spec:

S-DEMO-01.04

Task:

T-DEMO-01-004

Test artifact:

tests/test_counter.py

Implementation artifact:

counter.py

Journal records:

Search S-DEMO-01.04 in JOURNAL_SDD_TDD_SKILL.log.

Commits:

Each artifact and each journal update has its own commit.

Review evidence:

Each reviewed stage references the reviewed commit hash.

## Final Rule

A stage is not complete when the file is edited.

A stage is complete only when:

1. the artifact exists,
2. the artifact is committed,
3. the commit is reviewed,
4. the review result is written to JOURNAL_SDD_TDD_SKILL.log,
5. the journal update is committed.

That is the contract.
