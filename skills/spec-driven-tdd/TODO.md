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

### 5. Parallel implementation isolation needs verification

Background implementers must not write to the same worktree or branch concurrently. The current skill mentions worktree and branch in prompts, but the experiment should verify that each concurrent implementation shard actually receives its own isolated worktree and branch.

Possible direction:

- record logical task id -> worktree -> branch -> task_id;
- verify no two running implementers share the same worktree or branch;
- merge reviewed worktrees sequentially.

### 6. Merge/backmerge sequencing needs explicit validation

The intended flow is reviewed implementation result -> sequential merge task -> optional merge review. The experiment should verify that the orchestrator does not merge unreviewed work and does not merge multiple worktrees at once.

Possible direction:

- merge one reviewed worktree at a time;
- use a synchronous implementer with task kind MERGE;
- require committed merge evidence before any merge review or downstream step.

### 7. Optional future improvement: task_id continuity

OpenCode task tool supports resuming a subagent session by passing task_id. This may be useful for RED/GREEN continuity, but it is optional and should not become a hard requirement yet.

Possible direction:

- for the same logical task, RED and GREEN may reuse the same implementer task_id when practical;
- RED_REVIEW and GREEN_REVIEW may reuse the same reviewer task_id when practical;
- fresh tasks remain acceptable if full ancestry context is provided.
