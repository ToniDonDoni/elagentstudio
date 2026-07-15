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
- architecture work is illegal before `SPEC_REVIEW: PASS`.

## Stage 2 — Architecture

Create or revise `.sddtdd_skill/ARCHITECTURE.md` mapping design decisions back
to reviewed requirements.

Review gate:

- request `ARCHITECTURE_REVIEW`;
- task decomposition is illegal before `ARCHITECTURE_REVIEW: PASS`.

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
- implementation work is illegal before `TASK_REVIEW: PASS`.

## Stage 4 — Per-task RED/GREEN

For every automatically testable task:

1. select the reviewed task, requirement ids, architecture references, and acceptance condition;
2. write the highest practical proving test;
3. establish RED with exact failing command and expected missing-behavior reason;
4. request `RED_REVIEW`;
5. implement only the minimum change needed;
6. establish GREEN with exact passing commands on committed state;
7. request `GREEN_REVIEW`.

Rules:

- implementation is illegal before `RED_REVIEW: PASS`;
- task completion is illegal before `GREEN_REVIEW: PASS`;
- supplementary unit tests do not replace the proving test.

## Stage 5 — Task Convergence

When all required task branches pass GREEN review, append `TASKS_COMPLETE`.

Regression is illegal before convergence.

## Stage 6 — Regression

Run the complete required affected-suite regression on the final candidate
commit and record exact commands, scope, result, and justified omissions.

Review gate:

- request `REGRESSION_REVIEW`;
- final completion is illegal before `REGRESSION_REVIEW: PASS`.

## Stage 7 — Final

Prepare final evidence covering traceability, final behavior, explicit
deviations, residual risks, and final artifact list.

Review gate:

- request `FINAL_REVIEW`;
- DONE is illegal before `FINAL_REVIEW: PASS`.

## Stage 8 — Done

Append `DONE` only when all required artifacts exist, all required reviews pass,
all automatically testable behaviors completed reviewed RED/GREEN, regression
passed and was reviewed, and the journal chain is intact.
