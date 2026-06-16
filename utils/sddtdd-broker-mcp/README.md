# sddtdd-broker-mcp

MCP task broker for Spec-Driven TDD broker mode. The broker reads the
committed repository state, the SDDTDD journal, samples an LLM using the
shared process skill, the in-folder orchestrator role file, and the
stage-by-stage procedure, and answers two questions from the
implementer: what is the next task, and was the current task actually
completed correctly and within scope.

The orchestrator role file (`skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md`)
is the source of truth for the workflow order, the review rules, and
the broker-level task verification policy. The implementer only needs
the two decision tools and the self-contained broker task fields
(`instruction`, `allowed_scope`, `required_evidence`,
`independent_review_required`, `review_type`).

The broker is configured with the role files at startup, not per call.
The implementer does not hand the broker skill files on every call.

## Configuration

The broker resolves its skill paths at startup from environment
variables, with sensible fallbacks to the in-folder skill files:

| Environment variable | Default |
|---|---|
| `SDDTDD_BROKER_PROCESS_SKILL` | `skills/spec-driven-tdd/SKILL.md` |
| `SDDTDD_BROKER_ORCHESTRATOR_ROLE` | `skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md` |
| `SDDTDD_BROKER_STAGES_REF` | `skills/spec-driven-tdd/references/STAGES.md` |

## Tools

### `init`

Start or resume brokered work for a repository.

```json
{
  "repo_path": "/path/to/project",
  "user_input": "original user request"
}
```

### `getNextTask`

Ask the orchestrator for the next task, or for `complete` / `blocked`.

```json
{
  "repo_path": "/path/to/project",
  "previous_task_id": "B-000001"
}
```

`previous_task_id` is optional. On the first call after `init`, omit it.
On subsequent calls, pass the task id returned by the previously
verified task.

The response is one of:

- `{"status": "TASK", "task_id": "...", "instruction": "...", "allowed_scope": [...], "required_evidence": [...], "independent_review_required": true, "review_type": "...", "rationale": "..."}`
- `{"status": "complete", ...}`
- `{"status": "blocked", ...}`

A `TASK` is self-contained. The implementer follows the `instruction`
literally, stays within `allowed_scope`, produces the items in
`required_evidence`, and only runs the independent reviewer when
`independent_review_required` is true.

### `reviewTask`

Ask the orchestrator to verify that the current task was actually
completed correctly and within scope. This is a **semantic** task
verification, not a presence-of-paperwork check.

```json
{
  "repo_path": "/path/to/project",
  "task_id": "B-000001",
  "claimed_result": "SPEC.md committed and journaled",
  "evidence": {
    "commits": ["abc123"],
    "journal_ids": ["J-20260616-001", "J-20260616-002"],
    "review_request_id": "01HXX...",
    "test_commands": ["pytest -q"],
    "files": ["SPEC.md", "JOURNAL_SDD_TDD_SKILL.log"]
  }
}
```

The response is one of:

- `PASS` — the task is verified; call `getNextTask` again.
- `FAIL` — fix the listed gaps and call `reviewTask` again.
- `NEEDS_CLARIFICATION` — supply the missing information.
- `ERROR` — resolve tooling or repository state first.

## Broker access log

The broker writes every `reviewTask` call to an append-only JSONL log
so the broker's checks can be investigated:

```text
<repo>/.git/sddtdd/broker-access.jsonl
```

Each call produces two events:

- `task_review_started` — written at the start of `reviewTask`,
  containing the request id, the broker task id, the claimed head SHA,
  and a snapshot of the requested evidence.
- `task_review_completed` — written at the end, containing the request
  id, the broker task id, the actual head SHA, the verdict
  (`PASS`, `FAIL`, `NEEDS_CLARIFICATION`, or `ERROR`), the findings,
  and the duration in milliseconds.

The broker writes both events for every call, including `FAIL`,
`NEEDS_CLARIFICATION`, and `ERROR` calls. The implementer does not
need to look at this log; the broker uses it for its own investigation.

## Hermes Config

```yaml
mcp_servers:
  sddtdd_broker:
    command: "uv"
    args:
      - "--directory"
      - "/path/to/elagentstudio/utils/sddtdd-broker-mcp"
      - "run"
      - "server.py"
    sampling:
      enabled: true
      timeout: 120
    tools:
      include: [init, getNextTask, reviewTask]
```

## Tests

```bash
uv run pytest -v
```
