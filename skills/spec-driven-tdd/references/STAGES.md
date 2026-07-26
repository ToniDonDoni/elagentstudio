# Stage-by-Stage Procedure (Standalone Mode)

This file is for standalone mode only.

## Stage 0 — Capture User Input

Create `.sddtdd_skill/SPEC-DRAFT.md` as the exact raw user request.

Rules:

- preserve original wording and language;
- do not normalize, translate, or reinterpret;
- commit it once;
- never rewrite it after first commit.

Journal:

- `TYPE: USER_INPUT`
- `STATUS: COMPLETED`

## Stage 1 — Requirements

Create or revise `.sddtdd_skill/SPEC.md` with stable requirement IDs,
constraints, acceptance criteria, edge cases, and clarifications.

Review gate:

- request `SPEC_REVIEW`;
- record `ORCHESTRATOR_TASK_REVIEW` from native OMP evidence;
- architecture work is illegal before both pass.

## Stage 2 — Architecture

Create or revise `.sddtdd_skill/ARCHITECTURE.md` mapping design decisions back
to reviewed requirements.

Review gate:

- request `ARCHITECTURE_REVIEW`;
- record `ORCHESTRATOR_TASK_REVIEW`;
- task decomposition is illegal before both pass.

## Stage 3 — Decomposition

Create or revise `.sddtdd_skill/TASKS.md`.

Each task should define:

- `TASK_ID`
- `PARENT_TASK_ID`
- `ROOT_USER_INPUT_ID`
- reviewed requirement references
- architecture references
- acceptance condition
- real dependencies

Review gate:

- request `TASK_REVIEW`;
- record `ORCHESTRATOR_TASK_REVIEW`;
- implementation work is illegal before both pass.

## Stage 4 — Per-task RED/GREEN

For every automatically testable task:

1. select the reviewed task, requirement ids, architecture references, and acceptance condition;
2. write the highest practical proving test;
3. establish RED with exact failing command and expected missing-behavior reason;
4. request `RED_REVIEW` and record the process gate;
5. implement only the minimum change needed;
6. establish GREEN with exact passing commands on committed state;
7. request `GREEN_REVIEW` and record the process gate.

Rules:

- implementation is illegal before target-specific `RED_REVIEW: PASS` and its process gate;
- integration is illegal before `GREEN_REVIEW: PASS` and its process gate;
- supplementary unit tests do not replace the proving test.

## Stage 5 — Reviewed Integration

For each independently reviewed worker commit:

1. delegate one synchronous MERGE implementer;
2. integrate exactly one reviewed result;
3. resolve conflicts only in the merge worktree;
4. run required tests on the integrated commit;
5. commit the integration result and evidence;
6. request mandatory `MERGE_REVIEW` for that exact commit;
7. record `ORCHESTRATOR_TASK_REVIEW` after merge review PASS.

No other merge or downstream stage may consume the integration commit before
both gates pass.

## Stage 6 — Task Convergence

When all required task branches pass GREEN review, integration, mandatory merge
review, and process gates, append `TASKS_COMPLETE`.

Regression is illegal before convergence.

## Stage 7 — Regression

Run the complete required affected-suite regression on the final candidate
commit and record exact commands, scope, result, and justified omissions.

Review gate:

- request `REGRESSION_REVIEW`;
- record `ORCHESTRATOR_TASK_REVIEW`;
- final completion is illegal before both pass.

## Stage 8 — Final

Prepare final evidence covering traceability, final behavior, explicit
deviations, residual risks, and final artifact list.

Review gate:

- request `FINAL_REVIEW`;
- record `ORCHESTRATOR_TASK_REVIEW`;
- DONE is illegal before both pass.

## Stage 9 — Done

Append `DONE` only when all required artifacts exist, all required reviews pass,
all automatically testable behaviors completed reviewed RED/GREEN, every
integration commit passed mandatory merge review, regression passed and was
reviewed, and the journal chain is intact.
