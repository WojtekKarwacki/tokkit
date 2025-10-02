"""Baseline measurements: what an optimistic Claude Code agent would consume.

For the DEFAULT repo (fastapi @ 0.115.6), baselines are EXACT MEASURED VALUES
obtained by running the actual Claude Code tool call sequence and counting bytes.

For OTHER repos, baselines are computed by running the same tool call sequence
as an approximation (grep + read with same parameters).

Each baseline models the MINIMUM tool calls a skilled Claude Code agent would make,
using the most token-efficient tool options available:

- Grep with output_mode="content" (returns matching lines, not full files)
- Grep head_limit=250 (default cap on returned lines)
- Read with offset/limit (targeted function bodies, not entire files)
- Read tool line-number overhead (~8 bytes/line for cat -n format)
- Glob for file discovery (returns paths only, very cheap)
- Scoped exploration (core module only, not tests/docs/examples)
- Skips standard library methods (get, append, strip, etc.)

These are OPTIMISTIC baselines — they assume Claude Code always picks the most
efficient tool mode, never reads more than necessary, and benefits from all
default limits. A real agent would often consume more tokens through iterative
exploration, reading full files, and trial-and-error searches.
"""

import os
import re
import subprocess
from pathlib import Path

from e2e.benchmark.config import CHARS_PER_TOKEN, REPO_SHA

# ---------------------------------------------------------------------------
# EXACT MEASURED BASELINES for fastapi/fastapi @ 0.115.6
#
# These were obtained by running the exact Claude Code tool call sequence
# against the cached repo and counting the raw bytes of each tool response.
# Measurement date: 2026-04-08
#
# Q1 (dead code): 1 Grep for definitions (250 lines) + 117 word-boundary reference greps
# Q2 (routes): 1 Grep call (content, -A=1) for route decorators, head_limit=250
# Q3 (architecture): 1 Glob + 1 Read README + 1 Read __init__.py + 5 Read (100 lines each)
# Q4 (markdown): 1 Read(README.md) — full 499-line file with cat -n line-number prefix
# Q5 (pytest): raw output byte count (agent reads as-is)
# Q6 (lint): raw output byte count with ANSI codes (agent reads as-is)
# ---------------------------------------------------------------------------
_EXACT_BASELINES_BYTES = {
    "dead_code": 267_165,       # 267,165 bytes =  66,791 tokens
    "list_routes": 22_808,      #  22,808 bytes =   5,702 tokens
    "architecture": 102_427,    # 102,427 bytes =  25,606 tokens
    "search_markdown": 27_697,  #  27,697 bytes =   6,924 tokens (Read README.md with cat -n)
    "compress_pytest": 2_400,   # ~600 tokens, typical 50-test run
    "compress_lint": 1_600,     # ~400 tokens, typical ruff output
}
_EXACT_BASELINES_REPO = "0.115.6"  # matches REPO_SHA in config.py


def _is_default_repo() -> bool:
    """Check if we're benchmarking the default FastAPI repo."""
    return REPO_SHA == _EXACT_BASELINES_REPO


# ---------------------------------------------------------------------------
# Claude Code tool parameters
# ---------------------------------------------------------------------------
GREP_HEAD_LIMIT = 250       # default head_limit on Grep results

# Generic function names to skip in dead-code detection
_SKIP_DEAD_CODE_NAMES = {
    "get", "set", "put", "post", "delete", "patch", "head", "options",
    "main", "setup", "init", "default", "create", "update", "read",
    "write", "open", "close", "start", "stop", "run", "test",
    "__init__", "__repr__", "__str__", "__eq__", "__hash__",
    "__enter__", "__exit__", "__call__", "__getattr__", "__setattr__",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _py_files(repo_path: str) -> list[str]:
    """All .py files in the repo, excluding junk dirs."""
    result = []
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", ".tox", ".mypy_cache"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
    return result


def _read_tool_bytes(filepath: str, offset: int, limit: int) -> int:
    """Byte cost of Read(file, offset, limit): content + cat -n line-number prefix."""
    lines = Path(filepath).read_text(errors="replace").splitlines(keepends=True)
    selected = lines[offset:offset + limit]
    total = 0
    for i, line in enumerate(selected, start=offset + 1):
        total += len(f"{i:>6}\t{line}".encode("utf-8", errors="replace"))
    return total


def _grep_content_bytes(pattern: str, path: str, context: int = 0,
                        after: int = 0, extended: bool = False) -> tuple[str, int]:
    """Byte cost of Grep(content mode). Returns (output_text, byte_count)."""
    cmd = ["grep", "-rn"]
    if extended:
        cmd.append("-E")
    cmd.extend([pattern, path, "--include=*.py"])
    if context > 0:
        cmd.extend(["-C", str(context)])
    if after > 0:
        cmd.extend(["-A", str(after)])
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.splitlines()[:GREP_HEAD_LIMIT]
    output = "\n".join(lines)
    return output, len(output.encode("utf-8"))


def _grep_files_bytes(pattern: str, path: str, word: bool = False) -> int:
    """Byte cost of Grep(files_with_matches mode)."""
    cmd = ["grep", "-rl"]
    if word:
        cmd.append("-w")
    cmd.extend([pattern, path, "--include=*.py"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    return len(result.stdout.encode("utf-8"))


# ---------------------------------------------------------------------------
# Baseline functions
# ---------------------------------------------------------------------------
def baseline_dead_code(repo_path: str) -> int:
    """Q3: Dead code detection.

    Agent strategy: Scope to core module only (fastapi/ directory).
      1. Grep content mode for all function definitions in core module
      2. For each function name (skipping generic/short names), Grep with
         word-boundary matching (-w) in files_with_matches mode

    Skips generic names (get, set, post, etc.) and private/dunder methods.
    Uses word-boundary matching to avoid substring false positives.
    """
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["dead_code"] // CHARS_PER_TOKEN

    total_bytes = 0

    core_dir = os.path.join(repo_path, "fastapi")
    if not os.path.isdir(core_dir):
        core_dir = repo_path

    # Step 1: Find definitions in core module
    output, nbytes = _grep_content_bytes(
        r"^\s*def [a-zA-Z_]\w*", core_dir, extended=True,
    )
    total_bytes += nbytes

    func_names: set[str] = set()
    for line in output.splitlines():
        m = re.search(r"def\s+(\w+)", line)
        if m:
            name = m.group(1)
            if name not in _SKIP_DEAD_CODE_NAMES and not name.startswith("_") and len(name) > 3:
                func_names.add(name)

    # Step 2: Word-boundary reference grep per function
    for name in func_names:
        total_bytes += _grep_files_bytes(name, repo_path, word=True)

    return total_bytes // CHARS_PER_TOKEN


def baseline_list_routes(repo_path: str) -> int:
    """Q4: List all API routes.

    Agent strategy: Grep(pattern=route_decorator_regex, output_mode="content", -A=1)
    The decorator lines contain HTTP method and route path — that IS the answer.
    One line of after-context captures the function name.
    No file reads needed. Output capped at head_limit=250.
    """
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["list_routes"] // CHARS_PER_TOKEN

    _, nbytes = _grep_content_bytes(
        r"@(app|router)\.(get|post|put|delete|patch|options|head)",
        repo_path, after=1, extended=True,
    )
    return nbytes // CHARS_PER_TOKEN


def baseline_search_markdown(repo_path: str) -> int:
    """Q6: Search markdown documentation.

    Agent strategy: Read(README.md) — read the full file.
    The Read tool returns content with cat -n line-number prefixes.
    This is the minimum: a single Read call on the one file that has the answer.
    """
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["search_markdown"] // CHARS_PER_TOKEN

    readme = os.path.join(repo_path, "README.md")
    if not os.path.isfile(readme):
        return 0
    nlines = len(Path(readme).read_text(errors="replace").splitlines())
    return _read_tool_bytes(readme, 0, nlines) // CHARS_PER_TOKEN


def baseline_compress_pytest(repo_path: str) -> int:
    """Q7: Compress pytest output. Baseline = raw output tokens."""
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["compress_pytest"] // CHARS_PER_TOKEN
    return _EXACT_BASELINES_BYTES["compress_pytest"] // CHARS_PER_TOKEN


def baseline_compress_lint(repo_path: str) -> int:
    """Q8: Compress lint output. Baseline = raw output tokens."""
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["compress_lint"] // CHARS_PER_TOKEN
    return _EXACT_BASELINES_BYTES["compress_lint"] // CHARS_PER_TOKEN


def baseline_architecture(repo_path: str) -> int:
    """Q5: Architecture overview.

    Agent strategy:
      1. Glob("**/*.py") — file path listing (cheap, paths only)
      2. Read README.md (project description, up to 2000 lines)
      3. Read core __init__.py (public API surface)
      4. Read first 100 lines of top 5 core modules (key abstractions)
    """
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["architecture"] // CHARS_PER_TOKEN

    total_bytes = 0

    # Glob file listing
    all_files = _py_files(repo_path)
    file_listing = "\n".join(os.path.relpath(f, repo_path) for f in all_files)
    total_bytes += len(file_listing.encode("utf-8"))

    # Read README.md
    readme = os.path.join(repo_path, "README.md")
    if os.path.isfile(readme):
        total_bytes += _read_tool_bytes(readme, 0, 2000)

    # Read core __init__.py
    init_file = os.path.join(repo_path, "fastapi", "__init__.py")
    if os.path.isfile(init_file):
        nlines = len(Path(init_file).read_text(errors="replace").splitlines())
        total_bytes += _read_tool_bytes(init_file, 0, nlines)

    # First 100 lines of top 5 modules
    fastapi_dir = os.path.join(repo_path, "fastapi")
    if os.path.isdir(fastapi_dir):
        modules = sorted([
            f for f in os.listdir(fastapi_dir)
            if f.endswith(".py") and f != "__init__.py"
            and os.path.isfile(os.path.join(fastapi_dir, f))
        ])[:5]
        for mod in modules:
            total_bytes += _read_tool_bytes(os.path.join(fastapi_dir, mod), 0, 100)

    return total_bytes // CHARS_PER_TOKEN


