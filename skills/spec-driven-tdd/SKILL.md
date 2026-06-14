---
name: spec-driven-tdd
description: "Build software through a traceable artifact pipeline. Every agent-generated artifact is independently reviewed, every automatically testable behavior is implemented through reviewed RED-GREEN TDD, and every workflow event is committed and journaled."
version: 2.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, requirements, architecture, testing, review, traceability, audit]
---

# Spec-Driven TDD

## Purpose

Transform a user request into working software through a sequence of explicit,
traceable, committed, and independently reviewed artifacts, with automated
RED-GREEN testing for every behavior that can be tested automatically.

The workflow has four independent mandatory principles:

1. Every artifact created or modified by the primary agent is reviewed by a
   separate delegated reviewer before later work may depend on it.
2. Every behavior that can be verified automatically is implemented through a
   reviewed RED-GREEN test-driven cycle.
3. Every completed step, review result, correction, and dependency is recorded
   in the journal so the workflow can be reconstructed, diagnosed, and improved.
4. The result is not only working software, but also the reviewed, tested, and
   journaled artifacts that explain how it was produced. They make failures
   diagnosable and help improve the next iteration.

None of these principles replaces another.

A general review does not replace RED-GREEN.

Passing tests do not replace independent review.

The journal does not replace artifacts, reviews, or test evidence.

---

## Scope and Completion

The workflow applies to the explicitly approved scope of the current delivery.

- `IN_SCOPE` requirements and `REQUIRED` tasks must be completed before `DONE`.
- `DEFERRED` and `OUT_OF_SCOPE` items must be recorded but do not block the current delivery.
- `TASKS_COMPLETE` waits only for required task branches in the current scope.
- `DONE` means the approved current scope is complete, not that every possible future feature is finished.
- Non-automatable requirements must define their review method and required evidence in advance.
- The default review limit is 21 attempts per artifact unless the project explicitly defines another limit.

---

## Core Workflow

```text
USER INPUT
→ SPEC-DRAFT.md
→ SPEC.md
→ ARCHITECTURE.md
→ TASKS.md
→ per-task RED-GREEN cycles
→ TASKS_COMPLETE
→ REGRESSION
→ FINAL_REVIEW
→ DONE
```

Every arrow means that the next artifact is derived only from reviewed inputs.

---

## Principle 1 — Every Agent-Generated Artifact Is Reviewed

Every artifact created or modified by the primary agent MUST pass an independent
review before another artifact may depend on it.

This includes:

- `SPEC.md`;
- `ARCHITECTURE.md`;
- `TASKS.md`;
- test artifacts;
- RED evidence;
- implementation artifacts;
- GREEN evidence;
- regression evidence;
- final completion evidence;
- corrections to any of the above.

The review cycle is:

```text
CREATE OR MODIFY ARTIFACT
→ COMMIT ARTIFACT
→ DELEGATE REVIEW
→ RECEIVE VERDICT
→ APPEND REVIEW ENTRY TO JOURNAL
→ COMMIT JOURNAL
→ PASS: artifact becomes an approved input
→ FAIL: primary agent fixes the artifact
        → COMMIT
        → delegated follow-up review
→ NEEDS_CLARIFICATION: primary agent obtains clarification
                       → updates the artifact
                       → COMMIT
                       → delegated follow-up review
```

A delegated reviewer response is the source of a verdict, not the completed
review event.

A review exists in the workflow only when:

- the delegated reviewer has returned `PASS`, `FAIL`, or `NEEDS_CLARIFICATION`;
- the verdict has been recorded as the corresponding review entry in
  `JOURNAL_SDD_TDD_SKILL.log`;
- the journal update has been committed.

Until all three conditions hold, the artifact remains unreviewed for workflow
purposes.

A later stage MUST NOT use an artifact that has not received a completed,
journaled, and committed `PASS`.

The next workflow entry MUST use the committed review entry JID as its direct
`PARENT`, not the reviewed artifact entry or the transient delegated response.

After `PASS`, the next stage may begin only after the review journal commit exists.

After `FAIL` or `NEEDS_CLARIFICATION`, correction work may begin only after the
review verdict has been journaled and committed.

Review comments never modify artifacts automatically.

Only the primary agent applies corrections.

---

## Principle 2 — Automatically Testable Behavior Uses RED-GREEN

Every behavior that can be verified automatically MUST be implemented through
a reviewed RED-GREEN cycle.

This applies to:

- production code;
- API behavior;
- validation rules;
- data transformations;
- persistence behavior;
- configuration behavior;
- security controls that can be exercised automatically;
- performance or reliability requirements that can be measured automatically;
- integrations that can be tested in an automated environment.

The required sequence is:

```text
REVIEWED REQUIREMENT AND TASK
→ CREATE TEST
→ COMMIT TEST
→ RUN TEST
→ VALID RED
→ DELEGATE TEST AND RED REVIEW
→ RECEIVE PASS
→ APPEND RED_REVIEW PASS
→ COMMIT JOURNAL
→ CREATE MINIMUM IMPLEMENTATION
→ COMMIT IMPLEMENTATION
→ RUN TESTS
→ GREEN
→ DELEGATE IMPLEMENTATION AND GREEN REVIEW
→ RECEIVE PASS
→ APPEND GREEN_REVIEW PASS
→ COMMIT JOURNAL
```

Implementation MUST NOT begin until the test artifact and RED evidence have a
committed `RED_REVIEW` journal entry with `STATUS: PASS`.

Receiving `PASS` from `delegate_task` without recording and committing the
`RED_REVIEW` entry does not satisfy this condition.

A test that passes before implementation is not valid RED.

A test that fails because of syntax errors, broken fixtures, unrelated imports,
environment failure, or another accidental defect is not valid RED.

GREEN is valid only when:

- the reviewed test passes;
- all relevant previously passing tests still pass;
- the implementation satisfies the referenced requirements;
- the implementation follows the reviewed architecture;
- implementation and GREEN evidence receive independent review.

A normal code review without prior reviewed RED evidence is not a valid
implementation path for automatically testable behavior.

---

## Principle 3 — Every Workflow Event Is Journaled

The workflow MUST maintain:

```text
JOURNAL_SDD_TDD_SKILL.log
```

The journal exists to make the process:

- reconstructable;
- auditable;
- diagnosable;
- measurable;
- improvable.

The journal records:

- user input capture;
- artifact creation;
- artifact corrections;
- review requests and verdicts;
- RED and GREEN evidence;
- task selection and task relationships;
- convergence of task branches;
- regression results;
- escalation and clarification;
- deliberate deviations and accepted risks;
- final review and completion.

Every completed workflow step and every review result MUST be recorded.

A delegated review result MUST be recorded and committed immediately after it is
received, before attention shifts to correction, implementation, or the next stage.

Every journal update MUST be committed immediately after it is written.

This includes review verdicts for `PASS`, `FAIL`, and `NEEDS_CLARIFICATION`.
The workflow MUST NOT proceed, and correction work MUST NOT begin, until the
corresponding journal update is committed.

The journal MUST preserve exact relationships between entries and tasks.

A `PARENT` JID MUST be copied from an existing journal entry. It MUST NOT be
guessed, generated through string arithmetic, or reconstructed from timestamps.

All journal format, field, task-tree, and relationship rules are defined in:

```text
references/JOURNAL.md
```

This skill defines when journal events occur.

`references/JOURNAL.md` defines how those events are represented.

## Principle 4 — The Process Is Part of the Result

The required stages, reviews, tests, commits, and journal records are not optional
bureaucracy.

They provide the evidence needed to understand how the software was produced,
why something failed, and how the next iteration can be improved.

Working code alone is not a complete result if the process that produced it
cannot be reconstructed, trusted, and improved.

## Deviation Risks

The workflow describes the evidence required for a trustworthy result. Skipping or
changing a stage does not remove its purpose; it accepts the corresponding risk.

Typical consequences:

- skipping specification review risks implementing misunderstood or unsupported requirements;
- skipping architecture review risks inconsistent, excessive, or unworkable technical decisions;
- skipping task review risks missing work, duplicated work, and broken traceability;
- skipping RED means the behavior was not proven absent before implementation, so the tests may not detect defects and the resulting code may not work;
- skipping RED review risks accepting tests that prove the wrong behavior or fail for the wrong reason;
- skipping GREEN review risks accepting code that only satisfies tests superficially, violates architecture, or introduces unrelated defects;
- skipping regression risks breaking previously working behavior;
- skipping final review risks declaring completion while requirements, evidence, or artifacts remain incomplete;
- skipping or delaying journal entries makes the workflow impossible to reconstruct reliably, hides where the process failed, and prevents later diagnosis and improvement.

Any deliberate deviation MUST be recorded before the workflow continues as an
`AGENT_DECISION` journal entry.

This includes deciding not to create or review an artifact, not to run a required
test, or not to perform any other required stage.

The entry MUST briefly state:

- what was skipped or changed;
- why the normal stage was not performed;
- what evidence is missing;
- what risk is accepted;
- what alternative evidence or mitigation is used.

The `AGENT_DECISION` entry makes the deviation visible; it does not convert the
missing stage into `PASS` or make the workflow fully compliant.

---

## Roles

### Primary Agent

The primary agent is responsible for:

- capturing user input;
- creating and modifying artifacts;
- asking the user for clarification;
- running tests and commands;
- producing RED and GREEN evidence;
- committing artifacts;
- updating and committing the journal;
- applying fixes after review failure;
- selecting the next stage;
- recording deliberate deviations and accepted risks;
- producing the final implementation.

### Delegated Reviewer

`delegate_task` is used only for independent review.

Delegation is intentionally limited to review so that artifact creation and artifact
evaluation remain separate responsibilities. The primary agent creates and fixes
artifacts; the delegated reviewer evaluates them without taking ownership of the
implementation.

A delegated reviewer may:

- inspect the committed artifact under review;
- inspect its approved source artifacts;
- inspect test, RED, GREEN, regression, or other supporting evidence;
- compare the artifact with relevant requirements and architecture decisions;
- identify omissions, contradictions, unsupported assumptions, defects, and risks;
- return `PASS`, `FAIL`, or `NEEDS_CLARIFICATION`;
- explain the verdict and provide actionable findings.

A delegated reviewer MUST NOT:

- modify files;
- create or fix artifacts;
- implement features;
- write or change tests;
- update the journal;
- create the next workflow artifact;
- continue the pipeline;
- delegate implementation work.

These restrictions preserve review independence. A reviewer that changes the
artifact would be evaluating its own solution rather than independently assessing
the primary agent’s work.

#### Reviewer Context

A fresh delegated context is preferred for an initial review.

Fresh context reduces anchoring, confirmation bias, and reliance on assumptions
formed while the artifact was being created.

The reviewer SHOULD receive all required information explicitly rather than rely
on hidden or shared working context.

A follow-up review after `FAIL` or `NEEDS_CLARIFICATION` MAY use the same reviewer
when continuity is useful for checking whether specific findings were resolved.

Even during a follow-up review, the request MUST include the updated committed
artifact, previous findings, new evidence, and the current review scope. The
reviewer must not rely only on remembered context.

The objective is independent judgment supported by complete evidence, not forced
amnesia.

#### Review Request

Every review request MUST give the reviewer enough explicit traceability to
understand what is being reviewed, why it exists, and what evidence would justify
`PASS`.

Every review request MUST identify:

- the review type;
- the repository path;
- the reviewed commit;
- the artifact path or paths under review;
- the task ID, when applicable;
- the exact task title as recorded in `TASKS.md`;
- the current task-selection or workflow entry in `JOURNAL_SDD_TDD_SKILL.log`;
- `SPEC.md` as the requirements source;
- the exact relevant requirement IDs;
- `ARCHITECTURE.md` as the technical-decision source;
- the exact relevant architecture sections or decisions;
- `TASKS.md` as the task and acceptance-criteria source;
- `JOURNAL_SDD_TDD_SKILL.log` as the workflow-evidence source;
- the supporting RED, GREEN, regression, or other evidence being reviewed;
- previous findings, when this is a follow-up review;
- the exact review scope;
- the required verdict format: `PASS`, `FAIL`, or `NEEDS_CLARIFICATION`;
- an explicit instruction to review only and not modify files.

The review request MUST instruct the reviewer to verify traceability across:

```text
REQUIREMENT
→ ARCHITECTURE DECISION
→ TASK
→ ARTIFACT
→ EVIDENCE
```

For a test artifact and RED review, the request MUST additionally instruct the
reviewer to:

- verify that the primary test exercises the complete user story or externally
  observable behavior at the highest practical boundary;
- return `FAIL` when an end-to-end or acceptance-level test is practical but is
  missing;
- accept a lower-level substitute only when the reviewed artifacts contain a
  concrete reason why end-to-end execution is impractical or unreliable;
- verify that unit tests supplement rather than replace the primary
  acceptance-oriented test;
- verify that RED fails because the required behavior is absent, not because of
  broken setup, imports, fixtures, protocol wiring, or environment;
- verify that the test would detect an incorrect implementation.

A test review request MUST NOT merely ask whether the tests pass, fail, or look
reasonable. It must ask whether they prove the referenced requirements through
the real public behavior of the system.

A review request SHOULD contain enough context for the reviewer to reach a verdict
without access to the primary agent’s private reasoning.

Canonical test and RED review request structure:

```text
Review type: RED_REVIEW
Repository: <repository path>
Reviewed commit: <commit SHA>
Task: <TASK_ID> — <exact task title>
Task source: TASKS.md
Workflow entry: JOURNAL_SDD_TDD_SKILL.log — <current task entry/JID>
Requirements source: SPEC.md
Relevant requirements: <requirement IDs>
Architecture source: ARCHITECTURE.md
Relevant architecture: <sections or decisions>
Artifacts under review: <test paths>
Evidence under review: <RED evidence paths or command output>
Previous findings: <none or findings>
Scope:
- Review only.
- Do not modify files.
- Verify requirement, architecture, task, artifact, and evidence traceability.
- Require an end-to-end or acceptance-level primary test at the highest
  practical boundary.
- Return FAIL if such a test is practical but missing.
- Return FAIL if RED is caused by anything other than absent required behavior.
Verdict: PASS, FAIL, or NEEDS_CLARIFICATION, with concise findings.
```

If the verdict is `FAIL` or `NEEDS_CLARIFICATION`, the delegated reviewer stops.
The primary agent applies corrections, commits the updated artifact, updates the
journal, and submits it for another review.

---

## Artifact Dependency Model

The approved artifact chain is:

```text
SPEC-DRAFT.md
      ↓
SPEC.md
      ↓
ARCHITECTURE.md
      ↓
TASKS.md
      ↓
TASK TESTS + RED EVIDENCE
      ↓
TASK IMPLEMENTATION + GREEN EVIDENCE
      ↓
REGRESSION EVIDENCE
      ↓
FINAL REVIEW
```

Each derived artifact MUST reference the reviewed inputs from which it was created.

No artifact may depend on an unreviewed derived artifact.

---

## Stage 0 — Capture User Input

### Artifact: `SPEC-DRAFT.md`

`SPEC-DRAFT.md` preserves the original user request exactly as received.

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

Later clarifications are recorded in the journal and incorporated into `SPEC.md`.

They do not rewrite historical user input.

Because `SPEC-DRAFT.md` is raw user input rather than an agent-generated
solution artifact, it is exempt from semantic review. Its capture and commit
are still journaled.

---

## Stage 1 — Requirements

### Artifact: `SPEC.md`

`SPEC.md` is the editable working specification derived from `SPEC-DRAFT.md`.

It defines what the system must do.

### Required Content

`SPEC.md` SHOULD contain:

- reference to `SPEC-DRAFT.md`;
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

Every requirement MUST have a stable identifier.

Recommended forms:

```text
FR-001
NFR-001
```

### Review Scope

The delegated reviewer checks:

- fidelity to `SPEC-DRAFT.md` and recorded clarifications;
- completeness;
- internal consistency;
- absence of unsupported assumptions;
- testability of functional requirements;
- measurability of non-functional requirements;
- clarity and observability of acceptance criteria;
- explicit treatment of ambiguities and edge cases.

### Gate

Architecture work MUST NOT begin until `SPEC.md` receives `PASS`.

On `FAIL`, the primary agent edits `SPEC.md`, commits it, updates the journal,
and requests a fresh review.

On `NEEDS_CLARIFICATION`, the primary agent asks the user, records the answer,
updates `SPEC.md`, commits it, and requests a fresh review.

`SPEC-DRAFT.md` remains unchanged.

---

## Stage 2 — Technical and Architectural Design

### Artifact: `ARCHITECTURE.md`

`ARCHITECTURE.md` defines how the reviewed requirements will be implemented.

It is derived from reviewed `SPEC.md`.

### Required Content

`ARCHITECTURE.md` SHOULD contain:

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

### Review Scope

The delegated reviewer checks:

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

Task decomposition MUST NOT begin until `ARCHITECTURE.md` receives `PASS`.

---

## Stage 3 — Task Decomposition

### Artifact: `TASKS.md`

`TASKS.md` decomposes reviewed requirements and architecture into implementable
tasks.

### Required Task Fields

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

Sibling tasks share the same parent.

Sibling tasks MUST NOT be connected merely because they are executed
sequentially.

### Review Scope

The delegated reviewer checks:

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

Per-task implementation work MUST NOT begin until `TASKS.md` receives `PASS`.

---

## Stage 4 — Per-Task RED-GREEN Cycle

Every implementation task follows the same mandatory procedure.

### Step 4.1 — Select Reviewed Inputs

Before writing tests, identify:

- task ID;
- referenced requirement IDs;
- referenced architecture decisions;
- task acceptance criteria;
- relevant existing tests and implementation.

Record the selected task in the journal.

### Step 4.2 — Create Test Artifact

Create automated tests that prove the task’s required observable behavior.

The primary test MUST be acceptance-oriented and exercise the behavior at the
highest practical level available for the task.

Tests SHOULD:

- validate user-visible or externally observable behavior;
- represent the relevant user story or acceptance criterion;
- exercise the public interface of the application, service, component, or module;
- verify the behavior described by reviewed requirements;
- avoid unnecessary coupling to internal implementation details;
- avoid mocking internal components when the real behavior can be exercised directly.

A full system end-to-end test MUST be used when it is practical and reliable.

When full end-to-end execution is impractical, use the closest stable boundary
that still proves the required behavior, such as:

- API-level tests;
- service-level tests;
- component-level tests through public interfaces;
- integration tests across the relevant subsystem.

Unit tests MAY supplement the acceptance-oriented test but MUST NOT replace it
when the requirement describes higher-level application behavior.

Tests MUST be derived from reviewed requirements and task acceptance criteria.

Commit the test artifact.

Record test creation in the journal.

### Step 4.3 — Establish RED

Run the new tests before implementing the required behavior.

Capture evidence showing that the tests fail because the behavior is absent.

RED evidence MUST identify:

- executed test scope;
- failure result;
- failure reason;
- relevant environment details when needed.

### Step 4.4 — Review Test and RED

Delegate an independent review of:

- the test artifact;
- the referenced requirements;
- the task acceptance criteria;
- the RED evidence.

The reviewer checks:

- whether the tests prove the task's required observable behavior;
- whether the tests match the task acceptance criteria;
- whether the tests correctly cover the referenced requirements in `SPEC.md`;
- whether relevant architecture constraints are respected;
- whether the tests exercise the highest practical public boundary;
- whether the primary test is end-to-end or acceptance-level when that is
  practical and reliable;
- whether any lower-level substitute has a concrete documented justification;
- whether unit tests supplement rather than replace the primary
  acceptance-oriented test;
- whether important edge cases are covered;
- whether RED failed for the expected missing-behavior reason;
- whether an incorrect implementation would be detected.

The reviewer MUST return `FAIL` when an end-to-end or acceptance-level primary
test is practical but missing.

The reviewer returns one verdict for the test artifact and RED evidence.

The delegated response is not yet the completed workflow event. The primary agent
records the verdict as `RED_REVIEW`, commits the journal update, and uses that
review entry as the parent of the next workflow entry.

Implementation may begin only when a committed `RED_REVIEW` entry has
`STATUS: PASS`.

On `FAIL`, the primary agent records and commits `RED_REVIEW: FAIL` before fixing
the tests or test setup, rerunning RED, committing the correction, and requesting
a follow-up review.

### Step 4.5 — Create Minimum Implementation

After reviewed RED receives `PASS`, create the minimum implementation required
to satisfy:

- the reviewed requirements;
- the reviewed architecture;
- the reviewed task;
- the reviewed tests.

Do not add unrelated behavior.

Commit the implementation.

Record implementation creation in the journal.

### Step 4.6 — Establish GREEN

Run:

- the reviewed task tests;
- all relevant previously passing tests.

Capture GREEN evidence showing:

- the new tests pass;
- relevant existing tests still pass;
- the committed implementation is the tested state.

### Step 4.7 — Review Implementation and GREEN

Delegate an independent review of:

- the implementation artifact;
- reviewed requirements;
- reviewed architecture;
- reviewed task;
- reviewed tests;
- GREEN evidence.

The reviewer checks:

- requirement compliance;
- architecture compliance;
- passing evidence;
- correctness;
- minimality;
- absence of unrelated changes;
- security and reliability concerns;
- maintainability appropriate to the task;
- absence of regressions in the reviewed scope.

The delegated response is not yet the completed workflow event. The primary agent
records the verdict as `GREEN_REVIEW`, commits the journal update, and uses that
review entry as the terminal entry of the task branch.

The task is complete only when a committed `GREEN_REVIEW` entry has
`STATUS: PASS`.

On `FAIL`, the primary agent records and commits `GREEN_REVIEW: FAIL` before
fixing the implementation, committing the correction, rerunning tests, and
requesting a follow-up review.

---

## Stage 5 — Task Convergence

When all required task branches have passed implementation and GREEN review,
create the `TASKS_COMPLETE` journal event.

The convergence event MUST reference the terminal reviewed entry of every
completed task branch.

Regression MUST NOT begin before all required task branches have converged.

---

## Stage 6 — Regression

### Artifact: Regression Evidence

Run the complete automated test suite required to verify the final committed implementation.

Regression MUST include:

- all tests created for the current requirements;
- all previously existing tests for the affected application or component;
- all relevant integration tests;
- all relevant end-to-end and acceptance tests;
- all automated checks for applicable non-functional requirements;
- tests for shared components that may be affected by the changes.

Do not run only the tests added for the current tasks.

For a repository with multiple independent projects, run the complete required
suite for every affected project and every shared component that may be impacted.

If any required test or test suite cannot be executed, record:

- which tests were not executed;
- why they could not be executed;
- what risk remains;
- what alternative evidence was collected.

Regression evidence MUST record:

- the exact commands executed;
- the exact commit under test;
- the executed test scope;
- the total number of passed, failed, skipped, and omitted tests;
- failure details, if any;
- relevant environment and configuration;
- any known limitations in the collected evidence.

Regression is complete only when:

- all required tests pass;
- no required test was silently omitted;
- every exception is explicitly documented;
- the regression evidence corresponds to the final committed state.

### Review Scope

The delegated reviewer checks:

- whether the executed test scope is complete for the affected system;
- whether all newly added and previously existing relevant tests were executed;
- whether all required tests passed;
- whether skipped or omitted tests are justified and documented;
- whether previously completed behavior remains valid;
- whether automatically testable functional requirements are covered;
- whether automatically testable non-functional requirements are covered;
- whether the evidence corresponds to the exact final committed state;
- whether the recorded commands, environment, and result summary are sufficient to reproduce the regression run.

Final review MUST NOT begin until regression evidence receives `PASS`.

---

## Stage 7 — Final Review

The final review evaluates the complete committed solution and its artifact chain.

The reviewer checks:

- `SPEC-DRAFT.md` preserves the original user input;
- `SPEC.md` has `PASS`;
- `ARCHITECTURE.md` has `PASS`;
- `TASKS.md` has `PASS`;
- every requirement maps to tasks;
- every automatically testable behavior has reviewed RED-GREEN evidence;
- every task implementation has `PASS`;
- all required tests pass;
- non-automatable requirements have appropriate review evidence;
- architecture matches implementation;
- no required artifact is missing;
- traceability is complete;
- journal relationships are complete;
- every deliberate deviation is recorded as an `AGENT_DECISION` with its accepted risk and mitigation;
- the working tree contains no uncommitted solution artifacts.

`DONE` may be recorded only after `FINAL_REVIEW` receives `PASS`.

---

## Traceability

The complete traceability chain is:

```text
USER INPUT
→ SPEC-DRAFT.md
→ REQUIREMENT IN SPEC.md
→ DECISION IN ARCHITECTURE.md
→ TASK IN TASKS.md
→ TEST
→ RED EVIDENCE
→ IMPLEMENTATION
→ GREEN EVIDENCE
→ REGRESSION EVIDENCE
→ FINAL REVIEW
```

Every derived artifact MUST identify the reviewed source artifacts or IDs from
which it was created.

Every functional requirement MUST trace to:

- at least one task;
- at least one automated test when automatically testable;
- the implementation that satisfies it.

Every automatically testable non-functional requirement MUST trace to:

- a measurable acceptance condition;
- at least one automated test or benchmark;
- RED evidence;
- implementation or configuration;
- GREEN evidence.

A requirement that cannot be tested automatically MUST still trace to:

- a reviewed task or architectural decision;
- explicit completion evidence;
- independent review.

---

## Commit Rules

Every reviewable artifact MUST be committed before review.

A reviewer inspects a committed state, never a dirty working tree.

After every delegated review response:

- treat the response as verdict source data, not as a completed workflow event;
- append the corresponding review entry to the journal;
- commit the journal update immediately;
- use the committed review entry JID as the direct `PARENT` of the next workflow entry;
- do not proceed to the next stage before that journal commit exists;
- on `FAIL` or `NEEDS_CLARIFICATION`, do not begin corrections before that journal commit exists.

After `FAIL`:

- do not amend reviewed history;
- create a correction commit;
- rerun required checks;
- update the journal;
- request a fresh review.

A step is not complete until both the artifact and its journal event are committed.

---

## Escalation

Each artifact has its own review-attempt counter.

If the configured review limit is reached without `PASS`, stop the workflow and
escalate to the user.

Record the escalation in the journal.

The user may:

- clarify requirements;
- revise the approved direction;
- split the artifact;
- cancel the work;
- explicitly force continuation.

A forced continuation MUST be recorded and MUST NOT be represented as an
ordinary reviewer `PASS`.

---

## Completion Conditions

The workflow is complete only when:

- `SPEC-DRAFT.md` preserves the original request unchanged;
- `SPEC.md` has independent review `PASS`;
- `ARCHITECTURE.md` has independent review `PASS`;
- `TASKS.md` has independent review `PASS`;
- every agent-generated test artifact has independent review `PASS`;
- every automatically testable behavior has valid reviewed RED evidence;
- every implementation artifact has independent review `PASS`;
- every automatically testable behavior has valid reviewed GREEN evidence;
- all task branches have converged;
- regression evidence has independent review `PASS`;
- final review has `PASS`;
- all required tests pass;
- traceability is complete;
- the journal is complete and internally connected;
- every deliberate deviation is explicitly recorded and remains visible as missing evidence rather than an ordinary `PASS`;
- all required artifacts are committed;
- the working tree contains no uncommitted solution artifacts.

---

## Non-Negotiable Rules

1. Do not edit `SPEC-DRAFT.md`.
2. Do not use an unreviewed agent-generated artifact as input to a later stage.
3. Do not begin architecture before `SPEC.md` receives `PASS`.
4. Do not begin task decomposition before `ARCHITECTURE.md` receives `PASS`.
5. Do not begin implementation before test and RED review receive `PASS`.
6. Do not treat a passing test without prior valid RED as TDD evidence.
7. Do not let delegated reviewers modify artifacts.
8. Do not let review replace RED-GREEN.
9. Do not let RED-GREEN replace independent review.
10. Do not omit journal events for completed steps, reviews, fixes, or escalation.
11. Do not guess journal parent identifiers.
12. Do not declare completion without regression and final review.
13. Do not create artifacts that cannot be traced to reviewed inputs.
14. Do not represent forced continuation as an ordinary review `PASS`.
15. Record every deliberate deviation as a committed `AGENT_DECISION` before continuing.
16. Do not treat a delegated reviewer response as a completed review until the corresponding review entry is journaled and committed.

---

## References

- [JOURNAL.md](references/JOURNAL.md) — journal entry format, task relationships, parent/root rules, and required invariants.
- [SPEC-EXAMPLE.md](references/SPEC-EXAMPLE.md) — canonical walkthrough of the complete reviewed artifact and RED-GREEN workflow.

