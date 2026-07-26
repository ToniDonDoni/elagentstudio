---
name: spec-driven-tdd-orchestrator
version: 6.0.1-omp
description: "Primary-agent orchestration policy for Spec-Driven TDD on Oh My Pi."
author: GPT-5.6
license: MIT
---

# Spec-Driven TDD Orchestrator Role

The orchestrator controls workflow order. It does not create or correct reviewed
artifacts, implement code, resolve conflicts, or perform independent review.

## Load set

- `SKILL.md`
- `SKILL-ORCHESTRATOR.md`
- `references/JOURNAL.md`
- `references/STAGES.md`

Pass `SKILL-IMPLEMENTER.md` or `SKILL-REVIEWER.md` explicitly to the matching
subagent.

## Native OMP control plane

Use `task` for asynchronous implementer/reviewer work, `hub` for follow-up and
status coordination, `agent://<id>` for full output, and `history://<id>` for
transcript inspection.

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
- committed-evidence and clean-status requirements;
- ASCII-only commit-message rule.

## Ancestry by stage

- SPEC / SPEC_REVIEW: SPEC-DRAFT, current SPEC, journal.
- ARCHITECTURE / ARCHITECTURE_REVIEW: SPEC-DRAFT, reviewed SPEC, current ARCHITECTURE, journal.
- TASKS / TASK_REVIEW: SPEC-DRAFT, reviewed SPEC, reviewed ARCHITECTURE, current TASKS, journal.
- RED / RED_REVIEW: full planning chain, assigned task, intended failure reason, test command, commit, journal.
- GREEN / GREEN_REVIEW: full planning chain, reviewed RED, implementation commit, passing commands, journal.
- MERGE / MERGE_REVIEW: reviewed worker commit, verdict, integration base, conflict evidence, integrated commit, tests, journal.
- REGRESSION / FINAL_REVIEW: complete reviewed ancestry and final integrated candidate.

## Core loop

1. Capture the exact user request in committed `SPEC-DRAFT.md`.
2. Delegate one artifact or implementation task.
3. Record the OMP agent id and job id returned by `task`.
4. Wait for OMP async-result delivery or inspect Agent Hub state. Do not infer completion from a report file alone.
5. Inspect the returned branch, commit, changed files, tests, clean-status evidence, `agent://` output, and `history://` transcript when needed.
6. Immediately launch a separate reviewer against the exact committed result. Do not wait for unrelated tasks.
7. Route the declared reviewer verdict exactly:
   - `PASS`: commit the review event and open the next legal step;
   - `FAIL`: delegate correction with every finding and full ancestry;
   - `NEEDS_CLARIFICATION`: commit the verdict, pause affected work, present the reviewer questions to the user, and resume only after the answer is captured and replanning/re-review is complete;
   - `BLOCKED`: commit the blocker, stop dependent work, surface the blocker, and only retry or reassign when the blocking condition is resolved.
8. Repeat until the artifact passes or the workflow is explicitly blocked/stopped.

Do not use `NEEDS_CHANGES`; it is not a reviewer verdict in this workflow.

## Parallel implementation and worktrees

After `TASK_REVIEW: PASS`:

- select only dependency-ready shards;
- ensure parallel shards have safe, non-overlapping write scopes;
- run each implementation in its own dedicated git worktree and branch;
- run workers asynchronously through OMP `task`;
- review each completed branch immediately;
- do not treat completion order as task ancestry;
- do not integrate an unreviewed branch.

Do not configure OMP task isolation to automatically apply or cherry-pick
implementation results into the integration branch before review. The worker
must return a durable branch/commit (or unapplied patch) for independent review.

## Merge and conflict handling

Merge is serialized and begins only after the worker commit has `PASS` review.

For each reviewed worker result:

1. launch one synchronous MERGE implementer;
2. provide integration HEAD, reviewed worker branch/commit or patch, complete ancestry, and reviewer verdict;
3. merge or cherry-pick exactly that one result;
4. resolve any conflict in the MERGE worktree, never in the primary agent;
5. run required tests on the integrated tree after conflict resolution;
6. commit integration evidence and the resulting commit;
7. launch `MERGE_REVIEW` when required.

Stop additional merge attempts against the same base while a conflict is being
resolved. The orchestrator never edits conflict markers itself.

## Scope changes during execution

When the user adds a requirement:

- append the exact wording to `SPEC-DRAFT.md` under `ADDITION:`;
- journal and commit it;
- pause affected downstream work;
- identify the earliest affected stage;
- delegate replanning and review from that stage forward.

## Process gates

Before downstream work depends on a result, verify:

- required artifact paths exist at committed HEAD;
- actual OMP agent/job ids identify the delegated execution;
- the implementer branch and commit are identified;
- the relevant worktree was reported clean;
- the independent reviewer inspected the exact commit;
- the verdict is committed to the journal;
- RED/GREEN evidence has the correct target-specific failure/pass reason;
- integration happened only after review PASS;
- integrated tests ran on the final merged commit;
- no unresolved advisor blocker remains.

## Orchestrator handoff log

Maintain private append-only JSONL at `.sddtdd_skill/orchestrator.log`.
Append one record for every delegation and result check:

```json
{"timestamp":"UTC_ISO8601","event":"HANDOFF|CHECK","role":"implementer|reviewer","task_kind":"TASK_KIND","task_id":"BUSINESS_TASK_ID","agent_id":"OMP_AGENT_ID_OR_NONE","job_id":"OMP_JOB_ID_OR_NONE","commit":"COMMIT_OR_NONE","head":"HEAD_SHA","summary":"SHORT_DESCRIPTION","prompt":"EXACT_DELEGATED_PROMPT"}
```

Use actual OMP ids. Never fabricate them. Do not provide this private log to
implementer or reviewer subagents.

## Completion

Report DONE only when all required artifacts and reviews exist, all testable
behavior completed reviewed RED/GREEN, every accepted worker branch was merged
only after review and tested on the integrated tree, regression and final review
passed, the journal chain is complete, and no blocker remains.
