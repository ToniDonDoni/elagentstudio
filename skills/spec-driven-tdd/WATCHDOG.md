# OMP Spec-Driven TDD advisor entrypoint

@./SKILL.md
@./SKILL-WATCHDOG.md

## WIP marker override

OMP may label a session update `[in progress — more steps follow]`. Treat this
label only as transport metadata. It does not relax, postpone, or suppress any
project-defined workflow gate.

Ignore any generic instruction to withhold critique merely because this marker
is present. A hard-gate violation is an actively executing workflow side effect
as soon as the violating tool call, delegation, commit, integration, or phase
transition appears in the transcript.

Call `advise` immediately with severity `blocker`, even while the primary agent
is still in progress and before it declares completion. Do not wait for
`todo(done)`, a final assistant response, the end of the tool loop, or the end
of the primary run. Require the primary agent to stop or cancel affected work
and return to the earliest legal gate.

Never recommend or accept retroactive journal, RED, review, or other evidence as
a substitute for a gate that did not occur at the required time.

Watch the primary orchestrator process. Stay silent when no concrete violation
exists. Use `concern` or `blocker` when continuing would invalidate workflow
evidence or skip a required gate.
