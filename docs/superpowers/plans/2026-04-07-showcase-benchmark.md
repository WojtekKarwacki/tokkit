# Showcase Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standalone benchmark script that runs a "evaluate FastAPI for adoption" scenario, measuring token savings across code analysis, web scraping, and JSON processing.

**Architecture:** Single Python module (`py/tokkit_benchmark/`) with a `main.py` that orchestrates three phases. Each phase measures baseline tokens (raw file reads) vs tokkit tokens (graph queries / clean_html / compact_json). Results are collected and printed as a formatted table. Fixtures (HTML, JSON) are bundled; FastAPI repo is cloned on first run and cached.

**Tech Stack:** tokkit_py (Rust extension), tokkit_scraper, tokkit_json. No external dependencies beyond what tokkit already requires.

**Spec:** `docs/superpowers/specs/2026-04-07-showcase-benchmark-design.md`

---

## File Structure

```
py/tokkit_benchmark/
├── __init__.py              # empty
├── __main__.py              # `python -m tokkit_benchmark` entry
├── main.py                  # all benchmark logic + report formatting
└── fixtures/
    ├── fastapi_docs.html    # ~15KB cached HTML page
    ├── github_repo.json     # GitHub API repo metadata
    ├── github_contributors.json  # 30 contributor objects
    └── github_issues.json   # 25 issue objects with labels
```

**Modified:**
- `py/tokkit_cli/main.py` — add `benchmark` subcommand

---

### Task 1: Create fixture files

**Files:**
- Create: `py/tokkit_benchmark/fixtures/github_repo.json`
- Create: `py/tokkit_benchmark/fixtures/github_contributors.json`
- Create: `py/tokkit_benchmark/fixtures/github_issues.json`
- Create: `py/tokkit_benchmark/fixtures/fastapi_docs.html`

- [ ] **Step 1: Create the fixtures directory**

```bash
mkdir -p py/tokkit_benchmark/fixtures
```

- [ ] **Step 2: Create github_repo.json**

Write `py/tokkit_benchmark/fixtures/github_repo.json` — a realistic GitHub API `/repos/fastapi/fastapi` response. This should be ~2-3KB of JSON:

```json
{
  "id": 160919119,
  "node_id": "MDEwOlJlcG9zaXRvcnkxNjA5MTkxMTk=",
  "name": "fastapi",
  "full_name": "fastapi/fastapi",
  "private": false,
  "owner": {
    "login": "fastapi",
    "id": 156354,
    "node_id": "MDQ6VXNlcjE1NjM1NA==",
    "avatar_url": "https://avatars.githubusercontent.com/u/156354?v=4",
    "gravatar_id": "",
    "url": "https://api.github.com/users/fastapi",
    "html_url": "https://github.com/fastapi",
    "followers_url": "https://api.github.com/users/fastapi/followers",
    "following_url": "https://api.github.com/users/fastapi/following{/other_user}",
    "gists_url": "https://api.github.com/users/fastapi/gists{/gist_id}",
    "starred_url": "https://api.github.com/users/fastapi/starred{/owner}{/repo}",
    "subscriptions_url": "https://api.github.com/users/fastapi/subscriptions",
    "organizations_url": "https://api.github.com/users/fastapi/orgs",
    "repos_url": "https://api.github.com/users/fastapi/repos",
    "events_url": "https://api.github.com/users/fastapi/events{/privacy}",
    "received_events_url": "https://api.github.com/users/fastapi/received_events",
    "type": "User",
    "site_admin": false
  },
  "html_url": "https://github.com/fastapi/fastapi",
  "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
  "fork": false,
  "url": "https://api.github.com/repos/fastapi/fastapi",
  "forks_url": "https://api.github.com/repos/fastapi/fastapi/forks",
  "keys_url": "https://api.github.com/repos/fastapi/fastapi/keys{/key_id}",
  "collaborators_url": "https://api.github.com/repos/fastapi/fastapi/collaborators{/collaborator}",
  "teams_url": "https://api.github.com/repos/fastapi/fastapi/teams",
  "hooks_url": "https://api.github.com/repos/fastapi/fastapi/hooks",
  "issue_events_url": "https://api.github.com/repos/fastapi/fastapi/issues/events{/number}",
  "events_url": "https://api.github.com/repos/fastapi/fastapi/events",
  "assignees_url": "https://api.github.com/repos/fastapi/fastapi/assignees{/user}",
  "branches_url": "https://api.github.com/repos/fastapi/fastapi/branches{/branch}",
  "tags_url": "https://api.github.com/repos/fastapi/fastapi/tags",
  "blobs_url": "https://api.github.com/repos/fastapi/fastapi/git/blobs{/sha}",
  "git_tags_url": "https://api.github.com/repos/fastapi/fastapi/git/tags{/sha}",
  "git_refs_url": "https://api.github.com/repos/fastapi/fastapi/git/refs{/sha}",
  "trees_url": "https://api.github.com/repos/fastapi/fastapi/git/trees{/sha}",
  "statuses_url": "https://api.github.com/repos/fastapi/fastapi/statuses/{sha}",
  "languages_url": "https://api.github.com/repos/fastapi/fastapi/languages",
  "stargazers_url": "https://api.github.com/repos/fastapi/fastapi/stargazers",
  "contributors_url": "https://api.github.com/repos/fastapi/fastapi/contributors",
  "subscribers_url": "https://api.github.com/repos/fastapi/fastapi/subscribers",
  "subscription_url": "https://api.github.com/repos/fastapi/fastapi/subscription",
  "commits_url": "https://api.github.com/repos/fastapi/fastapi/commits{/sha}",
  "git_commits_url": "https://api.github.com/repos/fastapi/fastapi/git/commits{/sha}",
  "comments_url": "https://api.github.com/repos/fastapi/fastapi/comments{/number}",
  "issue_comment_url": "https://api.github.com/repos/fastapi/fastapi/issues/comments{/number}",
  "contents_url": "https://api.github.com/repos/fastapi/fastapi/contents/{+path}",
  "compare_url": "https://api.github.com/repos/fastapi/fastapi/compare/{base}...{head}",
  "merges_url": "https://api.github.com/repos/fastapi/fastapi/merges",
  "archive_url": "https://api.github.com/repos/fastapi/fastapi/{archive_format}{/ref}",
  "downloads_url": "https://api.github.com/repos/fastapi/fastapi/downloads",
  "issues_url": "https://api.github.com/repos/fastapi/fastapi/issues{/number}",
  "pulls_url": "https://api.github.com/repos/fastapi/fastapi/pulls{/number}",
  "milestones_url": "https://api.github.com/repos/fastapi/fastapi/milestones{/number}",
  "notifications_url": "https://api.github.com/repos/fastapi/fastapi/notifications{?since,all,participating}",
  "labels_url": "https://api.github.com/repos/fastapi/fastapi/labels{/name}",
  "releases_url": "https://api.github.com/repos/fastapi/fastapi/releases{/id}",
  "deployments_url": "https://api.github.com/repos/fastapi/fastapi/deployments",
  "created_at": "2018-12-08T00:49:30Z",
  "updated_at": "2025-03-15T12:30:00Z",
  "pushed_at": "2025-03-15T10:22:14Z",
  "git_url": "git://github.com/fastapi/fastapi.git",
  "ssh_url": "git@github.com:fastapi/fastapi.git",
  "clone_url": "https://github.com/fastapi/fastapi.git",
  "svn_url": "https://github.com/fastapi/fastapi",
  "homepage": "https://fastapi.tiangolo.com",
  "size": 31420,
  "stargazers_count": 82456,
  "watchers_count": 82456,
  "language": "Python",
  "has_issues": true,
  "has_projects": false,
  "has_downloads": true,
  "has_wiki": false,
  "has_pages": false,
  "has_discussions": true,
  "forks_count": 6734,
  "mirror_url": null,
  "archived": false,
  "disabled": false,
  "open_issues_count": 487,
  "license": {
    "key": "mit",
    "name": "MIT License",
    "spdx_id": "MIT",
    "url": "https://api.github.com/licenses/mit",
    "node_id": "MDc6TGljZW5zZTEz"
  },
  "allow_forking": true,
  "is_template": false,
  "web_commit_signoff_required": false,
  "topics": [
    "api",
    "async",
    "fastapi",
    "framework",
    "json-schema",
    "openapi",
    "pydantic",
    "python",
    "rest",
    "starlette",
    "swagger",
    "uvicorn",
    "web"
  ],
  "visibility": "public",
  "forks": 6734,
  "open_issues": 487,
  "watchers": 82456,
  "default_branch": "master",
  "network_count": 6734,
  "subscribers_count": 542
}
```

- [ ] **Step 3: Create github_contributors.json**

Write `py/tokkit_benchmark/fixtures/github_contributors.json` — an array of 30 contributor objects. Each contributor has the full GitHub API structure (login, id, avatar_url, all the URL fields, contributions count). Generate 30 realistic entries with varying contribution counts (highest first: 2847, 412, 198, 156, ... down to single digits). Use realistic usernames.

The file should be ~12-15KB of JSON — the verbose GitHub API format with all URL fields is key to demonstrating compact_json savings.

- [ ] **Step 4: Create github_issues.json**

Write `py/tokkit_benchmark/fixtures/github_issues.json` — an array of 25 issue objects. Each issue has: id, number, title, state, user (full object with URLs), labels (array of label objects with id, name, color, description), created_at, updated_at, comments count, body (1-3 sentences). Mix of open/closed states, various labels like "bug", "enhancement", "question", "documentation".

The file should be ~15-20KB of JSON.

- [ ] **Step 5: Create fastapi_docs.html**

Copy the existing fixture: `cp tests/e2e/benchmark/fixtures/html/python_docs.html py/tokkit_benchmark/fixtures/fastapi_docs.html`

This is a 14KB HTML documentation page — realistic for web research. The benchmark measures token reduction, not the specific content.

- [ ] **Step 6: Commit**

```bash
git add py/tokkit_benchmark/fixtures/
git commit -m "feat: add benchmark fixture files for showcase"
```

---

### Task 2: Implement the benchmark script

**Files:**
- Create: `py/tokkit_benchmark/__init__.py`
- Create: `py/tokkit_benchmark/__main__.py`
- Create: `py/tokkit_benchmark/main.py`

- [ ] **Step 1: Create __init__.py and __main__.py**

Write `py/tokkit_benchmark/__init__.py` (empty file).

Write `py/tokkit_benchmark/__main__.py`:

```python
from tokkit_benchmark.main import main

main()
```

- [ ] **Step 2: Write main.py — constants and helpers**

Write `py/tokkit_benchmark/main.py`:

```python
"""Showcase benchmark: Evaluate FastAPI for adoption."""

import json
import os
import subprocess
import sys
from pathlib import Path

CHARS_PER_TOKEN = 4
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CACHE_DIR = Path(__file__).parent.parent.parent / "tests" / "e2e" / "benchmark" / ".cache"
REPO_URL = "https://github.com/fastapi/fastapi.git"
REPO_TAG = "0.115.6"


def _tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _fmt(n: int) -> str:
    """Format token count with comma separator and 'tok' suffix."""
    return f"{n:,} tok"


def _ensure_repo() -> str:
    """Clone FastAPI repo if not cached. Returns repo path."""
    repo_path = CACHE_DIR / "fastapi"
    if repo_path.exists() and (repo_path / "fastapi").is_dir():
        return str(repo_path)

    print(f"  Cloning FastAPI {REPO_TAG} (first run only)...")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", REPO_TAG, REPO_URL, str(repo_path)],
        capture_output=True,
        check=True,
    )
    return str(repo_path)


def _db_path_for(repo_path: str) -> str:
    project = Path(repo_path).resolve().name
    cache = os.environ.get("TOKKIT_CACHE_DIR", "/tmp/tokkit")
    return str(Path(cache) / f"{project}.redb")


# ---------------------------------------------------------------------------
# Phase 1: Code Analysis
# ---------------------------------------------------------------------------

def _baseline_architecture(repo_path: str) -> int:
    """Baseline: read all Python files in fastapi/ to understand architecture."""
    total = 0
    src_dir = Path(repo_path) / "fastapi"
    for py_file in src_dir.rglob("*.py"):
        try:
            total += py_file.stat().st_size
        except OSError:
            pass
    return total // CHARS_PER_TOKEN


def _baseline_route_handlers(repo_path: str) -> int:
    """Baseline: grep for router decorators, read matching files."""
    total = 0
    seen = set()
    src_dir = Path(repo_path) / "fastapi"
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue
        if "router" in content.lower() or "@app." in content or "APIRouter" in content:
            if py_file not in seen:
                seen.add(py_file)
                total += len(content)
    return total // CHARS_PER_TOKEN


def _baseline_security(repo_path: str) -> int:
    """Baseline: read security-related files to understand auth."""
    total = 0
    src_dir = Path(repo_path) / "fastapi"
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
        except OSError:
            continue
        if "security" in str(py_file).lower() or "Security" in content or "OAuth" in content:
            total += len(content)
    return total // CHARS_PER_TOKEN


def _tokkit_code_analysis(repo_path: str) -> list[tuple[str, int]]:
    """Run tokkit code analysis and return (task_name, tokens) for each sub-task."""
    import tokkit_py

    db_path = _db_path_for(repo_path)

    # Index
    tokkit_py.index_repository(repo_path, "full")

    # Task 1: Architecture
    arch = tokkit_py.get_architecture(db_path, "")
    arch_tokens = _tokens(arch)

    # Task 2: Route handlers
    routes = tokkit_py.search_nodes(db_path, "router", label="Function", limit=20)
    routes_tokens = _tokens(routes)

    # Task 3: Security — search + snippets
    security_nodes = tokkit_py.search_nodes(db_path, "Security", limit=10)
    security_tokens = _tokens(security_nodes)
    # Get snippets for top 2 results
    try:
        nodes = json.loads(security_nodes)
        for node in nodes[:2]:
            qn = node.get("qualified_name", "")
            if qn:
                snippet = tokkit_py.get_snippet(db_path, qn, repo_path, context_lines=0)
                security_tokens += _tokens(snippet)
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return [
        ("Understand architecture", arch_tokens),
        ("Find route handlers", routes_tokens),
        ("Read security logic", security_tokens),
    ]


# ---------------------------------------------------------------------------
# Phase 2: Web Research
# ---------------------------------------------------------------------------

def _phase2_web_research() -> list[tuple[str, int, int]]:
    """Returns list of (task_name, baseline_tokens, tokkit_tokens)."""
    from tokkit_scraper import clean_html

    html = (FIXTURES_DIR / "fastapi_docs.html").read_text()
    baseline = _tokens(html)

    cleaned = clean_html(html, mode="markdown")
    tokkit = _tokens(cleaned)

    return [("FastAPI docs page", baseline, tokkit)]


# ---------------------------------------------------------------------------
# Phase 3: Project Health
# ---------------------------------------------------------------------------

def _phase3_project_health() -> list[tuple[str, int, int]]:
    """Returns list of (task_name, baseline_tokens, tokkit_tokens)."""
    from tokkit_json import compact_json

    results = []
    for name, filename in [
        ("GitHub repo metadata", "github_repo.json"),
        ("Contributors list", "github_contributors.json"),
        ("Recent issues", "github_issues.json"),
    ]:
        raw = (FIXTURES_DIR / filename).read_text()
        baseline = _tokens(raw)
        compacted = compact_json(raw)
        tokkit = _tokens(compacted)
        results.append((name, baseline, tokkit))

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _print_phase(title: str, rows: list[tuple[str, int, int]]) -> tuple[int, int]:
    """Print a phase table. Returns (total_baseline, total_tokkit)."""
    print(f"\n  Phase: {title}")
    print(f"  {'Task':<30} {'Without':>12} {'With':>12} {'Saved':>8}")
    print(f"  {'─' * 30} {'─' * 12} {'─' * 12} {'─' * 8}")

    phase_baseline = 0
    phase_tokkit = 0
    for task_name, baseline, tokkit in rows:
        saved = (1 - tokkit / baseline) * 100 if baseline > 0 else 0
        print(f"  {task_name:<30} {_fmt(baseline):>12} {_fmt(tokkit):>12} {saved:>7.1f}%")
        phase_baseline += baseline
        phase_tokkit += tokkit

    print(f"  {'─' * 30} {'─' * 12} {'─' * 12} {'─' * 8}")
    saved = (1 - phase_tokkit / phase_baseline) * 100 if phase_baseline > 0 else 0
    print(f"  {'Subtotal':<30} {_fmt(phase_baseline):>12} {_fmt(phase_tokkit):>12} {saved:>7.1f}%")

    return phase_baseline, phase_tokkit


def main() -> None:
    print()
    print("═" * 62)
    print('  tokkit benchmark — "Evaluate FastAPI for adoption"')
    print("═" * 62)

    # Phase 1: Code Analysis
    repo_path = _ensure_repo()
    code_results = _tokkit_code_analysis(repo_path)
    baselines = [
        _baseline_architecture(repo_path),
        _baseline_route_handlers(repo_path),
        _baseline_security(repo_path),
    ]
    phase1_rows = [
        (name, bl, tk) for (name, tk), bl in zip(code_results, baselines)
    ]
    total_bl, total_tk = _print_phase("Code Analysis", phase1_rows)

    # Phase 2: Web Research
    phase2_rows = _phase2_web_research()
    p2_bl, p2_tk = _print_phase("Web Research", phase2_rows)
    total_bl += p2_bl
    total_tk += p2_tk

    # Phase 3: Project Health
    phase3_rows = _phase3_project_health()
    p3_bl, p3_tk = _print_phase("Project Health", phase3_rows)
    total_bl += p3_bl
    total_tk += p3_tk

    # Grand total
    saved = (1 - total_tk / total_bl) * 100 if total_bl > 0 else 0
    print()
    print("═" * 62)
    print(f"  {'TOTAL':<30} {_fmt(total_bl):>12} {_fmt(total_tk):>12} {saved:>7.1f}%")
    print("═" * 62)
    print()
```

- [ ] **Step 3: Verify it runs**

Run: `cd /home/edge/code/tokkit && /home/edge/code/.venv/bin/python -m tokkit_benchmark`

Expected: The benchmark runs all three phases and prints the formatted report to stdout. First run will clone FastAPI (~10s). Numbers should show significant savings across all phases.

- [ ] **Step 4: Commit**

```bash
git add py/tokkit_benchmark/
git commit -m "feat: showcase benchmark — evaluate FastAPI for adoption"
```

---

### Task 3: Add CLI subcommand

**Files:**
- Modify: `py/tokkit_cli/main.py`

- [ ] **Step 1: Add benchmark subcommand to CLI**

In `py/tokkit_cli/main.py`, add a handler for the `benchmark` command. Add this block after the `init` handler:

```python
    if argv[0] == "benchmark":
        from tokkit_benchmark.main import main as benchmark_main
        benchmark_main()
        return
```

And update the `--help` output to include:

```python
        print("  tokkit benchmark    Run showcase benchmark")
```

Add this line after the `tokkit init` help line.

- [ ] **Step 2: Verify CLI subcommand works**

Run: `tokkit benchmark`
Expected: Same output as `python -m tokkit_benchmark`

- [ ] **Step 3: Commit**

```bash
git add py/tokkit_cli/main.py
git commit -m "feat: add 'tokkit benchmark' CLI subcommand"
```

---

### Task 4: Run and verify end-to-end

- [ ] **Step 1: Run the full benchmark**

Run: `/home/edge/code/.venv/bin/python -m tokkit_benchmark`

Expected output: A formatted table showing three phases with token counts and savings percentages. All savings should be positive:
- Phase 1 (Code Analysis): ~90-97% savings
- Phase 2 (Web Research): ~70-85% savings
- Phase 3 (Project Health): ~50-70% savings
- Total: ~80-90% savings

- [ ] **Step 2: Verify `tokkit benchmark` CLI also works**

Run: `/home/edge/code/.venv/bin/tokkit benchmark`
Expected: Same output.

- [ ] **Step 3: Fix any issues and commit**

If any numbers look wrong or formatting is off, fix and commit:
```bash
git add -A
git commit -m "fix: benchmark adjustments"
```
