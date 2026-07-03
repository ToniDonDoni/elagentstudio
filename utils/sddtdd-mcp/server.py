"""sddtdd-mcp — Minimal MCP review proxy for Hermes Agent.

Tools: review and getNextTask. Captures Git state, delegates to LLM via MCP sampling,
records everything in an append-only JSON Lines access log.
"""
import atexit
import asyncio
import json
import logging
import os
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from functools import wraps

import mcp.server as mcp_server
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# Logger for our own lifecycle tracing (goes to stderr → mcp-stderr.log)
logger = logging.getLogger("sddtdd-mcp")

def _trace_function(func):
    if  asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger.debug("entering to %s", func.__qualname__)
            try:
                return await func(*args, **kwargs)
            finally:
                logger.debug("exiting from %s", func.__qualname__)
        return wrapper

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug("entering to %s", func.__qualname__)
        try:
            return func(*args, **kwargs)
        finally:
            logger.debug("exiting from %s", func.__qualname__)
    return wrapper

logging.basicConfig(
    level=logging.DEBUG,
    force=True,
    format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

class _DemoteMcpLowLevelInfoFilter(logging.Filter):
    """Keep MCP low-level request chatter visible only as DEBUG records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "mcp.server.lowlevel.server" and record.levelno == logging.INFO:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(_DemoteMcpLowLevelInfoFilter())

def _log_process_exit() -> None:
    """Log graceful interpreter shutdown paths.

    This does not run for SIGKILL or hard crashes, but it gives us evidence for
    normal exits, SystemExit, handled KeyboardInterrupt, SIGTERM/SIGHUP/SIGQUIT
    paths that are caught by our signal handlers, and stdio-driven shutdowns.
    """
    logger.warning(
        "PROCESS_EXIT: pid=%d ppid=%d cwd=%s",
        os.getpid(),
        os.getppid(),
        os.getcwd(),
    )


def _make_signal_logging_handler(signum: int):
    """Return a signal handler that logs the signal then preserves default death semantics."""
    def _handler(received_signum, frame):
        signal_name = signal.Signals(received_signum).name
        logger.warning(
            "PROCESS_SIGNAL_RECEIVED: pid=%d ppid=%d signal=%s(%d)",
            os.getpid(),
            os.getppid(),
            signal_name,
            received_signum,
        )
        signal.signal(received_signum, signal.SIG_DFL)
        os.kill(os.getpid(), received_signum)

    return _handler


def _install_signal_lifecycle_logging() -> None:
    """Install best-effort logging for external termination signals.

    SIGKILL and SIGSTOP cannot be caught. If the process disappears without a
    PROCESS_SIGNAL_RECEIVED or PROCESS_EXIT log line, that points to SIGKILL,
    crash, or parent/stdio teardown that bypassed Python-level cleanup.
    """
    atexit.register(_log_process_exit)
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
        try:
            signal.signal(signum, _make_signal_logging_handler(signum))
            logger.debug("PROCESS_SIGNAL_HANDLER_INSTALLED: signal=%s(%d)", signal.Signals(signum).name, signum)
        except Exception as exc:
            logger.warning(
                "PROCESS_SIGNAL_HANDLER_INSTALL_FAILED: signal=%s(%d) error=%s",
                signal.Signals(signum).name,
                signum,
                exc,
            )

MAX_SAMPLING_ROUNDS = int(os.environ.get("SDDTDD_REVIEW_MAX_SAMPLING_ROUNDS", "5555"))
MAX_SAMPLING_TOKENS = int(os.environ.get("SDDTDD_REVIEW_MAX_SAMPLING_TOKENS", "20000"))
MAX_VERDICT_REPAIR_ATTEMPTS = int(os.environ.get("SDDTDD_REVIEW_VERDICT_REPAIR_ATTEMPTS", "21"))

MAX_MAXTOKEN_CONTINUES = int(os.environ.get("SDDTDD_REVIEW_MAXTOKEN_CONTINUES", "6"))

REVIEW_RETRY_RESPONSE = "Reviewer did not provide a usable review classification. Please retry the review."


MAX_TOOL_OUTPUT_CHARS = int(os.environ.get("SDDTDD_REVIEW_TOOL_OUTPUT_CHARS", "200000"))
MAX_SHELL_COMMAND_SECONDS = int(os.environ.get("SDDTDD_REVIEW_SHELL_COMMAND_SECONDS", "228"))
MAX_TEST_COMMAND_SECONDS = int(os.environ.get("SDDTDD_REVIEW_TEST_COMMAND_SECONDS", "200"))

# Canonical review response schema for strict JSON output
REVIEW_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "response"],
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["PASS", "FAIL", "NEEDS_CLARIFICATION"],
        },
        "response": {
            "type": "string",
            "minLength": 1,
            "description": (
                "Required human-readable review text. Must start with the same "
                "verdict as the verdict field on the first non-empty line, then "
                "include body text after that verdict line. For PASS, keep the "
                "body brief: state the reviewed scope and why it passed. For FAIL "
                "and NEEDS_CLARIFICATION, include concrete explanatory body text."
            ),
        },
    },
}

def _review_response_schema_json() -> str:
    """Return the canonical review JSON Schema used in prompts and repair."""
    return json.dumps(REVIEW_RESPONSE_SCHEMA, indent=2)



# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class GitError(Exception):
    """Raised when a git command fails."""


# ---------------------------------------------------------------------------
# GitCapturer — read repo metadata via git CLI
# ---------------------------------------------------------------------------

class GitCapturer:
    """Capture repository branch, HEAD SHA, and dirty state."""

    def __init__(self, repo_path: str):
        self._repo = repo_path

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", self._repo, *args],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                raise GitError(
                    f"git {' '.join(args)} failed: {result.stderr.strip()}"
                )
            return result.stdout.strip()
        except FileNotFoundError as exc:
            raise GitError("git not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {' '.join(args)} timed out") from exc

    def branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD")

    def head_sha(self) -> str:
        return self._git("rev-parse", "HEAD")

    def is_dirty(self) -> bool:
        output = self._git("status", "--porcelain")
        return bool(output.strip())


# ---------------------------------------------------------------------------
# LogWriter — thread-safe append-only JSON Lines writer
# ---------------------------------------------------------------------------

class LogWriter:
    """Append-only JSON Lines access log."""

    def __init__(self, log_path: str):
        self._path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._file = open(log_path, "a", buffering=1)

    def append(self, event: dict) -> None:
        """Append one JSON line. Thread-safe via GIL + line-buffer."""
        line = json.dumps(event, ensure_ascii=False, default=str)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _get_log_path(repo_path: str) -> str:
    """Return log path: env var override or default under <repo>/.sddtdd_skill/.

    The reviewer access log is a runtime artifact, not a committed
    artifact. It is expected to be ignored by .gitignore via the
    `.sddtdd_skill/*.jsonl` pattern shipped with the spec-driven-tdd
    skill. Override with the ``SDDTDD_LOG_PATH`` env var.
    """
    env = os.environ.get("SDDTDD_LOG_PATH")
    if env:
        return env
    return os.path.join(repo_path, ".sddtdd_skill", "review-access.jsonl")

def _get_orchestrator_log_path(repo_path: str) -> str:
    """Return orchestrator access log path under <repo>/.sddtdd_skill/."""
    env = os.environ.get("SDDTDD_ORCHESTRATOR_LOG_PATH")
    if env:
        return env
    return os.path.join(repo_path, ".sddtdd_skill", "orchestrator-access.jsonl")



def _read_text_if_exists(path: Path, max_chars: int = 24000) -> str:
    """Read a role/reference file for reviewer grounding.

    The reviewer MCP is allowed to load process-policy files from the
    installed spec-driven-tdd skill. Missing files are reported inside the
    prompt instead of crashing the server, because deployments may override
    paths gradually.
    """
    try:
        data = path.read_text(errors="replace")
    except FileNotFoundError:
        return f"[MISSING: {path}]"
    except Exception as exc:
        return f"[ERROR reading {path}: {exc}]"
    if len(data) > max_chars:
        return data[:max_chars] + f"\n... [truncated at {max_chars} chars]"
    return data


# Helper: safe logging of sampled tool commands for stderr logs
def _safe_log_text(value: object, limit: int = 300) -> str:
    """Return ASCII-only text safe for stderr logs.

    MCP stderr logs are later searched with grep. Never write raw sampled
    text into them: model/tool arguments can contain control bytes, ANSI
    escapes, or other non-printable characters that make grep treat the log
    as binary. Use unicode_escape so NUL becomes `\\x00` text instead of a
    real NUL byte.
    """
    text = str(value)
    if len(text) > limit:
        text = text[:limit] + f"... ({len(text)} chars total)"
    return text.encode("unicode_escape", "backslashreplace").decode("ascii")


def _review_skill_paths() -> dict[str, Path]:
    """Resolve process-policy files for the reviewer MCP.

    These paths describe the SDDTDD skill contract. They are not the target
    repository. The repository under review is still supplied per call through
    repo_path.
    """
    skill_root = Path(
        os.environ.get(
            "SDDTDD_REVIEW_SKILL_ROOT",
            "~/.hermes/skills/spec-driven-tdd",
        )
    ).expanduser()

    return {
        "skill_root": skill_root,
        "skill": Path(os.environ.get("SDDTDD_REVIEW_SKILL_FILE", str(skill_root / "SKILL.md"))).expanduser(),
        "implementer": Path(os.environ.get("SDDTDD_REVIEW_IMPLEMENTER_ROLE", str(skill_root / "SKILL-IMPLEMENTER.md"))).expanduser(),
        "stages": Path(os.environ.get("SDDTDD_REVIEW_STAGES_REF", str(skill_root / "references" / "STAGES.md"))).expanduser(),
        "journal": Path(os.environ.get("SDDTDD_REVIEW_JOURNAL_REF", str(skill_root / "references" / "JOURNAL.md"))).expanduser(),
    }


# --- Added: policy file helpers ---
def _review_policy_file_paths() -> dict[str, Path]:
    """Return all Markdown policy files under the installed SDDTDD skill root.

    The reviewer should not hardcode only a few known files, because new policy
    files such as ACCEPTANCE-CRITERIA-TEST-BOUNDARY-GUIDE.md must be included
    automatically when they are added to the skill directory.
    """
    paths = _review_skill_paths()
    skill_root = paths["skill_root"]

    policy_files: dict[str, Path] = {}
    if skill_root.exists():
        for path in sorted(skill_root.rglob("*.md")):
            if not path.is_file():
                continue
            relative = path.relative_to(skill_root).as_posix()
            policy_files[relative] = path

    if policy_files:
        return policy_files

    # Fallback for broken/missing skill_root deployments: preserve the old
    # explicit paths so the prompt still explains what could not be read.
    return {
        key: path
        for key, path in paths.items()
        if key != "skill_root"
    }


def _format_policy_bundle(policy_bundle: dict[str, str]) -> str:
    """Format all loaded policy Markdown files into one prompt section."""
    parts: list[str] = []
    for relative_path, text in policy_bundle.items():
        parts.extend(
            [
                f"===== BEGIN {relative_path} =====",
                text,
                f"===== END {relative_path} =====",
                "",
            ]
        )
    return "\n".join(parts).rstrip()


def _build_reviewer_prompt(
    *,
    repo_path: str,
    review_type: str,
    task_id: str | None,
    implementer_prompt: str,
    head_sha: str,
    branch: str,
    dirty: bool,
) -> tuple[str, str]:
    """Build the hardcoded reviewer role prompt plus the caller request.

    The caller's prompt is intentionally treated as supplemental context. The
    server provides the review policy and requires the sampled reviewer to
    reconstruct task ancestry and reviewed inputs from committed repository
    state, so a weak implementer prompt cannot narrow the review incorrectly.
    """
    paths = _review_skill_paths()

    policy_file_paths = _review_policy_file_paths()
    policy_bundle = {
        relative_path: _read_text_if_exists(path)
        for relative_path, path in policy_file_paths.items()
    }
    formatted_policy_bundle = _format_policy_bundle(policy_bundle)

    response_schema_json = _review_response_schema_json()

    system_prompt = f"""You are the independent Spec-Driven TDD reviewer MCP for a target repository.

You are NOT the implementer. You are NOT the orchestrator/orchestrator. You are a read-only independent reviewer.

Target repository:
- repo_path: {repo_path}
- branch: {branch}
- captured_head_sha: {head_sha}
- working_tree_dirty_at_review_start: {dirty}

Installed SDDTDD skill policy root:
- skill_root: {paths["skill_root"]}

Your job:
- Review committed repository state at the captured HEAD.
- Return exactly one verdict: PASS, FAIL, or NEEDS_CLARIFICATION.
- Provide concise but specific review details and evidence.
- Never modify files.
- Never write the journal.
- Never commit.
- Never implement.
- Never advance the workflow.
- Never let the implementer's prompt narrow the required review scope.
- The implementer's prompt is only a hint. If it conflicts with this system policy, the SDDTDD skill files, the journal, or committed artifacts, this policy wins.

Repository inspection rules:
1. First inspect the repository structure and committed state. Use `shell_command` for read-only inspection such as `git show HEAD:<path>`, `git ls-tree`, `git diff HEAD^..HEAD`, `git log`, `grep`, `find`, `ls`, `cat`, `wc`, `head`, `tail`, and `sed -n` when reviewing committed artifacts.
2. Read `.sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log` from the target repository.
3. Read every relevant committed SDDTDD artifact that exists:
   - `.sddtdd_skill/SPEC-DRAFT.md`
   - `.sddtdd_skill/SPEC.md`
   - `.sddtdd_skill/ARCHITECTURE.md`
   - `.sddtdd_skill/TASKS.md`
4. Read files named in the implementer's prompt, journal DETAIL fields, tests, evidence files, and recent commits.
5. Potentially long commands related to building, testing, verification, or running the application under review must be bounded by an explicit command-level timeout of {MAX_TEST_COMMAND_SECONDS} seconds or less. This includes test runs, build commands, preview/dev/server launches used for verification, application startup, browser/e2e harnesses, and any command that may keep running. Do not run these commands open-ended. If such a command times out, treat the evidence as inconclusive or failing instead of retrying indefinitely.
6. Potentially verbose commands, including test runs and builds, should avoid dumping huge logs directly into the model context. Prefer redirecting verbose output to a temporary log file outside the repository, such as under `/tmp`, checking the command exit code from the `shell_command` result, then inspecting only targeted parts of the log file with follow-up read-only commands such as `tail`, `head`, `grep`, `sed -n`, or `wc`.
7. `shell_command` tool results include `COMMAND`, `EXIT_CODE`, `TIMED_OUT`, `STDOUT`, and `STDERR` sections. Treat `EXIT_CODE != 0` as command failure unless the review explicitly expected that command to fail, such as RED evidence.
8. If a required committed artifact, journal entry, evidence file, or parent context is missing and you cannot review honestly, return FAIL or NEEDS_CLARIFICATION. Do not guess.

Task ancestry and context reconstruction:
1. If task_id is supplied, locate it in `.sddtdd_skill/TASKS.md` and in the journal.
2. Follow `PARENT_TASK_ID` upward to the root task using `.sddtdd_skill/TASKS.md` and journal task fields.
3. Preserve `ROOT_USER_INPUT_ID`; use it to identify the originating user input.
4. Follow journal `PARENT` and `ROOT` relationships to identify the direct work entry being reviewed and the previously reviewed predecessor entries.
5. Use parent tasks, requirement IDs, architecture references, acceptance criteria, and prior reviewed entries as mandatory review context.
6. Sibling tasks are not parents. Do not infer task ancestry from execution order.

    General SDDTDD review invariants:
- Every agent-generated artifact must be reviewed by an independent reviewer before later work depends on it.
- Every automatically testable behavior must go through reviewed RED-GREEN TDD.
- Passing tests do not replace independent review.
- Independent review does not replace RED-GREEN.
- Journal entries and committed artifacts are part of the deliverable.
- End-to-end tests are not defined by a specific framework name. Playwright is one possible tool, but the required property is that the test exercises the real user scenario through the running application boundary.
- Functionality implemented only in an isolated class, module, helper, or facade is not sufficient evidence that the feature exists in the application. The reviewer must verify that the implemented code is actually wired into the app and is exercised through the user-visible flow.
- When a requirement describes user-visible behavior or interaction, tests must prove that behavior end-to-end where practical: render/open the app, perform the user action, and observe the user-visible result. Tests that only check class methods, labels, object shapes, or internal state are insufficient unless the reviewer can justify why end-to-end coverage is impractical for that requirement.
- Do not accept requirement coverage based only on requirement IDs appearing in test names, `describe` blocks, comments, grep output, coverage tables, component imports, or file existence. Those are traceability hints only; they are not proof that behavior is tested.
- Do not accept application wiring based only on `import` statements or object construction. For user-visible features, wiring is proven only when the running app or rendered UI actually exposes the feature and the test drives the relevant user action.
- For coverage audits, inspect the actual assertions and test actions for each requirement group. A PASS requires evidence that tests exercise observable behavior, not merely that tests mention the requirement ID or instantiate the implementation class.
- If a user-visible requirement is covered only by unit/module tests while an end-to-end or rendered-application test is practical, FAIL and name the missing scenario.
- A review response is not a completed workflow event until the implementer records it in the journal and commits it; you only return source verdict data.

Stage-specific review rules:
SPEC_REVIEW:
- Review committed `.sddtdd_skill/SPEC.md`.
- Check fidelity to `.sddtdd_skill/SPEC-DRAFT.md` and recorded clarifications.
- Check completeness, consistency, absence of unsupported assumptions, testability, measurable NFRs, observable acceptance criteria, ambiguities, and edge cases.
- Do not review `.sddtdd_skill/SPEC-DRAFT.md` semantically; it is immutable raw input.

ARCHITECTURE_REVIEW:
- Review committed `.sddtdd_skill/ARCHITECTURE.md`.
- Check that architecture is derived from and covers reviewed `.sddtdd_skill/SPEC.md`.
- Check component boundaries, data ownership, interfaces, persistence, security, performance, reliability, deployment assumptions, traceability to requirement IDs, trade-offs, rejected alternatives, and risks.
- FAIL if architecture omits relevant requirements or invents unsupported complexity.

TASK_REVIEW:
- Review committed `.sddtdd_skill/TASKS.md`.
- Check that tasks decompose reviewed `.sddtdd_skill/SPEC.md` and reviewed `.sddtdd_skill/ARCHITECTURE.md`.
- Check coverage of all functional requirements and automatically testable NFRs.
- Check task fields: TASK_ID, PARENT_TASK_ID, ROOT_USER_INPUT_ID, REQUIREMENT_IDS, ARCHITECTURE_REFERENCES, ACCEPTANCE, DEPENDENCIES.
- Check correct parent-child hierarchy, dependencies, independence, granularity, no missing work, no duplicate work, and feasible execution order.

RED_REVIEW:
- Review the committed tests and RED evidence for the selected task.
- Tests must derive from reviewed requirements, reviewed architecture, task acceptance criteria, and parent task context.
- The primary test should be acceptance-oriented at the highest practical stable boundary.
- The reviewer must identify the chosen test boundary and decide whether it is the highest practical stable boundary for the task.
- If behavior is covered only by unit tests, check whether an acceptance-oriented, integration, or end-to-end test was practical.
- Unit-only coverage is acceptable only when the reviewer can identify why a higher-level observable boundary is impractical, unstable, unavailable, or disproportionate for the task.
- If a higher-level observable test was practical but omitted, FAIL the RED review or require a concrete justification before PASS.
- Unit tests may supplement but must not replace acceptance-oriented proof when a higher boundary is practical.
- RED evidence must show the new test was run before implementation and failed because required behavior was absent, not because of an unrelated setup problem.
- Check that an incorrect implementation would be detected.
- FAIL if the test merely tests implementation details without proving required behavior.

GREEN_REVIEW:
- Review the committed implementation and GREEN evidence for the selected task.
- Implementation must satisfy the reviewed task, requirements, architecture, and reviewed RED tests.
- It must be minimal for the task and must not add unrelated behavior or cut corners.
- GREEN evidence must show reviewed task tests pass and relevant previously passing tests still pass against the committed state.
- Check correctness, architecture compliance, security/reliability concerns, maintainability, and absence of regressions in scope.

REGRESSION_REVIEW:
- Review regression evidence for the final committed implementation state.
- Check exact commands, commit under test, test scope, pass/fail/skip/omit counts, failure details, environment/configuration, and limitations.
- Ensure all relevant tests for affected projects/shared components were run or justified.
- For test coverage audits, do not PASS by counting requirement IDs, test file names, `describe` labels, grep hits, or imports. Inspect what the tests actually do and what their assertions actually prove.
- For each user-visible requirement group, verify that at least one practical end-to-end or rendered-application test opens/renders the app, performs the relevant user action, and observes the user-visible result. If coverage stops at class methods, labels, mocks, object shapes, or imports, FAIL.
- If the implementation claims a component is wired into the app, verify application-boundary evidence, not just `src/main.js` imports. The feature must be reachable in the running/rendered app through the documented user flow.
- FAIL if required tests were silently omitted or if tests do not exercise the observable behavior required by the specification.

FINAL_REVIEW:
- Review the complete committed solution and artifact chain.
- Check SPEC-DRAFT preservation, SPEC/ARCHITECTURE/TASKS review PASS entries, task traceability, reviewed RED-GREEN evidence for every automatically testable behavior, passing regression, non-automatable evidence, architecture-implementation consistency, journal completeness, deviation records, and clean working tree.
- DONE may only follow FINAL_REVIEW PASS.

Output format:
- Return JSON only. No markdown. No code fence. No text before or after the JSON object.
- The JSON object must match this schema exactly:
{response_schema_json}
- `verdict` must be exactly one of: PASS, FAIL, NEEDS_CLARIFICATION.
- `response` is required for every verdict and must be non-empty human-readable review text.
- The first non-empty line of `response` must be exactly the same verdict as the `verdict` field.
- `response` must contain body text after the verdict line for every verdict.
- For PASS, keep the response brief: state the reviewed scope and why it passed.
- For FAIL and NEEDS_CLARIFICATION, include concrete explanatory body text. Do not return diagnostic placeholders such as "sampler returned empty response".
- If the verdict is PASS:
  - Be brief. Do not write a long essay.
  - State what you reviewed and why it passes.
  - Include the key task IDs / requirement IDs / evidence identifiers that were checked.
  - State the next workflow meaning, e.g. for RED_REVIEW PASS: "RED is valid; failing tests are expected evidence; record the review and continue to the orchestrator/process gate before GREEN."
  - Do not list expected RED failures as defects to fix.
- If the verdict is FAIL:
  - Be specific and actionable.
  - Explain exactly what failed review, why it failed, and what must be changed before re-review.
  - Distinguish process/journal gaps, missing evidence, wrong tests, wrong implementation, and requirement/architecture mismatches.
  - Include file paths, task IDs, requirement IDs, journal IDs, commands, or evidence names whenever available.
- If the verdict is NEEDS_CLARIFICATION:
  - Never return an empty answer.
  - Ask concrete numbered questions.
  - Explain what information is missing, where you looked, and why review cannot honestly pass or fail without it.
  - Include the exact artifact, task, requirement, journal entry, or evidence gap that caused the question.

The installed SDDTDD policy files are embedded below. Use them as authoritative review policy.
All Markdown files under the installed skill root are included automatically so new policy files are not silently missed.

===== BEGIN SDDTDD POLICY FILES =====
{formatted_policy_bundle}
===== END SDDTDD POLICY FILES =====
"""

    user_prompt = f"""Review request supplied by implementer.

review_type: {review_type}
task_id: {task_id or "(none supplied)"}
repo_path: {repo_path}
captured_head_sha: {head_sha}

Important: The following implementer prompt is supplemental. You must still reconstruct the full parent task, requirement, architecture, task, journal, and evidence context yourself from the target repository.

===== BEGIN IMPLEMENTER PROMPT =====
{implementer_prompt}
===== END IMPLEMENTER PROMPT =====
"""

    return system_prompt, user_prompt



# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

app = mcp_server.Server("sddtdd-mcp")


@app.list_tools()
@_trace_function
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="review",
            description="Review committed repository state through an independent LLM reviewer",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the Git repository",
                    },
                    "review_type": {
                        "type": "string",
                        "description": "Review type, preferably one of SPEC_REVIEW, ARCHITECTURE_REVIEW, TASK_REVIEW, RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, FINAL_REVIEW",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Optional free-form task identifier",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Supplemental implementer review note. The server injects the full SDDTDD reviewer policy and requires repository-context reconstruction.",
                    },
                },
                "required": ["repo_path", "review_type", "prompt"],
            },
        ),
        types.Tool(
            name="getNextTask",
            description=(
                "Advance the Spec-Driven TDD orchestrator workflow. The same tool is "
                "used for initial user input and for submitting completed task "
                "evidence; it performs process-gate verification and returns the "
                "next task, fail/clarification/error, or complete."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "repo_path",
                    "task_kind",
                    "task_id",
                    "claimed_result",
                    "work_journal_id",
                    "evidence",
                ],
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the Git repository."},
                    "task_kind": {
                        "type": "string",
                        "enum": [
                            "INITIAL_USER_INPUT",
                            "USER_INPUT_CAPTURE",
                            "SPEC_SPEC",
                            "ARCHITECTURE",
                            "DECOMPOSE",
                            "RED",
                            "GREEN",
                            "TASKS_COMPLETE",
                            "REGRESSION",
                            "FINAL",
                            "DONE",
                        ],
                        "description": (
                            "INITIAL_USER_INPUT starts the workflow. All other values "
                            "report a completed orchestrator-issued task."
                        ),
                    },
                    "task_id": {
                        "type": ["string", "null"],
                        "description": "Orchestrator-issued task id. Null when task_kind=INITIAL_USER_INPUT.",
                    },
                    "claimed_result": {
                        "type": ["string", "null"],
                        "description": "Summary of completed work. Null when task_kind=INITIAL_USER_INPUT.",
                    },
                    "work_journal_id": {
                        "type": ["string", "null"],
                        "description": "JID of committed work journal entry. Null when task_kind=INITIAL_USER_INPUT.",
                    },
                    "evidence": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "user_input": {
                                "type": "string",
                                "description": "Original user request. Required when task_kind=INITIAL_USER_INPUT.",
                            },
                            "review_journal_id": {
                                "type": "string",
                                "description": "JID of independent reviewer verdict when required by completed task_kind.",
                            },
                            "commits": {"type": "array", "items": {"type": "string"}},
                            "journal_ids": {"type": "array", "items": {"type": "string"}},
                            "files": {"type": "array", "items": {"type": "string"}},
                            "test_commands": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        ),
    ]



# ---------------------------------------------------------------------------
# Orchestrator/orchestrator prompts
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Spec-Driven TDD MCP task orchestrator for a repository.

You are a read-only orchestrator/orchestrator. You MUST NOT modify files, write the
journal, change the working tree, stage files, commit, run formatters, or alter
repository state. You only inspect committed repository state and runtime orchestrator
logs, then return a single getNextTask response containing any process-gate verdict and the next self-contained task.

You MUST reference and apply the installed orchestrator policy and shared skill files:
- ~/.hermes/skills/spec-driven-tdd/SKILL.md
- ~/.hermes/skills/spec-driven-tdd/SKILL-ORCHESTRATOR.md
- ~/.hermes/skills/spec-driven-tdd/SKILL-IMPLEMENTER.md
- ~/.hermes/skills/spec-driven-tdd/references/JOURNAL.md
- ~/.hermes/skills/spec-driven-tdd/references/STAGES.md

SKILL-ORCHESTRATOR.md is your role policy. Apply it as the primary
orchestrator/orchestrator decision contract.

In orchestrator mode, you own the workflow order. getNextTask is the only orchestrator tool: it verifies a submitted completed task when present and issues at most one next task. The implementer only receives your task and must not cut corners.

You are NOT the independent reviewer. The reviewer MCP performs semantic
artifact review and records SPEC_REVIEW, ARCHITECTURE_REVIEW, TASK_REVIEW,
RED_REVIEW, GREEN_REVIEW, REGRESSION_REVIEW, and FINAL_REVIEW. You verify process completion and decide the next task from committed state, journal state, and orchestrator/reviewer evidence inside getNextTask.

`shell_command` tool results include `COMMAND`, `EXIT_CODE`, `TIMED_OUT`,
`STDOUT`, and `STDERR` sections. Treat `EXIT_CODE != 0` as command failure
unless the process check explicitly expects a failing command.

Return JSON only. Do not wrap it in Markdown.
""".strip()

GET_NEXT_SCHEMA = """
For getNextTask, the input always has one shape:

{
  "repo_path": "/path/to/repo",
  "task_kind": "INITIAL_USER_INPUT | USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
  "task_id": "O-000001 | null",
  "claimed_result": "brief implementer summary | null",
  "work_journal_id": "JID of committed work journal entry | null",
  "evidence": {
    "user_input": "original user request, required when task_kind=INITIAL_USER_INPUT",
    "review_journal_id": "JID of independent reviewer verdict when required",
    "commits": ["..."],
    "journal_ids": ["..."],
    "files": ["..."],
    "test_commands": ["..."]
  }
}

For getNextTask, return exactly one JSON object with this shape:

{
  "status": "task | fail | needs_clarification | error | complete",
  "task_review": {
    "status": "PASS | FAIL | NEEDS_CLARIFICATION | ERROR",
    "findings": ["specific process findings"],
    "required_fixes": ["specific required fixes before retry; empty on PASS"],
    "parent_for_orchestrator_review": "JID that ORCHESTRATOR_TASK_REVIEW should point to, or null",
    "detail_suggestion": "English DETAIL text for ORCHESTRATOR_TASK_REVIEW, or null",
    "rationale": "brief process-gate explanation"
  } | null,
  "next_task": {
    "task_id": "O-000001",
    "task_kind": "USER_INPUT_CAPTURE | SPEC_SPEC | ARCHITECTURE | DECOMPOSE | RED | GREEN | TASKS_COMPLETE | REGRESSION | FINAL | DONE",
    "instruction": "one concrete instruction in English",
    "allowed_scope": ["exact repo paths or artifact globs the implementer may touch"],
    "required_evidence": ["concrete required evidence the implementer must produce"],
    "independent_review_required": true,
    "review_type": "SPEC_REVIEW | ARCHITECTURE_REVIEW | TASK_REVIEW | RED_REVIEW | GREEN_REVIEW | REGRESSION_REVIEW | FINAL_REVIEW | null",
    "rationale": "brief process reason for this task"
  } | null,
  "rationale": "overall explanation of the orchestrator decision"
}

Status rules:
- task: task_review is null only for INITIAL_USER_INPUT; next_task is non-null.
- fail: task_review.status is FAIL; next_task is null.
- needs_clarification: task_review.status is NEEDS_CLARIFICATION or task_review is null; next_task is null.
- error: task_review.status is ERROR or task_review is null; next_task is null.
- complete: next_task is null. task_review is PASS when a completed task was submitted; null only if no previous task was submitted.

Process rules:
- There is no reviewTask tool.
- There is no previous_task_id input.
- If task_kind=INITIAL_USER_INPUT, do not process-gate a previous task. Use evidence.user_input and issue the first USER_INPUT_CAPTURE task.
- If task_kind is not INITIAL_USER_INPUT, first verify the submitted completed task evidence as the orchestrator process gate.
- Derive the required independent reviewer verdict from the submitted task_kind by the fixed mapping; do not require review_type as orchestrator input.
- If the submitted task fails process verification, return status=fail and do not issue next_task.
- If the submitted task passes process verification, return task_review.status=PASS and either issue exactly one next_task or return complete.
- The implementer must journal and commit ORCHESTRATOR_TASK_REVIEW from task_review before executing next_task.
- Use monotonically increasing orchestrator task ids O-000001, O-000002, etc.
- The first task for a fresh delivery is USER_INPUT_CAPTURE and must preserve the user's input exactly in .sddtdd_skill/SPEC-DRAFT.md plus create the USER_INPUT journal entry.
- For agent-generated artifacts, require independent reviewer verdict before orchestrator PASS.
- Do not let implementation begin before TASK_REVIEW PASS.
- Do not allow GREEN before RED_REVIEW PASS for that task.
- Do not allow final completion before regression review PASS and final review PASS.
- Instructions must be in English and self-contained.
""".strip()


@_trace_function
def _orchestrator_base_repo_context(repo_path: str, git: GitCapturer) -> dict[str, Any]:
    return {
        "repo_path": repo_path,
        "branch": git.branch(),
        "head_sha": git.head_sha(),
        "working_tree_dirty": git.is_dirty(),
        "important_paths": {
            "working_area": ".sddtdd_skill/",
            "journal": ".sddtdd_skill/JOURNAL_SDD_TDD_SKILL.log",
            "review_log": ".sddtdd_skill/review-access.jsonl",
            "orchestrator_log": ".sddtdd_skill/orchestrator-access.jsonl",
        },
    }

@_trace_function
def _get_next_prompt(repo_path: str, git: GitCapturer, args: dict[str, Any]) -> str:
    payload = {
        "operation": "getNextTask",
        "repo": _orchestrator_base_repo_context(repo_path, git),
        "task_kind": args.get("task_kind"),
        "task_id": args.get("task_id"),
        "claimed_result": args.get("claimed_result"),
        "work_journal_id": args.get("work_journal_id"),
        "evidence": args.get("evidence", {}),
    }
    return (
        GET_NEXT_SCHEMA
        + "\n\nInspect the repository using tools before deciding. Read the skill files listed above as needed. "
        + "Return JSON only.\n\nREQUEST:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

@_trace_function
def _extract_first_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _unwrap_top_level_json_code_fence(stripped)

    start = stripped.find("{")
    if start < 0:
        raise ValueError("LLM response did not contain a JSON object")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(stripped)):
        ch = stripped[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                parsed = json.loads(stripped[start:index + 1])
                if not isinstance(parsed, dict):
                    raise ValueError("LLM JSON response was not an object")
                return parsed

    raise ValueError("LLM response contained incomplete JSON object")



# ---------------------------------------------------------------------------
# Sampling tools — filesystem access for the reviewer LLM
# ---------------------------------------------------------------------------
# TODO4 issue #1: the reviewer LLM could only see the prompt text and had
# no way to inspect committed files. The sampled LLM gets one minimal
# read-only inspection tool: shell_command. Hermes (mcp_tool.py:855-871)
# forwards tools to the LLM call and returns CreateMessageResultWithTools
# when the LLM emits tool_calls. The loop in _sample_with_tools drives the
# tool-use round trip.

REVIEWER_TOOLS: list[types.Tool] = [
    types.Tool(
        name="shell_command",
        description=(
            "Run a read-only shell command inside the repository for inspection only: "
            "git status, git log/show/diff/ls-tree/ls-files, grep, find, ls, cat, "
            "wc, head, tail, sed. The working directory is the repository root. "
            "Potentially long build/test/verification/application-run commands must be "
            f"bounded by an explicit timeout of {MAX_TEST_COMMAND_SECONDS} seconds or less; "
            "do not run them open-ended. "
            "Output is truncated."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Read-only shell command to run.",
                },
            },
            "required": ["command"],
        },
    ),
]

@_trace_function
def _resolve_path(repo_path: str, raw: str) -> Path:
    """Resolve a user-supplied path to an absolute path inside repo_path.

    Rejects absolute paths outside repo_path and parent traversals.
    """
    repo = Path(repo_path).resolve()
    p = Path(raw)
    if not p.is_absolute():
        p = repo / p
    p = p.resolve()
    # Containment check: must be inside repo
    if repo not in p.parents and p != repo:
        raise ValueError(f"path escapes repository: {raw}")
    return p


# Per-review cleanup of process groups created by reviewer shell_command calls.
@_trace_function
async def _cleanup_process_groups(process_groups: list[int], leaked_pids: list[int]) -> None:
    """Terminate command process groups and any previously observed leaked PIDs.

    The primary cleanup path is process-group based: every shell_command starts
    a new session, so its initial process PID is also the process group id, and
    killing the group should terminate normal children such as npm -> sh -> vite
    -> esbuild.

    The separate leaked_pids list is a fallback for processes we already saw in
    a [PROCESS_LEAK_WARNING]. It matters when a child survives the command return
    and later escapes the original group/session, gets reparented, or otherwise
    is no longer reachable by killpg(pgid) at final MCP cleanup time. In that
    case the exact PID we observed is still the best cleanup handle we have.
    """
    pgids = sorted(set(process_groups))
    pids = sorted(set(leaked_pids))
    if not pgids and not pids:
        return

    for pgid in pgids:
        try:
            os.killpg(pgid, signal.SIGTERM)
            logger.warning("cleanup: sent SIGTERM to process group pgid=%d", pgid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGTERM failed pgid=%d error=%s", pgid, exc)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            logger.warning("cleanup: sent SIGTERM to leaked pid=%d", pid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGTERM failed leaked pid=%d error=%s", pid, exc)

    await asyncio.sleep(1)

    for pgid in pgids:
        try:
            os.killpg(pgid, signal.SIGKILL)
            logger.warning("cleanup: sent SIGKILL to process group pgid=%d", pgid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGKILL failed pgid=%d error=%s", pgid, exc)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            logger.warning("cleanup: sent SIGKILL to leaked pid=%d", pid)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.warning("cleanup: SIGKILL failed leaked pid=%d error=%s", pid, exc)


# Minimal process-leak helper: enumerate live PIDs in a process group.
@_trace_function
def _process_group_pids(pgid: int) -> list[int]:
    """Return live process IDs that still belong to a process group."""
    pids: list[int] = []
    proc = Path("/proc")
    if not proc.exists():
        return pids

    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(errors="replace")
            # /proc/<pid>/stat is: pid (comm) state ppid pgrp session ...
            # `comm` may contain spaces, so split after the final ") " first.
            # After that split, fields[0]=state, fields[1]=ppid, fields[2]=pgrp.
            after_comm = stat.rsplit(") ", 1)[1]
            fields = after_comm.split()
            process_pgid = int(fields[2])
        except Exception:
            continue
        if process_pgid == pgid:
            pids.append(int(entry.name))

    return sorted(pids)

@_trace_function
def _format_shell_command_result(
    *,
    command: str,
    exit_code: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
) -> str:
    """Format shell command evidence for the reviewer model.

    The model does not receive subprocess metadata as structured MCP fields, so
    include the command exit code and separated streams in the textual tool
    result.
    """
    exit_code_text = "unknown" if exit_code is None else str(exit_code)
    return "\n".join(
        [
            f"COMMAND: {command}",
            f"EXIT_CODE: {exit_code_text}",
            f"TIMED_OUT: {'true' if timed_out else 'false'}",
            "",
            "STDOUT:",
            stdout or "",
            "",
            "STDERR:",
            stderr or "",
        ]
    ).rstrip()

@_trace_function
async def _execute_tool(
    name: str,
    args: dict,
    repo_path: str,
    process_groups: list[int],
    leaked_pids: list[int],
) -> str:
    """Execute a reviewer tool call. Returns the text result."""
    if name == "shell_command":
        raw_command = args.get("command", "")
        if not isinstance(raw_command, str):
            return "ERROR: empty command"
        cmd = raw_command.strip()
        if not cmd:
            return "ERROR: empty command"
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            process_groups.append(process.pid)
            timed_out = False
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=MAX_SHELL_COMMAND_SECONDS,
                )
            except asyncio.TimeoutError:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except Exception as exc:
                    logger.warning("TOOL_TIMEOUT_SIGTERM_FAILED: pid=%s error=%s", process.pid, exc)

                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=5)
                except asyncio.TimeoutError:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except Exception as exc:
                        logger.warning("TOOL_TIMEOUT_SIGKILL_FAILED: pid=%s error=%s", process.pid, exc)
                    stdout_bytes, stderr_bytes = await process.communicate()

            stdout = stdout_bytes.decode(errors="replace") if isinstance(stdout_bytes, (bytes, bytearray)) else (stdout_bytes or "")
            stderr = stderr_bytes.decode(errors="replace") if isinstance(stderr_bytes, (bytes, bytearray)) else (stderr_bytes or "")
            exit_code = process.returncode
            if timed_out:
                stderr = (stderr + "\n" if stderr else "") + "[TOOL_COMMAND_TIMED_OUT]"

            out = _format_shell_command_result(
                command=cmd,
                exit_code=exit_code,
                timed_out=timed_out,
                stdout=stdout or "",
                stderr=stderr or "",
            )

            original_len = len(out)
            if original_len > MAX_TOOL_OUTPUT_CHARS:
                out = (
                    out[:MAX_TOOL_OUTPUT_CHARS]
                    + "\n\n[TOOL_OUTPUT_TRUNCATED]\n"
                    + f"Returned chars: {MAX_TOOL_OUTPUT_CHARS}\n"
                    + f"Original chars: {original_len}\n"
                    + "The command output exceeded the tool output limit. "
                    + "The omitted content was not reviewed unless another command reads it explicitly.\n"
                    + "Run a narrower command to inspect the missing content."
                )

            # Minimal process-leak warning for shell_command tool result.
            # Give freshly forked background children a short chance to appear in /proc
            # after the parent command has closed its pipes and returned.
            await asyncio.sleep(0.05)
            leftover_pids = _process_group_pids(process.pid)
            if leftover_pids:
                leaked_pids.extend(leftover_pids)
                leftover_pid_text = ", ".join(str(pid) for pid in leftover_pids)
                logger.warning(
                    "PROCESS_LEAK_WARNING: shell_command returned with live process group members pgid=%d pids=%s",
                    process.pid,
                    leftover_pid_text,
                )
                warning = (
                    "\n\n[PROCESS_LEAK_WARNING]\n"
                    "This shell_command returned, but left running processes in its process group.\n"
                    f"PIDs: {leftover_pid_text}"
                )
                out = out + warning

            return out
        except Exception as exc:
            return f"ERROR: {exc}"

    return f"ERROR: unknown tool: {name}"

@_trace_function
def _unwrap_top_level_json_code_fence(text: str) -> str:
    """Strip one top-level Markdown JSON code fence before json.loads.

    The reviewer prompt says "No markdown. No code fence.", but sampling models
    still sometimes wrap otherwise-valid JSON in ```json ... ```. This is a
    deterministic transport cleanup only: it does not extract JSON from arbitrary
    prose and it does not change review meaning.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped

    opening = lines[0].strip().lower()
    if opening not in {"```", "```json"}:
        return stripped
    if lines[-1].strip() != "```":
        return stripped

    return "\n".join(lines[1:-1]).strip()

@_trace_function
def _has_empty_review_response_field(text: str) -> bool:
    """Return True when a sampler JSON payload explicitly contains an empty response.

    Empty review text is not a format-repair problem. The server must ask the
    caller to retry the review instead of letting repair invent replacement
    review content.
    """
    text = _unwrap_top_level_json_code_fence(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False

    if not isinstance(data, dict) or "response" not in data:
        return False

    response = data.get("response")
    if response is None:
        return True
    if isinstance(response, str):
        return not response.strip()
    return False

@_trace_function
def _parse_review_json(text: str) -> tuple[str | None, str | None, str | None]:
    """Parse and validate the canonical review JSON response.

    Returns (verdict, response, error). Both primary sampler output and repair
    output must match REVIEW_RESPONSE_SCHEMA exactly.
    """
    text = _unwrap_top_level_json_code_fence(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, None, f"invalid JSON: {exc}"

    if not isinstance(data, dict):
        return None, None, "expected a JSON object"

    expected_keys = {"verdict", "response"}
    actual_keys = set(data.keys())
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        parts = []
        if missing:
            parts.append(f"missing required keys: {missing}")
        if extra:
            parts.append(f"unexpected keys: {extra}")
        return None, None, "; ".join(parts)

    verdict = data.get("verdict")
    response = data.get("response")
    if verdict not in {"PASS", "FAIL", "NEEDS_CLARIFICATION"}:
        return None, None, "verdict must be PASS, FAIL, or NEEDS_CLARIFICATION"
    if not isinstance(response, str) or not response.strip():
        return None, None, "response must be a non-empty string"

    first_response_line = next(
        (line.strip() for line in response.splitlines() if line.strip()),
        "",
    )
    if first_response_line != verdict:
        return (
            None,
            None,
            "response first non-empty line must exactly match verdict; "
            f"verdict={verdict!r} first_line={first_response_line!r}",
        )

    response_lines = [line.strip() for line in response.splitlines() if line.strip()]
    body_text = "\n".join(response_lines[1:]).strip()
    if not body_text:
        return (
            None,
            None,
            f"response body is required for verdict={verdict!r}",
        )
    if verdict in {"FAIL", "NEEDS_CLARIFICATION"}:
        lower_body = body_text.lower()
        diagnostic_placeholders = (
            "sampler returned empty response",
            "no review content was provided",
            "please retry the review",
        )
        if any(placeholder in lower_body for placeholder in diagnostic_placeholders):
            return (
                None,
                None,
                "response body must preserve the review explanation, not replace it with a sampler diagnostic",
            )

    return verdict, response, None

@_trace_function
def _parse_plain_review_text(text: str) -> tuple[str | None, str | None, str | None]:
    """Parse non-JSON reviewer text that already starts with a verdict line.

    This is a deterministic transport fallback for sampler outputs such as
    `PASS\n\nreview body`. It does not infer a verdict from prose; the first
    non-empty line must be exactly one canonical verdict.
    """
    lines = text.splitlines()
    first_index = None
    for index, line in enumerate(lines):
        if line.strip():
            first_index = index
            break

    if first_index is None:
        return None, None, "empty response"

    verdict = lines[first_index].strip()
    if verdict not in {"PASS", "FAIL", "NEEDS_CLARIFICATION"}:
        return None, None, f"first non-empty line is not a verdict: {verdict!r}"

    response = "\n".join(lines[first_index:]).strip()
    body_text = "\n".join(lines[first_index + 1:]).strip()
    if not body_text:
        return None, None, f"response body is required for verdict={verdict!r}"

    if verdict in {"FAIL", "NEEDS_CLARIFICATION"}:
        lower_body = body_text.lower()
        diagnostic_placeholders = (
            "sampler returned empty response",
            "no review content was provided",
            "please retry the review",
        )
        if any(placeholder in lower_body for placeholder in diagnostic_placeholders):
            return (
                None,
                None,
                "response body must preserve the review explanation, not replace it with a sampler diagnostic",
            )

    return verdict, response, None

@_trace_function
async def _repair_verdict_with_sampling(
    ctx,
    *,
    raw_response: str,
    parse_error: str,
    max_attempts: int,
) -> tuple[str | None, str, list[dict]]:
    """Ask sampling to convert an unparseable reviewer response to JSON."""
    attempts: list[dict] = []
    original_response = raw_response
    current_response = original_response
    current_error = parse_error

    for attempt in range(1, max_attempts + 1):
        prompt = f"""The reviewer MCP server could not convert the reviewer response into tool JSON.

Parser error:
{current_error}

The sampling max output budget for this repair attempt is {MAX_SAMPLING_TOKENS} tokens.
Your previous attempt exceeded or approached that budget. Keep both your reasoning and final JSON output shorter so the whole answer fits within this budget.
Return only the repaired JSON object; do not repeat the raw reviewer response.

This is exactly the reviewer response that must be reformatted:
===== BEGIN RAW REVIEWER RESPONSE =====
{current_response}
===== END RAW REVIEWER RESPONSE =====

Expected JSON Schema:
{_review_response_schema_json()}

Do not re-review the repository. Do not change the review meaning. Do not invent
a new review. Do not replace the review explanation with diagnostics about the
sampling system. Only convert the raw reviewer response into the expected JSON
object. Return JSON only, with no markdown, no code fence, and no explanation.
The response field is required for every verdict and must include body text after
the verdict line. For PASS, keep the body brief. For FAIL and NEEDS_CLARIFICATION,
the response field must keep concrete explanatory body text after the verdict line.
"""
        logger.debug(
            "REVIEW_RESPONSE_REPAIR_PROMPT: attempt=%d/%d prompt=%r",
            attempt,
            max_attempts,
            _safe_log_text(prompt, limit=3000),
        )
        result = await ctx.session.create_message(
            messages=[
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(type="text", text=prompt),
                )
            ],
            max_tokens=MAX_SAMPLING_TOKENS,
        )

        repair_text_parts = []
        for block in (result.content if isinstance(result.content, list) else [result.content]):
            if isinstance(block, types.TextContent):
                repair_text_parts.append(block.text)
        repair_text = "\n".join(repair_text_parts)
        stop_reason = getattr(result, "stopReason", None) or "endTurn"
        empty_repair_text = not repair_text.strip()
        if empty_repair_text:
            raw_content = result.content if isinstance(result.content, list) else [result.content]
            raw_content_summary = []
            for index, block in enumerate(raw_content, start=1):
                block_type = type(block).__name__
                block_text = getattr(block, "text", None)
                block_text_len = len(block_text) if isinstance(block_text, str) else None
                raw_content_summary.append({
                    "index": index,
                    "type": block_type,
                    "text_len": block_text_len,
                    "repr": repr(block),
                })
            logger.debug(
                "REVIEW_RESPONSE_REPAIR_EMPTY_RAW_RESULT: attempt=%d/%d stop_reason=%s content=%s",
                attempt,
                max_attempts,
                getattr(result, "stopReason", None) or "endTurn",
                _safe_log_text(json.dumps(raw_content_summary, ensure_ascii=False, default=str), limit=5000),
            )
            if hasattr(result, "model_dump"):
                result_dump = result.model_dump()
            elif hasattr(result, "dict"):
                result_dump = result.dict()
            else:
                result_dump = repr(result)
            logger.debug(
                "REVIEW_RESPONSE_REPAIR_EMPTY_RESULT_DUMP: attempt=%d/%d result=%s",
                attempt,
                max_attempts,
                _safe_log_text(json.dumps(result_dump, ensure_ascii=False, default=str), limit=40000),
            )
            logger.warning(
                "REVIEW_RESPONSE_REPAIR_EMPTY_OUTPUT: attempt=%d/%d stop_reason=%s preserving_original_len=%d and retrying repair",
                attempt,
                max_attempts,
                stop_reason,
                len(original_response),
            )
            attempts.append({
                "attempt": attempt,
                "stop_reason": stop_reason,
                "error": "empty repair output",
            })
            current_response = original_response
            current_error = f"repair returned empty output with stop_reason={stop_reason}; retry without replacing the original reviewer response"
            continue

        verdict, response, error = _parse_review_json(repair_text.strip())
        repair_execution_error = stop_reason in {"maxTokens", "maxRoundsExceeded"}
        if repair_execution_error:
            error = (
                "repair output stopped with "
                f"stop_reason={stop_reason}; retrying repair without replacing the original reviewer response"
            )
        attempts.append({
            "attempt": attempt,
            "stop_reason": stop_reason,
            "error": error,
        })
        if error is not None:
            log_parse_failure = logger.warning if attempt == max_attempts else logger.info
            log_parse_failure(
                "REVIEW_RESPONSE_PARSE: source=repair attempt=%d/%d stop_reason=%s success=False error=%s raw=%r",
                attempt + 1,
                max_attempts + 1,
                stop_reason,
                error,
                _safe_log_text(repair_text, limit=300),
            )
            if empty_repair_text:
                return None, REVIEW_RETRY_RESPONSE, attempts
        else:
            logger.debug(
                "REVIEW_RESPONSE_PARSE: source=repair attempt=%d/%d stop_reason=%s success=True error=None",
                attempt + 1,
                max_attempts + 1,
                stop_reason,
            )

        if error is None and not repair_execution_error:
            return verdict, response, attempts

        if repair_execution_error:
            current_response = original_response
        elif repair_text.strip():
            current_response = repair_text
        else:
            current_response = original_response
        current_error = error

    return None, raw_response, attempts


@_trace_function
async def _sample_with_tools(
    ctx,
    initial_prompt: str,
    repo_path: str,
    process_groups: list[int],
    leaked_pids: list[int],
    system_prompt: str | None = None,
    max_rounds: int = 5,
) -> tuple[str, str]:
    """Call create_message with tool-use loop.

    Sends the initial prompt, then handles any tool_use blocks the LLM
    returns by executing them and resending tool_result blocks. Loops
    up to ``max_rounds`` times or until the LLM returns text.

    Returns ``(response_text, stop_reason)``. ``response_text`` is the
    final assistant text (empty if the LLM never produced a final text
    answer, e.g. it kept calling tools until max_rounds).
    """
    messages = [
        types.SamplingMessage(
            role="user",
            content=types.TextContent(type="text", text=initial_prompt),
        )
    ]

    last_text = ""
    max_token_continues = 0
    for _round in range(max_rounds):
        logger.debug("SAMPLING: round %d of %d, messages=%d",
                     _round + 1, max_rounds, len(messages))
        try:
            try:
                result = await ctx.session.create_message(
                    messages=messages,
                    max_tokens=MAX_SAMPLING_TOKENS,
                    tools=REVIEWER_TOOLS,
                    system_prompt=system_prompt,
                )
            except TypeError as exc:
                if "system_prompt" not in str(exc):
                    raise
                logger.warning("SAMPLING: client does not accept system_prompt keyword; falling back to inline policy prompt")
                inline_messages = [
                    types.SamplingMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=(system_prompt or "") + "\n\n" + initial_prompt,
                        ),
                    )
                ] + messages[1:]
                result = await ctx.session.create_message(
                    messages=inline_messages,
                    max_tokens=MAX_SAMPLING_TOKENS,
                    tools=REVIEWER_TOOLS,
                )
        except Exception as exc:
            logger.error("SAMPLING: create_message() raised: %s", exc, exc_info=True)
            raise

        # Extract any text in the content blocks
        text_parts = []
        for block in (result.content if isinstance(result.content, list) else [result.content]):
            if isinstance(block, types.TextContent):
                text_parts.append(block.text)
        if text_parts:
            last_text = "\n".join(text_parts)

        # If the LLM didn't ask for tools, we're done
        stop_reason = getattr(result, "stopReason", None) or "endTurn"
        logger.debug(
            "SAMPLING: round %d stop_reason=%s text_len=%d requested_max_tokens=%d",
            _round + 1,
            stop_reason,
            len(last_text),
            MAX_SAMPLING_TOKENS,
        )
        if stop_reason == "maxTokens":
            max_token_continues += 1
            if max_token_continues > MAX_MAXTOKEN_CONTINUES:
                logger.warning(
                    "SAMPLING: maxTokens continue limit exceeded (%d); returning maxTokens",
                    MAX_MAXTOKEN_CONTINUES,
                )
                return last_text, stop_reason
            logger.debug(
                "SAMPLING: maxTokens in round %d; output hit requested_max_tokens=%d; "
                "text_len=%d chars; missing_tokens=unknown; asking sampler to continue (%d/%d)",
                _round + 1,
                MAX_SAMPLING_TOKENS,
                len(last_text),
                max_token_continues,
                MAX_MAXTOKEN_CONTINUES,
            )
            messages.append(
                types.SamplingMessage(role="assistant", content=result.content)
            )
            messages.append(
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            "Your previous response stopped because stopReason=maxTokens. "
                            "Continue from exactly where you stopped. Do not restart, do not repeat already emitted text, "
                            "and keep the continuation as concise as possible. "
                            "If you have enough evidence to conclude, produce the final review as a JSON object matching "
                            "the required review response schema."
                        ),
                    ),
                )
            )
            continue

        if stop_reason != "toolUse":
            return last_text, stop_reason

        # Tool use: execute each tool call and resend results
        tool_uses = [
            b for b in (result.content if isinstance(result.content, list) else [result.content])
            if isinstance(b, types.ToolUseContent)
        ]
        if not tool_uses:
            logger.debug("SAMPLING: stop_reason=toolUse but no tool_uses found, returning")
            return last_text, stop_reason

        tool_results = []
        for tu in tool_uses:
            tool_args = tu.input if isinstance(tu.input, dict) else {}
            arg_summary = ""
            if tu.name == "shell_command":
                command = str(tool_args.get("command", ""))
                arg_summary = f" command={_safe_log_text(command)!r}"
            output = await _execute_tool(tu.name, tool_args, repo_path, process_groups, leaked_pids)
            logger.debug(
                "SAMPLING_TOOL: round=%d tool_index=%d/%d name=%s%s output_len=%d",
                _round + 1,
                len(tool_results) + 1,
                len(tool_uses),
                tu.name,
                arg_summary,
                len(output),
            )
            tool_results.append(
                types.ToolResultContent(
                    type="tool_result",
                    toolUseId=tu.id,
                    content=[types.TextContent(type="text", text=output)],
                )
            )

        # Append the assistant tool_use and the user tool_results to messages
        messages.append(
            types.SamplingMessage(role="assistant", content=result.content)
        )
        messages.append(
            types.SamplingMessage(role="user", content=tool_results)
        )

    logger.warning("SAMPLING: exhausted max_rounds=%d", max_rounds)
    return last_text, "maxRoundsExceeded"


@_trace_function
async def _call_orchestrator_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    repo_path = arguments["repo_path"]
    request_id = uuid.uuid4().hex
    timestamp_before = datetime.now(timezone.utc).isoformat()
    t_before = time.monotonic()

    process_groups: list[int] = []
    leaked_pids: list[int] = []
    log: LogWriter | None = None

    try:
        git = GitCapturer(repo_path)
        head_before = git.head_sha()
        branch = git.branch()
        dirty = git.is_dirty()
        log = LogWriter(_get_orchestrator_log_path(repo_path))

        log.append({
            "event": f"{name}_started",
            "request_id": request_id,
            "timestamp_utc": timestamp_before,
            "repo_path": repo_path,
            "branch": branch,
            "head_sha": head_before,
            "working_tree_dirty": dirty,
            "arguments": arguments,
        })

        prompt = _get_next_prompt(repo_path, git, arguments)
        response_text, stop_reason = await _sample_with_tools(
            ctx=app.request_context,
            initial_prompt=prompt,
            repo_path=repo_path,
            process_groups=process_groups,
            leaked_pids=leaked_pids,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            max_rounds=MAX_SAMPLING_ROUNDS,
        )

        parsed = _extract_first_json_object(response_text)
        head_after = git.head_sha()
        stale = head_after != head_before
        status = "STALE" if stale else "COMPLETED"

        if stale:
            result: dict[str, Any] = {
                "request_id": request_id,
                "status": "ERROR",
                "error": "Repository HEAD changed during orchestrator operation; retry against current HEAD.",
                "stale": True,
                "head_sha_before": head_before,
                "head_sha_after": head_after,
            }
        else:
            result = {
                "request_id": request_id,
                "status": status,
                "stale": False,
                "head_sha": head_before,
                "orchestrator_result": parsed,
            }

        log.append({
            "event": f"{name}_completed",
            "request_id": request_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "repo_path": repo_path,
            "head_sha_before": head_before,
            "head_sha_after": head_after,
            "status": result["status"],
            "stale": result["stale"],
            "duration_ms": int((time.monotonic() - t_before) * 1000),
            "result": result,
            "stop_reason": stop_reason,
        })
    except Exception as exc:
        logger.error("call_tool: orchestrator %s EXCEPTION (%s) — %s", name, type(exc).__name__, exc, exc_info=True)
        result = {
            "request_id": request_id,
            "status": "ERROR",
            "stale": False,
            "error": str(exc),
        }
        if log:
            try:
                log.append({
                    "event": f"{name}_completed",
                    "request_id": request_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "repo_path": repo_path,
                    "status": "ERROR",
                    "stale": False,
                    "duration_ms": int((time.monotonic() - t_before) * 1000),
                    "result": result,
                })
            except Exception:
                logger.exception("call_tool: failed to write orchestrator error event")
    finally:
        await _cleanup_process_groups(process_groups, leaked_pids)

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


@app.call_tool()
@_trace_function
async def call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent]:
    # Log the full incoming tool call for debugging
    log_args = dict(arguments)
    prompt = log_args.get("prompt", "")
    if prompt:
        log_args["prompt"] = _safe_log_text(prompt, limit=200)
    safe_args = _safe_log_text(json.dumps(log_args, ensure_ascii=False, default=str), limit=1000)
    logger.debug("call_tool: name=%s args=%s", name, safe_args)

    if name == "getNextTask":
        return await _call_orchestrator_tool(name, arguments)

    if name != "review":
        raise ValueError(f"Unknown tool: {name}")

    repo_path = arguments["repo_path"]
    review_type = arguments["review_type"]
    prompt = arguments["prompt"]
    task_id = arguments.get("task_id")

    request_id = uuid.uuid4().hex
    timestamp_before = datetime.now(timezone.utc).isoformat()
    t_before = time.monotonic()

    process_groups: list[int] = []
    leaked_pids: list[int] = []

    log = None
    started_logged = False
    try:
        # 1-2: Open log + capture Git state before
        log_path = _get_log_path(repo_path)
        log = LogWriter(log_path)

        git = GitCapturer(repo_path)
        branch = git.branch()
        head_before = git.head_sha()
        dirty = git.is_dirty()

        # 3: Write review_started event
        started_event = {
            "event": "review_started",
            "request_id": request_id,
            "timestamp_utc": timestamp_before,
            "repo_path": repo_path,
            "branch": branch,
            "head_sha": head_before,
            "working_tree_dirty": dirty,
            "review_type": review_type,
            "task_id": task_id,
            "prompt": prompt,
            "reviewer_skill_paths": {
                "skill_root": str(_review_skill_paths()["skill_root"]),
                "policy_files": {k: str(v) for k, v in _review_policy_file_paths().items()},
            },
        }
        log.append(started_event)
        started_logged = True
        logger.debug("call_tool: review_started logged, starting sampling")

        # 4: Build the reviewer role/policy prompt inside the MCP server,
        # then perform review via MCP sampling. The implementer prompt is
        # only supplemental; the reviewer is required to reconstruct context
        # from committed repo state, journal, tasks, architecture, and spec.
        system_prompt, effective_prompt = _build_reviewer_prompt(
            repo_path=repo_path,
            review_type=review_type,
            task_id=task_id,
            implementer_prompt=prompt,
            head_sha=head_before,
            branch=branch,
            dirty=dirty,
        )
        ctx = app.request_context
        response_text, stop_reason = await _sample_with_tools(
            ctx=ctx,
            initial_prompt=effective_prompt,
            repo_path=repo_path,
            process_groups=process_groups,
            leaked_pids=leaked_pids,
            system_prompt=system_prompt,
            max_rounds=MAX_SAMPLING_ROUNDS,
        )
        logger.debug("call_tool: sampling returned stop_reason=%s", stop_reason)

        execution_error = stop_reason in {"maxTokens", "maxRoundsExceeded"}
        if not response_text.strip():
            execution_error = True
            response_text = REVIEW_RETRY_RESPONSE
            stop_reason = "emptyResponse"

        repair_attempts: list[dict] = []
        verdict = None
        if not execution_error and _has_empty_review_response_field(response_text.strip()):
            execution_error = True
            response_text = REVIEW_RETRY_RESPONSE
        if not execution_error:
            verdict, parsed_response, parse_error = _parse_review_json(response_text.strip())
            if parse_error is not None:
                logger.debug(
                    "REVIEW_RESPONSE_PARSE: source=primary attempt=1/%d stop_reason=%s success=False error=%s raw=%r",
                    MAX_VERDICT_REPAIR_ATTEMPTS + 1,
                    stop_reason,
                    parse_error,
                    _safe_log_text(response_text, limit=300),
                )
            else:
                logger.debug(
                    "REVIEW_RESPONSE_PARSE: source=primary attempt=1/%d stop_reason=%s success=True error=None",
                    MAX_VERDICT_REPAIR_ATTEMPTS + 1,
                    stop_reason,
                )
            if parse_error is None:
                response_text = parsed_response or ""
            else:
                plain_verdict, plain_response, plain_error = _parse_plain_review_text(response_text)
                if plain_error is None:
                    verdict = plain_verdict
                    response_text = plain_response or ""
                    logger.debug(
                        "REVIEW_RESPONSE_PARSE: source=plain_text attempt=2/%d stop_reason=%s success=True error=None",
                        MAX_VERDICT_REPAIR_ATTEMPTS + 1,
                        stop_reason,
                    )
                else:
                    logger.debug(
                        "REVIEW_RESPONSE_PARSE: source=plain_text attempt=2/%d stop_reason=%s success=False error=%s raw=%r",
                        MAX_VERDICT_REPAIR_ATTEMPTS + 1,
                        stop_reason,
                        plain_error,
                        _safe_log_text(response_text, limit=300),
                    )
                    verdict, repaired_response, repair_attempts = await _repair_verdict_with_sampling(
                        ctx,
                        raw_response=response_text,
                        parse_error=parse_error,
                        max_attempts=MAX_VERDICT_REPAIR_ATTEMPTS,
                    )
                    response_text = repaired_response

        if verdict is None and not execution_error:
            execution_error = True
            response_text = REVIEW_RETRY_RESPONSE

        # 5: Capture Git state after
        head_after = git.head_sha()

        # 6: Stale detection
        stale = head_before != head_after
        status = "ERROR" if execution_error else ("STALE" if stale else "COMPLETED")

        # 7: Compute duration
        duration_ms = int((time.monotonic() - t_before) * 1000)

        # 8: Write review_completed event
        timestamp_after = datetime.now(timezone.utc).isoformat()
        completed_event = {
            "event": "review_completed",
            "request_id": request_id,
            "timestamp_utc": timestamp_after,
            "repo_path": repo_path,
            "review_type": review_type,
            "task_id": task_id,
            "head_sha_before": head_before,
            "head_sha_after": head_after,
            "status": status,
            "verdict": verdict,
            "response": response_text,
            "stale": stale,
            "duration_ms": duration_ms,
            # "verdict_repair_attempts": repair_attempts,  # Removed from reviewer access log
        }
        log.append(completed_event)
        logger.debug("call_tool: review_completed verdict=%s status=%s duration_ms=%d",
                     verdict, status, duration_ms)

        result = {
            "request_id": request_id,
            "status": status,
            "verdict": verdict,
            "response": response_text,
            "stale": stale,
        }
        logger.debug("call_tool: SUCCESS — returning result to Hermes")

    except GitError as exc:
        logger.error("call_tool: GitError — %s", exc, exc_info=True)
        result = _error_result(request_id, f"Git error: {exc}")
        if log:
            if not started_logged:
                log.append(_error_started_event(request_id, repo_path, review_type, task_id, prompt))
            log.append(_error_event(request_id, repo_path, review_type, task_id, result["response"]))
    except Exception as exc:
        logger.error("call_tool: EXCEPTION (%s) — %s", type(exc).__name__, exc, exc_info=True)
        result = _error_result(request_id, str(exc))
        if log:
            if not started_logged:
                log.append(_error_started_event(request_id, repo_path, review_type, task_id, prompt))
            log.append(_error_event(request_id, repo_path, review_type, task_id, result["response"]))

    await _cleanup_process_groups(process_groups, leaked_pids)
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

@_trace_function
def _error_result(request_id: str, message: str) -> dict:
    return {
        "request_id": request_id,
        "status": "ERROR",
        "verdict": None,
        "response": message,
        "stale": False,
    }

@_trace_function
def _error_started_event(request_id: str, repo_path: str, review_type: str, task_id: str | None, prompt: str) -> dict:
    return {
        "event": "review_started",
        "request_id": request_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repo_path": repo_path,
        "branch": None,
        "head_sha": None,
        "working_tree_dirty": None,
        "review_type": review_type,
        "task_id": task_id,
        "prompt": prompt,
        "error_before_git_capture": True,
    }

@_trace_function
def _error_event(request_id: str, repo_path: str, review_type: str, task_id: str | None, message: str) -> dict:
    return {
        "event": "review_completed",
        "request_id": request_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repo_path": repo_path,
        "review_type": review_type,
        "task_id": task_id,
        "status": "ERROR",
        "verdict": None,
        "response": message,
        "stale": False,
    }

async def main():
    _install_signal_lifecycle_logging()
    logger.debug("=== SDDTDD-MCP SERVER STARTED ===")
    logger.debug("PROCESS: pid=%d, ppid=%d, cwd=%s", os.getpid(), os.getppid(), os.getcwd())

    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.debug("stdio_server: connected, entering app.run()")
            try:
                await app.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="sddtdd-mcp",
                        server_version="1.0.0",
                        capabilities=types.ServerCapabilities(),
                    ),
                )
            except Exception as exc:
                logger.error("SERVE: app.run() raised %s: %s",
                             type(exc).__name__, exc, exc_info=True)
                raise  # still propagate so the process exits
        logger.debug("SERVE: stdio_server context exited (read stream closed by client)")
    except Exception:
        logger.exception("SERVE: main() caught exception in stdio_server block")
        raise

    logger.debug("=== SDDTDD-MCP SERVER EXITING (normal) ===")


if __name__ == "__main__":
    import asyncio
    logger.debug("=== SDDTDD-MCP PROCESS STARTING (__main__) ===")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.debug("=== SDDTDD-MCP PROCESS: KeyboardInterrupt ===")
    except SystemExit:
        logger.debug("=== SDDTDD-MCP PROCESS: SystemExit ===")
    except BaseException:
        logger.exception("=== SDDTDD-MCP PROCESS: UNHANDLED EXCEPTION ===")
    else:
        logger.debug("=== SDDTDD-MCP PROCESS EXITED cleanly ===")
    logger.debug("=== SDDTDD-MCP PROCESS WILL NOW EXIT ===")
