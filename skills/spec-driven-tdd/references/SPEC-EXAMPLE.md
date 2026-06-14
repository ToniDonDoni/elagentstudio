# Demo Feature Case: Counter API with Commit-Based Spec-Driven TDD


TODO update to the skill v2


This walkthrough demonstrates the workflow defined in `SKILL.md`.

All journal entries follow `references/JOURNAL.md`.

---

## 1. User Input

The user requests:

> Build a simple in-memory counter. It starts at zero, can be decremented, never goes below zero, and exposes its current value.

Create the initial journal entry:

```text
=== J-20260614-100000-001 ===
TYPE: USER_INPUT
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: --
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-000
PARENT_TASK_ID: --
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Initial Counter API request received.
```

Commit:

```text
spec-driven-tdd: record initial user input for S-DEMO-01
```

---

## 2. Capture Immutable Raw User Input

Create `SPEC-DRAFT.md` by copying the user request exactly as received:

```markdown
# Raw User Input

Build a simple in-memory counter. It starts at zero, can be decremented,
never goes below zero, and exposes its current value.
```

Do not normalize, translate, clarify, or add acceptance criteria.

Commit:

```text
spec: capture immutable raw input for S-DEMO-01
```

`SPEC-DRAFT.md` is now immutable. It is not reviewed and must never be edited.

---

## 3. Derive and Review the Working Specification

Create editable `SPEC.md` from `SPEC-DRAFT.md`:

```markdown
# Counter API Specification

Spec ID: S-DEMO-01
Source: SPEC-DRAFT.md
Parent: --

## S-DEMO-01.01 — Initial value

A new counter starts at `0`.

Acceptance criterion:

- `Counter().get_value()` returns `0`.

## S-DEMO-01.02 — Lower bound

Calling `decrement()` must never reduce the counter below `0`.

Acceptance criterion:

- Calling `decrement()` on a new counter keeps the value at `0`.
```

Commit:

```text
spec: derive editable Counter API specification S-DEMO-01
```

Record creation of the working specification:

```text
=== J-20260614-100000-002 ===
TYPE: SPEC_SPEC
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-001
ROOT: J-20260614-100000-001
DETAIL: Editable SPEC.md derived from immutable SPEC-DRAFT.md.
```

Review the committed `SPEC.md`.

`SPEC-DRAFT.md` is not reviewed.

Review scope:

- `SPEC.md` remains faithful to `SPEC-DRAFT.md`;
- both acceptance criteria are observable;
- the behavior is unambiguous;
- each acceptance criterion can be tested independently;
- no unsupported requirements were introduced.

Record the review:

```text
=== J-20260614-100000-003 ===
TYPE: SPEC_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-002
ROOT: J-20260614-100000-001
DETAIL: SPEC.md is faithful to SPEC-DRAFT.md, complete, unambiguous, and testable. Reviewed commit <hash>.
```

Commit:

```text
journal: record SPEC.md review for S-DEMO-01
```

If the review returns `FAIL` or `NEEDS_CLARIFICATION`:

1. keep `SPEC-DRAFT.md` unchanged;
2. edit `SPEC.md`;
3. commit the corrected `SPEC.md`;
4. update and commit the journal;
5. request a fresh review of `SPEC.md`.

Task decomposition starts only after `SPEC.md` receives `PASS`.

---

## 4. Decompose Reviewed SPEC.md into Tasks

After `SPEC.md` receives `PASS`, create `TASKS.md` from its acceptance criteria:

```markdown
# Counter API Tasks

## T-DEMO-01-001 — Initial value

Spec: S-DEMO-01.01
Parent task: T-DEMO-01-000
Root user input: T-DEMO-01-000

Acceptance criterion:

- `Counter().get_value()` returns `0`.

## T-DEMO-01-002 — Lower bound

Spec: S-DEMO-01.02
Parent task: T-DEMO-01-000
Root user input: T-DEMO-01-000

Acceptance criterion:

- Calling `decrement()` on a new counter keeps the value at `0`.
```

Commit:

```text
tasks: decompose Counter API into two TDD tasks
```

Record decomposition:

```text
=== J-20260614-100000-004 ===
TYPE: DECOMPOSE
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-003
ROOT: J-20260614-100000-001
DETAIL: Reviewed SPEC.md decomposed into T-DEMO-01-001 and T-DEMO-01-002.
```

Review the committed task decomposition.

Record the review:

```text
=== J-20260614-100000-005 ===
TYPE: TASK_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-004
ROOT: J-20260614-100000-001
DETAIL: Both tasks map to one acceptance criterion and share the correct root task. Reviewed commit <hash>.
```

Commit:

```text
journal: record task decomposition review for S-DEMO-01
```

---

## 5. Task T-DEMO-01-001 — Initial Value

### 4.1 Select the Task

```text
=== J-20260614-100000-006 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected the initial-value task.
```

### 4.2 RED

Create the first test in `tests/test_counter.py`:

```python
from counter import Counter


def test_new_counter_starts_at_zero():
    counter = Counter()

    assert counter.get_value() == 0
```

Run:

```text
pytest tests/test_counter.py::test_new_counter_starts_at_zero -v
```

Expected RED evidence:

```text
FAILED — ModuleNotFoundError: No module named 'counter'
```

Commit the test and RED evidence:

```text
test: add initial-value acceptance test
```

Record RED:

```text
=== J-20260614-100000-007 ===
TYPE: RED
SPEC: S-DEMO-01.01
STATUS: COMPLETED
PARENT: J-20260614-100000-006
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Initial-value test fails because the Counter implementation does not exist.
```

Review the committed test and RED evidence.

Record the review:

```text
=== J-20260614-100000-008 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.01
STATUS: PASS
PARENT: J-20260614-100000-007
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Test covers S-DEMO-01.01 and fails for the expected missing-feature reason. Reviewed commit <hash>.
```

### 4.3 GREEN

Create `counter.py`:

```python
class Counter:
    def __init__(self) -> None:
        self._value = 0

    def get_value(self) -> int:
        return self._value
```

Run the focused test again:

```text
pytest tests/test_counter.py::test_new_counter_starts_at_zero -v
```

Expected result:

```text
PASSED
```

Commit:

```text
impl: add minimal initial-value Counter implementation
```

Record GREEN:

```text
=== J-20260614-100000-009 ===
TYPE: GREEN
SPEC: S-DEMO-01.01
STATUS: COMPLETED
PARENT: J-20260614-100000-008
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Minimal implementation makes the initial-value test pass.
```

Review the committed implementation.

Record the review:

```text
=== J-20260614-100000-010 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.01
STATUS: PASS
PARENT: J-20260614-100000-009
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-001
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Implementation is minimal and satisfies S-DEMO-01.01. Reviewed commit <hash>.
```

---

## 6. Task T-DEMO-01-002 — Lower Bound

### 5.1 Select the Task

```text
=== J-20260614-100000-011 ===
TYPE: AGENT_DECISION
SPEC: S-DEMO-01.02
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Selected the lower-bound task.
```

### 5.2 RED

Append the second test to `tests/test_counter.py`:

```python
def test_decrement_does_not_go_below_zero():
    counter = Counter()

    counter.decrement()

    assert counter.get_value() == 0
```

Run:

```text
pytest tests/test_counter.py::test_decrement_does_not_go_below_zero -v
```

Expected RED evidence:

```text
FAILED — AttributeError: 'Counter' object has no attribute 'decrement'
```

Commit:

```text
test: add lower-bound acceptance test
```

Record RED:

```text
=== J-20260614-100000-012 ===
TYPE: RED
SPEC: S-DEMO-01.02
STATUS: COMPLETED
PARENT: J-20260614-100000-011
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Lower-bound test fails because decrement is not implemented.
```

Review the committed test and RED evidence.

Record the review:

```text
=== J-20260614-100000-013 ===
TYPE: RED_REVIEW
SPEC: S-DEMO-01.02
STATUS: PASS
PARENT: J-20260614-100000-012
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Test covers S-DEMO-01.02 and fails for the expected missing-feature reason. Reviewed commit <hash>.
```

### 5.3 GREEN

Update `counter.py`:

```python
class Counter:
    def __init__(self) -> None:
        self._value = 0

    def decrement(self) -> None:
        if self._value > 0:
            self._value -= 1

    def get_value(self) -> int:
        return self._value
```

Run the focused test:

```text
pytest tests/test_counter.py::test_decrement_does_not_go_below_zero -v
```

Expected result:

```text
PASSED
```

Commit:

```text
impl: add minimal lower-bound behavior
```

Record GREEN:

```text
=== J-20260614-100000-014 ===
TYPE: GREEN
SPEC: S-DEMO-01.02
STATUS: COMPLETED
PARENT: J-20260614-100000-013
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Minimal decrement implementation keeps the value at zero.
```

Review the committed implementation.

Record the review:

```text
=== J-20260614-100000-015 ===
TYPE: GREEN_REVIEW
SPEC: S-DEMO-01.02
STATUS: PASS
PARENT: J-20260614-100000-014
ROOT: J-20260614-100000-001
TASK_ID: T-DEMO-01-002
PARENT_TASK_ID: T-DEMO-01-000
ROOT_USER_INPUT_ID: T-DEMO-01-000
DETAIL: Implementation is minimal and satisfies S-DEMO-01.02. Reviewed commit <hash>.
```

---

## 7. Converge the Task Branches

Both sibling task branches are complete:

| Task | Terminal journal entry |
|---|---|
| `T-DEMO-01-001` | `J-20260614-100000-010` |
| `T-DEMO-01-002` | `J-20260614-100000-015` |

Create the convergence entry:

```text
=== J-20260614-100000-016 ===
TYPE: TASKS_COMPLETE
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-005
ROOT: J-20260614-100000-001
DEPENDS: J-20260614-100000-010, J-20260614-100000-015
DETAIL: Both task branches reached GREEN_REVIEW with PASS.
```

Commit:

```text
journal: record completion of Counter API task branches
```

---

## 8. Regression

Run all tests:

```text
pytest tests/ -v
```

Expected result:

```text
2 passed
```

Record regression:

```text
=== J-20260614-100000-017 ===
TYPE: REGRESSION
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-016
ROOT: J-20260614-100000-001
DETAIL: Full Counter API test suite passes.
```

Review the regression evidence.

Record the review:

```text
=== J-20260614-100000-018 ===
TYPE: REGRESSION_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-017
ROOT: J-20260614-100000-001
DETAIL: Regression evidence confirms both acceptance criteria remain satisfied. Reviewed commit <hash>.
```

---

## 9. Final Review

Review the complete committed feature.

Review scope:

- both acceptance criteria from reviewed `SPEC.md` are implemented;
- both task branches have reviewed RED and GREEN stages;
- all tests pass;
- journal and commit history are complete;
- no uncommitted solution artifacts remain.

Record the result:

```text
=== J-20260614-100000-019 ===
TYPE: FINAL_REVIEW
SPEC: S-DEMO-01
STATUS: PASS
PARENT: J-20260614-100000-018
ROOT: J-20260614-100000-001
DETAIL: Final feature review passed. Reviewed commit <hash>.
```

Commit:

```text
journal: record final review for S-DEMO-01
```

---

## 10. Completion

Record pipeline completion:

```text
=== J-20260614-100000-020 ===
TYPE: DONE
SPEC: S-DEMO-01
STATUS: COMPLETED
PARENT: J-20260614-100000-019
ROOT: J-20260614-100000-001
DETAIL: Counter API completed through the reviewed spec-driven TDD workflow.
```

Commit:

```text
journal: mark S-DEMO-01 complete
```

---

## 11. Final Artifacts

The completed example contains:

```text
SPEC-DRAFT.md
SPEC.md
TASKS.md
JOURNAL_SDD_TDD_SKILL.log
tests/test_counter.py
counter.py
```

Final `tests/test_counter.py`:

```python
from counter import Counter


def test_new_counter_starts_at_zero():
    counter = Counter()

    assert counter.get_value() == 0


def test_decrement_does_not_go_below_zero():
    counter = Counter()

    counter.decrement()

    assert counter.get_value() == 0
```

Final `counter.py`:

```python
class Counter:
    def __init__(self) -> None:
        self._value = 0

    def decrement(self) -> None:
        if self._value > 0:
            self._value -= 1

    def get_value(self) -> int:
        return self._value
```

---

## 12. Traceability

`SPEC-DRAFT.md` preserves the original request. `SPEC.md` defines the reviewed requirements used by the tasks and tests.

| Requirement | Task | Test | Implementation | Terminal task entry |
|---|---|---|---|---|
| `S-DEMO-01.01` | `T-DEMO-01-001` | `test_new_counter_starts_at_zero` | `Counter.__init__`, `Counter.get_value` | `J-20260614-100000-010` |
| `S-DEMO-01.02` | `T-DEMO-01-002` | `test_decrement_does_not_go_below_zero` | `Counter.decrement` | `J-20260614-100000-015` |

Both tasks trace to:

```text
ROOT_USER_INPUT_ID: T-DEMO-01-000
```

All workflow events trace to:

```text
ROOT: J-20260614-100000-001
```
