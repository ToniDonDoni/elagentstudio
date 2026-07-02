"""sddtdd-mcp — Minimal MCP review proxy for Hermes Agent.

Single tool: review. Captures Git state, delegates to LLM via MCP sampling,
records everything in an append-only JSON Lines access log.
"""
import json
import logging
import os
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mcp.server as mcp_server
import mcp.types as types
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# Logger for our own lifecycle tracing (goes to stderr → mcp-stderr.log)
logger = logging.getLogger("sddtdd-mcp")

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

MAX_SAMPLING_ROUNDS = int(os.environ.get("SDDTDD_REVIEW_MAX_SAMPLING_ROUNDS", "5555"))
MAX_SAMPLING_TOKENS = int(os.environ.get("SDDTDD_REVIEW_MAX_SAMPLING_TOKENS", "128000"))
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

    policy_bundle = {
        "SKILL.md": _read_text_if_exists(paths["skill"]),
        "SKILL-IMPLEMENTER.md": _read_text_if_exists(paths["implementer"]),
        "references/STAGES.md": _read_text_if_exists(paths["stages"]),
        "references/JOURNAL.md": _read_text_if_exists(paths["journal"]),
    }

    response_schema_json = _review_response_schema_json()

    system_prompt = f"""You are the independent Spec-Driven TDD reviewer MCP for a target repository.

You are NOT the implementer. You are NOT the broker/orchestrator. You are a read-only independent reviewer.

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
6. If a required committed artifact, journal entry, evidence file, or parent context is missing and you cannot review honestly, return FAIL or NEEDS_CLARIFICATION. Do not guess.

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
- FAIL if required tests were silently omitted.

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
  - State the next workflow meaning, e.g. for RED_REVIEW PASS: "RED is valid; failing tests are expected evidence; record the review and continue to the broker/process gate before GREEN."
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

===== BEGIN SKILL.md =====
{policy_bundle["SKILL.md"]}
===== END SKILL.md =====

===== BEGIN SKILL-IMPLEMENTER.md =====
{policy_bundle["SKILL-IMPLEMENTER.md"]}
===== END SKILL-IMPLEMENTER.md =====

===== BEGIN references/STAGES.md =====
{policy_bundle["references/STAGES.md"]}
===== END references/STAGES.md =====

===== BEGIN references/JOURNAL.md =====
{policy_bundle["references/JOURNAL.md"]}
===== END references/JOURNAL.md =====
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
        )
    ]


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

def _cleanup_process_groups(process_groups: list[int], leaked_pids: list[int]) -> None:
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

    time.sleep(1)

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


def _execute_tool(
    name: str,
    args: dict,
    repo_path: str,
    process_groups: list[int],
    leaked_pids: list[int],
) -> str:
    """Execute a reviewer tool call. Returns the text result."""
    if name == "shell_command":
        cmd = str(args.get("command", "")).strip()
        if not cmd:
            return "ERROR: empty command"
        # Run from repo root in a new process session so timeout can terminate
        # the whole command tree, not just the intermediate shell. This protects
        # against commands such as `npm run dev`, `vite preview`, watch-mode test
        # runners, or e2e harnesses that spawn child processes and keep running.
        # On timeout, send SIGTERM to the process group first, then SIGKILL if
        # children do not exit promptly.
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            process_groups.append(process.pid)
            try:
                stdout, stderr = process.communicate(timeout=MAX_SHELL_COMMAND_SECONDS)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                out = (stdout or "") + (stderr or "")
                timeout_notice = (
                    f"\n\n[TOOL_COMMAND_TIMED_OUT]\n"
                    f"Timeout seconds: {MAX_SHELL_COMMAND_SECONDS}\n"
                    "The command exceeded the shell command timeout and its process group was terminated."
                )
                out = out + timeout_notice
            else:
                out = (stdout or "") + (stderr or "")

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

            # Minimal process-leak warning for shell_command tool result
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
                out = (out or f"(no output, exit={process.returncode})") + warning

            return out if out else f"(no output, exit={process.returncode})"
        except Exception as exc:
            return f"ERROR: {exc}"

    return f"ERROR: unknown tool: {name}"


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
                _safe_log_text(json.dumps(result_dump, ensure_ascii=False, default=str), limit=2000),
            )
            logger.warning(
                "REVIEW_RESPONSE_REPAIR_EMPTY_OUTPUT: attempt=%d/%d stop_reason=%s preserving_original_len=%d and returning retry response",
                attempt,
                max_attempts,
                stop_reason,
                len(original_response),
            )
            return None, REVIEW_RETRY_RESPONSE, attempts

        verdict, response, error = _parse_review_json(repair_text.strip())
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

        if error is None:
            return verdict, response, attempts

        if repair_text.strip():
            current_response = repair_text
        else:
            current_response = original_response
        current_error = error

    return None, raw_response, attempts



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
                            "Your previous response hit the max token limit before producing a usable final review. "
                            "Continue from where you stopped. Do not restart the review from scratch. "
                            "If you have enough evidence to conclude, produce the final review and start the response "
                            "with a JSON object matching the required review response schema. "
                            "If the verdict is FAIL or NEEDS_CLARIFICATION, include concise actionable explanation in the response field."
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
            output = _execute_tool(tu.name, tool_args, repo_path, process_groups, leaked_pids)
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


@app.call_tool()
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
    try:
        # 1-2: Capture Git state before + open log
        git = GitCapturer(repo_path)
        branch = git.branch()
        head_before = git.head_sha()
        dirty = git.is_dirty()

        log_path = _get_log_path(repo_path)
        log = LogWriter(log_path)

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
            "reviewer_skill_paths": {k: str(v) for k, v in _review_skill_paths().items()},
        }
        log.append(started_event)
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
            log.append(_error_event(request_id, repo_path, review_type, task_id, result["response"]))
    except Exception as exc:
        logger.error("call_tool: EXCEPTION (%s) — %s", type(exc).__name__, exc, exc_info=True)
        result = _error_result(request_id, str(exc))
        if log:
            log.append(_error_event(request_id, repo_path, review_type, task_id, result["response"]))

    _cleanup_process_groups(process_groups, leaked_pids)
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


def _error_result(request_id: str, message: str) -> dict:
    return {
        "request_id": request_id,
        "status": "ERROR",
        "verdict": None,
        "response": message,
        "stale": False,
    }


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
    logger.debug("=== SDDTDD-MCP SERVER STARTED ===")
    logger.debug("PROCESS: pid=%d, cwd=%s", os.getpid(), os.getcwd())

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
