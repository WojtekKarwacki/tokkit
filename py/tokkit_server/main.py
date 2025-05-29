"""MCP server entry point — JSON-RPC over stdio."""

import json
import signal
import sys
from typing import IO

from tokkit_server import __version__
from tokkit_server.protocol import (
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    build_error,
    build_initialize_response,
    build_tools_list_response,
    parse_request,
)
from tokkit_server.tools import handle_tool_call
from tokkit_server.watcher import Watcher


def dispatch(method: str, params: dict, request_id, watcher: Watcher) -> str | None:
    """Dispatch a JSON-RPC method and return a response string or None."""
    if method == "initialize":
        client_info = params.get("clientInfo", {})
        agent_name = client_info.get("name", "unknown")
        from tokkit_server.token_stats import set_session_info  # noqa: PLC0415
        set_session_info(agent_name)
        return build_initialize_response(request_id)

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return build_tools_list_response(request_id)

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        import sys as _sys  # noqa: PLC0415
        print(f"[tokkit] tool_call: {tool_name}", file=_sys.stderr, flush=True)
        result = handle_tool_call(tool_name, tool_args)
        if tool_name == "index_repository" and not result.get("isError"):
            from tokkit_server.tools import _session_project_path  # noqa: PLC0415
            if _session_project_path:
                watcher.set_project(_session_project_path)
        from tokkit_server.protocol import build_response  # noqa: PLC0415
        return build_response(request_id, result)

    return build_error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")


def serve_stdio(stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    """Run the JSON-RPC event loop over stdio."""
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    watcher = Watcher()
    watcher.start()

    shutdown = False

    def _handle_signal(signum, frame):  # noqa: ARG001
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    content_length: int | None = None

    try:
        while not shutdown:
            try:
                line = stdin.readline()
            except (KeyboardInterrupt, EOFError):
                break

            if not line:
                break

            stripped = line.strip()

            if stripped.startswith("Content-Length:"):
                try:
                    content_length = int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    content_length = None
                continue

            if stripped == "" and content_length is not None:
                try:
                    body = stdin.read(content_length)
                except (EOFError, OSError):
                    break
                content_length = None
                stripped = body.strip()
            elif stripped == "":
                continue

            try:
                req = parse_request(stripped)
            except ValueError as exc:
                response = build_error(None, PARSE_ERROR, str(exc))
                stdout.write(response + "\n")
                stdout.flush()
                continue

            try:
                response = dispatch(req["method"] or "", req["params"] or {}, req["id"], watcher)
            except Exception as exc:  # noqa: BLE001
                response = build_error(req.get("id"), INTERNAL_ERROR, str(exc))

            if response is not None:
                stdout.write(response + "\n")
                stdout.flush()
    finally:
        watcher.stop()

    return 0


def main() -> None:
    """Entry point for `python -m tokkit_server.main` (backwards compat)."""
    argv = sys.argv[1:]

    if not argv:
        sys.exit(serve_stdio())

    if argv[0] == "--version":
        print(f"tokkit {__version__}")
        sys.exit(0)

    if argv[0] == "cli":
        if len(argv) < 3:
            print("Usage: tokkit cli <tool_name> <json_args>", file=sys.stderr)
            sys.exit(1)
        tool_name = argv[1]
        try:
            tool_args = json.loads(argv[2])
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON args: {exc}", file=sys.stderr)
            sys.exit(1)
        result = handle_tool_call(tool_name, tool_args)
        for block in result.get("content", []):
            if block.get("type") == "text":
                print(block["text"])
        sys.exit(0 if not result.get("isError") else 1)

    print(f"Unknown argument: {argv[0]}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
