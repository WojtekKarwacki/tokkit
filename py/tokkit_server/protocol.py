"""JSON-RPC 2.0 protocol helpers for the MCP server."""
import json

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

TOOL_DEFINITIONS = [
    {
        "name": "index_repository",
        "description": (
            "Index a repository to build a code intelligence graph. "
            "MUST be called once before using get_architecture, find_dead_code, find_routes, or trace_fan. "
            "Parses Python, JavaScript, and TypeScript files. Takes 1-5 seconds."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the repository root."},
                "force": {"type": "boolean", "description": "Force re-indexing even if already indexed."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_architecture",
        "description": (
            "Get a project overview: languages, packages, key files, entry points — in one call. "
            "Use INSTEAD OF Glob + multiple Read calls to understand a codebase. "
            "Requires index_repository first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "find_dead_code",
        "description": (
            "Find functions with zero references — dead code detection in one call. "
            "Use INSTEAD OF manually grepping definitions then cross-referencing calls "
            "(would require O(N^2) grep calls). Requires index_repository first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum results (default: 200)."},
            },
        },
    },
    {
        "name": "find_routes",
        "description": (
            "Find all HTTP route handlers with method, path, and function name — in one call. "
            "Use INSTEAD OF grepping for route decorators. Detects FastAPI, Flask, Express, "
            "Next.js, and more. Requires index_repository first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum results (default: 200)."},
            },
        },
    },
    {
        "name": "trace_fan",
        "description": (
            "Trace what a function calls (fan-out) or what calls it (fan-in) through the call graph. "
            "Use INSTEAD OF recursive grep+read to follow call chains — "
            "one call replaces 10-20 grep+read iterations. "
            "Accepts plain function names. Requires index_repository first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string", "description": "Function name or qualified name to trace from."},
                "direction": {
                    "type": "string",
                    "enum": ["outbound", "inbound"],
                    "description": "Trace direction. 'outbound': what this function calls. 'inbound': who calls this function.",
                },
                "depth": {"type": "integer", "description": "Maximum hop depth (default: 3)."},
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "clean_html",
        "description": (
            "Convert HTML to clean markdown or text. "
            "Use INSTEAD OF Read for any .html file — reads the file server-side via path= "
            "so raw HTML never enters your context. "
            "Removes scripts, styles, nav, ads. Saves 60-90% tokens."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the HTML file to clean (preferred — file is read server-side)."},
                "html": {"type": "string", "description": "Raw HTML content to clean (use path instead when possible to avoid loading HTML into context)."},
                "mode": {
                    "type": "string",
                    "enum": ["markdown", "text", "minimal"],
                    "description": "Output mode. 'markdown' (default): semantic markdown. 'text': plain text. 'minimal': light clean, keep HTML.",
                },
            },
        },
    },
    {
        "name": "compact_json",
        "description": (
            "Convert JSON to compact CSV or YAML. "
            "Use INSTEAD OF Read for any .json file — reads the file server-side via path= "
            "so raw JSON never enters your context. "
            "CSV for flat data (50-70% savings), YAML for nested (20-30% savings)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the JSON file to compact (preferred — file is read server-side)."},
                "json": {"type": "string", "description": "Raw JSON string to compact (use path instead when possible to avoid loading JSON into context)."},
            },
        },
    },
    {
        "name": "search_markdown",
        "description": (
            "Search markdown for relevant sections by keyword. "
            "Use INSTEAD OF Read for .md files when you need specific info — "
            "reads the file server-side via path= and returns only matching sections. "
            "Saves 70-85% tokens vs reading the full document."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the markdown file to search (read server-side)."},
                "query": {"type": "string", "description": "Search keywords. Empty string returns header tree only."},
            },
            "required": ["path", "query"],
        },
    },
    {
        "name": "compact_output",
        "description": (
            "Compress shell output saved to a file. "
            "For LIVE shell commands, the PreToolUse hook handles compression automatically — "
            "use this tool only for output already saved to disk via path=. "
            "Supports: pytest, ruff, eslint, mypy, jest, tsc, cargo, docker, kubectl, "
            "git (diff/status/log/show/blame/branch/stash), pip list, npm ls, "
            "grep/rg, gh cli, env, tree, find, ls. "
            "Lint output is grouped by rule for 70-85% savings."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to file containing command output (preferred — read server-side)."},
                "text": {"type": "string", "description": "Raw command output to compress (use path instead when possible)."},
                "hint": {"type": "string", "description": "Tool hint: pytest, unittest, ruff, mypy, pyright, pip, traceback, jest, vitest, mocha, eslint, tsc, webpack, vite, npm, cargo-test, cargo-build, cargo-clippy, docker, docker-compose, docker-ps, docker-images, docker-logs, kubectl, git-diff, git-status, git-log, git-show, git-blame, git-branch, git-stash, pip-list, pip-freeze, npm-ls, grep, rg, ag, ls, tree, find, gh, env. Omit for auto-detection."},
                "verbose": {"type": "boolean", "description": "Include all items, not just problems. Default: false."},
            },
        },
    },
]


def parse_request(line: str) -> dict:
    """Parse a JSON-RPC 2.0 request line."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Request must be a JSON object")
    return {
        "id": data.get("id"),
        "method": data.get("method"),
        "params": data.get("params", {}),
    }


def build_response(request_id, result) -> str:
    """Build a JSON-RPC 2.0 success response."""
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})


def build_error(request_id, code: int, message: str, data=None) -> str:
    """Build a JSON-RPC 2.0 error response."""
    error: dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error})


def build_initialize_response(request_id) -> str:
    """Build the MCP initialize response."""
    return build_response(
        request_id,
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "tokkit", "version": "0.1.20"},
        },
    )


def build_tools_list_response(request_id) -> str:
    """Build the MCP tools/list response."""
    return build_response(request_id, {"tools": TOOL_DEFINITIONS})
