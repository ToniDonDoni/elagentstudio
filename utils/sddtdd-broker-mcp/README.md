# sddtdd-broker-mcp

MCP task broker for Spec-Driven TDD broker mode. The broker reads the
committed repository state and the SDDTDD journal, and answers two
questions from the implementer: what is the next task, and is the
current task process-complete.

The orchestrator role file (`skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md`)
is the source of truth for the workflow order and the broker-level
process-gate verification policy. The implementer only needs the two
decision tools and the self-contained broker task fields
(`task_kind`, `instruction`, `allowed_scope`, `required_evidence`,
`independent_review_required`, `review_type`).

The broker is configured with the role files at startup, not per call.
The implementer does not hand the broker skill files on every call.
The broker does not sample an LLM. The process-gate verification is
enforced in code by the broker itself.

## Configuration

The broker resolves its skill paths at startup from environment
variables, with sensible fallbacks to the in-folder skill files:

| Environment variable | Default |
|---|---|
| `SDDTDD_BROKER_PROCESS_SKILL` | `skills/spec-driven-tdd/SKILL.md` |
| `SDDTDD_BROKER_ORCHESTRATOR_ROLE` | `skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md` |
| `SDDTDD_BROKER_STAGES_REF` | `skills/spec-driven-tdd/references/STAGES.md` |

## Tools

There are exactly two tools. There is no `init`.

### `getNextTask`

The first call carries `user_input` and starts a new delivery.
Subsequent calls carry `previous_task_id`.

```json
{
  "repo_path": "/path/to/project",
  "user_input": "original user request"
}
```

The response is one of:

- `{"status": "TASK", "task_id": "...", "task_kind": "...", "instruction": "...", "allowed_scope": [...], "required_evidence": [...], "independent_review_required": true, "review_type": "SPEC_REVIEW | ... | null", "rationale": "..."}`
- `{"status": "complete", ...}`
- `{"status": "blocked", ...}`

A `TASK` is self-contained. The implementer follows the `instruction`
literally, stays within `allowed_scope`, produces the items in
`required_evidence`, and only runs the independent reviewer when
`independent_review_required` is true. `task_kind` is the workflow
stage; `review_type` is the type of independent reviewer verdict the
implementer must obtain and journal, and is `null` for capture tasks
(`USER_INPUT`, `SPEC_DRAFT`) that do not require a reviewer.

### `reviewTask`

`reviewTask` performs process-gate verification. The broker itself
reads the committed journal, the issued `task_kind`, the
`work_journal_id`, and (when one is required) the
`review_journal_id`, and decides whether the issued step is
process-complete. The broker does not re-review the artifact's
correctness — that is the independent reviewer's job.

```json
{
  "repo_path": "/path/to/project",
  "task_id": "B-000001",
  "task_kind": "RED",
  "review_type": "RED_REVIEW",
  "claimed_result": "RED evidence committed and reviewer passed",
  "work_journal_id": "J-20260616-001",
  "evidence": {
    "review_journal_id": "J-20260616-002",
    "commits": ["abc123"],
    "journal_ids": ["J-20260616-001", "J-20260616-002"],
    "review_request_id": "01HXX...",
    "test_commands": ["pytest -q"],
    "files": ["tests/test_foo.py"]
  }
}
```

For capture tasks (`USER_INPUT`, `SPEC_DRAFT`) the implementer passes
`review_type: null` and omits `evidence.review_journal_id`.

The response is one of:

- `PASS` — the task is process-complete; call `getNextTask` again.
- `FAIL` — fix the listed process gaps and call `reviewTask` again.
- `NEEDS_CLARIFICATION` — supply the missing information.
- `ERROR` — resolve tooling or repository state first.

## Process-gate checks

The broker applies these checks in order:

1. Working tree is clean (`git status --porcelain` is empty).
2. `JOURNAL_SDD_TDD_SKILL.log` exists at `HEAD`.
3. `work_journal_id` exists in the committed journal.
4. The work entry has `STATUS: COMPLETED`.
5. Prerequisite reviewer verdicts exist (`RED_REVIEW: PASS` before
   `GREEN`, `REGRESSION_REVIEW: PASS` before `FINAL`).
6. When `review_type` is non-null, a reviewer-verdict journal entry
   with the right `TYPE` and `STATUS: PASS` exists.
7. The reviewer verdict's `PARENT` resolves in the journal.

The broker does not check whether the artifact's content is correct,
idiomatic, or appropriate. That is the reviewer's job.

## Broker access log

The broker writes every `reviewTask` call to an append-only JSONL log
so the broker's checks can be investigated:

```text
<repo>/.git/sddtdd/broker-access.jsonl
```

Each call produces two events:

- `task_review_started` — written at the start of `reviewTask`,
  containing the request id, the broker task id, the committed `HEAD`
  SHA before, and the arguments the implementer passed.
- `task_review_completed` — written at the end, containing the request
  id, the broker task id, the `HEAD` SHA before and after, the
  verdict, the findings, and the duration in milliseconds.

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
    tools:
      include: [getNextTask, reviewTask]
```

## Tests

```bash
uv run pytest -v
```
