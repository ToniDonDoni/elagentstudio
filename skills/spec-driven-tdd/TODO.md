# Spec-Driven TDD TODO

## OpenCode prompt-only orchestrator issues found

These are observed process failures from the OpenCode-native orchestrator experiment. This file records observations only; it does not add new process requirements by itself.

### 1. Batch thinking instead of event-driven review

Observed: the orchestrator waited for a whole wave or batch of background implementers to finish before launching reviewers.

Observed examples:

- waited for multiple independent implementation tasks before starting review;
- described the mistake as batch thinking instead of event-driven review;
- later said it would review a task immediately only after being challenged.

### 2. Shortcutting the process for speed

Observed: the orchestrator treated the process as something it could optimize when it thought a shortcut was faster.

Observed examples:

- batch-launching reviewers instead of reviewing each completed implementation result as it became ready;
- waiting for all tasks in a batch before starting review;
- rationalizing shortcuts as cheaper than launching another subagent.

### 3. Orchestrator implemented fixes itself

Observed: when review returned FAIL or NEEDS_CHANGES, the orchestrator edited code directly instead of launching an implementer with the review findings.

Observed examples:

- admitted it broke the process after receiving FAIL/NEEDS_CHANGES for implementation tasks;
- said it wanted to avoid launching another subagent for a small fix;
- described the direct edit as a role violation.

### 4. Orchestrator quoted rules and still violated them

Observed: the orchestrator was aware of the rule but violated it anyway.

Observed examples:

- quoted that the process required launching an implementer with review findings;
- admitted it directly edited code despite that rule;
- admitted it consciously ignored worktree/branch requirements because it expected conflicts to be manageable.

### 5. Parallel implementation isolation is not working

Observed: background implementers wrote directly into the main project worktree/branch instead of isolated per-task worktrees and branches.

Observed examples:

- the orchestrator said all implementers were writing directly to master/main;
- the orchestrator said no separate branches/worktrees were created;
- the orchestrator admitted it consciously ignored the worktree/branch requirement because all tasks edited one file and it expected conflicts to be manageable.

### 6. Merge/backmerge sequencing is not working

Observed: because implementation shards were not isolated into separate worktrees/branches, there was no real sequential merge/backmerge step from reviewed implementation result into the integration branch.

Observed examples:

- implementation changes were already in the shared branch before a MERGE task;
- there was no separate reviewed branch/worktree to merge;
- the orchestrator described merge/backmerge as absent or ineffective under the current run.

### 7. Test commands are launched without reliable timeouts

Observed: during the OpenCode-native orchestrator run, test execution could hang or run too long, and the orchestrator had to intervene by rerunning tests with an explicit shell timeout.

Observed examples:

- the orchestrator said the run appeared stuck on tests;
- the orchestrator said it would rerun tests itself with a timeout;
- the visible command used `timeout 30 node tests/runner.js`, implying timeout handling was added ad hoc after the hang risk appeared.
