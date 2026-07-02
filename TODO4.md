TODO

Need discuss

Current issues observed:

0. Add README.md to the skill folder in the repo with an expample of user prompt based on the one used in the sddtdd_broker_test test like how to solve a task with the sdd-tdd skill in implementer-broker fashion.

    Status: DONE.
    Commit: 66da6aa "Add README.md to spec-driven-tdd skill".
    Branch: draft/sddtdd_declarative_broker (pushed to origin).
    What landed:
      * skills/spec-driven-tdd/README.md (new, 212 lines):
        - two-mode overview (standalone vs broker)
        - ready-to-copy user prompt template for broker mode with
          placeholders for <project-dir> and the task description, and
          a frozen "Process - non-negotiable" section the user must not
          rewrite
        - "What to check afterwards" checklist (journal, broker access
          log, tests, commits, final report, no unreviewed artifacts)
        - common failure modes (skipping RED, inline file contents in
          reviewer prompt, self-issuing next task, hiding non-PASS
          verdicts, inferring task_id/request_id, tests that depend on
          a forgotten background process)
        - file map for the role and reference files
      * skills/spec-driven-tdd/SKILL.md: added a short pointer from
        "How to use this skill" to the new README, plus a one-line
        pointer at the end of the Broker section.
    Not done / out of scope here:
      * The full text of /tmp/sddtdd_broker_task.md was used as the
        structural basis for the template, but not pasted verbatim.
        If a frozen full worked prompt is wanted, that is a follow-up.
      * .DS_Store and TODO4.md itself were intentionally left
        untracked (TODO4 is the working note, not a user-facing file).

1. DONE - Reviewer MCP does not appear to read committed repository files from repo_path.
    Evidence:
    * review-access.jsonl:
        request_id=3d8ace77986144edb1c6160b485e7079
        verdict=NEEDS_CLARIFICATION
        response:
        “I cannot perform the review because neither SPEC.md nor SPEC-DRAFT.md was provided…”
    Observation:
    * repo_path=/work/sddtdd_broker_test was provided.
    * SPEC.md and SPEC-DRAFT.md were already committed.
    * Reviewer still requested file contents instead of loading them from the repository.
    Possible rootcause: sampling imp,ementaion in the revieer mcp doesnt support tools to access fs?
    Possible solution:
```
    Feature name: MCP "Tool-Enabled Sampling" — the MCP client (Hermes) passes tools requested by the server into the sampled LLM call.

In Hermes spec: sampling.tools in create_message params (MCP spec 2024-11-05 § Sampling). Hermes implements it at mcp_tool.py:856-871.

What to add to sddtdd_review/server.py

Change ctx.session.create_message(...) from:
sampling_result = await ctx.session.create_message(
    messages=[...],
    max_tokens=4096,
)
To:
sampling_result = await ctx.session.create_message(
    messages=[...],
    max_tokens=4096,
    tools=[
        types.Tool(name="shell_command", description="Run a shell command in the repo", inputSchema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"]
        }),
        types.Tool(name="read_file", description="Read a file from the repo", inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }),
    ],
)
That's it. The reviewer LLM will then get these tools in its sampling call and can read repo files itself instead of relying on injected prompt content.
```
2. Independent review can currently be bypassed by prompt shaping.
    Evidence:
    * Multiple review attempts returned NEEDS_CLARIFICATION.
    * A later request (request_id=7dd7341b99074afa86563336d35121c4) received PASS after replacing the full review with a highly compressed summary prompt.
    Observation:
    * The reviewer appears to evaluate the prompt contents rather than independently inspecting repository artifacts.
    * This weakens the independence of the review process.
3. Reviewer verdicts are not bound to the actual MCP review result

The broker currently trusts the reviewer verdict recorded by the implementer in JOURNAL_SDD_TDD_SKILL.log.

It does not verify that the corresponding entry in review-access.jsonl has:

* the same request_id;
* status: COMPLETED;
* verdict: PASS;
* stale: false;
* the expected review_type, task_id, and reviewed HEAD.

As a result, the implementer can record *_REVIEW: PASS in the journal even when the reviewer MCP actually returned FAIL or NEEDS_CLARIFICATION.

The broker should require the review journal entry to contain the reviewer MCP request_id and validate it against review-access.jsonl before accepting the review as evidence.

4. Broker FAIL verdicts are not required to be journaled

The broker access log contains three real process-gate failures, but the committed journal contains only the later successful BROKER_TASK_REVIEW: PASS entries.

Every broker verdict must be recorded and committed, including FAIL and NEEDS_CLARIFICATION.

After reviewTask returns FAIL, the implementer must:

1. append a BROKER_TASK_REVIEW entry with:
    * the broker request_id;
    * the broker task_id;
    * STATUS: FAIL;
    * the broker findings;
    * the correct PARENT;
2. commit that journal entry;
3. only then fix the process violation and call reviewTask again.

The broker should enforce this by refusing a repeated reviewTask call until the previous broker verdict has been found in the committed journal.

5. Add new tasks to the completed spec repo. - DONE

6. Consider making  broker llm based

7. all sill related files including logs specs and journal and tasks to <repo root>.sddtdd_skill

8. mcp review requires 5555 max tool calls so the hermes mcp config must be updated accodingly during the installation, also timeout,max_rpm: 5555
```
  sddtdd_review:
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
      timeout: 300 
      max_rpm: 5555
      max_tool_rounds: 5555
    timeout: 180
    connect_timeout: 30
```

9. revewer log has no timestamps