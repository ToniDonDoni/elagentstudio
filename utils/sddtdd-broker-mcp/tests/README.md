# Broker MCP tests

This directory contains focused unit-style tests for `utils/sddtdd-broker-mcp/server.py`.

## What is tested

The tests cover the broker MCP server contract and its local state-handling helpers:

- server registration (`app.name`, MCP tool handler registration);
- JSON response parsing from the sampled broker model;
- broker prompt construction, including loading the shared `spec-driven-tdd` skill and the in-folder orchestrator role file;
- `next_task` input-schema gating;
- extraction of evidence file paths from journal text;
- repository-state capture from committed `HEAD` instead of dirty working-tree contents;
- gating that prevents `next_task` before the previous task has passed broker verification.

## Why there are temporary Git repos in the tests

Some broker behavior depends on real Git state, not mocks:

- committed `HEAD` contents;
- dirty working-tree detection;
- `.git/...` runtime files.

For those cases, the tests use pytest's `tmp_path` fixture to create throwaway repositories at runtime with `git init`, commit minimal files, and then call the server helpers against that temporary repo.

This is why the tests write files such as:

- `JOURNAL_SDD_TDD_SKILL.log`
- `evidence/red.txt`
- `.git/sddtdd/broker-access.jsonl`

These files are test fixtures created inside a temporary repository so the broker code can be exercised against realistic repository state.

## What the log file is

`broker-access.jsonl` is the broker runtime event log used by the server.

Current tests use it to model one important state transition:

- a broker task is verified with status `PASS`;
- only after that may `next_task` proceed.

The helper `_append_broker_event(...)` writes JSON Lines records into:

- `<repo>/.git/sddtdd/broker-access.jsonl`

The test `test_next_task_gate_requires_verified_task` creates this log in a temporary repo and appends a synthetic `task_verified` event to prove that the gate opens only after verification.

## Test scenario style

These are not end-to-end workflow tests for the full SDDTDD process.
They are small contract tests for the broker server itself:

1. create minimal input state;
2. call a helper or MCP-facing function;
3. assert the contract the broker must preserve.

That keeps the suite fast while still checking the Git/journal behavior that matters for broker sequencing.

## Main scenario covered by the Git-backed tests

The most important broker scenario in this directory is:

1. create a temporary Git repository;
2. write a minimal `JOURNAL_SDD_TDD_SKILL.log` and, when needed, an evidence file such as `evidence/red.txt`;
3. commit that state so the repo has a real `HEAD`;
4. optionally dirty the working tree after the commit;
5. optionally append a broker runtime event to `.git/sddtdd/broker-access.jsonl`;
6. call the broker helper under test;
7. verify that the helper behaves as the broker contract requires.

### Expected behavior in that scenario

- `capture_repo_state(...)` should read the committed files from `HEAD`, not the uncommitted dirty version.
- `capture_repo_state(...)` should load evidence files that are referenced explicitly or discoverable from the journal.
- `_verify_next_task_gate(...)` should block `next_task` before broker verification has passed.
- `_verify_next_task_gate(...)` should allow `next_task` only after a `task_verified` event with status `PASS` exists in the broker log.

### Practical interpretation

So the scenario is not "run the full SDDTDD workflow".
It is "simulate just enough repository and broker state to prove that the broker reads the right truth source and enforces sequencing".

## How to run

From the repository root:

```bash
uv run --directory utils/sddtdd-broker-mcp pytest -q
```
