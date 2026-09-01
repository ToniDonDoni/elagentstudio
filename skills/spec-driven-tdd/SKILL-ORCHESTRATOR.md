---
name: spec-driven-tdd-orchestrator
version: 8.0.0-simple
description: "Orchestration policy for lightweight Spec-Driven TDD in an existing product."
author: GPT-5.6
license: MIT
---

# Simple Spec-Driven TDD Orchestrator

The orchestrator owns sequence and gates. It does not implement or independently review.

## Flow

1. Treat the user request as an in-memory SPEC-DRAFT.
2. Delegate a spec author to inspect the repository and produce a concise working spec using the current architecture.
3. Delegate a separate `SPEC_REVIEW` reviewer.
4. On review PASS, present the spec to the user and require explicit approval.
5. If the user changes the spec, revise, re-review, and ask for approval again.
6. After approval, delegate RED on the current feature branch.
7. Delegate `RED_REVIEW` against the exact RED commit.
8. After PASS, delegate GREEN on the same branch.
9. Delegate `GREEN_REVIEW` against the exact GREEN commit.
10. Finish only on GREEN review PASS.

## Delegation rules

Every worker prompt is self-contained and includes the repository/branch, role file, user request or approved spec, relevant repository paths, expected output, and ASCII-only commit-message rule where commits are produced.

Reviewers must be separate agents from the author/implementer whose result they inspect and must remain read-only.

## Spec gate

The spec author should inspect the existing project before proposing requirements. The spec should include behavior, acceptance criteria, important edge cases/non-goals, proving-test boundary, expected RED failure, and GREEN condition. It should not create a replacement architecture.

After `SPEC_REVIEW: PASS`, show the spec to the user. RED is forbidden until the user clearly approves that exact version.

## RED gate

RED runs on the current feature branch without worktree fan-out. The implementer adds proving tests only, writes the approved `SDDTDD SPEC` header in the primary test, runs the narrow test, proves a target-specific failure, and commits.

Immediately delegate a separate reviewer against the exact commit. On FAIL, return findings to the RED implementer and repeat review. Do not start GREEN until PASS.

## GREEN gate

GREEN starts from reviewed RED. The implementer follows existing project architecture and conventions, makes the minimum production change, runs proving and relevant regression tests, and commits.

Immediately delegate a separate reviewer against the exact GREEN commit. On FAIL, return findings to the GREEN implementer and repeat review.

## Scope changes

Before RED review PASS, a changed requirement returns to spec revision, independent spec review, and human approval.

After RED review PASS, a changed requirement returns to spec revision, review, human approval, and then RED must be updated and reviewed again before GREEN continues.

## Forbidden complexity

Do not create workflow artifact directories, architecture documents, task graphs, journals, runtime logs, evidence manifests, per-task worktrees, merge workers, merge reviews, scheduling waves, dependency graphs, or parallel task orchestration unless the user explicitly asks for them.

## Completion

Report the approved spec summary, RED commit and test result, GREEN commit and tests, and final reviewer verdict. Nothing more ceremonial is required; software development has survived the loss of several markdown files before.
