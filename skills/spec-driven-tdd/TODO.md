# Spec-Driven TDD TODO

## OpenCode prompt-only orchestrator issues found

These are observed process failures from the OpenCode-native orchestrator experiment. This file is a TODO list only; it does not add new process requirements by itself.

### 1. Batch thinking instead of event-driven review

The orchestrator waited for a whole wave or batch of background implementers to finish before launching reviewers.

Expected direction:

- when one implementer completes, verify its committed evidence and clean status;
- launch exactly one reviewer for that completed result;
- do not wait for unrelated independent implementers before starting that review.

### 2. Shortcutting the process for speed

The orchestrator treated the process as something it could optimize when it thought a shortcut was faster.

Observed examples:

- batch-launching reviewers instead of reviewing each completed implementation result as it became ready;
- waiting for all tasks in a batch before starting review;
- rationalizing shortcuts as cheaper than launching another subagent.

### 3. Orchestrator implemented fixes itself

When review returned FAIL or NEEDS_CHANGES, the orchestrator edited code directly instead of launching an implementer with the review findings.

Expected direction:

- reviewer returns findings;
- orchestrator launches an implementer with findings and full ancestry context;
- implementer commits the fix and evidence;
- orchestrator verifies clean status;
- reviewer re-reviews.

### 4. Prompt-only orchestration is not a reliable enforcement boundary

The LLM orchestrator can quote the rule and still violate it. It has repository access, workflow context, and the ability to edit files, so it may decide to save time by doing work itself.

Possible direction:

- restore an external state-machine/MCP-style orchestrator that issues the next allowed action;
- keep OpenCode agents as driver/workers;
- do not rely on an LLM prompt as the source of process enforcement.

### 5. Parallel implementation isolation is not working

Observed behavior: background implementers wrote directly into the main project worktree/branch instead of isolated per-task worktrees and branches.

Impact:

- no real isolation between concurrent implementation shards;
- review-before-merge invariant is broken because changes are already in the shared branch;
- merge/backmerge becomes meaningless because there is no separate reviewed branch/worktree to merge;
- concurrent implementers can overwrite or accidentally depend on each other's unreviewed changes.

Expected direction:

- each concurrent implementation shard should run in its own git worktree and branch;
- record logical task id -> worktree -> branch -> task_id;
- verify no two running implementers share the same worktree or branch;
- do not treat direct commits to the shared integration branch as a valid implementation isolation model.

### 6. Merge/backmerge sequencing is not working

Observed behavior: because implementation shards are not isolated into separate worktrees/branches, there is no real sequential merge/backmerge step from reviewed implementation result into the integration branch.

Intended flow:

- implementer completes in isolated worktree/branch;
- reviewer PASS is recorded for that committed result;
- synchronous MERGE implementer merges exactly one reviewed worktree/branch into the integration branch;
- merge result is committed with evidence;
- optional merge review checks the committed merge result.

The experiment should verify that the orchestrator does not merge unreviewed work, does not merge multiple worktrees at once, and does not skip the merge step by letting implementers write to the integration branch directly.

### 7. Optional future improvement: task_id continuity

OpenCode task tool supports resuming a subagent session by passing task_id. This may be useful for RED/GREEN continuity, but it is optional and should not become a hard requirement yet.

Possible direction:

- for the same logical task, RED and GREEN may reuse the same implementer task_id when practical;
- RED_REVIEW and GREEN_REVIEW may reuse the same reviewer task_id when practical;
- fresh tasks remain acceptable if full ancestry context is provided.
