# JOURNAL.log as a First-Class Artifact

This reference clarifies a mandatory rule for the spec-driven TDD skill:

`JOURNAL.log` is not optional documentation and not a side-effect note. It is a required state artifact produced by every completed pipeline step.

## Rule

Every completed step MUST produce two things:

1. The primary step artifact.
2. A corresponding `JOURNAL.log` entry.

Both artifacts are required. If either one is missing, the step is not complete.

## Definition of Done

A pipeline cycle is complete only when:

- the goal from the spec is fully solved;
- all code passes all tests;
- every commit along the chain has a PASS verdict from review;
- `JOURNAL.log` exists;
- `JOURNAL.log` contains an unbroken `PARENT` chain from `USER_INPUT` to `DONE`.

## Step Completion Contract

For every step, use this completion contract:

```text
Artifacts produced by this step:

1. <primary artifact>
2. JOURNAL.log entry with the expected TYPE and STATUS

Both artifacts are REQUIRED.
If either artifact is missing, this step is NOT COMPLETE.
The next step MUST NOT start until both artifacts exist and are committed.
```

## Why this exists

Agents tend to treat `-> JOURNAL:` instructions as trailing notes. This file makes the journal part of the target state, like `SPEC-DRAFT.md`, tests, and implementation code.

Missing journal entry = missing artifact = incomplete step.
