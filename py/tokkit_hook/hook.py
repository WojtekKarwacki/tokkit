"""PreToolUse hook — intercept Bash tool calls and compress output."""

from __future__ import annotations

import json
import shlex
import sys

from tokkit_hook.chain import split_chain, find_primary
from tokkit_hook.match import match_command


def handle_hook_request(request: dict) -> dict:
    """Process a PreToolUse hook request.

    Input: {"tool_name": "Bash", "tool_input": {"command": "..."}}
    Output: {"decision": "allow"} or {"decision": "allow", "params": {"command": "tokkit compress '...'"}}
    """
    tool_name = request.get("tool_name", "")

    if tool_name != "Bash":
        return {"decision": "allow"}

    tool_input = request.get("tool_input", {})
    original_command = tool_input.get("command", "")

    if not original_command:
        return {"decision": "allow"}

    commands = split_chain(original_command)
    if not commands:
        return {"decision": "allow"}

    primary = find_primary(commands)
    hint = match_command(primary)

    if hint is None:
        return {"decision": "allow"}

    # Wrap entire original command in tokkit compress
    escaped = original_command.replace("'", "'\\''")
    wrapped = f"tokkit compress '{escaped}'"

    return {
        "decision": "allow",
        "params": {"command": wrapped},
    }


def main() -> None:
    """Read JSON from stdin, process hook, write JSON to stdout. Fail open on errors."""
    try:
        raw = sys.stdin.read()
        request = json.loads(raw)
        response = handle_hook_request(request)
    except Exception:
        response = {"decision": "allow"}

    print(json.dumps(response))


if __name__ == "__main__":
    main()
