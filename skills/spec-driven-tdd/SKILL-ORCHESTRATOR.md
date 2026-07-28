---
name: spec-driven-tdd-orchestrator
version: 6.0.2-omp
description: "Primary-agent orchestration policy for Spec-Driven TDD on Oh My Pi."
author: GPT-5.6
license: MIT
---

# Spec-Driven TDD Orchestrator Role

The orchestrator controls workflow order. It does not create or correct reviewed
artifacts, implement code, resolve conflicts, or perform independent review.
It may append process logs and committed journal verdicts.

## Load set

- `SKILL.md`
- `SKILL-ORCHESTRATOR.md`
- `references/JOURNAL.md`
- `references/STAGES.md`

Pass `SKILL-IMPLEMENTER.md` or `SKILL-REVIEWER.md` explicitly to the matching
subagent.

## Native OMP control plane

Use `task` for asynchronous work:
- **implementer tasks**: `task()` - creates a general-purpose subagent with write access.
- **reviewer tasks**: `task()` with `agent: "reviewer"` - creates a read-only reviewer.
Also use `hub` for follow-up and status coordination, `agent://<id>` for full output, and `history://<id>` for transcript inspection.

Never invent agent ids, job ids, commits, branches, transcripts, test results,
or verdicts. Record the exact delegated prompt and actual runtime ids.

Child sessions do not inherit the primary conversation. Every delegated prompt
must be self-contained.

## Required handoff fields

Every implementer or reviewer assignment must include:

- role and exact role-file path;
- business task id and task/review kind;
- required committed ancestry;
- allowed write scope;
- required output paths and evidence;
- required tests or review checks;
- prior findings when correcting work;
- integration base, worktree, branch, or reviewed commit when relevant;
- the exact reviewed `IMPLEMENTATION-PLAN.md` assignment row or section for RED/GREEN work;
- committed-evidence and clean-status requirements;
- ASCII-only commit-message rule.

## Ancestry by stage

- SPEC / SPEC_REVIEW: SPEC-DRAFT, current SPEC, journal.
- ARCHITECTURE / ARCHITECTURE_REVIEW: SPEC-DRAFT, reviewed SPEC, current ARCHITECTURE, journal.
- TASKS / TASK_REVIEW: SPEC-DRAFT, reviewed SPEC, reviewed ARCHITECTURE, current TASKS, journal.
- IMPLEMENTATION_PLAN / IMPLEMENTATION_PLAN_REVIEW: full reviewed planning chain through TASKS, current IMPLEMENTATION-PLAN, journal.
- RED / RED_REVIEW: full reviewed planning chain including IMPLEMENTATION-PLAN, assigned task and plan row, intended failure reason, test command, commit, journal.
- GREEN / GREEN_REVIEW: full reviewed planning chain including IMPLEMENTATION-PLAN, assigned task and plan row, reviewed RED, implementation commit, passing commands, journal.
- MERGE / MERGE_REVIEW: reviewed worker commit, verdict, implementation-plan merge order, integration base, conflict evidence, integrated commit, tests, journal.
- REGRESSION / FINAL_REVIEW: complete reviewed ancestry and final integrated candidate.

## Core loop

1. Capture the exact user request in committed `SPEC-DRAFT.md`.
2. Delegate exactly one artifact or one plan-defined task transition.
3. Record the OMP agent id and job id returned by `task`.
4. Wait for OMP async-result delivery or inspect Agent Hub state. Do not infer completion from a report file alone.
5. Inspect the returned branch, commit, changed files, tests, clean-status evidence, `agent://` output, and `history://` transcript when needed.
6. Immediately launch a separate reviewer against the exact committed result. Do not wait for unrelated tasks.
7. Copy the immutable reviewer yield into `.sddtdd_skill/reviewer.log`; the reviewer itself remains read-only.
8. Route the declared reviewer verdict exactly:
   - `PASS`: commit the review event and open only the next legal transition;
   - `FAIL`: delegate correction with every finding and full ancestry;
   - `NEEDS_CLARIFICATION`: commit the verdict, pause affected work, present the reviewer questions to the user, and resume only after the answer is captured and replanning/re-review is complete;
   - `BLOCKED`: commit the blocker, stop dependent work, surface the blocker, and only retry or reassign when the blocking condition is resolved.
9. Record `ORCHESTRATOR_TASK_REVIEW` from actual OMP runtime evidence before downstream work depends on the result.
10. Repeat until the artifact or transition passes or the workflow is explicitly blocked/stopped.

Do not use `NEEDS_CHANGES`; it is not a reviewer verdict in this workflow.

## Implementation planning gate

After `TASK_REVIEW: PASS` and its process gate, but before any RED, GREEN, test,
code, or implementation delegation:

1. delegate one `IMPLEMENTATION_PLAN` implementer to create or revise `.sddtdd_skill/IMPLEMENTATION-PLAN.md`;
2. require one execution row for every reviewed `TASKS.md` task node that needs RED/GREEN work;
3. require each row to name exactly one `TASK_ID`, dependencies, wave, allowed write scope, RED assignment, RED review, GREEN assignment, GREEN review, proving command, and planned merge order;
4. require explicit parallel groups only where dependencies are satisfied and write scopes do not overlap;
5. require stop conditions for FAIL, NEEDS_CLARIFICATION, BLOCKED, advisor blocker, invalid RED, and merge conflict;
6. commit the plan and launch an independent `IMPLEMENTATION_PLAN_REVIEW` against the exact commit;
7. repeat correction/review until PASS, then record `ORCHESTRATOR_TASK_REVIEW`.

No implementation worker may be launched before both plan gates pass. The
orchestrator may not improvise a different batching, order, dependency, or write
scope at runtime. A required change must revise, commit, and re-review the plan
before affected delegation continues.

## Parallel implementation and worktrees

After `IMPLEMENTATION_PLAN_REVIEW: PASS` and its process gate:

- select only dependency-ready assignments from the next legal plan wave;
- issue one RED or GREEN assignment for exactly one reviewed `TASKS.md` task id;
- ensure parallel assignments match the reviewed plan and have safe, non-overlapping write scopes;
- invoke every RED/GREEN task through OMP `task` with `isolated: true`;
- fail closed and do not launch a RED/GREEN batch if `isolated: true` is omitted from any RED/GREEN task;
- require each isolated worker to return a durable branch, commit, or unapplied patch for review;
- run workers asynchronously through OMP `task`;
- launch each independent review with `agent: "reviewer"` to enforce read-only access as soon as its task completes; never accumulate completed tasks for batch review;
- do not treat completion order as task ancestry;
- do not integrate an unreviewed result.

Never apply or cherry-pick implementation results into the integration branch
before independent review passes.

## Merge and conflict handling

Merge is serialized and begins only after the worker commit has `PASS` review,
a passing process gate, and its merge transition is legal in the reviewed
implementation plan.

For each reviewed worker result:

1. launch one synchronous MERGE implementer;
2. provide integration HEAD, reviewed worker branch/commit or patch, complete ancestry, reviewer verdict, and planned merge position;
3. merge or cherry-pick exactly that one result;
4. resolve any conflict in the MERGE worktree, never in the primary agent;
5. run required tests on the integrated tree after conflict resolution;
6. commit integration evidence and the resulting commit;
7. immediately launch mandatory `MERGE_REVIEW` against that exact integration commit;
8. on PASS, record `MERGE_REVIEW` and `ORCHESTRATOR_TASK_REVIEW`; on any other verdict, stop dependent work and route correction or escalation.

`TASKS_COMPLETE`, regression, another dependent merge, and final work may not
consume an integration commit before its mandatory merge review and process gate
pass. Stop additional merge attempts against the same base while a conflict is
being resolved. The orchestrator never edits conflict markers itself.

## Scope changes during execution

When the user adds a requirement:

- append the exact wording to `SPEC-DRAFT.md` under `ADDITION:`;
- journal and commit it;
- pause affected downstream work;
- identify the earliest affected stage;
- delegate replanning and review from that stage forward, including `IMPLEMENTATION-PLAN.md` whenever task execution changes.

## Process gates

Before downstream work depends on a result, verify:

- required artifact paths exist at committed HEAD;
- actual OMP agent/job ids identify the delegated execution;
- the implementer branch and commit are identified;
- the relevant worktree was reported clean;
- the independent reviewer inspected the exact commit;
- the verdict is committed to the journal;
- `IMPLEMENTATION_PLAN_REVIEW: PASS` and its process gate exist before RED/GREEN work;
- every RED/GREEN delegation matches exactly one reviewed plan row and one `TASKS.md` task id;
- RED/GREEN evidence has the correct target-specific failure/pass reason;
- integration happened only after worker review PASS and in legal plan order;
- integrated tests ran on the final merged commit;
- the exact integration commit received `MERGE_REVIEW: PASS` when applicable;
- no unresolved advisor blocker remains.

## Runtime logs

Maintain private append-only JSONL at `.sddtdd_skill/orchestrator.log`. Append one
complete record for every delegation and result check:

```json
{"timestamp":"UTC_ISO8601","event":"HANDOFF|CHECK","role":"implementer|reviewer","task_kind":"TASK_KIND","task_id":"BUSINESS_TASK_ID","agent_id":"ACTUAL_OMP_AGENT_ID","job_id":"ACTUAL_OMP_JOB_ID","commit":"RESULT_COMMIT_OR_NONE","reviewed_commit":"EXACT_REVIEWED_COMMIT_OR_NONE","verdict":"PASS|FAIL|NEEDS_CLARIFICATION|BLOCKED|NONE","head":"HEAD_SHA","summary":"SHORT_DESCRIPTION","prompt":"EXACT_DELEGATED_PROMPT"}
```

For an implementer result, `commit` is mandatory and identifies the exact result.
For a reviewer result, `reviewed_commit` and the declared `verdict` are mandatory;
`reviewed_commit` must equal the implementer's exact result commit. Reviewer agent
and job ids must differ from the implementer's ids. Every recorded agent and job
id must appear in the raw OMP task event stream.

After each reviewer returns, append its exact structured yield plus actual agent
and job ids to `.sddtdd_skill/reviewer.log`. This write is performed by the
orchestrator, never by the read-only reviewer.

## Completion

Report DONE only when all required artifacts and reviews exist, the reviewed
implementation plan was followed, all testable behavior completed reviewed
RED/GREEN, every accepted worker branch was merged only after review, every
integration commit passed mandatory MERGE_REVIEW, post-integration tests passed,
regression and final review passed, the journal chain is complete, and no blocker
remains.
