



⸻

name: spec-driven-development
description: “Build software through a reviewed artifact pipeline: immutable user input, requirements, architecture, task decomposition, tests, implementation, regression, and final verification.”
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
hermes:
tags: [spec-driven, tdd, requirements, architecture, testing, review, workflow]

Spec-Driven Development

Purpose

Transform a user request into working software through a sequence of explicit,
committed, and independently reviewed artifacts.

The workflow is based on one rule:

Every stage produces an artifact, and every artifact must receive an independent
review verdict before any later stage may depend on it.

The primary agent creates and fixes artifacts.

Delegated agents review artifacts only.

⸻

Core Pipeline

USER INPUT
→ SPEC-DRAFT.md
→ SPEC.md
→ ARCHITECTURE.md
→ TASKS.md
→ per-task TEST artifact
→ per-task IMPLEMENTATION artifact
→ REGRESSION evidence
→ FINAL REVIEW
→ DONE

Each arrow means that the next artifact is derived from previously reviewed artifacts.

⸻

Artifact Review Cycle

Every reviewable artifact follows the same cycle:

CREATE
→ COMMIT
→ REVIEW
→ PASS: continue
→ FAIL: fix the same artifact
        → COMMIT
        → fresh REVIEW

A later stage MUST NOT begin until every required input artifact has received PASS.

Review comments do not modify artifacts automatically.

The primary agent applies all corrections.

⸻

Roles

Primary Agent

The primary agent is responsible for:

* creating artifacts;
* modifying artifacts after review failure;
* running tests and commands;
* committing changes;
* updating the journal;
* selecting the next workflow stage;
* producing the final implementation.

Delegated Reviewer

Every delegate_task call is review-only.

A delegated reviewer may:

* inspect one committed artifact;
* inspect its source artifacts and supporting evidence;
* identify omissions, contradictions, defects, and unsupported decisions;
* return PASS, FAIL, or NEEDS_CLARIFICATION;
* explain the verdict.

A delegated reviewer MUST NOT:

* modify files;
* implement features;
* fix the reviewed artifact;
* create the next artifact;
* continue the workflow;
* run the complete pipeline.

Each review uses a fresh delegated context.

⸻

Artifact 1: SPEC-DRAFT.md

Purpose

SPEC-DRAFT.md preserves the original user request.

Rules

SPEC-DRAFT.md MUST:

* contain the user input exactly as received;
* preserve the original language and wording;
* be committed once;
* remain immutable.

SPEC-DRAFT.md MUST NOT:

* contain interpreted requirements;
* contain inferred acceptance criteria;
* be normalized or translated;
* be edited after creation;
* be reviewed for correctness.

Later clarifications are recorded separately and incorporated into SPEC.md.

⸻

Artifact 2: SPEC.md

Purpose

SPEC.md is the editable working specification derived from SPEC-DRAFT.md.

It defines what the system must do.

Required Content

SPEC.md SHOULD contain:

* reference to SPEC-DRAFT.md;
* system goal;
* functional requirements;
* non-functional requirements;
* constraints;
* entities and external interfaces;
* acceptance criteria;
* edge cases;
* open questions;
* recorded clarifications.

Every requirement MUST have a stable requirement ID.

Example:

FR-001
NFR-001

Review Scope

The reviewer checks:

* fidelity to the original user input;
* completeness;
* internal consistency;
* absence of unsupported assumptions;
* testability of functional requirements;
* measurability of non-functional requirements;
* clarity of acceptance criteria.

Failure Handling

On FAIL, the primary agent edits SPEC.md, commits it, and requests a fresh review.

On NEEDS_CLARIFICATION, the primary agent asks the user, records the answer,
updates SPEC.md, commits it, and requests a fresh review.

Task or architecture work MUST NOT begin until SPEC.md receives PASS.

⸻

Artifact 3: ARCHITECTURE.md

Purpose

ARCHITECTURE.md describes how the reviewed requirements will be implemented.

It is derived from SPEC.md.

Required Content

ARCHITECTURE.md SHOULD contain:

* architecture overview;
* major components;
* component responsibilities;
* data model;
* external interfaces;
* persistence decisions;
* security decisions;
* performance and scalability decisions;
* operational constraints;
* mapping from architectural decisions to requirement IDs;
* known trade-offs and rejected alternatives.

Every significant technical decision MUST reference the requirements that justify it.

Review Scope

The reviewer checks:

* whether every technical decision is supported by reviewed requirements;
* whether functional requirements are implementable;
* whether non-functional requirements are addressed;
* whether component boundaries are coherent;
* whether interfaces and data ownership are clear;
* whether unnecessary complexity was introduced;
* whether risks and trade-offs are documented.

Task decomposition MUST NOT begin until ARCHITECTURE.md receives PASS.

⸻

Artifact 4: TASKS.md

Purpose

TASKS.md decomposes the reviewed specification and architecture into implementable tasks.

Required Content

Every task MUST contain:

TASK_ID
PARENT_TASK_ID
ROOT_USER_INPUT_ID
REQUIREMENTS
ARCHITECTURE_REFERENCES
ACCEPTANCE

Every task MUST:

* reference one or more requirement IDs;
* reference relevant architectural decisions;
* define an observable completion condition;
* be small enough to implement and review independently;
* have one direct parent task;
* remain traceable to the root user input.

Sibling tasks share the same parent.

Sibling tasks MUST NOT be connected merely because they are executed sequentially.

Review Scope

The reviewer checks:

* coverage of all functional requirements;
* traceability to requirements and architecture;
* correct parent-child task relationships;
* task independence and granularity;
* absence of missing or duplicate work;
* clear acceptance conditions;
* feasible execution order where dependencies exist.

Implementation MUST NOT begin until TASKS.md receives PASS.

⸻

Artifact 5: Task Test

For every implementation task, create tests before implementation.

Tests are derived from:

* the task acceptance condition;
* referenced functional requirements;
* relevant non-functional requirements;
* public behavior defined by the architecture.

RED Stage

Create and run the test before implementing the required behavior.

The test must fail because the required behavior is missing.

A failure caused by broken setup, syntax errors, or unrelated infrastructure is not valid RED evidence.

Test Review Scope

The reviewer checks:

* whether the test proves the referenced requirement;
* whether the test uses observable behavior;
* whether the expected outcome matches SPEC.md;
* whether the failure occurred for the correct reason;
* whether important edge cases are represented;
* whether the test is unnecessarily coupled to implementation details.

Implementation MUST NOT begin until the test and RED evidence receive PASS.

⸻

Artifact 6: Task Implementation

Create the minimum implementation required to satisfy the reviewed tests and requirements.

The implementation is derived from:

* reviewed SPEC.md;
* reviewed ARCHITECTURE.md;
* reviewed task definition;
* reviewed tests.

GREEN Stage

Run the task tests after implementation.

The required tests must pass.

Implementation Review Scope

The reviewer checks:

* compliance with referenced requirements;
* consistency with the reviewed architecture;
* passing test evidence;
* correctness;
* minimality;
* security and reliability concerns;
* absence of unrelated changes;
* maintainability appropriate to the task.

On FAIL, the primary agent fixes the implementation, commits it, reruns the tests,
and requests a fresh review.

A task is complete only after its implementation receives PASS.

⸻

Artifact 7: Regression Evidence

After all required task branches are complete, run the complete test suite.

Record:

* executed test scope;
* result summary;
* failures, if any;
* environment or configuration relevant to the result.

Review Scope

The reviewer checks:

* whether all required tests were executed;
* whether all tests passed;
* whether previously completed behavior remains valid;
* whether the regression evidence corresponds to the final committed state.

Final review MUST NOT begin until regression evidence receives PASS.

⸻

Artifact 8: Final Review

The final review evaluates the complete committed solution.

Review Scope

The reviewer checks:

* every functional requirement is implemented;
* every non-functional requirement is addressed or explicitly justified;
* architecture matches the implementation;
* every task is complete;
* every task has reviewed tests and implementation;
* all tests pass;
* no required artifact is missing;
* traceability is complete from user input to code;
* the working tree contains no uncommitted solution artifacts;
* the journal represents the completed workflow.

DONE may be recorded only after FINAL_REVIEW receives PASS.

⸻

Traceability

The complete traceability chain is:

USER INPUT
→ SPEC-DRAFT.md
→ requirement in SPEC.md
→ decision in ARCHITECTURE.md
→ task in TASKS.md
→ test
→ implementation
→ regression evidence
→ final review

Every derived artifact MUST identify the source artifacts or IDs from which it was created.

A requirement is complete only when it can be traced to:

* at least one implementation task;
* at least one test;
* the implementation that satisfies it.

⸻

Journal

The workflow MUST maintain:

JOURNAL_SDD_TDD_SKILL.log

The journal records completed workflow events, review outcomes, artifact relationships,
task relationships, and originating user input.

All journal format and content requirements are defined in:

references/JOURNAL.md

The journal does not replace the artifacts.

It records how the artifacts were created, reviewed, corrected, and completed.

⸻

Commit Rules

Every artifact MUST be committed before review.

A review always inspects a committed state.

After a review:

* record the verdict in the journal;
* commit the journal update;
* on FAIL, create a new fix commit;
* never rewrite reviewed history by amending previous commits.

⸻

Completion Conditions

The workflow is complete only when:

* SPEC-DRAFT.md preserves the original request unchanged;
* SPEC.md has PASS;
* ARCHITECTURE.md has PASS;
* TASKS.md has PASS;
* every task test has valid reviewed RED evidence;
* every task implementation has reviewed GREEN evidence;
* all task branches are complete;
* regression evidence has PASS;
* final review has PASS;
* all tests pass;
* traceability is complete;
* the journal is complete;
* all required artifacts are committed.

⸻

Non-Negotiable Rules

1. Do not edit SPEC-DRAFT.md.
2. Do not derive tasks from an unreviewed SPEC.md.
3. Do not derive implementation tasks from an unreviewed architecture.
4. Do not implement a task before its test and RED evidence pass review.
5. Do not proceed after a failed review.
6. Do not let delegated reviewers modify artifacts.
7. Do not declare completion without full regression and final review.
8. Do not create artifacts that cannot be traced to reviewed inputs.