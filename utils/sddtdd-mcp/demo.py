"""Demo: talk to sddtdd-mcp over stdio.
Shows init, tools/list, and a review call.
"""
import json
import os
import subprocess
import sys
import time
import uuid

PROJECT_ROOT = "/work/sddtdd-mcp"
LOG_PATH = "/tmp/sddtdd-demo-log.jsonl"

env = {**os.environ, "SDDTDD_LOG_PATH": LOG_PATH}

proc = subprocess.Popen(
    ["uv", "run", "server.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, cwd=PROJECT_ROOT,
    text=True, bufsize=1, env=env,
)

def send(obj):
    line = json.dumps(obj, ensure_ascii=False)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    print(f">>> {json.dumps(obj, indent=2)}", file=sys.stderr)

def recv(timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Server died. stderr: {proc.stderr.read()}")
        line = proc.stdout.readline()
        if line:
            data = json.loads(line.strip())
            print(f"<<< {json.dumps(data, indent=2)}", file=sys.stderr)
            return data
        time.sleep(0.05)
    raise TimeoutError(f"No response in {timeout}s")

try:
    # ---- 1. Initialize ----
    print("=" * 60)
    print("1. INITIALIZE")
    print("=" * 60, file=sys.stderr)
    send({"jsonrpc":"2.0","id":"init-1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"sampling":{}},"clientInfo":{"name":"demo","version":"1.0"}}})
    resp = recv()
    send({"jsonrpc":"2.0","method":"notifications/initialized"})

    # ---- 2. List tools ----
    print("=" * 60)
    print("2. TOOLS/LIST")
    print("=" * 60, file=sys.stderr)
    send({"jsonrpc":"2.0","id":"list-1","method":"tools/list"})
    resp = recv()
    tools = resp.get("result", {}).get("tools", [])
    print(f"\n→ Server has {len(tools)} tool(s):", file=sys.stderr)
    for t in tools:
        print(f"   • {t['name']}: {t['description']}", file=sys.stderr)
        print(f"     schema: {json.dumps(t.get('inputSchema', {}), indent=6)}", file=sys.stderr)

    # ---- 3. Call review ----
    print("=" * 60)
    print("3. TOOLS/CALL — review")
    print("=" * 60, file=sys.stderr)

    review_prompt = "PASS: Review the sddtdd-mcp project. Verify that it captures git state, uses MCP sampling, and writes a JSON Lines access log. PASS if all requirements are met."

    send({"jsonrpc":"2.0","id":"review-1","method":"tools/call","params":{"name":"review","arguments":{"repo_path":PROJECT_ROOT,"review_type":"architecture review","task_id":"DEMO-001","prompt":review_prompt}}})

    # Handle sampling/createMessage from server
    while True:
        msg = recv(timeout=60)
        if msg.get("method") == "sampling/createMessage":
            # Respond with mock PASS
            send({"jsonrpc":"2.0","id":msg["id"],"result":{"role":"assistant","content":{"type":"text","text":"PASS: The sddtdd-mcp project correctly implements all requirements: it captures git state, delegates to MCP sampling, and writes JSON Lines access log entries."},"model":"test-model","stopReason":"endTurn"}})
        elif msg.get("id") == "review-1":
            # This is the review response
            content = msg.get("result", {}).get("content", [])
            result = json.loads(content[0]["text"]) if content else {}
            print(f"\n→ REVIEW RESULT:", file=sys.stderr)
            print(f"  request_id: {result.get('request_id')}", file=sys.stderr)
            print(f"  status:     {result.get('status')}", file=sys.stderr)
            print(f"  verdict:    {result.get('verdict')}", file=sys.stderr)
            print(f"  stale:      {result.get('stale')}", file=sys.stderr)
            print(f"  response:   {result.get('response')[:80]}...", file=sys.stderr)
            break

    # ---- 4. Show log file ----
    print("=" * 60)
    print("4. ACCESS LOG")
    print("=" * 60, file=sys.stderr)
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            content = f.read()
            print(f"\nLog file: {LOG_PATH}", file=sys.stderr)
            print(f"Size: {len(content)} bytes, {content.count(chr(10))+1} lines", file=sys.stderr)
            print(f"\nContent:", file=sys.stderr)
            for i, line in enumerate(content.strip().split("\n"), 1):
                event = json.loads(line)
                event_type = event.get("event", "?")
                rid = event.get("request_id", "?")[:12]
                fields = {k: v for k, v in event.items() if k not in ("event", "request_id", "timestamp_utc", "prompt")}
                print(f"  [{i}] {event_type} | {rid} | {json.dumps(fields)}", file=sys.stderr)

except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    if proc.poll() is not None:
        print(f"Server stderr:\n{proc.stderr.read()}", file=sys.stderr)
finally:
    proc.stdin.close()
    proc.wait(timeout=5)
    print("\nDone.", file=sys.stderr)
