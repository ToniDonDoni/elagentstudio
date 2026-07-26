#!/usr/bin/env python3
"""Smoke-test concise rendering of noisy OMP task tool events."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("render_omp_events.py")


def main() -> int:
    event = {
        "type": "tool_execution_update",
        "toolName": "task",
        "toolCallId": "call-1",
        "args": {
            "context": "# Goal\n" + ("long context " * 200),
            "tasks": [
                {
                    "name": "CreateSPEC",
                    "task": "FULL SECRETLY NOISY TASK PROMPT " + ("details " * 200),
                }
            ],
        },
    }

    completed = subprocess.run(
        [sys.executable, "-u", str(SCRIPT)],
        input=json.dumps(event) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        print(completed.stderr, file=sys.stderr)
        return completed.returncode

    output = completed.stdout
    required = ("tool_execution_update tool=task", "tasks=1", "names=CreateSPEC", "context_chars=")
    for marker in required:
        if marker not in output:
            raise AssertionError(f"missing marker {marker!r} in {output!r}")

    forbidden = ("# Goal", "FULL SECRETLY NOISY TASK PROMPT", "long context")
    for marker in forbidden:
        if marker in output:
            raise AssertionError(f"noisy task content leaked into live output: {marker!r}")

    print("render_omp_events concise task rendering: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
