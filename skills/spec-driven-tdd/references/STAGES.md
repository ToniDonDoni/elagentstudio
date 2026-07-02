# Stage-by-Stage Procedure (Standalone Mode)

This document defines the stage-by-stage procedure for the Spec-Driven TDD
pipeline in **standalone mode** — when there is no MCP task broker and the
implementer walks the artifact chain directly.

In broker mode the implementer does **not** read this document; the broker
loads the orchestrator role file and applies the same stage order, but the
implementer only ever sees one task at a time.

The four mandatory principles, the artifact chain, the role separation, and
the non-negotiable rules are defined in `../SKILL.md` and are not repeated
here. The journal format and entry types are defined in `JOURNAL.md`.

## Stage 0 — Capture User Input

### Artifact: `.sddtdd_skill/SPEC-DRAFT.md`

`.sddtdd_skill/SPEC-DRAFT.md` preserves the original user request exactly as received.

It is a source record, not an agent-authored interpretation.

It MUST:

- preserve the original wording;
- preserve the original language;
- be created before normalization or analysis;
- be committed once;
- remain immutable.

It MUST NOT:

- contain inferred requirements;
- contain normalized acceptance criteria;
- contain architecture decisions;
- be translated;
- be corrected;
- be semantically reviewed;
- be edited after the first commit.

Later clarifications are recorded in the journal and incorporated into
`.sddtdd_skill/SPEC.md`. They do not rewrite historical user input.

Because `.sddtdd_skill/SPEC-DRAFT.md` is raw user input rather than an agent-generated
solution artifact, it is exempt from semantic review. Its capture and
commit are still journaled.

## Stage 1 — Requirements

### Artifact: `.sddtdd_skill/SPEC.md`

`.sddtdd_skill/SPEC.md` is the editable working specification derived from
`.sddtdd_skill/SPEC-DRAFT.md`. It defines what the system must do.

### Required content

`.sddtdd_skill/SPEC.md` SHOULD contain:

- reference to `.sddtdd_skill/SPEC-DRAFT.md`;
- system goal;
- functional requirements;
- non-functional requirements;
- constraints;
- entities;
- external interfaces;
- observable acceptance criteria;
- edge cases;
- open questions;
- recorded clarifications.

Every requirement MUST have a stable identifier, e.g. `FR-001`, `NFR-001`.

### Review scope

The independent reviewer checks:

- fidelity to `.sddtdd_skill/SPEC-DRAFT.md` and recorded clarifications;
- completeness;
- internal consistency;
- absence of unsupported assumptions;
- testability of functional requirements;
- measurability of non-functional requirements;
- clarity and observability of acceptance criteria;
- explicit treatment of ambiguities and edge cases.

### Gate

Architecture work MUST NOT begin until `.sddtdd_skill/SPEC.md` receives `PASS`.

On `FAIL`, the primary agent edits `.sddtdd_skill/SPEC.md`, commits it, updates the
journal, and requests a fresh review.

On `NEEDS_CLARIFICATION`, the primary agent asks the user, records the
answer, updates `.sddtdd_skill/SPEC.md`, commits it, and requests a fresh review.

`.sddtdd_skill/SPEC-DRAFT.md` remains unchanged.

## Stage 2 — Technical and Architectural Design

### Artifact: `.sddtdd_skill/ARCHITECTURE.md`

`.sddtdd_skill/ARCHITECTURE.md` defines how the reviewed requirements will be
implemented. It is derived from reviewed `.sddtdd_skill/SPEC.md`.

### Required content

`.sddtdd_skill/ARCHITECTURE.md` SHOULD contain:

- architecture overview;
- major components;
- component responsibilities;
- data ownership;
- data model;
- external interfaces;
- persistence decisions;
- security decisions;
- performance and scalability decisions;
- reliability and operational constraints;
- deployment assumptions;
- mapping from technical decisions to requirement IDs;
- trade-offs;
- rejected alternatives;
- known risks.

Every significant technical decision MUST reference the requirements that
justify it.

### Review scope

The independent reviewer checks:

- support for all relevant functional requirements;
- treatment of non-functional requirements;
- coherence of component boundaries;
- clarity of interfaces and data ownership;
- consistency of technical decisions;
- absence of unsupported complexity;
- feasibility;
- security and reliability risks;
- documented trade-offs and alternatives;
- traceability from decisions to requirements.

### Gate

Task decomposition MUST NOT begin until `.sddtdd_skill/ARCHITECTURE.md` receives `PASS`.

## Stage 3 — Task Decomposition

### Artifact: `.sddtdd_skill/TASKS.md`

`.sddtdd_skill/TASKS.md` decomposes reviewed requirements and architecture into
implementable tasks.

### Required task fields

Every task MUST contain:

```text
TASK_ID
PARENT_TASK_ID
ROOT_USER_INPUT_ID
REQUIREMENT_IDS
ARCHITECTURE_REFERENCES
ACCEPTANCE
DEPENDENCIES
```

Every task MUST:

- reference one or more reviewed requirement IDs;
- reference relevant reviewed architectural decisions;
- define an observable completion condition;
- be small enough to implement and review independently;
- identify one direct parent task;
- preserve the root user-input task ID;
- declare real dependencies separately from parent-child hierarchy.

Sibling tasks share the same parent. Sibling tasks MUST NOT be connected
merely because they are executed sequentially.

### Review scope

The independent reviewer checks:

- coverage of all functional requirements;
- coverage of automatically testable non-functional requirements;
- traceability to reviewed requirements and architecture;
- correct parent-child task relationships;
- correct dependency declarations;
- task independence and granularity;
- absence of missing or duplicate work;
- clear acceptance conditions;
- feasible execution order.

### Gate

Per-task implementation work MUST NOT begin until `.sddtdd_skill/TASKS.md` receives
`PASS`.

## Stage 4 — Per-Task RED-GREEN Cycle

Every implementation task follows the same mandatory procedure.

### Step 4.1 — Select reviewed inputs

Before writing tests, identify:

- task ID;
- referenced requirement IDs;
- referenced architecture decisions;
- task acceptance criteria;
- relevant existing tests and implementation.

Record the selected task in the journal.

### Step 4.2 — Create test artifact

Create automated tests that prove the task's required observable behavior.

The primary test MUST be acceptance-oriented and exercise the behavior at
the highest practical level available for the task. A full-system
end-to-end test is the default. When end-to-end execution is impossible,
use the closest stable boundary that still proves the required behavior
(API-level, service-level, component-level, or integration).

Unit tests MAY supplement the acceptance-oriented test but MUST NOT
replace it.

Tests MUST be derived from reviewed requirements and task acceptance
criteria. Commit the test artifact. Record test creation in the journal.

### Step 4.3 — Establish RED

Run the new tests before implementing the required behavior. Capture
evidence showing that the tests fail because the behavior is absent.

RED evidence MUST identify:

- executed test scope;
- failure result;
- failure reason;
- relevant environment details when needed.

### Step 4.4 — Review test and RED

Call `mcp_sddtdd_review_review` to request an independent review of the
test artifact, the referenced requirements, the task acceptance criteria,
and the RED evidence. The reviewer checks whether the tests prove the
required behavior, whether RED failed for the expected missing-behavior
reason, and whether an incorrect implementation would be detected.

Record the verdict as `RED_REVIEW`, commit the journal update, and use
that review entry as the parent of the next workflow entry.

Implementation may begin only when a committed `RED_REVIEW` entry has
`STATUS: PASS`.

On `FAIL`, record `RED_REVIEW: FAIL` before fixing the tests or test
setup, rerunning RED, committing the correction, and requesting a
follow-up review.

### Step 4.5 — Create minimum implementation

After reviewed RED receives `PASS`, create the minimum implementation
required to satisfy the reviewed requirements, architecture, task, and
tests. Do not add unrelated behavior. Commit the implementation. Record
implementation creation in the journal.

### Step 4.6 — Establish GREEN

Run the reviewed task tests and all relevant previously passing tests.
Capture GREEN evidence showing that the new tests pass, the relevant
existing tests still pass, and the committed implementation is the tested
state.

### Step 4.7 — Review implementation and GREEN

Call `mcp_sddtdd_review_review` to request an independent review of the
implementation artifact, the reviewed requirements, architecture, task,
tests, and GREEN evidence. The reviewer checks requirement compliance,
architecture compliance, passing evidence, correctness, minimality,
absence of unrelated changes, security and reliability concerns,
maintainability, and absence of regressions in the reviewed scope.

Record the verdict as `GREEN_REVIEW`, commit the journal update, and use
that review entry as the terminal entry of the task branch.

The task is complete only when a committed `GREEN_REVIEW` entry has
`STATUS: PASS`.

## Stage 5 — Task Convergence

When all required task branches have passed implementation and GREEN
review, create the `TASKS_COMPLETE` journal event. The convergence event
MUST reference the terminal reviewed entry of every completed task
branch. Regression MUST NOT begin before all required task branches have
converged.

## Stage 6 — Regression

### Artifact: Regression evidence

Run the complete automated test suite required to verify the final
committed implementation. Regression MUST include all tests created for
the current requirements, all previously existing tests for the affected
application or component, all relevant integration tests, all relevant
end-to-end and acceptance tests, all automated checks for applicable
non-functional requirements, and tests for shared components that may be
affected by the changes.

For a repository with multiple independent projects, run the complete
required suite for every affected project and every shared component
that may be impacted.

If any required test or test suite cannot be executed, record which tests
were not executed, why they could not be executed, what risk remains, and
what alternative evidence was collected.

Regression evidence MUST record the exact commands executed, the exact
commit under test, the executed test scope, the total number of passed,
failed, skipped, and omitted tests, failure details, relevant environment
and configuration, and any known limitations in the collected evidence.

Regression is complete only when all required tests pass, no required
test was silently omitted, every exception is explicitly documented, and
the regression evidence corresponds to the final committed state.

### Review scope

The independent reviewer checks whether the executed test scope is
complete for the affected system, whether all newly added and previously
existing relevant tests were executed, whether all required tests passed,
whether skipped or omitted tests are justified and documented, whether
previously completed behavior remains valid, whether automatically
testable requirements are covered, and whether the evidence corresponds
to the exact final committed state.

## Commit rules

Every reviewable artifact and every evidence file named in a review
request MUST be committed before review. The working tree MUST be clean
before `mcp_sddtdd_review_review` is called. The reviewer inspects only
files loaded by the MCP server from its captured committed `HEAD`, never
mutable working-tree content.

After every MCP review response:

- treat the response as verdict source data, not as a completed
  workflow event;
- append the corresponding review entry to the journal;
- commit the journal update immediately;
- use the committed review entry JID as the direct `PARENT` of the next
  workflow entry;
- do not proceed to the next stage before that journal commit exists;
- on `FAIL` or `NEEDS_CLARIFICATION`, do not begin corrections before
  that journal commit exists.

After `FAIL`:

- do not amend reviewed history;
- create a correction commit;
- rerun required checks;
- update the journal;
- request a fresh review.

A step is not complete until both the artifact and its journal event are
committed.

## Escalation

Each artifact has its own review-attempt counter. If the configured
review limit is reached without `PASS`, stop the workflow and escalate to
the user. Record the escalation in the journal.

The user may clarify requirements, revise the approved direction, split
the artifact, cancel the work, or explicitly force continuation. A
forced continuation MUST be recorded and MUST NOT be represented as an
ordinary reviewer `PASS`.

## Completion conditions

The workflow is complete only when:

- `.sddtdd_skill/SPEC-DRAFT.md` preserves the original request unchanged;
- `.sddtdd_skill/SPEC.md` has independent review `PASS`;
- `.sddtdd_skill/ARCHITECTURE.md` has independent review `PASS`;
- `.sddtdd_skill/TASKS.md` has independent review `PASS`;
- every agent-generated test artifact has independent review `PASS`;
- every automatically testable behavior has valid reviewed RED evidence;
- every implementation artifact has independent review `PASS`;
- every automatically testable behavior has valid reviewed GREEN
  evidence;
- all task branches have converged;
- regression evidence has independent review `PASS`;
- all required tests pass;
- traceability is complete;
- the journal is complete and internally connected;
- every deliberate deviation is explicitly recorded and remains visible
  as missing evidence rather than an ordinary `PASS`;
- all required artifacts are committed;
- the working tree contains no uncommitted solution artifacts.
