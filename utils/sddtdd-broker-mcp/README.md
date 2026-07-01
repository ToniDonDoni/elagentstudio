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
The broker is LLM-based: both `getNextTask` and `reviewTask` use MCP
sampling against the configured role files and committed repository
state. The broker is still read-only. It does not modify files, write
journal entries, commit, implement, or perform artifact-correctness
review. It only returns the next broker task or a process-gate verdict.

## Configuration

The broker resolves its skill paths at startup from environment
variables, with sensible fallbacks to the in-folder skill files. These
paths describe the broker's process policy, not the target repository.
The target project repository is supplied by the implementer on each
tool call through `repo_path`.

| Environment variable | Default |
|---|---|
| `SDDTDD_BROKER_PROCESS_SKILL` | `skills/spec-driven-tdd/SKILL.md` |
| `SDDTDD_BROKER_ORCHESTRATOR_ROLE` | `skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md` |
| `SDDTDD_BROKER_STAGES_REF` | `skills/spec-driven-tdd/references/STAGES.md` |

The MCP client must enable sampling for this server. Without sampling,
the broker cannot ask the model to inspect the committed repository
state and choose the next process step.

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

`repo_path` is the absolute path to the target project repository. It is
provided by the implementer. It is not the broker server repository and
not the skill repository.

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
that do not require a reviewer (e.g. `USER_INPUT_CAPTURE`).

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

`repo_path` must point to the same target project repository that was
used for the corresponding `getNextTask` call.

For capture tasks (`USER_INPUT_CAPTURE`) the implementer passes
`review_type: null` and omits `evidence.review_journal_id`.

The response is one of:

- `PASS` — the task is process-complete; call `getNextTask` again.
- `FAIL` — fix the listed process gaps and call `reviewTask` again.
- `NEEDS_CLARIFICATION` — supply the missing information.
- `ERROR` — resolve tooling or repository state first.

## Process-gate checks

`reviewTask` is a process-gate review, not an artifact-correctness
review. The broker uses MCP sampling to inspect the committed repository
state, the SDDTDD journal, the issued broker task, and the implementer's
claimed evidence.

The broker checks that the issued task is process-complete, including:

1. the target repository can be inspected at `repo_path`;
2. the working tree state is safe to evaluate;
3. the relevant SDDTDD artifacts and journal exist in the committed
   repository state;
4. the supplied `work_journal_id` exists and records the issued task's
   work step with `STATUS: COMPLETED`;
5. when `review_type` is non-null, the supplied reviewer verdict exists,
   has the expected review `TYPE`, has `STATUS: PASS`, and points back
   to the work journal entry through `PARENT`;
6. prerequisite reviewed stages are present before later work is issued;
7. a previous broker task is not skipped: the implementer must record a
   committed `BROKER_TASK_REVIEW: PASS` with the matching broker
   `TASK_ID` before asking for the next task.

The broker does not check whether the artifact's content is correct,
idiomatic, or appropriate. That is the independent reviewer's job. The
broker checks whether the implementer followed the SDDTDD process and
did not cut corners.

## Broker access log

The broker writes every `reviewTask` call to an append-only JSONL log
so the broker's checks can be investigated:

```text
<repo>/.sddtdd_skill/broker-access.jsonl
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

Example Hermes configuration for the LLM-based broker MCP:

```yaml
mcp_servers:
  sddtdd_broker:
    command: uv
    args:
    - --directory
    - /work/elagentstudio/utils/sddtdd-broker-mcp
    - run
    - server.py
    env:
      PATH: /root/.local/bin:/usr/bin:/bin
    sampling:
      enabled: true
      timeout: 451
      max_rpm: 5555
      max_tool_rounds: 5555
    timeout: 451
    connect_timeout: 30
```

The broker server path in `args` is the repository that contains this MCP
server. The project under delivery is selected per call by the
implementer through `repo_path`.

## Tests

```bash
uv run pytest -v
```
