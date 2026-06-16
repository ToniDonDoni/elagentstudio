import asyncio
import json
import subprocess

from server import (
    BROKER_TOOLS,
    _append_broker_event,
    _broker_log_path,
    _check_process_gate,
    _committed_journal,
    _parse_journal,
    _read_repo_state,
    _select_next_task,
    _working_tree_dirty,
    app,
    list_tools,
)


# ---------------------------------------------------------------------------
# Server registration
# ---------------------------------------------------------------------------


def test_server_name():
    assert app.name == "sddtdd-broker-mcp"


def test_tool_handlers_registered():
    from mcp.types import CallToolRequest

    assert CallToolRequest in app.request_handlers


def test_broker_tool_names():
    """The broker exposes only getNextTask and reviewTask. There is no init."""
    tool_defs = asyncio.run(list_tools())
    names = {tool.name for tool in tool_defs}
    assert names == {"getNextTask", "reviewTask"}
    assert names == BROKER_TOOLS
    assert "init" not in names


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------


def test_get_next_task_schema_does_not_require_init_fields():
    tool_defs = asyncio.run(list_tools())
    next_tool = [tool for tool in tool_defs if tool.name == "getNextTask"][0]
    # On the first call the implementer passes user_input; on subsequent
    # calls previous_task_id. Neither is required, so the broker can be
    # called without a prior init.
    required = set(next_tool.inputSchema["required"])
    assert required == {"repo_path"}
    assert "user_input" not in required
    assert "previous_task_id" not in required


def test_review_task_schema_requires_process_inputs():
    tool_defs = asyncio.run(list_tools())
    review_tool = [tool for tool in tool_defs if tool.name == "reviewTask"][0]
    required = set(review_tool.inputSchema["required"])
    assert required == {
        "repo_path",
        "task_id",
        "task_kind",
        "claimed_result",
        "work_journal_id",
    }
    # review_type may be null (capture tasks have no reviewer).
    rt = review_tool.inputSchema["properties"]["review_type"]
    assert "null" in rt["type"] or rt["type"] == "null" or "string" in rt["type"]


# ---------------------------------------------------------------------------
# Journal parsing
# ---------------------------------------------------------------------------


def test_parse_journal_basic_entries():
    text = """
=== J-20260616-001 ===
|TYPE: USER_INPUT
|SPEC: S-DEMO
|STATUS: COMPLETED
|PARENT: --
|ROOT: J-20260616-001
|TASK_ID: T-000001
|PARENT_TASK_ID: --
|ROOT_USER_INPUT_ID: T-000001
|DETAIL: original user request

=== J-20260616-002 ===
|TYPE: SPEC_REVIEW
|SPEC: S-DEMO
|STATUS: PASS
|PARENT: J-20260616-001
|ROOT: J-20260616-001
|TASK_ID: T-000001
|PARENT_TASK_ID: --
|ROOT_USER_INPUT_ID: T-000001
|DETAIL: spec reviewed and passed
""".strip()
    entries = _parse_journal(text)
    assert len(entries) == 2
    assert entries[0]["TYPE"] == "USER_INPUT"
    assert entries[0]["STATUS"] == "COMPLETED"
    assert entries[1]["TYPE"] == "SPEC_REVIEW"
    assert entries[1]["STATUS"] == "PASS"


# ---------------------------------------------------------------------------
# getNextTask state machine
# ---------------------------------------------------------------------------


def _make_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    return tmp_path


def test_get_next_task_empty_repo_requires_user_input(tmp_path):
    _make_repo(tmp_path)
    state = _read_repo_state(str(tmp_path))
    result = _select_next_task(state, previous_task_id=None, user_input=None)
    assert result["status"] == "blocked"


def test_get_next_task_empty_repo_with_user_input_starts_with_user_input(tmp_path):
    _make_repo(tmp_path)
    state = _read_repo_state(str(tmp_path))
    result = _select_next_task(state, previous_task_id=None, user_input="build a thing")
    assert result["status"] == "TASK"
    assert result["task_kind"] == "USER_INPUT"
    assert result["independent_review_required"] is False
    assert result["review_type"] is None


def test_get_next_task_with_user_input_asks_for_spec_spec(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "SPEC-DRAFT.md").write_text("build a thing")
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text(
        "=== J-20260616-001 ===\nTYPE: USER_INPUT\nSTATUS: COMPLETED\nPARENT: --\nROOT: J-20260616-001\nTASK_ID: T-000001\nPARENT_TASK_ID: --\nROOT_USER_INPUT_ID: T-000001\nDETAIL: original user request\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    state = _read_repo_state(str(tmp_path))
    assert state["has_user_input"]
    result = _select_next_task(state, previous_task_id=None, user_input=None)
    assert result["status"] == "TASK"
    assert result["task_kind"] == "SPEC_SPEC"
    assert result["review_type"] == "SPEC_REVIEW"
    assert result["independent_review_required"] is True


def test_get_next_task_returns_complete_when_done(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text(
        "=== J-1 ===\nTYPE: USER_INPUT\nSTATUS: COMPLETED\nDETAIL: x\n"
        "\n=== J-2 ===\nTYPE: SPEC_REVIEW\nSTATUS: PASS\nDETAIL: x\n"
        "\n=== J-3 ===\nTYPE: ARCHITECTURE_REVIEW\nSTATUS: PASS\nDETAIL: x\n"
        "\n=== J-4 ===\nTYPE: TASK_REVIEW\nSTATUS: PASS\nDETAIL: x\n"
        "\n=== J-5 ===\nTYPE: REGRESSION_REVIEW\nSTATUS: PASS\nDETAIL: x\n"
        "\n=== J-6 ===\nTYPE: FINAL_REVIEW\nSTATUS: PASS\nDETAIL: x\n"
        "\n=== J-7 ===\nTYPE: DONE\nSTATUS: COMPLETED\nDETAIL: x\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    state = _read_repo_state(str(tmp_path))
    assert state["has_done"]
    result = _select_next_task(state, previous_task_id=None, user_input=None)
    assert result["status"] == "complete"


# ---------------------------------------------------------------------------
# reviewTask process-gate verification
# ---------------------------------------------------------------------------


def _commit_journal(tmp_path, text: str) -> None:
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text(text)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "journal update"], cwd=tmp_path, check=True, capture_output=True)


def test_review_task_pass_when_capture_task_no_reviewer_required(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: USER_INPUT\nSTATUS: COMPLETED\nDETAIL: original user request\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000001",
        task_kind="USER_INPUT",
        review_type=None,
        work_journal_id="J-1",
        evidence={},
    )
    assert result["status"] == "PASS", result


def test_review_task_fail_when_working_tree_dirty(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: USER_INPUT\nSTATUS: COMPLETED\nDETAIL: original user request\n",
    )
    (tmp_path / "SPEC-DRAFT.md").write_text("dirty uncommitted draft")
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000001",
        task_kind="USER_INPUT",
        review_type=None,
        work_journal_id="J-1",
        evidence={},
    )
    assert result["status"] == "FAIL"
    assert any("dirty" in f.lower() for f in result["findings"])


def test_review_task_fail_when_work_journal_entry_missing(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: USER_INPUT\nSTATUS: COMPLETED\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000001",
        task_kind="USER_INPUT",
        review_type=None,
        work_journal_id="J-DOES-NOT-EXIST",
        evidence={},
    )
    assert result["status"] == "FAIL"
    assert any("work_journal_id" in f for f in result["findings"])


def test_review_task_fail_when_work_entry_status_not_completed(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: USER_INPUT\nSTATUS: PENDING\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000001",
        task_kind="USER_INPUT",
        review_type=None,
        work_journal_id="J-1",
        evidence={},
    )
    assert result["status"] == "FAIL"
    assert any("STATUS" in f and "COMPLETED" in f for f in result["findings"])


def test_review_task_pass_when_red_review_passes(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: RED\nSTATUS: COMPLETED\nPARENT: J-0\nDETAIL: x\n"
        "\n=== J-2 ===\nTYPE: RED_REVIEW\nSTATUS: PASS\nPARENT: J-1\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000010",
        task_kind="RED",
        review_type="RED_REVIEW",
        work_journal_id="J-1",
        evidence={"review_journal_id": "J-2"},
    )
    assert result["status"] == "PASS", result


def test_review_task_fail_when_red_review_missing(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: RED\nSTATUS: COMPLETED\nPARENT: J-0\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000010",
        task_kind="RED",
        review_type="RED_REVIEW",
        work_journal_id="J-1",
        evidence={},
    )
    assert result["status"] == "FAIL"
    assert any("RED_REVIEW" in f for f in result["findings"])


def test_review_task_fail_when_reviewer_verdict_not_pass(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: RED\nSTATUS: COMPLETED\nPARENT: J-0\nDETAIL: x\n"
        "\n=== J-2 ===\nTYPE: RED_REVIEW\nSTATUS: FAIL\nPARENT: J-1\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000010",
        task_kind="RED",
        review_type="RED_REVIEW",
        work_journal_id="J-1",
        evidence={"review_journal_id": "J-2"},
    )
    assert result["status"] == "FAIL"
    assert any("STATUS" in f and "PASS" in f for f in result["findings"])


def test_review_task_fail_when_reviewer_verdict_wrong_type(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: RED\nSTATUS: COMPLETED\nPARENT: J-0\nDETAIL: x\n"
        "\n=== J-2 ===\nTYPE: GREEN_REVIEW\nSTATUS: PASS\nPARENT: J-1\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000010",
        task_kind="RED",
        review_type="RED_REVIEW",
        work_journal_id="J-1",
        evidence={"review_journal_id": "J-2"},
    )
    assert result["status"] == "FAIL"
    assert any("TYPE" in f and "RED_REVIEW" in f for f in result["findings"])


def test_review_task_fail_when_green_without_prior_red_review(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: GREEN\nSTATUS: COMPLETED\nPARENT: J-0\nDETAIL: x\n"
        "\n=== J-2 ===\nTYPE: GREEN_REVIEW\nSTATUS: PASS\nPARENT: J-1\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000020",
        task_kind="GREEN",
        review_type="GREEN_REVIEW",
        work_journal_id="J-1",
        evidence={"review_journal_id": "J-2"},
    )
    assert result["status"] == "FAIL"
    assert any("RED_REVIEW" in f and "prerequisite" in f.lower() for f in result["findings"])


def test_review_task_pass_when_green_has_red_review_prerequisite(tmp_path):
    tmp_path = _make_repo(tmp_path)
    _commit_journal(
        tmp_path,
        "=== J-1 ===\nTYPE: RED\nSTATUS: COMPLETED\nPARENT: J-0\nDETAIL: x\n"
        "\n=== J-2 ===\nTYPE: RED_REVIEW\nSTATUS: PASS\nPARENT: J-1\nDETAIL: x\n"
        "\n=== J-3 ===\nTYPE: GREEN\nSTATUS: COMPLETED\nPARENT: J-2\nDETAIL: x\n"
        "\n=== J-4 ===\nTYPE: GREEN_REVIEW\nSTATUS: PASS\nPARENT: J-3\nDETAIL: x\n",
    )
    result = _check_process_gate(
        repo_path=str(tmp_path),
        task_id="B-000020",
        task_kind="GREEN",
        review_type="GREEN_REVIEW",
        work_journal_id="J-3",
        evidence={"review_journal_id": "J-4"},
    )
    assert result["status"] == "PASS", result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_working_tree_dirty_false_on_clean_repo(tmp_path):
    tmp_path = _make_repo(tmp_path)
    assert _working_tree_dirty(str(tmp_path)) is False


def test_working_tree_dirty_true_after_uncommitted_change(tmp_path):
    tmp_path = _make_repo(tmp_path)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: x\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: y\n")
    assert _working_tree_dirty(str(tmp_path)) is True


def test_committed_journal_returns_committed_text_not_dirty(tmp_path):
    tmp_path = _make_repo(tmp_path)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: committed journal\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "JOURNAL_SDD_TDD_SKILL.log").write_text("DETAIL: dirty uncommitted journal\n")
    content = _committed_journal(str(tmp_path))
    assert content == "DETAIL: committed journal\n"


# ---------------------------------------------------------------------------
# Broker access log
# ---------------------------------------------------------------------------


def test_broker_log_path_is_under_dot_git_sddtdd(tmp_path):
    tmp_path = _make_repo(tmp_path)
    path = _broker_log_path(str(tmp_path))
    assert path == tmp_path / ".git" / "sddtdd" / "broker-access.jsonl"


def test_broker_log_records_both_started_and_completed_for_every_verdict(tmp_path):
    tmp_path = _make_repo(tmp_path)
    for verdict in ("PASS", "FAIL", "NEEDS_CLARIFICATION", "ERROR"):
        _append_broker_event(str(tmp_path), {
            "event": "task_review_started",
            "task_id": f"B-{verdict}",
            "head_sha_before": "abc",
        })
        _append_broker_event(str(tmp_path), {
            "event": "task_review_completed",
            "task_id": f"B-{verdict}",
            "head_sha_before": "abc",
            "head_sha_after": "abc",
            "status": verdict,
            "duration_ms": 1,
        })
    log_path = tmp_path / ".git" / "sddtdd" / "broker-access.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8
    statuses = [
        json.loads(line)["status"]
        for line in lines
        if json.loads(line)["event"] == "task_review_completed"
    ]
    assert statuses == ["PASS", "FAIL", "NEEDS_CLARIFICATION", "ERROR"]
