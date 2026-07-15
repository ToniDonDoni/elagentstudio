---
name: spec-driven-tdd
description: "Traceable delivery through reviewed artifacts, reviewed RED-GREEN TDD, and committed workflow evidence."
version: 4.2.1-min
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [spec-driven, tdd, review, traceability, audit]
---

# Spec-Driven TDD

## Purpose

This skill turns a user request into committed software through a strict
artifact chain, independent review, RED/GREEN TDD for automatically testable
behavior, and a committed journal.

## Project-side layout

```text
<repo_root>/.sddtdd_skill/
├── SPEC-DRAFT.md
├── SPEC.md
├── ARCHITECTURE.md
├── TASKS.md
├── JOURNAL_SDD_TDD_SKILL.log
├── review-access.jsonl          # runtime only
└── orchestrator-access.jsonl    # runtime only
```

Committed artifacts and the journal are part of the deliverable.

## Core chain

```text
USER INPUT
→ SPEC-DRAFT
→ SPEC
→ ARCHITECTURE
→ TASKS
→ per-task RED/GREEN cycles
→ TASKS_COMPLETE
→ REGRESSION
→ FINAL
→ DONE
```

## Four hard rules

1. Every agent-generated artifact must receive the required independent review before downstream work depends on it.
2. Every automatically testable behavior must pass through reviewed RED then reviewed GREEN.
3. Every work step, review verdict, correction, and orchestrator gate must be journaled and committed before it counts as evidence.
4. Reviewer approval and orchestrator process approval are distinct proofs. Neither replaces the other.

### Cardinal rule (orchestrator mode only)

**Commit ORCHESTRATOR_TASK_REVIEW for the completed task BEFORE executing the
returned next_task.** This is the single most-common process violation. The
orchestrator returns `next_task` only after approving the current task. You must
journal and commit that approval (TYPE: ORCHESTRATOR_TASK_REVIEW, STATUS: PASS)
before starting the returned next_task. If you skip this, the next submission
will fail with a process-gap error.

## Modes

### Standalone

The implementer reads:

- `SKILL-IMPLEMENTER.md`
- `references/STAGES.md`
- `references/JOURNAL.md`

### Orchestrator

The implementer uses exactly:

```text
mcp_sddtdd_getNextTask
mcp_sddtdd_review
```

**Before starting, read `references/ORCHESTRATOR-PITFALLS.md`** — it contains
the critical process rules discovered through repeated orchestrator rejections.
Skipping this file is the #1 cause of process-gate failures.

**For grep-based RED tests during GREEN, read `references/GREP-RED-GREEN.md`**
for guidance on matching test patterns without modifying the test file.

**For instrumentation-based RED tests (console.log boot hooks), read
`references/INSTRUMENTED-TESTING.md`** for the pattern of adding lifecycle
log points and verifying them via static analysis. That file also covers
**vision-driven RED tests** (Playwright + screenshots + automated assertions
+ vision review), which is the preferred shape for user-visible boot-flow
bugs in single-file HTML apps — see the "Vision-driven RED tests" section
of `INSTRUMENTED-TESTING.md`. The full template (Playwright script,
assertion shape, pixel-based probes, reviewer checklist) is in
`references/VISION-RED-TEST.md`.

The implementer must not read `SKILL-ORCHESTRATOR.md`; that file is server
policy.

### User-as-Orchestrator (ad-hoc)

When the user explicitly says **"я твой оркестратор сейчас"** (I am your
orchestrator now) or equivalent, the agent switches to direct-instruction mode:

- The user gives tasks directly instead of going through the automated registrar
- Follow their instructions without calling `mcp_sddtdd_getNextTask` proactively
- Still follow SDDTDD artifact discipline: SPEC-DRAFT.md append-only, SPEC.md
  reviewed, RED → GREEN cycle, journal entries, commits
- The user may review artifacts themselves ("покажи ревьюверу") instead of using
  `mcp_sddtdd_review`
- Context compaction may interrupt the flow — re-read the skill on resume and
  ask the user where to continue if unsure

**Key difference:** In automated orchestrator mode, the MCP tools control the
sequence. In user-as-orchestrator mode, the user controls the sequence — the
agent executes steps as directed while maintaining artifact discipline.

### "Process-skip" mode (user explicitly approves a shortcut)

When the user says things like **"в этот раз обходим процесс"** or
**"нас главное именно пройти эту спецификацию red→green"**, the agent
is being given explicit, scoped permission to skip parts of the full
ceremony. The user is acknowledging that the full process is overhead
and is opting out for this specific delivery.

**What the user is approving:**
- A direct `SPEC-DRAFT` → `RED` → reviewer → `GREEN` → reviewer cycle.
- Skipping the `SPEC.md` / `ARCHITECTURE.md` / `TASKS.md` formal
  artefact chain (in favour of inline comments in code or a single
  SPEC-DRAFT entry).
- Skipping the `REGRESSION` / `FINAL` / `DONE` close-out.

**What the user is NOT approving:**
- Skipping the reviewer (`mcp_sddtdd_review`) entirely. The reviewer
  is the only source of independent approval; without it, the agent
  is grading its own work. The user can act as the reviewer themselves
  ("я твой ревьювер"), but the review still happens.
- Skipping the journal. The journal is the audit trail; without it,
  future agents cannot reconstruct what was done and why.
- Skipping the `SPEC-DRAFT` append. Even in process-skip mode, new
  user requests must be appended to `SPEC-DRAFT.md` (post-DONE bug
  rule still applies).
- Skipping evidence commits. The reviewer needs to inspect evidence
  from `HEAD`, not from `/tmp`.

**Heuristic for the implementer:** "what is the user trying to
optimise for?" If they want speed, the spec chain is overhead. If
they want correctness, the review is the only signal that matters.
The user has explicitly chosen speed. Do the minimum the user
asked for, but never less than the review and the journal.

If the user later asks for a more rigorous process on a follow-up
task, return to the full ceremony — the process-skip was a per-task
override, not a permanent policy change.

### Hotfix mode (post-DONE, short-form)

When the user says something like "let's not run the full pipeline, we just
need spec/red/green" or "обходим процесс, нам главное пройти эту спецификацию
red green", they are explicitly opting into the **hotfix short-form**. This is
a valid mode, not a process violation — but it still has hard requirements.
See `references/POST-DONE-BUG-FIX.md` for the full recipe. The minimum chain:

1. **SPEC-DRAFT.md** — append a `## BUG:` entry (append-only, never overwrite
   existing content). Commit.
2. **RED test** — write, run, get exit≠0, commit the test file AND the
   evidence (screenshots, state.json) into the repo. Add a `TYPE: RED,
   STATUS: COMPLETED` journal entry. Commit.
3. **RED_REVIEW** — call `mcp_sddtdd_review(review_type='RED_REVIEW')`. Wait
   for PASS. (In user-as-orchestrator mode the user may do the review
   themselves; in that case the user IS the reviewer and the verdict comes
   from them.)
4. **GREEN** — minimal source fix. Add a `TYPE: GREEN, STATUS: COMPLETED`
   journal entry. Commit. Re-run the RED test, confirm exit 0.
5. **GREEN_REVIEW** — call `mcp_sddtdd_review(review_type='GREEN_REVIEW')`.

What hotfix mode **does not** allow you to skip: the RED_REVIEW before GREEN
(it's the proof the test catches the right bug); the SPEC-DRAFT append (it's
the proof the bug was reported); the journal entries (they're the audit
trail); the evidence-in-repo rule (otherwise the review can't re-inspect).

What hotfix mode **does** let you skip: SPEC_SPEC / SPEC_REVIEW /
ARCHITECTURE / ARCHITECTURE_REVIEW / DECOMPOSE / REGRESSION. The user has
already approved the scope when they opted in.

## Post-DONE bug fix

When a bug is found after the pipeline has reached DONE, follow a specific
sequence: manually append the bug description to SPEC-DRAFT.md → commit →
then call `getNextTask` with `INITIAL_USER_INPUT`. Do NOT jump to debugging
the source code directly or start a new INITIAL_USER_INPUT without the
manual SPEC-DRAFT.md update. See `references/POST-DONE-BUG-FIX.md`.

## Required invariants

- `SPEC-DRAFT.md` preserves the original request exactly and is **immutable after first commit. APPEND-ONLY — never overwrite or delete existing content.** If a new user request comes in, append it to the end of the file. Overwriting existing user input is forbidden; restore immediately if accidentally overwritten (use `git checkout <prior> -- .sddtdd_skill/SPEC-DRAFT.md`).
- `SPEC.md`, `ARCHITECTURE.md`, and `TASKS.md` are reviewed source-of-truth artifacts.
- RED means committed failing proof for the expected missing-behavior reason.
- GREEN means the minimal committed implementation satisfying the reviewed RED.
- In orchestrator mode, `ORCHESTRATOR_TASK_REVIEW` must be committed before the returned `next_task` is executed.
- Evidence is valid only when it is committed, correctly journaled, and still matches the inspected HEAD.

### Pitfall: Per-module GREEN ≠ boot-flow GREEN

A common failure mode in single-file HTML apps (games, demos, single-page tools):

- T-MENU, T-INPUT-MOUSE, T-INPUT-TOUCH, T-INPUT-CAMERA, T-CAT-BASE, T-CAT-TYPES, T-AUDIO, etc. all show **GREEN_REVIEW PASS** because each one tests its own module in isolation.
- The user opens `index.html` in a browser, clicks a mode button — **nothing happens**. The welcome overlay stays. No game starts.
- Root cause: a top-level `ReferenceError` (most often a Temporal Dead Zone violation — a `let`/`const` is referenced before its declaration, or the script crashes during initial module load). All `addEventListener('click', ...)` registrations that come **after** the crash line never execute.

**Why per-module tests miss it:** the test rig usually loads the file, then *drives* the relevant module directly (calls `startGame()`, `setupInput()`, etc.) — bypassing the boot sequence that crashes. Per-module GREEN says "this function works"; it does not say "the script that registers this function's caller reaches that point."

**Defence — T-BOOT (or equivalent) boot-flow integration test is REQUIRED for any single-file HTML app with ≥ 3 modules**, not optional. It must:

1. Load the page with `page.goto('file://...index.html')` and wait for parse.
2. Subscribe to `page.on('pageerror')` and capture the error stream.
3. **Assert no `ReferenceError` / TDZ** in the error stream.
4. Click a real `.mode-btn` (or its visible user-equivalent) via `page.click()`.
5. Assert the welcome-screen pixel is **gone** and a game-running pixel-marker is **present** (pixel tests per the `browser-e2e-testing` skill, OR vision review of two screenshots per `INSTRUMENTED-TESTING.md` → "Vision-driven RED tests").
6. Be committed (the test file AND the evidence — screenshots, state.json — must be in the repo, not in `/tmp`).
7. Be reviewed by `mcp_sddtdd_review(review_type='RED_REVIEW')` and return PASS **before** any GREEN work begins.

This test is RED when there's a boot crash, GREEN after the fix. It catches the entire class of "UI looks fine, button does nothing" bugs that per-module tests greenwash.

### Pitfall: RED assertions must describe the DESIRED post-fix behaviour, not the bug's presence

When writing a RED test, it is tempting to phrase assertions in the "bug is present" direction:

```javascript
// WRONG — passes when the bug is present, fails when fixed
check('A: TDZ exists in pageerrors', hasTdz, ...);
```

But RED means "committed failing proof for the **expected missing-behavior reason**" (SKILL.md). A test that PASSes when the bug is present and FAILs when the fix lands is **upside-down** — it would have to be re-flipped before GREEN could even be verified.

Correct shape:

```javascript
// CORRECT — passes only when the fix is in place, fails while the bug is present
check('A: no TDZ ReferenceError in pageerror stream', !hasTdz, ...);
check('B: window.gameState became "playing" after Touch click', after.gameState === 'playing', ...);
check('C: welcomeOverlay is hidden after click', after.welcomeVisible === false, ...);
check('D: at least one cat has been spawned', after.catsLen > 0, ...);
```

The same assertions drive both RED (fail because bug present) and GREEN (pass because fix present). The reviewer will FAIL a RED_REVIEW whose assertions describe the bug rather than the fix.

### Pitfall: Evidence must be committed, not left in /tmp

`/tmp/...` files are wiped on reboot and are not part of the repo's audit trail. SDDTDD requires evidence (screenshots, state.json, captured pageerror streams) to live **inside the repo**, under e.g. `.sddtdd_skill/evidence/T-BOOT-VISION/`, and to be committed in the same commit as the RED test. The reviewer will FAIL a RED_REVIEW whose evidence cannot be re-inspected from HEAD.

### Pitfall: Process short-form (hotfix) is allowed, but skipping the review is not

For a post-DONE bug fix, the user may say "let's skip the full SPEC → ARCHITECTURE → TASKS → REGRESSION chain, we just want spec/red/green." That is allowed and is documented in `references/POST-DONE-BUG-FIX.md`. What is **NOT** allowed:

- Skipping the `mcp_sddtdd_review(review_type='RED_REVIEW')` step. RED_REVIEW is the proof that the test actually catches the bug for the right reason. Skipping it means GREEN is unverified.
- Skipping the append-only `SPEC-DRAFT.md` update + commit (see `references/POST-DONE-BUG-FIX.md`).
- Skipping the `JOURNAL` entries (`TYPE: RED, STATUS: COMPLETED` before RED_REVIEW; `TYPE: GREEN, STATUS: COMPLETED` before GREEN_REVIEW).

The minimal hotfix chain is: SPEC-DRAFT append + commit → RED test + journal RED entry + commit → RED_REVIEW PASS → GREEN fix + journal GREEN entry + commit → GREEN_REVIEW PASS. Nothing more is required, but nothing less is allowed.

### Pitfall: A "moved higher" TDZ fix can still be in the TDZ

When fixing a TDZ (Temporal Dead Zone) crash, the common half-fix is to
move the `let` declaration to a block that *feels* like the top of the
script (e.g. an "Input State" or "Module Init" section) but is still
BELOW the first reader. The reader is the first **executed** statement
that touches the binding — and that includes functions called from
top-level code, like `resizeCanvas()` invoked at script load:

```javascript
// top of script (line ~160):
resizeCanvas();                       // ← called at module top
function resizeCanvas() {
  // ...
  if (fractalCanvas) { ... }          // ← reads fractalCanvas
}

// partial fix: move the let to line 324
let mouseMode = false;
let touchMode  = false;
let cameraMode = false;
let fractalCanvas = null;             // ← still AFTER line 168 — still TDZ!
```

The rule: when fixing a TDZ, find the **earliest reader** with `grep -n`
on the binding, look at the topmost match, and put the `let` strictly
above that statement. Section names like "Input State" or "Module Init"
are not a guarantee of position — only line numbers are.

### Pitfall: Strict-mode `let` is not on `window` — don't probe `window.gameState` from Playwright

In a script with `'use strict';` at the top (which most modern single-file
HTML games use), `let` and `const` declarations are NOT attached to the
global `window` object. From Playwright's `page.evaluate(...)`:

```javascript
await page.evaluate(() => window.gameState);
// → returns `undefined` whether the script crashed at line 166
//   or whether gameState is actually 'playing'.
```

This makes `window.*` probes useless as RED assertions because they
cannot distinguish a crashed script from a running one. The same applies
to `window.cats`, `window.touchMode`, etc.

Use **pixel-based assertions** on the canvas instead. See
`references/VISION-RED-TEST.md` for the canonical template (cyan
game-marker at `(100,100)`, magenta welcome button at `(215,426)`,
dynamic neon background at `(50,50)`). Pixel probes are also more
realistic: they assert what the user actually sees on screen.

### Pitfall: Vision review of screenshots is an additional layer, not a replacement for automated assertions

A vision-driven RED test has two layers:

1. **Automated pixel-based assertions** in the test script, with
   `process.exit(1)` on failure. These produce a hard PASS/FAIL and let
   the test run in CI.
2. **Vision review** of the two PNG screenshots by the independent
   reviewer (or by the user in user-as-orchestrator mode). The
   reviewer uses `vision_analyze` to confirm the visible user scenario
   (welcome screen before, running game after).

A "deferred-verdict" test that just collects screenshots + state.json
and lets the reviewer decide — with **no** automated assertions and
**no** `process.exit(1)` — is rejected by the reviewer as "zero
assertions, deferred-verdict design is not a valid RED test." Always
include automated assertions. Vision review is layered on top, not a
replacement.

**When T-BOOT fails, run the Boot-Flow Diagnosis ritual** in
`references/BOOT-FLOW-DIAGNOSIS.md`: a probe script that combines
`pageerror` capture, `window.<stateVars>` reflection, before/after
screenshots, and `vision_analyze` to distinguish the four common boot
breakages (TDZ, missing handler, handler error, no rendering) in one
~10 s pass. The diagnosis script is **diagnostic**, not a TDD test —
pair it with the static TDZ regex checker from
`references/POST-DONE-BUG-FIX.md` for full coverage.
