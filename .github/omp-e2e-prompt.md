Use the Spec-Driven TDD workflow imported by AGENTS.md and run as the primary orchestrator.

Build a small runnable browser Arkanoid game in this repository.

Product requirements:
- The game is served from `app/` and opens in a browser.
- It has a visible canvas, paddle, ball, destructible brick grid, score, lives, start/restart control, keyboard controls, collision handling, win state, and game-over state.
- Keep the implementation dependency-free.
- Add `package.json` with `npm test` and `npm run start` scripts.
- `npm test` must run deterministic automated checks covering the core game logic and generated browser files.
- `npm run start` must serve `app/` on port 4173.

Process requirements:
- Capture the exact request in `.sddtdd_skill/SPEC-DRAFT.md`.
- Create, commit, independently review, and journal SPEC, ARCHITECTURE, and TASKS.
- Use `TASK_REVIEW`, never `TASKS_REVIEW`.
- Delegate RED and GREEN work to asynchronous OMP implementer subagents.
- The primary orchestrator must not implement or review.
- Use dedicated git worktrees and branches for implementation work.
- Do not integrate implementation commits before independent review PASS.
- Route PASS, FAIL, NEEDS_CLARIFICATION, and BLOCKED explicitly.
- Merge reviewed work through one synchronous MERGE implementer at a time.
- Run tests again on the integrated commit.
- Complete regression and final independent reviews.
- Record native OMP agent/job ids, commits, test evidence, review verdicts, ORCHESTRATOR_GATE events, and DONE in the committed journal.
- Use ASCII-only commit messages.
- Commit every generated artifact and journal entry.
- Finish only after the repository is clean and the game is runnable.
