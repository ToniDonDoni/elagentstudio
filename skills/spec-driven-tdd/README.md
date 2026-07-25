# Spec-Driven TDD for Oh My Pi

This directory contains the OMP-native adaptation of the Spec-Driven TDD skill.
It no longer requires `utils/sddtdd-mcp/server.py` at runtime.

## Files

- `SKILL.md` - shared workflow policy.
- `SKILL-ORCHESTRATOR.md` - primary OMP agent policy.
- `SKILL-IMPLEMENTER.md` - delegated artifact/code worker policy.
- `SKILL-REVIEWER.md` - delegated independent reviewer policy.
- `SKILL-WATCHDOG.md` - advisor supervision policy.
- `AGENTS.md` - importable OMP primary-agent entrypoint.
- `WATCHDOG.md` - importable OMP advisor entrypoint.

`SKILL.md` is intentionally not renamed. OMP discovers `AGENTS.md` for the
primary context and `WATCHDOG.md` for advisor-only context; those files import
the role policies.

## Enable in a project

Add this to the project-root `AGENTS.md`:

```markdown
@skills/spec-driven-tdd/AGENTS.md
```

Add this to the project-root `WATCHDOG.md` or `.omp/WATCHDOG.md`:

```markdown
@skills/spec-driven-tdd/WATCHDOG.md
```

Relative imports inside these files resolve from the skill directory.

Configure OMP so that:

- asynchronous task execution is enabled;
- task isolation is enabled for implementation workers;
- isolated tasks use branch-mode merge when automatic integration is desired;
- the advisor is enabled and an advisor model is assigned.

## Runtime model

- The primary agent is the orchestrator.
- Implementers and reviewers are separate native OMP `task` subagents.
- Independent implementation shards run asynchronously and in isolation.
- OMP provides agent/job ids, `agent://` outputs, `history://` transcripts,
  patches/branches, automatic merge attempts, and async-result delivery.
- The advisor loads `WATCHDOG.md`, watches every primary turn, and reports
  process violations through OMP advisories.
- Merge conflicts or failed automatic application are serialized into a
  dedicated conflict-resolution implementer task and tested on the integrated
  tree.

## Reviewer correction included

The reviewer policy includes commit
`144b8f35fe25369372bcdd6760f64f25f8d5a07d`: RED must fail because of the target
unimplemented feature or target bug. An unrelated prerequisite or unrelated
failure makes RED review fail.

## Removed dependency

Do not invoke `sddtdd_getNextTask`, `sddtdd_taskStatus`, or MCP sampling for this
OMP variant. Workflow decisions come from committed artifacts, journal state,
native OMP task results, subagent transcripts, reviewer verdicts, and watchdog
advice.
