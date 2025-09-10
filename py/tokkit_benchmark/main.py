"""Tokkit benchmark: measure token savings across code intelligence, HTML, and JSON.

Usage:
    tokkit benchmark                    # default: fastapi/fastapi
    tokkit benchmark owner/repo         # any GitHub repo
    python -m tokkit_benchmark          # same as above
    python -m tokkit_benchmark owner/repo

DEFAULT REPO (fastapi/fastapi):
  Shows REAL agent-measured results. Each scenario was run by dispatching two
  independent Claude Haiku agents (baseline vs tokkit) with the same question.
  total_tokens measured from actual API usage reports (2026-04-09).
  Reports both total savings (what you pay) and content savings (compression ratio).

CUSTOM REPOS:
  Shows content compression ratios computed on-the-fly. These are NOT total agent
  savings — real-world savings are lower due to ~27K fixed overhead per agent API
  call. Use the default benchmark for verified real-world numbers.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHARS_PER_TOKEN = 4
DEFAULT_REPO = "fastapi/fastapi"
CACHE_DIR = Path.home() / ".cache" / "tokkit-benchmark"
GITHUB_API = "https://api.github.com"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Claude Code tool parameters
GREP_HEAD_LIMIT = 250
FUNCTION_READ_LINES = 50
CALLS_PER_FUNCTION = 3

# ---------------------------------------------------------------------------
# EXACT MEASURED BASELINES for fastapi/fastapi
# ---------------------------------------------------------------------------

# Code intelligence: measured by running actual Claude Code tool calls (2026-04-08)
_EXACT_CODE_BYTES = {
    "find_function": 742,       # 1 Grep(content, -C=3) for "def Depends"
    "trace_calls": 25_698,      # 21 tool calls tracing setup->openapi->... depth 3
    "dead_code": 267_165,       # 1 Grep defs + 117 word-boundary ref greps
    "list_routes": 22_808,      # 1 Grep(content, -A=1) for route decorators
    "architecture": 102_427,    # Glob + Read README + __init__.py + 5 modules
}

# HTML: raw bytes of cached fixture files (what enters context via curl/MCP/file read)
# Scenario: agent reads HTML from a non-WebFetch source (MCP tool, curl, local file)
_EXACT_HTML_BYTES = {
    "fastapi_homepage": 160_900,  # curl https://fastapi.tiangolo.com/
    "pypi_page": 318_349,         # curl https://pypi.org/project/fastapi/
}

# JSON: raw bytes of cached fixture files (what enters context from APIs)
_EXACT_JSON_BYTES = {
    "pypi_releases": 441_367,
    "contributors": 29_610,
    "similar_repos": 140_924,
}

# Skip lists for baseline computation
_SKIP_CALLS = {
    "if", "for", "while", "with", "return", "print", "len", "str", "int",
    "list", "dict", "set", "tuple", "isinstance", "type", "super", "range",
    "enumerate", "zip", "map", "filter", "getattr", "setattr", "hasattr",
    "callable", "repr", "sorted", "reversed", "any", "all", "min", "max",
    "abs", "round", "open", "next", "iter", "bool", "float", "bytes",
    "property", "staticmethod", "classmethod",
    "Optional", "List", "Dict", "Union", "Tuple", "Set", "Type", "Callable",
    "Any", "cast", "Annotated",
    "get", "set", "add", "remove", "pop", "append", "extend", "insert",
    "update", "clear", "copy", "keys", "values", "items", "format",
    "strip", "rstrip", "lstrip", "split", "join", "replace",
    "startswith", "endswith", "lower", "upper", "encode", "decode",
    "read", "write", "close", "seek", "tell", "flush",
    "JSONResponse", "HTMLResponse", "Response", "Request",
    "Field", "Depends", "Doc",
}
_SKIP_DEAD_CODE = {
    "get", "set", "put", "post", "delete", "patch", "head", "options",
    "main", "setup", "init", "default", "create", "update", "read",
    "write", "open", "close", "start", "stop", "run", "test",
    "__init__", "__repr__", "__str__", "__eq__", "__hash__",
    "__enter__", "__exit__", "__call__", "__getattr__", "__setattr__",
}

# ---------------------------------------------------------------------------
# Real agent-measured results for fastapi/fastapi
# Measured 2026-04-09 with independent Claude Haiku subagents
# Each scenario: two agents (baseline + tokkit), same question, same model.
# total_tokens from actual API usage reports.
# ---------------------------------------------------------------------------
# Fixed overhead per agent session — measured from first-turn
# cache_creation + cache_read across all benchmark agents.
#
# Breakdown (measured 2026-04-10):
#   Claude Code system prompt:  ~17,660 tokens
#     (behavioral instructions, built-in tool schemas for
#      Read, Grep, Glob, Bash, Edit, Write, Agent, etc.)
#   Subagent framing:           ~5,690 tokens
#     (agent dispatch context, user prompt, CLAUDE.md,
#      MCP tool definitions ~50 tokens)
#   Total:                      ~23,350 tokens
#
# This is identical for baseline and tokkit agents (±50 tokens).
# MCP tool definitions add ~50 tokens — negligible.
# We subtract the same 23,350 from both sides to isolate content.
AGENT_OVERHEAD = 23_350

_REAL_AGENT_RESULTS = [
    # (task, category, baseline_total_tokens, tokkit_total_tokens)
    ("Blast radius analysis", "Code graph", 56_054, 45_271),
    ("Trace setup call chain", "Code graph", 38_427, 35_766),
    ("Dead code detection", "Code graph", 42_666, 30_218),
    ("List route handlers", "Code graph", 46_072, 31_904),
    ("Architecture overview", "Code graph", 41_627, 34_691),
    ("Search README", "Markdown", 34_157, 27_075),
    ("Clean Python docs (14KB)", "HTML", 30_392, 27_000),
    ("Clean blog post (24KB)", "HTML", 33_984, 26_770),
    ("Compact flat records (14KB)", "JSON", 33_000, 27_304),
    ("Compact nested data (10KB)", "JSON", 29_214, 26_366),
    ("Compress pytest (13.7KB)", "Shell", 36_954, 25_836),
    ("Compress ruff lint (8.3KB)", "Shell", 28_748, 28_292),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _fmt(n: int) -> str:
    return f"{n:,} tok"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "tokkit-benchmark/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fetch_json(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "tokkit-benchmark/0.1", "Accept": "application/json",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token and "github" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(errors="replace")


def _clone_repo(owner: str, name: str) -> str:
    repo_path = CACHE_DIR / name
    if repo_path.exists() and any(repo_path.iterdir()):
        return str(repo_path)
    print(f"  Cloning {owner}/{name} (first run only)...")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1",
         f"https://github.com/{owner}/{name}.git", str(repo_path)],
        capture_output=True, check=True,
    )
    return str(repo_path)


def _db_path_for(repo_path: str) -> str:
    project = Path(repo_path).resolve().name
    cache = os.environ.get("TOKKIT_CACHE_DIR", "/tmp/tokkit")
    return str(Path(cache) / f"{project}.redb")


def _find_source_dir(repo_path: str, name: str) -> Path:
    rp = Path(repo_path)
    for candidate in [name, name.replace("-", "_"), "src", "lib"]:
        d = rp / candidate
        if d.is_dir() and any(d.rglob("*.py")):
            return d
    return rp


def _py_files(path: str) -> list[str]:
    result = []
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", ".tox", ".mypy_cache"}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
    return result


# ---------------------------------------------------------------------------
# Baseline computation (for non-default repos)
# ---------------------------------------------------------------------------
def _grep_content(pattern: str, path: str, context: int = 0, after: int = 0,
                  extended: bool = False) -> tuple[str, int]:
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


def _read_tool_bytes(filepath: str, offset: int, limit: int) -> int:
    lines = Path(filepath).read_text(errors="replace").splitlines(keepends=True)
    selected = lines[offset:offset + limit]
    total = 0
    for i, line in enumerate(selected, start=offset + 1):
        total += len(f"{i:>6}\t{line}".encode("utf-8", errors="replace"))
    return total


def _compute_bl_find_function(repo_path: str) -> int:
    _, nb = _grep_content("def Depends", repo_path, context=3)
    return nb


def _compute_bl_trace_calls(repo_path: str) -> int:
    total = 0
    visited: set[str] = set()

    def _trace(func: str, depth: int):
        nonlocal total
        if depth > 3 or func in visited:
            return
        visited.add(func)
        out, nb = _grep_content(f"def {func}", repo_path)
        total += nb
        if not out.strip():
            return
        parts = out.splitlines()[0].split(":", 2)
        if len(parts) < 2:
            return
        fp = parts[0].strip()
        try:
            ln = int(parts[1])
        except (ValueError, IndexError):
            return
        if not os.path.isfile(fp):
            return
        total += _read_tool_bytes(fp, ln - 1, FUNCTION_READ_LINES)
        text = "\n".join(Path(fp).read_text(errors="replace").splitlines()[ln-1:ln+49])
        calls = []
        for m in re.findall(r"\b([a-zA-Z_]\w*)\s*\(", text):
            if m not in _SKIP_CALLS and m != func and m not in visited and m not in calls:
                calls.append(m)
                if len(calls) >= CALLS_PER_FUNCTION:
                    break
        for c in calls:
            _trace(c, depth + 1)

    _trace("setup", 0)
    return total


def _compute_bl_dead_code(repo_path: str, src_dir: str) -> int:
    out, total = _grep_content(r"^\s*def [a-zA-Z_]\w*", src_dir, extended=True)
    names = set()
    for line in out.splitlines():
        m = re.search(r"def\s+(\w+)", line)
        if m:
            n = m.group(1)
            if n not in _SKIP_DEAD_CODE and not n.startswith("_") and len(n) > 3:
                names.add(n)
    for n in names:
        r = subprocess.run(["grep", "-rlw", n, repo_path, "--include=*.py"],
                           capture_output=True, text=True)
        total += len(r.stdout.encode("utf-8"))
    return total


def _compute_bl_list_routes(repo_path: str) -> int:
    _, nb = _grep_content(
        r"@(app|router)\.(get|post|put|delete|patch|options|head)",
        repo_path, after=1, extended=True,
    )
    return nb


def _compute_bl_architecture(repo_path: str, src_dir: str) -> int:
    total = len("\n".join(
        os.path.relpath(f, repo_path) for f in _py_files(repo_path)
    ).encode("utf-8"))
    readme = os.path.join(repo_path, "README.md")
    if os.path.isfile(readme):
        total += _read_tool_bytes(readme, 0, 2000)
    init = os.path.join(src_dir, "__init__.py")
    if os.path.isfile(init):
        nlines = len(Path(init).read_text(errors="replace").splitlines())
        total += _read_tool_bytes(init, 0, nlines)
    if os.path.isdir(src_dir):
        mods = sorted([
            f for f in os.listdir(src_dir)
            if f.endswith(".py") and f != "__init__.py"
            and os.path.isfile(os.path.join(src_dir, f))
        ])[:5]
        for mod in mods:
            total += _read_tool_bytes(os.path.join(src_dir, mod), 0, 100)
    return total


# ---------------------------------------------------------------------------
# Phase 1: Code Intelligence
# ---------------------------------------------------------------------------
def _phase1(repo_path: str, name: str, is_default: bool) -> list[tuple[str, int, int]]:
    import tokkit_py

    src_dir = str(_find_source_dir(repo_path, name))
    db_path = _db_path_for(repo_path)

    print("  Indexing repository...")
    tokkit_py.index_repository(repo_path, "full")

    results = []

    # Q1: Find function
    bl = _EXACT_CODE_BYTES["find_function"] if is_default else _compute_bl_find_function(repo_path)
    resp = tokkit_py.search_nodes(db_path, "", name_pattern="Depends.*")
    results.append(("Find function", bl // CHARS_PER_TOKEN, _tokens(resp)))

    # Q2: Trace calls
    bl = _EXACT_CODE_BYTES["trace_calls"] if is_default else _compute_bl_trace_calls(repo_path)
    nodes = json.loads(tokkit_py.search_nodes(db_path, "setup", label="Function"))
    resp = tokkit_py.trace_fan(db_path, nodes[0]["qualified_name"], direction="outbound", depth=3) if nodes else "[]"
    results.append(("Trace calls (depth 3)", bl // CHARS_PER_TOKEN, _tokens(resp)))

    # Q3: Dead code
    bl = _EXACT_CODE_BYTES["dead_code"] if is_default else _compute_bl_dead_code(repo_path, src_dir)
    resp = tokkit_py.search_nodes(db_path, "", max_degree=0, exclude_entry_points=True, limit=200)
    results.append(("Dead code detection", bl // CHARS_PER_TOKEN, _tokens(resp)))

    # Q4: List routes
    bl = _EXACT_CODE_BYTES["list_routes"] if is_default else _compute_bl_list_routes(repo_path)
    resp = tokkit_py.search_nodes(db_path, "", label="Route", limit=200)
    results.append(("List routes", bl // CHARS_PER_TOKEN, _tokens(resp)))

    # Q5: Architecture
    bl = _EXACT_CODE_BYTES["architecture"] if is_default else _compute_bl_architecture(repo_path, src_dir)
    resp = tokkit_py.get_architecture(db_path, "")
    results.append(("Architecture overview", bl // CHARS_PER_TOKEN, _tokens(resp)))

    return results


# ---------------------------------------------------------------------------
# Phase 2: HTML Processing (MCP/curl/file sources)
#
# Scenario: agent receives raw HTML from a non-WebFetch source — an MCP tool
# (Jira, Confluence, CMS), curl via Bash, or reading a local .html file.
# Raw HTML enters context as-is. clean_html extracts content as markdown.
#
# This does NOT benchmark WebFetch, which already converts HTML to markdown
# via Turndown + Haiku summarization before entering context.
# ---------------------------------------------------------------------------
def _phase2(owner: str, name: str, is_default: bool) -> list[tuple[str, int, int]]:
    from tokkit_scraper import clean_html

    results = []

    if is_default:
        # Use cached fixtures — deterministic, no network needed
        html_home = _load_fixture("fastapi_homepage.html")
        bl_home = _EXACT_HTML_BYTES["fastapi_homepage"]
        cleaned_home = clean_html(html_home, mode="markdown")
        results.append(("FastAPI homepage", bl_home // CHARS_PER_TOKEN, _tokens(cleaned_home)))

        html_pypi = _load_fixture("pypi_fastapi.html")
        bl_pypi = _EXACT_HTML_BYTES["pypi_page"]
        cleaned_pypi = clean_html(html_pypi, mode="markdown")
        results.append(("PyPI page", bl_pypi // CHARS_PER_TOKEN, _tokens(cleaned_pypi)))
    else:
        # Fetch live — simulates curl/MCP returning raw HTML
        print("  Fetching repo metadata...")
        try:
            repo_json = _fetch_json(f"{GITHUB_API}/repos/{owner}/{name}")
            homepage = json.loads(repo_json).get("homepage", "") or ""
        except Exception:
            homepage = ""
        if not homepage:
            homepage = f"https://pypi.org/project/{name}/"

        print(f"  Fetching {homepage}...")
        try:
            raw = _fetch(homepage)
        except Exception:
            homepage = f"https://pypi.org/project/{name}/"
            print(f"  Fallback: {homepage}...")
            raw = _fetch(homepage)
        label = homepage if len(homepage) <= 30 else homepage[:27] + "..."
        results.append((label, _tokens(raw), _tokens(clean_html(raw, mode="markdown"))))

        pypi_url = f"https://pypi.org/project/{name}/"
        if pypi_url != homepage:
            print(f"  Fetching {pypi_url}...")
            try:
                raw = _fetch(pypi_url)
                results.append(("PyPI page", _tokens(raw), _tokens(clean_html(raw, mode="markdown"))))
            except Exception:
                pass

    return results


# ---------------------------------------------------------------------------
# Phase 3: Data Processing (JSON)
# ---------------------------------------------------------------------------
def _phase3(owner: str, name: str, is_default: bool) -> list[tuple[str, int, int]]:
    from tokkit_json import compact_json

    results = []

    if is_default:
        # Use cached fixtures
        raw_pypi = _load_fixture("pypi_releases.json")
        bl_pypi = _EXACT_JSON_BYTES["pypi_releases"]
        data = json.loads(raw_pypi)
        all_files = []
        for ver, files in data.get("releases", {}).items():
            for f in files:
                f["version"] = ver
                all_files.append(f)
        compacted = compact_json(json.dumps(all_files) if all_files else raw_pypi)
        results.append(("PyPI releases", bl_pypi // CHARS_PER_TOKEN, _tokens(compacted)))

        raw_contribs = _load_fixture("github_contributors.json")
        bl_contribs = _EXACT_JSON_BYTES["contributors"]
        results.append(("Contributors", bl_contribs // CHARS_PER_TOKEN, _tokens(compact_json(raw_contribs))))

        raw_similar = _load_fixture("github_similar.json")
        bl_similar = _EXACT_JSON_BYTES["similar_repos"]
        items = json.loads(raw_similar).get("items", [])
        compacted = compact_json(json.dumps(items))
        results.append(("Similar repos", bl_similar // CHARS_PER_TOKEN, _tokens(compacted)))
    else:
        # Fetch live
        print("  Fetching PyPI data...")
        try:
            raw = _fetch_json(f"https://pypi.org/pypi/{name}/json")
            baseline = _tokens(raw)
            data = json.loads(raw)
            all_files = []
            for ver, files in data.get("releases", {}).items():
                for f in files:
                    f["version"] = ver
                    all_files.append(f)
            compacted = compact_json(json.dumps(all_files) if all_files else raw)
            results.append(("PyPI releases", baseline, _tokens(compacted)))
        except Exception as e:
            print(f"    Skipped: {e}")

        print("  Fetching contributors...")
        try:
            raw = _fetch_json(f"{GITHUB_API}/repos/{owner}/{name}/contributors?per_page=30")
            results.append(("Contributors", _tokens(raw), _tokens(compact_json(raw))))
        except Exception as e:
            print(f"    Skipped: {e}")

        print("  Fetching similar repos...")
        try:
            raw = _fetch_json(f"{GITHUB_API}/search/repositories?q={name}+language:python&per_page=25")
            items = json.loads(raw).get("items", [])
            results.append(("Similar repos", _tokens(raw), _tokens(compact_json(json.dumps(items)))))
        except Exception as e:
            print(f"    Skipped: {e}")

    return results


# ---------------------------------------------------------------------------
# Report (real agent measurements — default repo)
# ---------------------------------------------------------------------------
def _verify_tools(repo_path: str) -> bool:
    """Run tokkit tools silently to verify they work."""
    import tokkit_py
    db_path = _db_path_for(repo_path)
    try:
        tokkit_py.search_nodes(db_path, "setup", label="Function")
        tokkit_py.get_architecture(db_path, "")
        return True
    except Exception:
        return False


def _print_real_results():
    """Print real agent-measured results for default repo."""
    # Collect unique categories in order
    categories: list[str] = []
    for _, cat, _, _ in _REAL_AGENT_RESULTS:
        if cat not in categories:
            categories.append(cat)

    grand_bl, grand_tk = 0, 0

    for cat in categories:
        rows = [(t, bl, tk) for t, c, bl, tk in _REAL_AGENT_RESULTS if c == cat]
        print(f"\n  Phase: {cat}")
        print(f"  {'Task':<30} {'Baseline':>12} {'Tokkit':>12} {'Saved':>8}")
        print(f"  {'─' * 30} {'─' * 12} {'─' * 12} {'─' * 8}")
        phase_bl, phase_tk = 0, 0
        for task, bl, tk in rows:
            saved = (1 - tk / bl) * 100 if bl > 0 else 0
            print(f"  {task:<30} {_fmt(bl):>12} {_fmt(tk):>12} {saved:>7.1f}%")
            phase_bl += bl
            phase_tk += tk
        if len(rows) > 1:
            print(f"  {'─' * 30} {'─' * 12} {'─' * 12} {'─' * 8}")
            saved = (1 - phase_tk / phase_bl) * 100 if phase_bl > 0 else 0
            print(f"  {'Subtotal':<30} {_fmt(phase_bl):>12} {_fmt(phase_tk):>12} {saved:>7.1f}%")
        grand_bl += phase_bl
        grand_tk += phase_tk

    n = len(_REAL_AGENT_RESULTS)
    grand_bl_c = grand_bl - AGENT_OVERHEAD * n
    grand_tk_c = grand_tk - AGENT_OVERHEAD * n
    saved_total = (1 - grand_tk / grand_bl) * 100
    saved_content = (1 - grand_tk_c / grand_bl_c) * 100

    print()
    print("═" * 62)
    print(f"  TOTAL TOKEN SAVINGS:    {saved_total:.0f}%   (what you pay)")
    print(f"  CONTENT SAVINGS:        {saved_content:.0f}%   (excl. ~{AGENT_OVERHEAD // 1000}K overhead/task)")
    print(f"    (MCP tool definitions add ~50 tokens, not subtracted)")
    print("═" * 62)


# ---------------------------------------------------------------------------
# Report (content compression — non-default repos)
# ---------------------------------------------------------------------------
def _print_phase(title: str, rows: list[tuple[str, int, int]]) -> tuple[int, int]:
    print(f"\n  Phase: {title}")
    print(f"  {'Task':<30} {'Without':>12} {'With':>12} {'Compress':>8}")
    print(f"  {'─' * 30} {'─' * 12} {'─' * 12} {'─' * 8}")
    phase_bl, phase_tk = 0, 0
    for task, baseline, tokkit in rows:
        saved = (1 - tokkit / baseline) * 100 if baseline > 0 else 0
        print(f"  {task:<30} {_fmt(baseline):>12} {_fmt(tokkit):>12} {saved:>7.1f}%")
        phase_bl += baseline
        phase_tk += tokkit
    print(f"  {'─' * 30} {'─' * 12} {'─' * 12} {'─' * 8}")
    saved = (1 - phase_tk / phase_bl) * 100 if phase_bl > 0 else 0
    print(f"  {'Subtotal':<30} {_fmt(phase_bl):>12} {_fmt(phase_tk):>12} {saved:>7.1f}%")
    return phase_bl, phase_tk


def _print_methodology(is_default: bool):
    print()
    print("  ─── Methodology ───")
    print()
    if is_default:
        print("  Real agent sessions — each task dispatched two independent")
        print("  Claude Haiku agents (baseline vs tokkit) with the same question.")
        print("  total_tokens measured from actual API usage reports.")
        print()
        print(f"  Fixed overhead per session: ~{AGENT_OVERHEAD:,} tokens")
        print("    Claude Code system prompt:  ~17,660 tokens")
        print("    Subagent framing + prompt:   ~5,690 tokens")
        print("    MCP tool definitions:           ~50 tokens")
        print()
        print("  'Total savings' = what you actually pay (includes overhead).")
        print("  'Content savings' = total minus fixed overhead per task.")
        print()
        print("  Content tools (HTML, JSON, markdown, shell) use server-side")
        print("  file reading via path= so raw content never enters context.")
        print("  Baseline agents use Read tool which loads full content.")
    else:
        print("  Content compression ratio — NOT real agent token savings.")
        print("  'Without' = raw content bytes / 4 (estimated tokens)")
        print("  'With'    = tokkit output bytes / 4 (computed on the fly)")
        print()
        print("  Real-world agent savings are LOWER than these ratios")
        print(f"  due to ~{AGENT_OVERHEAD // 1000}K+ fixed overhead per agent API call (system")
        print("  prompt + tool definitions).")
        print("  For verified real-world numbers, run the default benchmark:")
        print("    tokkit benchmark fastapi/fastapi")
        print()
        print("  HTML scenario: raw HTML from MCP tools, curl, or file reads.")
        print("  Does NOT apply to WebFetch (which already cleans HTML).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(repo: str | None = None) -> None:
    if repo is None:
        repo = DEFAULT_REPO

    if "/" not in repo:
        print(f"Error: repo must be 'owner/name' format, got '{repo}'", file=sys.stderr)
        sys.exit(1)

    owner, name = repo.split("/", 1)
    is_default = (repo == DEFAULT_REPO)

    print()
    print("═" * 62)
    print(f'  tokkit benchmark — "Evaluate {owner}/{name}"')
    if is_default:
        print("  (real agent measurements, Claude Haiku, 2026-04-09)")
    else:
        print("  (content compression ratios, live data)")
    print("═" * 62)

    repo_path = _clone_repo(owner, name)

    if is_default:
        # Index + verify tools work, then show real agent-measured results
        import tokkit_py
        print("  Indexing repository...")
        tokkit_py.index_repository(repo_path, "full")
        if _verify_tools(repo_path):
            print("  Tools verified OK")
        else:
            print("  WARNING: Tool verification failed")
        _print_real_results()
    else:
        # Non-default: compute content compression on-the-fly
        p1 = _phase1(repo_path, name, is_default)
        total_bl, total_tk = _print_phase("Code Intelligence", p1)

        p2 = _phase2(owner, name, is_default)
        bl, tk = _print_phase("HTML Processing (curl/MCP)", p2)
        total_bl += bl
        total_tk += tk

        p3 = _phase3(owner, name, is_default)
        bl, tk = _print_phase("Data Processing (JSON)", p3)
        total_bl += bl
        total_tk += tk

        saved = (1 - total_tk / total_bl) * 100 if total_bl > 0 else 0
        print()
        print("═" * 62)
        print(f"  {'CONTENT COMPRESSION':<30} {_fmt(total_bl):>12} {_fmt(total_tk):>12} {saved:>7.1f}%")
        print("═" * 62)
        print()
        print("  NOTE: These are content compression ratios, not total")
        print("  agent savings. Real-world savings are lower — see methodology.")

    _print_methodology(is_default)
