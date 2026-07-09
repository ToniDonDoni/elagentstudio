# Spec-Driven TDD Example

Start call:

```json
{
  "repo_path": "/repo",
  "task_kind": "INITIAL_USER_INPUT",
  "task_id": null,
  "claimed_result": null,
  "work_journal_id": null,
  "evidence": {
    "user_input": "Build a counter API with increment and read endpoints."
  }
}
```

Expected result:

- `status: task`
- `task_review: null`
- `next_task.task_kind: USER_INPUT_CAPTURE`

For a reviewed task like `RED`, the legal chain is:

```text
RED work entry (COMPLETED)
→ RED_REVIEW (PASS, parent = RED)
→ getNextTask completed-task call
→ ORCHESTRATOR_TASK_REVIEW (PASS, parent = RED_REVIEW)
→ GREEN task
```

If reviewed files changed after `RED_REVIEW: PASS`, the orchestrator must return
`FAIL` until a fresh committed review verdict exists on the current HEAD.
