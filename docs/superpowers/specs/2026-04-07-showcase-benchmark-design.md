# Showcase Benchmark Design

**Date:** 2026-04-07
**Status:** Approved
**Goal:** Standalone benchmark script that runs a realistic "evaluate a library for adoption" scenario with and without tokkit, measuring token savings per feature, printing a formatted report.

---

## 1. The Scenario

Simulates an agent evaluating FastAPI for adoption. Three phases map to tokkit's three main features.

### Phase 1 — Code Analysis ("Understand the architecture")

- **Without tokkit:** Read full source files that an agent would grep/open to understand the codebase. Sum their sizes as baseline tokens.
- **With tokkit:** `index_repository`, `get_architecture`, `search_graph("router")`, `get_code_snippet` for 2-3 key functions. Sum response sizes as tokkit tokens.

Tasks:
1. Understand architecture — baseline: read all Python files in `fastapi/` dir; tokkit: `get_architecture`
2. Find route handlers — baseline: grep for `@router` and read matching files; tokkit: `search_graph("router", label="Function")`
3. Read authentication logic — baseline: read `security/` files; tokkit: `search_graph("Security")` + `get_code_snippet` for top results

### Phase 2 — Web Research ("What do people think?")

- **Without tokkit:** Raw HTML passed to LLM context.
- **With tokkit:** `clean_html(html, mode="markdown")`.

Tasks:
1. FastAPI docs page — cached HTML fixture (~20KB), clean to markdown

### Phase 3 — Project Health ("Is it actively maintained?")

- **Without tokkit:** Raw JSON passed to LLM context.
- **With tokkit:** `compact_json(json_str)`.

Tasks:
1. GitHub repo metadata — cached JSON fixture (repo info endpoint)
2. Contributors list — cached JSON fixture (top 30 contributors)
3. Recent issues — cached JSON fixture (25 recent issues with labels/comments)

## 2. Fixtures

All fixtures are cached files — no network required at runtime.

**Code analysis:** FastAPI repo cloned to `tests/e2e/benchmark/.cache/fastapi/` (already exists from current benchmarks). If not present, the benchmark clones it.

**Web research:** One HTML file. Reuse `tests/e2e/benchmark/fixtures/html/python_docs.html` (already 14KB) or add a new FastAPI docs page.

**JSON processing:** Three JSON files in a new `py/tokkit_benchmark/fixtures/` directory:
- `github_repo.json` — GitHub API `/repos/fastapi/fastapi` response
- `github_contributors.json` — GitHub API `/repos/fastapi/fastapi/contributors?per_page=30`
- `github_issues.json` — GitHub API `/repos/fastapi/fastapi/issues?per_page=25&state=all`

These are static snapshots — fetched once during development, committed as fixtures.

## 3. Token Counting

`len(text) / 4` — chars-per-token estimate, consistent with `token_stats.py::CHARS_PER_TOKEN`.

## 4. Report Format

```
══════════════════════════════════════════════════════════
  tokkit benchmark — "Evaluate FastAPI for adoption"
══════════════════════════════════════════════════════════

Phase 1: Code Analysis
  Task                        Without     With      Saved
  ─────────────────────────── ────────── ───────── ──────
  Understand architecture     42,150 tok  1,230 tok  97.1%
  Find route handlers          8,400 tok    380 tok  95.5%
  Read authentication logic   12,300 tok    620 tok  95.0%
  ─────────────────────────── ────────── ───────── ──────
  Subtotal                    62,850 tok  2,230 tok  96.5%

Phase 2: Web Research
  Task                        Without     With      Saved
  ─────────────────────────── ────────── ───────── ──────
  FastAPI docs page           18,200 tok  3,100 tok  83.0%
  ─────────────────────────── ────────── ───────── ──────
  Subtotal                    18,200 tok  3,100 tok  83.0%

Phase 3: Project Health
  Task                        Without     With      Saved
  ─────────────────────────── ────────── ───────── ──────
  GitHub repo metadata         2,400 tok    850 tok  64.6%
  Contributors list            8,100 tok  2,300 tok  71.6%
  Recent issues                6,500 tok  2,100 tok  67.7%
  ─────────────────────────── ────────── ───────── ──────
  Subtotal                    17,000 tok  5,250 tok  69.1%

══════════════════════════════════════════════════════════
  TOTAL                       98,050 tok 10,580 tok  89.2%
══════════════════════════════════════════════════════════
```

Printed to stdout. No file output unless `--output report.md` flag is passed.

## 5. Entry Points

- `python -m tokkit_benchmark` — standalone, no pytest needed
- `tokkit benchmark` — added as subcommand to CLI

Both run the same code.

## 6. File Structure

```
py/tokkit_benchmark/
├── __init__.py
├── __main__.py          # python -m tokkit_benchmark entry
├── main.py              # benchmark logic + report formatting
└── fixtures/
    ├── fastapi_docs.html
    ├── github_repo.json
    ├── github_contributors.json
    └── github_issues.json
```

## 7. Dependencies

- `tokkit_py` (Rust extension) — for code analysis
- `tokkit_scraper` — for HTML cleaning
- `tokkit_json` — for JSON compaction
- FastAPI repo on disk (cloned if needed)

No new external dependencies.

## 8. What's NOT in Scope

- Comparison against other tools (just with vs without tokkit)
- LLM-in-the-loop (no actual API calls — just measures token sizes)
- Accuracy measurement (this measures efficiency, not correctness)
- Interactive mode or TUI
