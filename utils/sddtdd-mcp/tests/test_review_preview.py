"""
End-to-end test: invoke the reviewer MCP server with the sampling tools
capability advertised, but intercept the sampling/createMessage request
and have a "virtual LLM" actually call read_file and shell_command against
the real repository. This proves that the reviewer MCP can:

  1. Receive a review prompt from the user
  2. Pass tools=[read_file, shell_command] to create_message
  3. Receive a toolUse response from the sampled LLM
  4. Execute the tool against the real repo
  5. Send the result back to the LLM
  6. Receive a final text verdict

This is the full tool-use loop integration test.

The "virtual LLM" behavior:
  - First call: returns toolUse for shell_command "git log --oneline -3"
  - Second call: returns toolUse for shell_command "git show HEAD"
  - Third call: returns text "PASS: Inspected commit 7299d07..."

We then verify:
  - The server wrote the right events to the access log
  - The verdict in the response is PASS
  - The tool execution actually returned commit data
"""

import json
import os
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
REPO_PATH = "/work/elagentstudio"

# Where the server should write the access log
LOG_PATH = "/tmp/review_preview_test.jsonl"

# Clean previous log
if os.path.exists(LOG_PATH):
    os.remove(LOG_PATH)


class VirtualLLM:
    """Simulated sampled LLM. Knows the right tool calls to make, in order."""

    def __init__(self):
        self.round = 0
        self.tool_calls_made = []  # list of (name, args) seen by the server
        self.tool_results_seen = []  # list of result strings the LLM "received"

    def next_response(self, params):
        """Return the next MCP sampling response based on round."""
        self.round += 1

        if self.round == 1:
            # Round 1: ask to run git log
            return self._tool_use("shell_command", {"command": "git log --oneline -3"})
        if self.round == 2:
            # Round 2: ask to run git show HEAD
            return self._tool_use("shell_command", {"command": "git show HEAD"})
        if self.round == 3:
            # Round 3: final text verdict
            return self._text(
                "PASS: I was able to inspect the most recent commit using the "
                "shell_command tool. The commit 7299d07 modifies utils/sddtdd-mcp/server.py "
                "and adds 11 unit tests for the new tool executors. The change is safe to merge."
            )
        return self._text("PASS: done.")

    def _tool_use(self, name, args):
        # Record what we (the LLM) asked for
        self.tool_calls_made.append((name, args))
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": f"tool_{self.round}",
                        "name": name,
                        "input": args,
                    }
                ],
                "model": "virtual-llm",
                "stopReason": "toolUse",
            },
        }

    def _text(self, text):
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "result": {
                "role": "assistant",
                "content": {"type": "text", "text": text},
                "model": "virtual-llm",
                "stopReason": "endTurn",
            },
        }


def main():
    env = {**os.environ, "SDDTDD_LOG_PATH": LOG_PATH}
    proc = subprocess.Popen(
        ["uv", "run", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT,
        text=True, bufsize=1,
        env=env,
    )

    llm = VirtualLLM()
    pending = {}  # id -> request method
    buf = ""

    def send(obj):
        line = json.dumps(obj) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

    def recv_one():
        nonlocal buf
        while "\n" not in buf:
            chunk = proc.stdout.read(1)
            if not chunk:
                stderr = proc.stderr.read()
                raise RuntimeError(f"server closed; stderr:\n{stderr}")
            buf += chunk
        line, _, buf = buf.partition("\n")
        return json.loads(line)

    # Initialize MCP session — must advertise sampling.tools capability
    init_resp = send({
        "jsonrpc": "2.0",
        "id": "init",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"sampling": {"tools": {}}},
            "clientInfo": {"name": "preview-test", "version": "1.0"},
        },
    })
    init_msg = recv_one()
    assert "result" in init_msg, f"init failed: {init_msg}"

    send({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    })

    # Call the review tool
    review_call_id = "review-1"
    send({
        "jsonrpc": "2.0",
        "id": review_call_id,
        "method": "tools/call",
        "params": {
            "name": "review",
            "arguments": {
                "repo_path": REPO_PATH,
                "review_type": "preview recent commits",
                "task_id": "preview-todo4-1",
                "prompt": (
                    "Please preview the most recent commit on this repository. "
                    "Use shell_command to run 'git show HEAD' so you can see the "
                    "actual commit content."
                ),
            },
        },
    })

    # Now process server requests and respond. The server will:
    #   1. Send sampling/createMessage (round 1) — we reply with tool_use shell_command git log
    #   2. The server executes the tool, then sends sampling/createMessage (round 2) — we reply with tool_use shell_command git show
    #   3. The server executes, sends sampling/createMessage (round 3) — we reply with text PASS
    #   4. The server finalizes the review and returns the tools/call response
    final_response = None
    deadline = time.time() + 30
    while time.time() < deadline:
        msg = recv_one()
        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "sampling/createMessage":
            # The server is asking the LLM to respond. Get tool results from
            # the previous round by inspecting params.
            params = msg.get("params", {})
            messages = params.get("messages", [])
            # Find any tool_result blocks in user messages — those are the
            # results the LLM "sees" from prior tool executions
            for m in messages:
                content = m.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            llm.tool_results_seen.append(block.get("content", [{}])[0].get("text", "")[:200])

            # Generate the next response
            response = llm.next_response(params)
            response["id"] = msg_id
            send(response)
        elif msg.get("id") == review_call_id:
            final_response = msg
            break
        else:
            # Unknown — send error
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"unknown: {method}"},
            })

    # Cleanup
    proc.stdin.close()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    # ── Assertions ──
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # 1. Final response
    assert final_response is not None, "no final response from server"
    assert "result" in final_response, f"final response error: {final_response}"
    content = final_response["result"]["content"]
    result_obj = json.loads(content[0]["text"])
    print(f"  Status:   {result_obj['status']}")
    print(f"  Verdict:  {result_obj['verdict']}")
    print(f"  Stale:    {result_obj['stale']}")
    print(f"  Response: {result_obj['response'][:120]}...")
    assert result_obj["status"] == "COMPLETED", f"expected COMPLETED, got {result_obj['status']}"
    assert result_obj["verdict"] == "PASS", f"expected PASS, got {result_obj['verdict']}"
    assert result_obj["stale"] is False

    # 2. LLM made the expected tool calls
    print(f"\n  LLM tool calls made: {len(llm.tool_calls_made)}")
    for name, args in llm.tool_calls_made:
        print(f"    - {name}({args})")
    assert len(llm.tool_calls_made) == 2, f"expected 2 tool calls, got {len(llm.tool_calls_made)}"
    assert llm.tool_calls_made[0][0] == "shell_command"
    assert "git log" in llm.tool_calls_made[0][1]["command"]
    assert llm.tool_calls_made[1][0] == "shell_command"
    assert "git show" in llm.tool_calls_made[1][1]["command"]

    # 3. LLM saw the tool results. Note: each tool_use round sends a user
    # message containing 1 tool_result. We may see 1 result in round 2's
    # params (from round 1) and 1 result in round 3's params (from round 2).
    # Round 1's params contain only the initial user prompt. So we expect
    # at least 1 result, and the last result must be the git show output.
    print(f"\n  LLM tool results seen: {len(llm.tool_results_seen)}")
    for r in llm.tool_results_seen:
        print(f"    - {r[:80]}...")
    assert len(llm.tool_results_seen) >= 1, "LLM never saw a tool result"
    # Last result should be the git show of HEAD — must mention the commit
    last_result = llm.tool_results_seen[-1]
    assert "7299d07" in last_result or "TODO4" in last_result or "reviewer MCP" in last_result, (
        f"expected last result to be git show of HEAD, got: {last_result[:300]}"
    )

    # 4. Access log
    print(f"\n  Access log: {LOG_PATH}")
    with open(LOG_PATH) as f:
        lines = f.readlines()
    events = [json.loads(l) for l in lines]
    started = [e for e in events if e["event"] == "review_started"]
    completed = [e for e in events if e["event"] == "review_completed"]
    assert len(started) == 1, f"expected 1 review_started, got {len(started)}"
    assert len(completed) == 1, f"expected 1 review_completed, got {len(completed)}"
    c = completed[0]
    print(f"  Log verdict: {c['verdict']}, status: {c['status']}, duration: {c['duration_ms']}ms")
    assert c["verdict"] == "PASS"
    assert c["status"] == "COMPLETED"
    # The started event's prompt should contain the tools the LLM used? No, the
    # prompt is the original user prompt. The tools are in the sampling request,
    # which we don't log. That's fine.

    print("\n" + "=" * 70)
    print("✓ ALL ASSERTIONS PASS — reviewer MCP with tools WORKS end-to-end")
    print("=" * 70)


if __name__ == "__main__":
    main()
