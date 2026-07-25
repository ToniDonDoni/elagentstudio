---
name: spec-driven-tdd
version: 6.0.0-omp
description: "Spec-Driven TDD workflow implemented with native Oh My Pi orchestration, isolated subagents, independent review, and advisor watchdog supervision."
author: GPT-5.6
license: MIT
---

# Spec-Driven TDD for Oh My Pi

## Purpose

Turn a user request into committed software through a strict artifact chain,
independent review, reviewed RED/GREEN TDD, isolated parallel implementation,
and committed evidence.

This variant uses native Oh My Pi (OMP) facilities. It does not require the
`sddtdd-mcp` registrar or MCP sampling.

## OMP entrypoints

- `AGENTS.md` loads the shared and orchestrator policies into the primary agent.
- `WATCHDOG.md` loads advisor-only process supervision.
- `SKILL-ORCHESTRATOR.md` controls delegation and process gates.
- `SKILL-IMPLEMENTER.md` controls artifact creation, tests, code, and merge work.
- `SKILL-REVIEWER.md` controls independent semantic review.
- `SKILL-WATCHDOG.md` tells the OMP advisor what process violations to detect.

## Roles

There are four roles with strict separation:

- Orchestrator: the primary OMP agent. It delegates, monitors, gates, and records handoffs. It does not implement or review.
- Implementer: an OMP `task` subagent that creates one requested artifact or implementation result.
- Reviewer: a separate OMP reviewer subagent that reviews committed evidence and never fixes it.
- Watchdog: the OMP advisor attached to the primary session. It continuously checks the orchestrator process and emits `nit`, `concern`, or `blocker` advice. It does not replace independent artifact review.

## Native OMP primitives

Use these instead of MCP:

- `task` for asynchronous subagents and batch fan-out.
- `isolated: true` for implementation work that must run in an isolated workspace.
- OMP branch-mode isolation for automatic commit/cherry-pick merge when configured.
- `hub` for follow-up, correction, cancellation, and status coordination.
- `agent://<id>` for full subagent output.
- `history://<id>` for the subagent transcript.
- parent async job delivery and the Agent Hub for completion state.
- session and advisor JSONL transcripts as the raw execution audit trail.

## Workflow artifacts

The workflow state lives under `.sddtdd_skill/`:

- `SPEC-DRAFT.md`: exact user input and later append-only additions.
- `SPEC.md`: reviewed requirements and acceptance criteria.
- `ARCHITECTURE.md`: reviewed design and test boundaries.
- `TASKS.md`: reviewed task graph and dependencies.
- `JOURNAL_SDD_TDD_SKILL.log`: committed workflow evidence.
- `orchestrator.log`: append-only orchestrator handoff/check records.
- `reviewer.log`: append-only independent review records.

OMP session transcripts, `agent://`, `history://`, advisor transcripts, patches,
and task metadata are runtime audit evidence. Required workflow decisions must
also be summarized in the committed journal so the repository remains auditable
without a live OMP session.

## Hard rules

1. Every agent-generated artifact receives independent review before downstream work depends on it.
2. Every automatically testable behavior passes through reviewed RED and reviewed GREEN.
3. Review only committed evidence. Uncommitted working-tree state is not evidence.
4. The orchestrator never implements or reviews its own delegated work.
5. The reviewer never authors fixes, merges, or advances the workflow.
6. Independent review and watchdog supervision are different gates; neither replaces the other.
7. Commit messages are ASCII-only.
8. Parallel implementation is allowed only for tasks whose dependencies and write scopes do not overlap dangerously.
9. Merge results must be tested after integration, not only inside the isolated worker.
10. A RED test is valid only when it fails for the target missing behavior or target bug. Failure caused by unrelated prerequisites or unrelated defects is not valid RED evidence.

## User scope changes

`SPEC-DRAFT.md` is append-only after its first commit.

When the user adds or changes a product requirement during work:

1. append the exact new wording under an `ADDITION:` label;
2. journal and commit the addition before acting on it;
3. treat it as a scope change;
4. return to the earliest affected stage;
5. revise and re-review SPEC, architecture, tasks, RED, and GREEN evidence as needed.

Never silently overwrite the original request or squeeze a new requirement into
the current implementation task without replanning.

## Required flow

1. Capture and commit `SPEC-DRAFT.md`.
2. Delegate SPEC creation to an implementer; commit; launch an independent SPEC reviewer.
3. Repeat implementer/reviewer correction cycles until SPEC passes.
4. Repeat the same cycle for ARCHITECTURE and TASKS.
5. Launch eligible implementation shards through asynchronous isolated OMP tasks.
6. As soon as one worker completes, inspect its returned commit, transcript, output, tests, and clean-state evidence; immediately launch a separate reviewer for that result.
7. On review failure, message the original worker through `hub` when it remains revivable; otherwise launch a new implementer with the complete ancestry and findings.
8. Let OMP branch-mode isolation merge reviewed work automatically when possible.
9. If automatic merge reports conflicts, patch-apply failure, or `stashConflict`, serialize integration and delegate one conflict-resolution task with both parent and worker evidence. Re-run required tests on the integrated tree before accepting the merge.
10. Run and review regression evidence on the final integrated candidate.
11. Run final traceability review and record DONE only after every required gate passes.

## Delegation context

Every implementer and reviewer receives:

- exact role and role-file path;
- task id and task kind;
- allowed write scope;
- required output and evidence;
- repository and target branch context;
- relevant committed ancestry;
- relevant prior verdicts and corrections;
- explicit instruction to use ASCII-only commit messages;
- an output schema when structured output is useful.

Child sessions do not inherit the parent conversation. Never rely on unstated
conversation history; pass the required context in the `task` request.
