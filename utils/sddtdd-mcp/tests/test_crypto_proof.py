"""
Cryptographic proof: verify that the reviewer MCP's read_file tool actually
reads real file contents from disk.

Procedure:
  1. Create a file with a random secret word inside the repo
  2. Ask the reviewer to read it via the review tool
  3. Virtual LLM responds with tool_use for read_file on that path
  4. Server executes read_file — returns the secret word
  5. Virtual LLM reads the result and responds with "PASS: <secret word>"
  6. Test verifies the word in the response matches the original

If the read_file tool was stubbed or faked (returning empty/static content),
the secret word wouldn't match — the test would fail.
"""

import json
import os
import secrets
import string
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
REPO_PATH = "/work/elagentstudio"
LOG_PATH = "/tmp/crypto_proof_test.jsonl"

# ── Generate the secret ──────────────────────────────────────────────
# Random alphanumeric token unique to this run
SECRET_WORD = "crypto_" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))
SECRET_FILE = os.path.join(REPO_PATH, f".crypto_proof_{uuid.uuid4().hex[:8]}.txt")


def main():
    # Clean previous log
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)

    # ── Step 1: Create a file with the secret word ─────────────────
    print(f"  Secret word:  {SECRET_WORD}")
    print(f"  Secret file:  {SECRET_FILE}")
    with open(SECRET_FILE, "w") as f:
        f.write(SECRET_WORD + "\n")
    print(f"  File written ✓")

    # ── Step 2: Simulated LLM ──────────────────────────────────────
    class VirtualLLM:
        def __init__(self):
            self.round = 0
            self.tool_calls_made = []
            self.tool_results_seen = []
            self.secret_word = None  # captured from tool result

        def next_response(self, params):
            self.round += 1

            if self.round == 1:
                # Round 1: ask to read the secret file
                return self._tool_use("read_file", {"path": SECRET_FILE})
            if self.round == 2:
                # Round 2: should have received the secret word as tool_result
                # Return it as the verdict
                word = self.secret_word or "UNKNOWN"
                return self._text(
                    f"PASS: I read the file and the secret word is '{word}'."
                )
            return self._text("PASS: done.")

        def _tool_use(self, name, args):
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

    llm = VirtualLLM()

    # ── Step 3: Launch the server ──────────────────────────────────
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

    def send(obj):
        line = json.dumps(obj) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

    def recv_one():
        buf = ""
        while "\n" not in buf:
            chunk = proc.stdout.read(1)
            if not chunk:
                stderr = proc.stderr.read()
                raise RuntimeError(f"server closed; stderr:\n{stderr}")
            buf += chunk
        line, _, buf = buf.partition("\n")
        return json.loads(line)

    try:
        # ── Step 4: Initialize MCP session ─────────────────────────
        send({
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"sampling": {"tools": {}}},
                "clientInfo": {"name": "crypto-proof-test", "version": "1.0"},
            },
        })
        init_msg = recv_one()
        assert "result" in init_msg, f"init failed: {init_msg}"

        send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

        # ── Step 5: Call the review tool ───────────────────────────
        review_call_id = "crypto-proof-1"
        send({
            "jsonrpc": "2.0",
            "id": review_call_id,
            "method": "tools/call",
            "params": {
                "name": "review",
                "arguments": {
                    "repo_path": REPO_PATH,
                    "review_type": "crypto proof: read secret file",
                    "task_id": "crypto-proof-1",
                    "prompt": (
                        "Please read the file at the following path and tell me "
                        "the exact secret word it contains. "
                        f"Use read_file with path '{SECRET_FILE}'."
                    ),
                },
            },
        })

        # ── Step 6: Drive the sampling loop ────────────────────────
        final_response = None
        deadline = time.time() + 30
        while time.time() < deadline:
            msg = recv_one()
            method = msg.get("method")
            msg_id = msg.get("id")

            if method == "sampling/createMessage":
                params = msg.get("params", {})
                messages = params.get("messages", [])

                # Extract tool results from prior round
                for m in messages:
                    content = m.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                result_text = block.get("content", [{}])[0].get("text", "")
                                llm.tool_results_seen.append(result_text[:200])
                                # Capture the secret word from the file contents
                                # The file contains our secret word — clean it up
                                llm.secret_word = result_text.strip()

                # Generate next response
                response = llm.next_response(params)
                response["id"] = msg_id
                send(response)

            elif msg.get("id") == review_call_id:
                final_response = msg
                break
            else:
                send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"unknown: {method}"},
                })

        # ── Step 7: Verify ─────────────────────────────────────────
        print("\n" + "=" * 70)
        print("CRYPTO PROOF RESULTS")
        print("=" * 70)

        # 7a: Final response
        assert final_response is not None, "no final response from server"
        assert "result" in final_response, f"final response error: {final_response}"
        content = final_response["result"]["content"]
        result_obj = json.loads(content[0]["text"])
        print(f"  Status:   {result_obj['status']}")
        print(f"  Verdict:  {result_obj['verdict']}")
        print(f"  Response: {result_obj['response'][:200]}")
        assert result_obj["status"] == "COMPLETED", f"expected COMPLETED, got {result_obj['status']}"

        # 7b: LLM made the right tool call(s)
        print(f"\n  LLM tool calls: {len(llm.tool_calls_made)}")
        for name, args in llm.tool_calls_made:
            print(f"    - {name}({args})")
        assert len(llm.tool_calls_made) >= 1, "LLM never called a tool"
        assert llm.tool_calls_made[0][0] == "read_file", f"expected read_file, got {llm.tool_calls_made[0][0]}"
        assert SECRET_FILE in str(llm.tool_calls_made[0][1]), f"expected path {SECRET_FILE}"

        # 7c: LLM saw the tool result
        print(f"\n  Tool results seen: {len(llm.tool_results_seen)}")
        for r in llm.tool_results_seen:
            print(f"    - {r[:100]}")
        assert len(llm.tool_results_seen) >= 1, "LLM never saw a tool result"

        # 7d: ⭐ CRYPTOGRAPHIC PROOF — the LLM read the actual file
        print(f"\n  ═══════════════════════════════════════════════")
        print(f"  Expected secret: {SECRET_WORD}")
        print(f"  LLM got secret:  {llm.secret_word}")
        print(f"  ═══════════════════════════════════════════════")
        assert llm.secret_word is not None, "LLM never received the secret word"
        # Strip whitespace — file has \n
        assert SECRET_WORD == llm.secret_word.strip(), (
            f"SECRET MISMATCH!\n"
            f"  Created: '{SECRET_WORD}'\n"
            f"  Read:    '{llm.secret_word.strip()}'\n"
            f"The read_file tool did NOT return the actual file contents!"
        )
        print(f"  ✓ SECRET MATCH — read_file returned real file contents")

        # 7e: Verdict should be PASS (the LLM returned PASS in its text)
        print(f"\n  Verdict from server: {result_obj['verdict']}")
        assert result_obj["verdict"] == "PASS", f"expected PASS, got {result_obj['verdict']}"

        # 7f: Access log
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

        print("\n" + "=" * 70)
        print("✓ CRYPTOGRAPHIC PROOF PASSED — read_file works end-to-end")
        print("=" * 70)

    finally:
        # Cleanup
        proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if os.path.exists(SECRET_FILE):
            os.remove(SECRET_FILE)


if __name__ == "__main__":
    main()
