# Demo Feature Case: Counter API with Commit-Based Spec-Driven TDD

## Purpose

This demo shows how spec-driven-tdd works when every artifact is treated declaratively and immutably.

Core idea:

Every meaningful change creates an artifact.  
Every artifact is committed.  
Every committed artifact is reviewed.  
Every review result is written to JOURNAL.log.  
Every JOURNAL.log update is also committed.  
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
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  TASKS.md  
 ->  commit  
 ->  review tasks  
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  test file  
 ->  commit  
 ->  review test  
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  RED test run  
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  review RED  
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  implementation code  
 ->  commit  
 ->  review GREEN  
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  optional refactor  
 ->  commit  
 ->  review refactor  
 ->  JOURNAL.log update  
 ->  commit journal  
 ->  regression run  
 ->  JOURNAL.log update  
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

After every review result, append a record to JOURNAL.log.

Review outcomes:

- PASS
- FAIL
- NEEDS_CLARIFICATION
- CANCELLED

### Rule 4 -- Journal updates are committed

After appending to JOURNAL.log, commit the journal change.

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

If the user clarifies or changes something, write it to JOURNAL.log and create a derived spec amendment artifact if needed.

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

JOURNAL.log  
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

TYPE: USER_INPUT  
SPEC: S-DEMO-01  
STATUS: COMPLETED  
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

TYPE: SPEC_REVIEW  
SPEC: S-DEMO-01  
STATUS: PASS  
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

T-DEMO-01.01  
Spec: S-DEMO-01.01  
Acceptance: a new counter returns 0 from get_value().

T-DEMO-01.02  
Spec: S-DEMO-01.02  
Acceptance: after one increment(), get_value() returns 1.

T-DEMO-01.03  
Spec: S-DEMO-01.03  
Acceptance: after two increments and one decrement, get_value() returns 1.

T-DEMO-01.04  
Spec: S-DEMO-01.04  
Acceptance: calling decrement() on a new counter keeps value at 0.

T-DEMO-01.05  
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

TYPE: TASK_REVIEW  
SPEC: S-DEMO-01  
STATUS: PASS  
DETAIL: TASKS.md maps five tasks to five acceptance criteria. Reviewed commit <hash>.

Commit journal:

journal: record task decomposition review for S-DEMO-01

## Stage 3 -- Implement Task T-DEMO-01.04

This walkthrough focuses on lower-bound behavior.

Task:

T-DEMO-01.04  
Spec: S-DEMO-01.04  
Acceptance: calling decrement() on a new counter keeps value at 0.

## Stage 3.1 -- Select Task

Action:

Agent chooses T-DEMO-01.04.

Journal update:

TYPE: AGENT_DECISION  
SPEC: S-DEMO-01.04  
STATUS: COMPLETED  
DETAIL: Selected lower-bound behavior task T-DEMO-01.04.

Commit journal:

journal: select lower-bound counter task

## Stage 3.2 -- Write Test

Action:

Create or update tests/test_counter.py.

Test intent:

- create a new counter
- call decrement()
- verify current value is still 0
- test public behavior only
- do not inspect private fields

Commit:

test: add lower-bound acceptance test for counter

Review request:

Review commit <hash>.

Scope:

- Does the test verify S-DEMO-01.04?
- Does it test behavior, not implementation details?
- Is it focused on exactly one acceptance criterion?
- Would it fail without lower-bound behavior?

Expected review result:

PASS.

Journal update:

TYPE: TEST_REVIEW  
SPEC: S-DEMO-01.04  
STATUS: PASS  
DETAIL: Lower-bound test matches acceptance criterion and public behavior. Reviewed commit <hash>.

Commit journal:

journal: record test review for S-DEMO-01.04

If review fails:

- create fix commit for test
- re-review new commit
- append FAIL and retry records to journal
- commit journal after each review/fix

## Stage 3.3 -- RED

Action:

Run the focused test before implementation.

Expected result:

The test fails.

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

Journal update:

TYPE: RED  
SPEC: S-DEMO-01.04  
STATUS: COMPLETED  
DETAIL: Focused test failed before implementation. Failure reason: missing lower-bound behavior.

Commit journal:

journal: record RED result for S-DEMO-01.04

Review request:

Review journal commit <hash> and RED evidence.

Scope:

- Did the test actually fail?
- Did it fail for the correct reason?
- Is this a real RED and not a broken test?
- Is terminal evidence recorded?

Expected review result:

PASS.

Journal update:

TYPE: RED_REVIEW  
SPEC: S-DEMO-01.04  
STATUS: PASS  
DETAIL: RED is valid. Failure proves behavior is not implemented.

Commit journal:

journal: record RED review for S-DEMO-01.04

If RED review fails:

- fix test/setup in a new commit
- run RED again
- journal retry
- commit journal
- re-review

## Stage 3.4 -- GREEN

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

TYPE: GREEN_REVIEW  
SPEC: S-DEMO-01.04  
STATUS: PASS  
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

## Stage 3.5 -- Refactor Decision

Action:

Agent decides whether refactor is needed.

For this demo:

No refactor is needed.

Journal update:

TYPE: AGENT_DECISION  
SPEC: S-DEMO-01.04  
STATUS: COMPLETED  
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

## Stage 3.6 -- Regression Check

Action:

Run all tests created so far.

Expected result:

PASS.

Journal update:

TYPE: REGRESSION  
SPEC: S-DEMO-01.04  
STATUS: PASS  
DETAIL: All existing tests pass after lower-bound implementation.

Commit journal:

journal: record regression result for S-DEMO-01.04

Review request:

Optional but recommended.

Scope:

- Is regression evidence present?
- Are previous task tests still green?
- Did the implementation introduce unrelated breakage?

Journal update if reviewed:

TYPE: REGRESSION_REVIEW  
SPEC: S-DEMO-01.04  
STATUS: PASS  
DETAIL: Regression evidence accepted.

Commit journal:

journal: record regression review for S-DEMO-01.04

## Stage 3.7 -- Mark Task Done

Completion criteria for T-DEMO-01.04:

- task selected and journaled
- test created and committed
- test reviewed
- review result journaled and committed
- RED run journaled and committed
- RED reviewed
- RED review journaled and committed
- implementation committed
- GREEN reviewed
- GREEN review journaled and committed
- refactor decision journaled and committed
- regression result journaled and committed

Journal update:

TYPE: DONE  
SPEC: S-DEMO-01.04  
STATUS: COMPLETED  
DETAIL: Task T-DEMO-01.04 completed with committed artifacts, review gates, and audit trail.

Commit journal:

journal: mark S-DEMO-01.04 complete

## Stage 4 -- Continue Remaining Tasks

Repeat the same pattern for:

- T-DEMO-01.01
- T-DEMO-01.02
- T-DEMO-01.03
- T-DEMO-01.05

Each task follows:

1. select task
2. journal selection
3. commit journal
4. write test
5. commit test
6. review test commit
7. journal review
8. commit journal
9. run RED
10. journal RED
11. commit journal
12. review RED
13. journal RED review
14. commit journal
15. write minimal implementation
16. commit implementation
17. review GREEN commit
18. journal GREEN review
19. commit journal
20. decide refactor
21. commit refactor if any
22. review refactor if any
23. journal refactor result
24. commit journal
25. run regression
26. journal regression
27. commit journal
28. mark task done
29. commit journal

## Stage 5 -- Final Feature Review

Action:

After all tasks are complete, run full verification.

Checks:

- all acceptance criteria are covered
- every spec ID has at least one task
- every task has a test
- every test was reviewed before RED
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

TYPE: FINAL_REVIEW  
SPEC: S-DEMO-01  
STATUS: PASS  
DETAIL: Full feature review passed. All spec items implemented through committed TDD workflow.

Commit journal:

journal: record final feature review for S-DEMO-01

## Stage 6 -- Final Done

Journal update:

TYPE: DONE  
SPEC: S-DEMO-01  
STATUS: COMPLETED  
DETAIL: Counter API completed through commit-based spec-driven TDD pipeline.

Commit journal:

journal: mark counter API feature complete

## Traceability Example

Spec:

S-DEMO-01.04

Task:

T-DEMO-01.04

Test artifact:

tests/test_counter.py

Implementation artifact:

counter.py

Journal records:

Search S-DEMO-01.04 in JOURNAL.log.

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
4. the review result is written to JOURNAL.log,
5. the journal update is committed.

That is the contract.
