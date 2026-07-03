---
name: spec-driven-tdd
description: "Build software through a traceable artifact pipeline. Every agent-generated artifact is independently reviewed, every automatically testable behavior is implemented through reviewed RED-GREEN TDD, and every workflow event is committed and journaled."
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, requirements, architecture, testing, review, traceability, audit]
---

# Spec-Driven TDD

## What this skill is

A pipeline that turns a user request into working software through a reviewed,
tested, committed, and journaled artifact chain.

## File layout

```text
<repo_root>/
├── .sddtdd_skill/
│   ├── SPEC-DRAFT.md
│   ├── SPEC.md
│   ├── ARCHITECTURE.md
│   ├── TASKS.md
│   ├── JOURNAL_SDD_TDD_SKILL.log
│   ├── review-access.jsonl    # runtime, not committed
│   └── orchestrator-access.jsonl    # runtime, not committed
└── ...
```

Committed artifacts and the journal must be tracked in git.

## Files in this skill

- `SKILL.md`
- `SKILL-IMPLEMENTER.md`
- `SKILL-ORCHESTRATOR.md`
- `references/JOURNAL.md`
- `references/SPEC-EXAMPLE.md`
- `references/STAGES.md`
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`

## Four mandatory principles

1. Every agent-generated artifact is independently reviewed before later work
   depends on it.
2. Every automatically testable behavior goes through reviewed RED-GREEN TDD.
3. Every completed step, review result, correction, and dependency is recorded
   in `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` and committed.
4. The reviewed, tested, and journaled process artifacts are part of the result.

## Core artifact chain

```text
USER INPUT
→ .sddtdd_skill/SPEC-DRAFT.md
→ .sddtdd_skill/SPEC.md
→ .sddtdd_skill/ARCHITECTURE.md
→ .sddtdd_skill/TASKS.md
→ per-task RED-GREEN cycles
→ TASKS_COMPLETE
→ REGRESSION
→ FINAL
→ DONE
```

## Operating modes

### Standalone mode

There is no orchestrator. The implementer reads `SKILL-IMPLEMENTER.md` and
`references/STAGES.md`, then walks the chain directly.

### Orchestrator mode

There is one orchestrator tool and one reviewer tool:

```text
mcp_sddtdd_getNextTask
mcp_sddtdd_review
```

The implementer asks the orchestrator for the next task and executes only that task.
The orchestrator owns workflow order and process-gate verification. The orchestrator policy
lives in `SKILL-ORCHESTRATOR.md`; the implementer does not read it.

The independent reviewer checks artifact correctness. The orchestrator checks process
state. These are separate verification chains.

In orchestrator mode, `mcp_sddtdd_getNextTask` is used for both:

- initial user input (`task_kind=INITIAL_USER_INPUT`);
- completed task advancement (`task_kind=<completed task kind>`).

The orchestrator response contains:

- `task_review` — process-gate verdict for the submitted completed task, or
  null for initial input;
- `next_task` — the next task to execute, or null;
- `status` — `task`, `fail`, `needs_clarification`, `error`, or `complete`.

The implementer must journal and commit `ORCHESTRATOR_TASK_REVIEW` from
`task_review` before executing `next_task`.

## Roles

### Implementer

Creates artifacts, runs tests, calls reviewer when required, journals,
commits, calls orchestrator, and follows only orchestrator-issued tasks.

### Independent reviewer

Invoked through `mcp_sddtdd_review`. Reviews committed artifacts and evidence
against reviewed inputs and SDDTDD policy. It does not implement, journal,
commit, or advance the workflow.

### Orchestrator / orchestrator

Invoked through `mcp_sddtdd_getNextTask`. Chooses next tasks and verifies
process completion from committed state. It does not perform semantic artifact
review and does not modify the repository.

## Required invariants

- `.sddtdd_skill/SPEC-DRAFT.md` preserves raw user input and is immutable.
- `.sddtdd_skill/SPEC.md`, `ARCHITECTURE.md`, and `TASKS.md` require
  independent review before downstream work depends on them.
- RED tests must fail for the expected missing-behavior reason before GREEN.
- GREEN must be minimal for the reviewed task.
- Regression and final review must pass before DONE.
- Reviewer PASS does not replace orchestrator process PASS.
- Orchestrator process PASS is `task_review.status=PASS` in a `getNextTask` response.
- `ORCHESTRATOR_TASK_REVIEW` must be journaled and committed before executing the
  returned `next_task`.
