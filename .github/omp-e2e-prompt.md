Use the Spec-Driven TDD workflow imported by AGENTS.md and run as the primary orchestrator.

Build a minimal runnable Hello World web page in this repository.

Product requirements:
- The application is served from `app/` and opens in a browser.
- `app/index.html` visibly displays the exact text `Hello World`.
- Keep the implementation dependency-free.
- Add `package.json` with `npm test` and `npm run start` scripts.
- `npm test` must run a deterministic automated check proving the generated page contains `Hello World`.
- `npm run start` must serve `app/` on port 4173.

Process requirements:
- Capture the exact request in `.sddtdd_skill/SPEC-DRAFT.md`.
- Create, commit, independently review, and journal SPEC, ARCHITECTURE, and TASKS.
- Use `TASK_REVIEW`, never `TASKS_REVIEW`.
- After TASK_REVIEW passes, create and commit `.sddtdd_skill/IMPLEMENTATION-PLAN.md` before any RED, GREEN, test, code, or implementation delegation.
- The implementation plan must define one TASKS.md task id per RED/GREEN assignment, dependency waves, non-overlapping parallel write scopes, RED then RED_REVIEW then GREEN then GREEN_REVIEW order, and serialized merge order.
- Independently review the exact plan commit with `IMPLEMENTATION_PLAN_REVIEW`, record the following `ORCHESTRATOR_TASK_REVIEW`, and do not start implementation before both pass.
- Delegate RED and GREEN work to asynchronous OMP implementer subagents exactly as defined by the reviewed implementation plan.
- Every RED/GREEN writing task item must set `isolated: true` and `apply: false`; treat either omission as a process failure and do not launch the batch.
- Use native branch-mode task isolation and return durable task branches or commits for review.
- Implementation workers must not use `git stash`; commit intermediate state inside their isolated task branch.
- The primary orchestrator must not implement or review.
- Independent reviewers are strictly read-only and return immutable yields; the orchestrator records those yields in runtime logs.
- Do not integrate implementation commits before independent review PASS.
- Route PASS, FAIL, NEEDS_CLARIFICATION, and BLOCKED explicitly.
- Merge reviewed work through one synchronous MERGE implementer at a time and in reviewed plan order.
- Run tests again on the integrated commit.
- Independently review every exact integration commit with mandatory MERGE_REVIEW before any downstream use.
- Complete regression and final independent reviews.
- Record committed workflow verdicts with the original journal schema, including IMPLEMENTATION_PLAN, IMPLEMENTATION_PLAN_REVIEW, ORCHESTRATOR_TASK_REVIEW, MERGE, MERGE_REVIEW, and DONE.
- Record complete `.sddtdd_skill/orchestrator.log` JSONL rows with actual OMP agent/job ids, exact prompts, task ids, result commits, reviewer verdicts, and `reviewed_commit` values matching the exact implementer commits.
- Every recorded agent and job id must be the actual id returned in the raw OMP task event stream.
- Use ASCII-only commit messages.
- Commit every generated artifact and journal entry.
- Finish only after the repository is clean and the Hello World page is runnable.
