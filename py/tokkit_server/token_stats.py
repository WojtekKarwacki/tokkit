"""Token savings estimation and tracking.

Methodology
-----------
- "Content tokens" = len(result_text.encode("utf-8")) / CHARS_PER_TOKEN.  This
  is the payload that enters the agent's context window from a single tool call.

- "Baseline tokens" = estimated content tokens a skilled Claude Code agent
  would consume for the same task using standard tools (Grep, Read, Glob).
  Baselines model OPTIMISTIC agent behavior: content-mode grep with context,
  targeted reads with offset/limit, word-boundary matching, head_limit=250.

- Agent infrastructure overhead (system prompt, tool definitions, conversation
  history) is NOT included.  For Claude Code this is estimated at ~27K tokens
  per turn (inferred from minimum observed session totals, not directly
  measured).  Other agents (Cursor, Windsurf, Copilot, etc.) will differ.
  This overhead is paid regardless of whether tokkit is used.

- Both sides use the same chars-per-token constant, so savings percentages
  reflect real content compression ratios.
"""

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

try:
    import fcntl  # POSIX-only; used for cross-process stats locking
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

CHARS_PER_TOKEN = 4  # rough estimate for code

# Identity for queries recorded by the Bash compression hook (`tokkit compress`).
# Each hook invocation is a separate short-lived process, so they share one
# stable chat id rather than minting a per-process uuid (which would explode
# the chats map). Agent name distinguishes them from MCP-client sessions.
_HOOK_CHAT_ID = "bash-hook"
_HOOK_AGENT = "hook"
_STATS_FORMAT_VERSION = 4

# ---------------------------------------------------------------------------
# Session identity — one chat_id per MCP server process
# ---------------------------------------------------------------------------
_chat_id: str = uuid.uuid4().hex[:12]
_agent: str = "unknown"
_session_start: str = datetime.now(timezone.utc).isoformat(timespec="seconds")


def set_session_info(agent: str, chat_id: str | None = None) -> None:
    """Set the agent name (from MCP clientInfo) and optionally override chat_id."""
    global _agent, _chat_id
    _agent = agent
    if chat_id:
        _chat_id = chat_id


def get_session_info() -> dict:
    """Return current session identity."""
    return {"chat_id": _chat_id, "agent": _agent, "started_at": _session_start}

_lock = Lock()

# ---------------------------------------------------------------------------
# Constants matching real Claude Code tool behavior
# ---------------------------------------------------------------------------
_GREP_HEAD_LIMIT = 250       # default head_limit on Grep results
_GREP_CONTEXT_LINES = 7      # match line + 3 before + 3 after (-C=3)
_AVG_LINE_CHARS = 80          # average source line length
_CAT_N_PREFIX = 8             # "  123\t" line-number prefix added by Read
_FUNCTION_READ_LINES = 50     # lines per targeted function read
_DEFS_PER_FILE = 8            # average function definitions per source file
_CHECKABLE_FRACTION = 0.6     # fraction of defs worth reference-checking
_BYTES_PER_REF_CHECK = 500    # average grep -rl -w output per function

# Context overhead model (measured from benchmark, 2026-04-10)
_OVERHEAD_PER_TURN = 23_350    # system prompt + tool defs per API turn
_CALLS_PER_TURN = 4            # average tool calls batched per API turn


def show_savings() -> bool:
    """Check if inline savings display is enabled via TOKKIT_SHOW_SAVINGS=1."""
    return os.environ.get("TOKKIT_SHOW_SAVINGS") == "1"


def _data_dir() -> str:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        base = os.path.join(xdg, "tokkit")
    else:
        base = os.path.join(Path.home(), ".local", "share", "tokkit")
    os.makedirs(base, exist_ok=True)
    return base


def _stats_path() -> str:
    return os.path.join(_data_dir(), "stats.json")


def _empty_stats() -> dict:
    return {
        "format_version": _STATS_FORMAT_VERSION,
        "total_queries": 0,
        "total_content_tokens": 0,
        "total_baseline_tokens": 0,
        "total_content_saved": 0,
        "total_baseline_calls": 0,
        "calls_saved": 0,
        "by_tool": {},
        "chats": {},
        "sessions": [],
    }


def _load_stats() -> dict:
    path = _stats_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            if data.get("format_version") == _STATS_FORMAT_VERSION:
                return data
            # Migrate v3 → v4: add chats dict
            if data.get("format_version") == 3:
                data["format_version"] = _STATS_FORMAT_VERSION
                data.setdefault("chats", {})
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return _empty_stats()


def _save_stats(stats: dict) -> None:
    # Atomic write: a concurrent reader/writer never sees a half-written file.
    path = _stats_path()
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(stats, f, indent=2)
    os.replace(tmp, path)


@contextmanager
def _interprocess_lock():
    """Serialize read-modify-write of stats.json across processes.

    The Bash hook records from many short-lived `tokkit compress` processes that
    may run concurrently; the threading lock alone does not protect across
    processes. Falls back to a no-op where fcntl is unavailable.
    """
    if fcntl is None:
        yield
        return
    lock_path = os.path.join(_data_dir(), "stats.lock")
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Baseline estimation — what a skilled Claude Code agent would consume
# ---------------------------------------------------------------------------

def estimate_baseline_content_tokens(
    tool_name: str, args: dict, result_text: str,
    session_project_path: str | None, raw_size: int | None = None,
) -> int:
    """Estimate content tokens a skilled Claude Code agent would consume.

    Models optimistic agent behavior: Grep(content mode, -C=3),
    Read(offset/limit=50), word-boundary matching, head_limit=250.
    Returns content tokens only — excludes agent infrastructure overhead.
    """
    # --- Transformation tools: baseline = raw input size ---
    if tool_name in ("clean_html", "compact_json", "search_markdown", "compact_output"):
        if raw_size:
            return raw_size // CHARS_PER_TOKEN
        return len(result_text) * 2 // CHARS_PER_TOKEN

    if not session_project_path:
        return 0

    if tool_name == "index_repository":
        return 0

    if tool_name in ("find_dead_code", "find_routes"):
        return _baseline_search_graph({"max_degree": 0} if tool_name == "find_dead_code" else {"relationship": "HANDLES"}, result_text, session_project_path)

    if tool_name == "trace_fan":
        return _baseline_trace(result_text)

    if tool_name == "get_architecture":
        return _baseline_architecture(session_project_path)

    if tool_name == "get_graph_schema":
        # Agent would glob the file tree + skim a few files
        return 500

    if tool_name == "detect_changes":
        # Agent would run git diff
        return 500

    if tool_name in ("index_status", "list_projects", "delete_project"):
        return 50

    return 0


def estimate_baseline_calls(
    tool_name: str, args: dict, result_text: str,
    session_project_path: str | None = None,
) -> int:
    """Estimate tool calls a skilled agent would make without tokkit.

    Each MCP call replaces N standard tool calls (Grep, Read, Glob).
    Based on real agent behavior measured in benchmarks (2026-04-10):
      trace_fan:     1 call replaces ~2×nodes grep+read calls
      find_dead_code: 1 call replaces 1 + N×0.6 reference greps
      get_architecture: 1 call replaces ~8 calls (glob+readme+init+modules)
      transform tools: 1 call replaces 1 Read call
    """
    if tool_name == "index_repository":
        return 0

    if tool_name == "get_architecture":
        return 8  # glob + readme + init + 5 modules

    if tool_name == "find_dead_code":
        # 1 grep for all defs + N reference greps
        if session_project_path:
            num_files = _count_source_files(session_project_path)
            checkable = int(num_files * _DEFS_PER_FILE * _CHECKABLE_FRACTION)
            return 1 + checkable
        return 10

    if tool_name == "find_routes":
        return 1  # single grep with -E

    if tool_name == "trace_fan":
        # per-node: grep to find function + read its body
        try:
            result = json.loads(result_text)
            if isinstance(result, dict):
                levels = result.get("levels", [])
                num_nodes = sum(
                    len(level.get("nodes", []))
                    for level in levels
                )
                return max((num_nodes + 1) * 2, 2)  # +1 for root, ×2 for grep+read
        except (json.JSONDecodeError, TypeError):
            pass
        return 6  # default: 3 hops × 2 calls

    if tool_name in ("clean_html", "compact_json", "search_markdown", "compact_output"):
        return 1  # single Read

    return 1  # default for admin tools


def _baseline_search_graph(args: dict, result_text: str, repo_path: str) -> int:
    """Baseline for search_graph — varies by query complexity.

    Simple search:     Grep(content, -C=3) — 7 lines × 80 chars per match.
    Dead code filter:  Grep all defs + per-function word-boundary reference grep.
    Relationship:      Grep(content, -A=1) for decorator patterns.
    """
    has_degree_filter = (
        args.get("max_degree") is not None or args.get("exclude_entry_points")
    )
    has_relationship = args.get("relationship") is not None

    if has_degree_filter:
        # Dead code detection: O(N) greps where N = number of functions
        num_files = _count_source_files(repo_path)
        estimated_defs = num_files * _DEFS_PER_FILE
        # Step 1: grep all function defs (capped at head_limit)
        grep_defs_chars = min(
            estimated_defs * 25,
            _GREP_HEAD_LIMIT * _AVG_LINE_CHARS,
        )
        # Step 2: per-function reference grep (word-boundary, files_with_matches)
        checkable = int(estimated_defs * _CHECKABLE_FRACTION)
        ref_check_chars = checkable * _BYTES_PER_REF_CHECK
        return (grep_defs_chars + ref_check_chars) // CHARS_PER_TOKEN

    if has_relationship:
        # Route listing: Grep(content, -A=1) for decorators
        try:
            nodes = json.loads(result_text)
            if isinstance(nodes, list):
                # decorator line + function signature per route
                chars_per_route = 2 * _AVG_LINE_CHARS
                return max(len(nodes) * chars_per_route // CHARS_PER_TOKEN, 200)
        except (json.JSONDecodeError, TypeError):
            pass
        return 500

    # Simple name search: Grep(content, -C=3)
    try:
        nodes = json.loads(result_text)
        if isinstance(nodes, list):
            chars_per_match = _GREP_CONTEXT_LINES * _AVG_LINE_CHARS
            return max(len(nodes) * chars_per_match // CHARS_PER_TOKEN, 100)
    except (json.JSONDecodeError, TypeError):
        pass
    return 200


def _baseline_code_snippet() -> int:
    """Baseline: Grep(content) to find function + Read(offset, limit=50).

    Fixed cost regardless of file size — a skilled agent reads only the
    function body, not the entire file.
    """
    grep_chars = 3 * _AVG_LINE_CHARS
    read_chars = _FUNCTION_READ_LINES * (_AVG_LINE_CHARS + _CAT_N_PREFIX)
    return (grep_chars + read_chars) // CHARS_PER_TOKEN


def _baseline_trace(result_text: str) -> int:
    """Baseline: per-hop Grep + Read(offset, 50 lines).

    Each hop costs one Grep to find the function + one Read for its body.
    """
    per_hop_chars = (
        3 * _AVG_LINE_CHARS
        + _FUNCTION_READ_LINES * (_AVG_LINE_CHARS + _CAT_N_PREFIX)
    )

    try:
        result = json.loads(result_text)
        if isinstance(result, dict):
            # trace_fan returns {levels: [{nodes: [...]}, ...]}
            levels = result.get("levels", [])
            num_nodes = sum(
                len(level.get("nodes", []))
                for level in levels
            ) if levels else 0
            num_nodes = max(num_nodes + 1, 2)  # +1 for root
        elif isinstance(result, list):
            num_nodes = max(len(result), 2)
        else:
            num_nodes = 3
    except (json.JSONDecodeError, TypeError):
        num_nodes = 3

    return (num_nodes * per_hop_chars) // CHARS_PER_TOKEN


def _baseline_architecture(repo_path: str) -> int:
    """Baseline: Glob listing + Read README + Read init + 5 partial modules.

    NOT the entire repo — models what a skilled agent actually reads to
    understand a project's architecture.
    """
    total_chars = 0
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "dist",
        "target", ".tox", ".mypy_cache",
    }
    exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}

    # 1. Glob file listing (paths only — cheapest operation)
    paths = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if any(f.endswith(ext) for ext in exts):
                paths.append(os.path.relpath(os.path.join(root, f), repo_path))
    total_chars += len("\n".join(paths))

    # 2. Read README (up to 2000 lines)
    for name in ("README.md", "readme.md", "README.rst", "README"):
        readme = os.path.join(repo_path, name)
        if os.path.isfile(readme):
            size = min(os.path.getsize(readme), 2000 * _AVG_LINE_CHARS)
            est_lines = max(size // _AVG_LINE_CHARS, 1)
            total_chars += size + est_lines * _CAT_N_PREFIX
            break

    # 3. Read main package __init__.py
    for candidate in _find_package_inits(repo_path):
        size = os.path.getsize(candidate)
        est_lines = max(size // _AVG_LINE_CHARS, 1)
        total_chars += size + est_lines * _CAT_N_PREFIX
        break

    # 4. First 100 lines of 5 source files in main package
    src_dir = _find_main_package(repo_path)
    if src_dir:
        source_files = sorted([
            f for f in os.listdir(src_dir)
            if any(f.endswith(ext) for ext in exts)
            and f not in ("__init__.py", "index.ts", "index.js", "mod.rs")
            and os.path.isfile(os.path.join(src_dir, f))
        ])[:5]
        for sf in source_files:
            fpath = os.path.join(src_dir, sf)
            size = min(os.path.getsize(fpath), 100 * _AVG_LINE_CHARS)
            total_chars += size + min(100, size // max(_AVG_LINE_CHARS, 1)) * _CAT_N_PREFIX

    return max(total_chars // CHARS_PER_TOKEN, 500)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_source_files(repo_path: str) -> int:
    """Count source files in repo, excluding junk directories."""
    count = 0
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", "target", ".tox"}
    exts = {".py", ".js", ".ts", ".jsx", ".tsx"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if any(f.endswith(ext) for ext in exts):
                count += 1
    return count


def _find_package_inits(repo_path: str):
    """Yield likely package __init__.py paths."""
    skip = {"tests", "test", "docs", "scripts", "examples", "node_modules"}
    try:
        entries = sorted(os.listdir(repo_path))
    except OSError:
        return
    for entry in entries:
        if entry.startswith(".") or entry in skip:
            continue
        candidate = os.path.join(repo_path, entry, "__init__.py")
        if os.path.isfile(candidate):
            yield candidate
    src = os.path.join(repo_path, "src")
    if os.path.isdir(src):
        try:
            for entry in sorted(os.listdir(src)):
                candidate = os.path.join(src, entry, "__init__.py")
                if os.path.isfile(candidate):
                    yield candidate
        except OSError:
            pass


def _find_main_package(repo_path: str) -> str | None:
    """Find the main source package directory."""
    skip = {
        "tests", "test", "docs", "scripts", "examples",
        "node_modules", "dist", "target",
    }
    try:
        entries = sorted(os.listdir(repo_path))
    except OSError:
        return None
    for entry in entries:
        if entry.startswith(".") or entry in skip:
            continue
        candidate = os.path.join(repo_path, entry)
        if os.path.isdir(candidate):
            init = os.path.join(candidate, "__init__.py")
            if os.path.isfile(init):
                return candidate
    src = os.path.join(repo_path, "src")
    if os.path.isdir(src):
        try:
            for entry in sorted(os.listdir(src)):
                candidate = os.path.join(src, entry)
                if os.path.isdir(candidate):
                    return candidate
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------
# Recording & reporting
# ---------------------------------------------------------------------------

def record_query(
    tool_name: str, content_tokens: int, baseline_tokens: int,
    baseline_calls: int = 1,
) -> None:
    """Record a query's token metrics to persistent stats."""
    saved = baseline_tokens - content_tokens
    with _lock, _interprocess_lock():
        stats = _load_stats()
        stats["total_queries"] += 1
        stats["total_content_tokens"] += content_tokens
        stats["total_baseline_tokens"] += baseline_tokens
        stats["total_content_saved"] += saved
        stats.setdefault("total_baseline_calls", 0)
        stats["total_baseline_calls"] += baseline_calls
        stats.setdefault("calls_saved", 0)
        stats["calls_saved"] += max(baseline_calls - 1, 0)

        tool_stats = stats["by_tool"].setdefault(tool_name, {
            "queries": 0, "content_tokens": 0,
            "baseline_tokens": 0, "content_saved": 0,
            "baseline_calls": 0,
        })
        tool_stats["queries"] += 1
        tool_stats["content_tokens"] += content_tokens
        tool_stats["baseline_tokens"] += baseline_tokens
        tool_stats["content_saved"] += saved
        tool_stats.setdefault("baseline_calls", 0)
        tool_stats["baseline_calls"] += baseline_calls

        # Per-chat tracking
        chats = stats.setdefault("chats", {})
        chat = chats.setdefault(_chat_id, {
            "agent": _agent,
            "started_at": _session_start,
            "total_queries": 0,
            "total_content_tokens": 0,
            "total_baseline_tokens": 0,
            "total_content_saved": 0,
            "total_baseline_calls": 0,
            "calls_saved": 0,
            "by_tool": {},
        })
        # Keep agent/started_at current (in case set_session_info was called late)
        chat["agent"] = _agent
        chat["total_queries"] += 1
        chat["total_content_tokens"] += content_tokens
        chat["total_baseline_tokens"] += baseline_tokens
        chat["total_content_saved"] += saved
        chat["total_baseline_calls"] += baseline_calls
        chat["calls_saved"] += max(baseline_calls - 1, 0)

        chat_tool = chat["by_tool"].setdefault(tool_name, {
            "queries": 0, "content_tokens": 0,
            "baseline_tokens": 0, "content_saved": 0,
            "baseline_calls": 0,
        })
        chat_tool["queries"] += 1
        chat_tool["content_tokens"] += content_tokens
        chat_tool["baseline_tokens"] += baseline_tokens
        chat_tool["content_saved"] += saved
        chat_tool["baseline_calls"] += baseline_calls

        _save_stats(stats)


def record_bash_compression(hint: str | None, raw_text: str, compressed_text: str) -> dict:
    """Record savings for a Bash command compressed by the `tokkit compress` hook.

    `raw_text` is the original command output (the baseline a bare shell would
    have dumped into context); `compressed_text` is what tokkit actually emits.
    Recorded under the `compress:<hint>` tool key and attributed to the synthetic
    "hook" agent so hook savings are visible alongside MCP-tool savings.

    Best-effort: never raises — the caller must not let stats break a command.
    """
    try:
        content_tokens = len(compressed_text.encode("utf-8")) // CHARS_PER_TOKEN
        baseline_tokens = len(raw_text.encode("utf-8")) // CHARS_PER_TOKEN
        tool_name = f"compress:{hint}" if hint else "compress:other"

        # Attribute to the shared hook chat/agent for this process.
        global _agent, _chat_id, _session_start
        _agent = _HOOK_AGENT
        _chat_id = _HOOK_CHAT_ID

        record_query(tool_name, content_tokens, baseline_tokens, baseline_calls=1)
        return {
            "tool": tool_name,
            "content_tokens": content_tokens,
            "baseline_tokens": baseline_tokens,
            "content_saved": baseline_tokens - content_tokens,
        }
    except Exception:
        return {}


def _estimate_context_tokens(content_tokens: int, num_calls: int) -> int:
    """Estimate total context window tokens for a set of tool calls.

    Models the growing conversation context: each API turn re-sends
    the system prompt + accumulated conversation history.  With prompt
    caching, re-sent content is cheaper (0.1× cost) but still consumes
    the context window.

    Model:
      turns = ceil(num_calls / CALLS_PER_TURN)
      fixed = turns × OVERHEAD_PER_TURN
      carryover = content × (turns - 1) / 2   # avg history re-sent
      total = fixed + content + carryover
    """
    if num_calls == 0:
        return 0
    num_turns = max(-(-num_calls // _CALLS_PER_TURN), 1)
    fixed = num_turns * _OVERHEAD_PER_TURN
    carryover = content_tokens * max(num_turns - 1, 0) // 2
    return fixed + content_tokens + carryover


def get_stats() -> dict:
    """Get aggregate token savings statistics with methodology explanation."""
    with _lock:
        stats = _load_stats()

    total_baseline = stats["total_baseline_tokens"]
    total_content = stats["total_content_tokens"]
    total_queries = stats["total_queries"]
    total_baseline_calls = stats.get("total_baseline_calls", total_queries)
    calls_saved = stats.get("calls_saved", 0)

    stats["savings_pct"] = (
        round((1 - total_content / total_baseline) * 100, 1)
        if total_baseline > 0 else 0.0
    )
    stats["efficiency_ratio"] = (
        round(total_baseline / total_content, 1)
        if total_content > 0 else 0.0
    )

    # Context-aware estimate: overhead from system prompt × turns + carryover
    ctx_with = _estimate_context_tokens(total_content, total_queries)
    ctx_without = _estimate_context_tokens(total_baseline, total_baseline_calls)
    ctx_saved = ctx_without - ctx_with

    stats["estimated_total"] = {
        "with_tokkit": ctx_with,
        "without_tokkit": ctx_without,
        "saved": ctx_saved,
        "savings_pct": (
            round((1 - ctx_with / ctx_without) * 100, 1)
            if ctx_without > 0 else 0.0
        ),
        "overhead_per_turn": _OVERHEAD_PER_TURN,
        "calls_per_turn": _CALLS_PER_TURN,
    }

    # Per-chat summary
    by_chat = {}
    for cid, chat_data in stats.get("chats", {}).items():
        bl = chat_data.get("total_baseline_tokens", 0)
        ct = chat_data.get("total_content_tokens", 0)
        by_chat[cid] = {
            "agent": chat_data.get("agent", "unknown"),
            "started_at": chat_data.get("started_at", ""),
            "queries": chat_data.get("total_queries", 0),
            "content_tokens": ct,
            "baseline_tokens": bl,
            "content_saved": chat_data.get("total_content_saved", 0),
            "savings_pct": round((1 - ct / bl) * 100, 1) if bl > 0 else 0.0,
            "baseline_calls": chat_data.get("total_baseline_calls", 0),
            "calls_saved": chat_data.get("calls_saved", 0),
            "by_tool": chat_data.get("by_tool", {}),
        }
    stats["by_chat"] = by_chat

    # Per-agent summary
    by_agent: dict = {}
    for chat_data in stats.get("chats", {}).values():
        agent = chat_data.get("agent", "unknown")
        agg = by_agent.setdefault(agent, {
            "chats": 0,
            "total_queries": 0,
            "total_content_tokens": 0,
            "total_baseline_tokens": 0,
            "total_content_saved": 0,
            "total_baseline_calls": 0,
            "calls_saved": 0,
        })
        agg["chats"] += 1
        agg["total_queries"] += chat_data.get("total_queries", 0)
        agg["total_content_tokens"] += chat_data.get("total_content_tokens", 0)
        agg["total_baseline_tokens"] += chat_data.get("total_baseline_tokens", 0)
        agg["total_content_saved"] += chat_data.get("total_content_saved", 0)
        agg["total_baseline_calls"] += chat_data.get("total_baseline_calls", 0)
        agg["calls_saved"] += chat_data.get("calls_saved", 0)
    for agg in by_agent.values():
        bl = agg["total_baseline_tokens"]
        ct = agg["total_content_tokens"]
        agg["savings_pct"] = round((1 - ct / bl) * 100, 1) if bl > 0 else 0.0
    stats["by_agent"] = by_agent

    stats["methodology"] = {
        "what_is_measured": (
            "Content tokens = tool result payload entering the agent's "
            "context window. Computed as "
            f"len(response.encode('utf-8')) / {CHARS_PER_TOKEN}. "
            "Baseline calls = estimated Grep/Read/Glob calls a skilled "
            "agent would make for the same task."
        ),
        "what_baseline_means": (
            "Estimated content tokens a skilled Claude Code agent would "
            "consume for the same task using standard tools (Grep, Read, "
            "Glob). Models optimistic behavior: content-mode grep with "
            "context, targeted reads with offset/limit, word-boundary "
            "matching, head_limit=250."
        ),
        "estimated_total_model": (
            "Models total context window consumption including system "
            "prompt overhead (~23K tokens/turn) and conversation history "
            "carryover. Each API turn re-sends the full conversation. "
            "More tool calls = more turns = more overhead. "
            "Formula: turns × 23,350 + content + content × (turns-1)/2. "
            "Assumes ~4 tool calls per turn (agent batching)."
        ),
        "chars_per_token": CHARS_PER_TOKEN,
        "baseline_strategies": {
            "find_dead_code": (
                "Grep all function defs + per-function word-boundary "
                "reference grep across repo."
            ),
            "find_routes": (
                "Grep(content, -A=1) for decorator patterns."
            ),
            "trace_fan": (
                "Per-hop: Grep to locate function + Read(offset, "
                "limit=50). Repeated for each node in the trace."
            ),
            "get_architecture": (
                "Glob file listing + Read README + Read package init "
                "+ Read first 100 lines of 5 key modules."
            ),
            "clean_html/compact_json/compact_output/search_markdown": (
                "Raw input size — agent would consume the full content."
            ),
        },
    }
    return stats


def make_meta(
    tool_name: str, result_text: str, session_project_path: str | None,
    raw_size: int | None = None, display_size: int | None = None,
    args: dict | None = None,
) -> dict:
    """Build the _meta field for a tool response.

    Also records the query to persistent stats.
    Returns a dict with content_tokens, baseline_tokens, content_saved,
    and baseline_calls.

    Args:
        display_size: If provided, use this byte count for content_tokens instead of
            len(result_text). Useful when result_text is raw JSON used for baseline
            estimation but the actual displayed output is a compacted version.
    """
    effective_size = display_size if display_size is not None else len(result_text.encode("utf-8"))
    content_tokens = effective_size // CHARS_PER_TOKEN
    baseline_tokens = estimate_baseline_content_tokens(
        tool_name, args or {}, result_text, session_project_path,
        raw_size=raw_size,
    )
    baseline_calls = estimate_baseline_calls(
        tool_name, args or {}, result_text, session_project_path,
    )
    content_saved = baseline_tokens - content_tokens

    record_query(tool_name, content_tokens, baseline_tokens, baseline_calls)

    return {
        "content_tokens": content_tokens,
        "baseline_tokens": baseline_tokens,
        "content_saved": content_saved,
        "baseline_calls": baseline_calls,
    }


def reset_stats() -> None:
    """Reset all statistics."""
    with _lock:
        _save_stats(_empty_stats())
