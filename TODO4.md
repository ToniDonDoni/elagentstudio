TODO

Current актуальные issues after single-orchestrator rename:

1. Bind reviewer journal verdicts to real reviewer MCP results.

   Problem:
   The orchestrator must not trust a `*_REVIEW: PASS` journal entry just
   because the implementer wrote it.

   Required:
   Review journal entries must include the reviewer MCP `request_id` in
   `DETAIL`, and the orchestrator must validate that request against
   `.sddtdd_skill/review-access.jsonl`.

   The matching review-access entry must prove:

   - same `request_id`;
   - completed request status;
   - `verdict: PASS`;
   - `stale: false`;
   - expected review type for the submitted `task_kind`;
   - expected task id when applicable;
   - reviewed commit/head matches the committed state being verified.

   Without this, the implementer can forge a passing review in the journal.

2. Require every orchestrator process-gate verdict to be journaled.

   Problem:
   Failed process-gate results can disappear from the committed journal.

   Required:
   Every `getNextTask` response with a non-null `task_review` must be recorded
   as `ORCHESTRATOR_TASK_REVIEW`, including `PASS`, `FAIL`,
   `NEEDS_CLARIFICATION`, and `ERROR`.

   For `task_review.status != PASS`, the implementer must:

   1. append `ORCHESTRATOR_TASK_REVIEW` with the orchestrator request id,
      task id, status, findings, and required fixes;
   2. commit that journal entry;
   3. only then fix the process violation;
   4. retry `getNextTask` with the same completed-task evidence after the fix.

   The orchestrator should refuse repeated verification of the same submitted
   task until the previous orchestrator verdict is present in the committed
   journal.

3. Add timestamps to runtime access logs.

   Problem:
   Runtime logs are harder to audit without timestamps.

   Required:
   Add timestamp fields to:

   - `.sddtdd_skill/review-access.jsonl`;
   - `.sddtdd_skill/orchestrator-access.jsonl`.

   Prefer both `started_at` and `completed_at` in UTC ISO-8601 format.

4. Verify reviewer tool-enabled sampling actually reads committed repo files.

   Problem:
   Earlier reviewer behavior suggested it could ask for file contents even when
   `repo_path` was provided and relevant files were committed.

   Required:
   Add or keep e2e coverage proving that `mcp_sddtdd_review` can inspect
   committed repository files through tool-enabled sampling instead of relying
   on injected prompt summaries.

   The reviewer must not pass merely because the prompt contains a compressed
   artifact summary.

5. Update install/config docs for high tool-call sampling limits.

   Problem:
   Reviewer/orchestrator sampling may require large tool budgets.

   Required:
   Installation docs should show the current single-server MCP config using
   the orchestrator naming and high limits, for example:

   ```yaml
   sddtdd:
     command: uv
     args:
       - --directory
       - /work/elagentstudio/utils/sddtdd-mcp
       - run
       - server.py
     env:
       PATH: /root/.local/bin:/usr/bin:/bin
     sampling:
       enabled: true
       timeout: 1228
       max_rpm: 5555
       max_tool_rounds: 5555
     timeout: 1228
     connect_timeout: 30
     max_tokens_cap: 40000
   ```

6. Optional: consider whether the orchestrator should ever be LLM-assisted.

   Current preference:
   Keep the process gate deterministic. LLM assistance may be useful for task
   wording or planning, but it must not replace deterministic verification of
   committed journal state, access logs, and artifacts.