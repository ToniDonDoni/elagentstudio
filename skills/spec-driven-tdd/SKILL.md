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

A pipeline that turns a user request into working software through a chain of
explicit, traceable, committed, and independently reviewed artifacts, with
automated RED-GREEN testing for every behavior that can be tested
automatically. The pipeline records its own execution in a journal so the
work can be reconstructed, audited, and improved.

The pipeline is one skill: `skills/spec-driven-tdd/`. The installable
artifact is this directory. The role files inside it are part of the same
skill; they are not separate top-level skills.

## File layout

The skill uses a single per-repo directory for all of its artifacts
and runtime logs:

```text
<repo_root>/
├── .sddtdd_skill/                       # SDDTDD working area
│   ├── SPEC-DRAFT.md                    # immutable, user input (committed)
│   ├── SPEC.md                          # editable spec (committed)
│   ├── ARCHITECTURE.md                  # architecture (committed)
│   ├── TASKS.md                         # task decomposition (committed)
│   ├── JOURNAL_SDD_TDD_SKILL.log        # workflow journal (committed)
│   ├── review-access.jsonl              # reviewer MCP log (NOT committed)
│   └── broker-access.jsonl              # broker MCP log (NOT committed)
└── ... (the project being built)
```

The committed artifacts and the journal MUST be tracked in git
so the broker can read the journal at a pinned `HEAD` and verify
the journal chain (race protection).

## Files in this skill

- `SKILL.md` — this file. Overview, principles, roles, invariants, references.
- `SKILL-IMPLEMENTER.md` — implementer loop for the standalone pipeline.
  Standalone implementer reads this file plus the references to know the
  stage order, RED-GREEN mechanics, and journal rules.
- `SKILL-ORCHESTRATOR.md` — broker/orchestrator decision contract for MCP
  task-broker mode. Loaded by the broker MCP server, not by the implementer.
- `references/JOURNAL.md` — journal format, entry types, required fields,
  task-tree rules, invariants.
- `references/SPEC-EXAMPLE.md` — canonical worked example of the pipeline.
- `references/STAGES.md` — stage-by-stage procedure for standalone mode:
  Stage 0..7, RED-GREEN steps, commit rules, escalation, completion
  conditions.
- `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md` — guide for translating
  user requirements into observable acceptance criteria, test-boundary
  requirements, architecture/test-design requirements, tasks, and tests.

## Four mandatory principles

These are invariants. They do not replace each other.

1. **Every agent-generated artifact is reviewed by a separate independent
   reviewer before later work may depend on it.** Independent review does not
   replace RED-GREEN.
2. **Every behavior that can be verified automatically is implemented through
   a reviewed RED-GREEN test-driven cycle.** Requirements must first be
   translated into observable acceptance criteria and the highest practical
   automated test boundary, following
   `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`. User-visible, audible,
   public-API, log, downstream-integration, and performance requirements must
   be tested at the application boundary where practical; implementation-only
   evidence such as classes, methods, imports, labels, mocks, or requirement
   IDs in test names is not enough. Passing tests do not replace independent
   review.
3. **Every completed step, review result, correction, and dependency is
   recorded in `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` and committed.** The journal does
   not replace artifacts, reviews, or test evidence.
4. **The result is not only working software but also the reviewed, tested,
   and journaled artifacts that explain how it was produced.** The process
   is part of the result.

## Core artifact chain

All SDDTDD artifacts live under a single per-repo directory,
`.sddtdd_skill/`, which is the working area for the spec-driven
pipeline. Committed artifacts and the journal go under that
directory; runtime access logs from the reviewer and broker MCPs
also live there but are excluded by `.gitignore` (see
`File layout` below).

```text
USER INPUT
→ .sddtdd_skill/SPEC-DRAFT.md
→ .sddtdd_skill/SPEC.md
→ .sddtdd_skill/ARCHITECTURE.md
→ .sddtdd_skill/TASKS.md
→ per-task RED-GREEN cycles
→ TASKS_COMPLETE
→ REGRESSION
→ DONE
```

Every arrow means: the next artifact is derived only from reviewed inputs.
During SPEC, ARCHITECTURE, TASKS, and RED-GREEN planning, requirements MUST be
converted using `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`:

```text
user requirement
→ observable acceptance criterion
→ required test boundary
→ architecture / test-design requirement
→ task
→ automated test
```

For example, a visible button requirement must become an acceptance criterion
that the button is visible in the rendered app/browser and a test at the
rendered-app or end-to-end boundary where practical. A backend log requirement
must become an acceptance criterion that the running application writes the
actual log entry to a real configured destination that the test reads.

Standalone implementer reads the full stage-by-stage procedure in
`references/STAGES.md` and the journal format in `references/JOURNAL.md`.

## Two ways to run the pipeline

The pipeline has two operating modes. The artifacts, journal, and principles
are identical in both.

### Standalone mode

There is no broker. The implementer reads `SKILL-IMPLEMENTER.md` plus
`references/STAGES.md` and walks the artifact chain stage by stage. The
implementer selects the next stage from committed state and the journal.
This is the original mode.

### Broker mode

In broker mode there is an MCP task broker. The implementer asks the
broker for the next task via the broker MCP and executes only the task
the broker returns. The broker owns the workflow order and the
process-gate verification; its decision policy lives in
`SKILL-ORCHESTRATOR.md`. The implementer does not read
`SKILL-ORCHESTRATOR.md`; the broker does.

There are two independent verifications in broker mode. The
independent reviewer (`mcp_sddtdd_review`) checks artifact
correctness. The broker checks process state. These are separate
verification chains, with separate verdict JIDs, and they do not
replace each other. The detailed broker checks are defined in
`SKILL-ORCHESTRATOR.md`.

## Roles

There are three roles in the pipeline. A single agent may fill more
than one role in standalone mode, but in broker mode the implementer
and the broker are always different.

### Implementer

The implementer creates and modifies artifacts, runs tests, requests
reviews, updates the journal, commits, and reports task completion.

In standalone mode the implementer selects the next stage from
committed state.

In broker mode the implementer asks the broker for the next task and
executes only that task. The implementer does not know the workflow
order; the broker decides. The implementer must record the broker's
verification in the journal — every completed broker task produces a
`BROKER_TASK_REVIEW` entry with `TASK_ID` and `STATUS: PASS | FAIL |
NEEDS_CLARIFICATION | ERROR`. The broker also enforces a process
gate: while a previous broker task id has no committed
`BROKER_TASK_REVIEW: PASS` with matching `TASK_ID`, the broker will
not issue the next task; `getNextTask` returns `blocked` and names
the outstanding `task_id` in `unverified_task_ids`.

### Independent reviewer

Invoked through `mcp_sddtdd_review`. Reviews the committed artifact
against its already-reviewed predecessor inputs and returns a structured result
whose `verdict` field is the authoritative review outcome: `PASS`, `FAIL`, or
`NEEDS_CLARIFICATION`. Callers MUST decide review success from `verdict`, not
from the MCP transport status and not from words like "failed" inside RED
evidence. `status: COMPLETED` means only that the MCP call completed.

`PASS` means the reviewed stage is accepted. For `RED_REVIEW`, `PASS` means
the failing tests are valid RED evidence, not a request to implement or fix the
missing behavior immediately. `FAIL` includes specific findings explaining what
is wrong. `NEEDS_CLARIFICATION` includes questions that must be answered before
a truthful pass/fail verdict is possible. Never modifies files, never
implements, never writes the journal, never advances the pipeline. A reviewer
that changes the artifact would be evaluating its own work.

When a reviewer identifies a deliberate compromise, deviation, or practical
substitution in an artifact, the reviewer MUST NOT silently accept it as an
ordinary `PASS`. If the compromise has not already been recorded in the
committed journal, the reviewer MUST return `FAIL` or `NEEDS_CLARIFICATION`
and require the implementer to record a committed `AGENT_DECISION` before the
pipeline continues. The `AGENT_DECISION` MUST identify the affected acceptance
criterion, test boundary, artifact, or workflow rule; explain why the
compromise is necessary; state the accepted risk; and describe the mitigation
or replacement boundary.

If the compromise changes, weakens, replaces, or reinterprets an acceptance
criterion, user-visible behavior, user-observable evidence, or required test
boundary, the reviewer MUST require the implementer to report the compromise
to the user or owner before continuing. The reviewer MUST NOT return a clean
`PASS` for such a stage until the journaled decision and required user/owner
notification have happened. A compromise that does not change the acceptance
contract still MUST be journaled, but it does not require user/owner
notification unless another rule requires escalation.

### Broker / orchestrator

In broker mode only. Invoked through the broker MCP server. Owns the
workflow process. The detailed broker policy is in
`SKILL-ORCHESTRATOR.md`.

## Required invariants

These rules are not optional. Any deliberate deviation must be journaled
as `AGENT_DECISION` with the skipped stage, the accepted risk, and the
mitigation.

1. Do not edit `.sddtdd_skill/SPEC-DRAFT.md`.
2. Do not use an unreviewed agent-generated artifact as input to a later
   stage.
3. Do not begin a stage before the previous stage's review entry is
   journaled and committed with `STATUS: PASS`.
4. Do not begin implementation before test and RED review receive `PASS`.
5. Do not treat a passing test without prior valid RED as TDD evidence.
6. Do not let independent reviewers modify artifacts.
7. Do not let review replace RED-GREEN.
8. Do not let RED-GREEN replace independent review.
9. Do not omit journal events for completed steps, reviews, fixes, or
   escalation.
10. Do not guess journal parent identifiers. Copy them from an existing
    journal entry.
11. Do not declare completion without regression and final review.
12. Do not create artifacts that cannot be traced to reviewed inputs.
13. Do not represent forced continuation as an ordinary review `PASS`.
14. Record every deliberate deviation, compromise, or practical substitution
    as a committed `AGENT_DECISION` before continuing.
15. Do not treat an MCP review response as a completed review until the
    corresponding review entry is journaled and committed.
16. In broker mode, do not self-select the next workflow task; request it
    from the task broker and execute only the task it returns.
17. In broker mode, do not consume `SKILL-ORCHESTRATOR.md` as your own
    instructions. It is the broker's policy.
18. Do not treat a requirement as test-ready until it has observable acceptance
    criteria and an explicit highest practical test boundary, as defined in
    `ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md`.
19. Do not accept implementation-only evidence for user-visible, audible,
    public-API, log, downstream-integration, or performance requirements when
    application-boundary testing is practical. Classes, methods, imports,
    labels, mocks, source strings, and requirement IDs in test names are
    traceability hints, not proof of behavior.

20. Do not silently continue after a compromise that changes, weakens,
    replaces, or reinterprets an acceptance criterion, user-visible behavior,
    user-observable evidence, or required test boundary. The implementer MUST
    report the compromise to the user or owner before continuing.
21. Do not let a reviewer return an ordinary `PASS` for an unjournaled
    compromise. The reviewer MUST require a committed `AGENT_DECISION` first,
    and MUST require user/owner notification when the compromise changes the
    acceptance contract.

## How to use this skill

For a worked example of a user prompt, a checklist of what to verify
afterwards, and the common failure modes, see
[`README.md`](README.md). The two short procedures below are the minimum
a running agent needs.

### Standalone

```text
Read SKILL.md (this file).
Then read SKILL-IMPLEMENTER.md.
Then read references/STAGES.md.
Then read references/JOURNAL.md.
Walk the artifact chain.
```

### Broker

```text
Read SKILL.md (this file).
Then read SKILL-IMPLEMENTER.md.
Ask the broker MCP for the next task.
Execute only the task the broker returns.
```

A ready-to-copy user prompt template (broker mode) lives in
[`README.md`](README.md) under "Example user prompt — broker mode".

## References

- [SKILL-IMPLEMENTER.md](SKILL-IMPLEMENTER.md) — implementer loop.
- [SKILL-ORCHESTRATOR.md](SKILL-ORCHESTRATOR.md) — broker decision contract.
- [references/JOURNAL.md](references/JOURNAL.md) — journal format and invariants.
- [references/STAGES.md](references/STAGES.md) — stage-by-stage procedure for standalone mode.
- [references/SPEC-EXAMPLE.md](references/SPEC-EXAMPLE.md) — canonical worked example.
- [ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md](ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md) — how to translate requirements into observable acceptance criteria, architecture/test-design requirements, tasks, and automated tests at the right boundary.
