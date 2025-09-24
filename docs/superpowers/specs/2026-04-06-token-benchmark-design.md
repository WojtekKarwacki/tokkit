# Token Savings Benchmark - Design Spec

## Goal

A reproducible, CI-friendly benchmark that measures real token savings from tokkit graph queries vs simulated agent file exploration. Runs against a real open-source repo (fastapi/fastapi) pinned to a specific commit. Produces a Markdown report tracking savings over time.

## Background

The upstream project (codebase-memory-mcp) claims "120x fewer tokens" / "99.2% reduction" based on 5 structural questions. The claim links to a non-existent `BENCHMARK_REPORT.md` and has no reproducible methodology. Tokkit's own `token_stats.py` uses inflated theoretical estimates (e.g. summing all source file sizes for `get_architecture`).

This benchmark replaces both with honest, reproducible numbers.

## Target Repo

**fastapi/fastapi** pinned at a specific commit SHA.

- Pure Python, ~200 source files
- Well-structured: models, routing, dependencies, middleware
- Has decorators/routes that exercise the HANDLES edge detection
- Stable, well-known - credible for marketing

The SHA is a constant in the benchmark config. Updated manually when needed.

## The 5 Questions

These match the original codebase-memory-mcp benchmark exactly:

| # | Question | Tokkit tool | What it tests |
|---|----------|-------------|---------------|
| 1 | Find function by pattern | `search_graph(name_pattern="Depends.*")` | Graph search vs grep + file reads |
| 2 | Trace call chain (depth 3) | `trace_path(function_name=..., direction="outbound", depth=3)` | Graph traversal vs manual hop-by-hop |
| 3 | Dead code detection | `search_graph(max_degree=0, exclude_entry_points=true)` | Degree filtering vs brute-force cross-reference |
| 4 | List all routes | `search_graph(relationship="HANDLES")` | Edge-type filtering vs decorator grep |
| 5 | Architecture overview | `get_architecture` | Summarized graph vs reading tree + key files |

## Token Counting

`len(content_bytes) // 4` (CHARS_PER_TOKEN = 4).

Applied identically to both tokkit responses and baseline file reads. The ratio is fair regardless of the constant's accuracy. What matters is the relative comparison, not the absolute token count.

## Measurement: Tokkit Path

For each question, call the tokkit MCP server via the existing `McpClient` (JSON-RPC over stdio). Measure `len(response_content_text)` from the tool result. This is the actual bytes that would enter an LLM's context window.

The MCP server is started once per benchmark run. The repo is indexed once before all questions.

## Measurement: Baseline Path (Simulated Agent)

For each question, execute the file operations an agent without tokkit would perform. Accumulate every byte of file content that would enter the agent's context window.

### Baseline 1: Find function by pattern

1. `grep -rl "def Depends"` across the repo (count: grep output bytes)
2. For each matching file: `open(f).read()` (count: full file content bytes)
3. Total = grep output + all file contents

Rationale: an agent using Grep gets file paths, then uses Read to examine each match. Read returns the entire file.

### Baseline 2: Trace call chain (depth 3)

1. Grep for the starting function name to find its file
2. Read the starting file (count bytes)
3. Parse the function body for call targets (simple regex: `\b(\w+)\(`)
4. For each call target at depth < 3:
   - Grep for `def {target}` to find its file
   - Read that file (count bytes)
   - Extract its call targets, recurse
5. Total = all grep outputs + all file reads

Rationale: an agent traces calls by reading source, identifying calls, grepping for definitions, reading those files. Each hop requires at minimum a grep + file read.

### Baseline 3: Dead code detection

1. Read all `.py` files to collect every `def` name (count: all file bytes)
2. For each function name, grep the entire repo for references (count: grep output bytes)
3. Functions with zero references outside their definition = dead code
4. Total = all file reads (step 1) + all grep outputs (step 2)

Rationale: without a graph, dead code detection requires reading the entire codebase to find definitions, then cross-referencing each one. This is genuinely expensive.

### Baseline 4: List all routes

1. `grep -rn "@app\.\|@router\."` across the repo (count: grep output bytes)
2. For each matching file: `open(f).read()` (count: full file content bytes)
3. Total = grep output + all file contents

Rationale: an agent would grep for route decorators, then read each file to understand the handler.

### Baseline 5: Architecture overview

1. `glob("**/*.py")` to get the file tree (count: path listing bytes)
2. Read every `__init__.py` file (count: all content bytes)
3. Read every top-level module (files directly under `fastapi/`) (count: all content bytes)
4. Total = file listing + all init files + all top-level modules

Rationale: an agent understanding architecture would glob the structure, read package inits to understand exports, and read top-level modules to understand the entry points.

## New Tokkit Features Required

The following must be implemented before the benchmark can run all 5 questions:

### search_graph parameter additions

Current signature: `search_graph(query, label, limit)`

New params needed:
- `name_pattern` (str, optional) - regex filter on node name. Maps to SQL `WHERE name REGEXP ?`
- `max_degree` (int, optional) - filter nodes with outbound degree <= N. Requires computing degree from edges table
- `exclude_entry_points` (bool, optional, default false) - when true, exclude nodes that are likely entry points (e.g. `main`, `__init__`, test functions, route handlers). Heuristic: exclude nodes with `HANDLES` edges or names matching `main|__main__|test_*`
- `relationship` (str, optional) - filter to nodes that participate in edges of this type (e.g. "HANDLES" returns only nodes with HANDLES edges)

### trace_path signature change

Current signature: `trace_path(from, to, max_depth)`

New signature: `trace_path(function_name, direction, depth)`
- `function_name` (str) - starting node name or qualified name
- `direction` (str, enum: "inbound"/"outbound"/"both", default "both") - which edges to follow
- `depth` (int, default 3) - max hops

This is a breaking change from the current from/to point-to-point trace to a fan-out trace from a single starting point.

## Output Format

`BENCHMARK_RESULTS.md` in repo root, regenerated each CI run:

```markdown
# Tokkit Token Savings Benchmark

**Repo:** fastapi/fastapi @ `<commit-sha>`
**Date:** 2026-04-06
**Tokkit version:** 0.x.y

| # | Question | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |
|---|----------|----------------:|------------------:|----------:|------:|
| 1 | Find function by pattern | 180 | 42,000 | 99.6% | 233x |
| 2 | Trace call chain (depth 3) | 750 | 115,000 | 99.3% | 153x |
| 3 | Dead code detection | 480 | 78,000 | 99.4% | 163x |
| 4 | List all routes | 350 | 55,000 | 99.4% | 157x |
| 5 | Architecture overview | 1,200 | 95,000 | 98.7% | 79x |
| | **Total** | **2,960** | **385,000** | **99.2%** | **130x** |

*Token estimate: len(bytes) / 4. Both paths use the same constant.*
```

Numbers above are illustrative. Actual numbers will be determined by the benchmark run.

## File Structure

```
e2e/
  benchmark/
    __init__.py
    conftest.py          # clone + cache fastapi, start MCP server, shared fixtures
    baselines.py         # 5 baseline measurement functions
    test_benchmark.py    # 5 tokkit measurements, comparison, report generation
    config.py            # pinned commit SHA, repo URL, constants
```

## CI Integration

- Pytest marker: `@pytest.mark.benchmark`
- Separate from the fast e2e suite: `pytest e2e/benchmark/ -m benchmark`
- The fastapi clone is cached between runs (only cloned if missing or SHA changed)
- Index is rebuilt each run (fast, ~1-2 seconds for fastapi)
- Report is written to `BENCHMARK_RESULTS.md` at repo root
- CI can commit the updated report or post it as a PR comment

## Implementation Order

1. Implement `search_graph` parameter additions in Rust core + Python bindings
2. Implement `trace_path` signature change in Rust core + Python bindings
3. Update MCP server `tools.py` to pass new params through
4. Write `config.py` with pinned SHA
5. Write `conftest.py` with repo clone + MCP fixtures
6. Write `baselines.py` with 5 baseline functions
7. Write `test_benchmark.py` with 5 tokkit functions + report generation
8. Run benchmark, capture initial results
9. Update `BENCHMARK_RESULTS.md` with real numbers

## Success Criteria

- All 5 questions produce non-zero results on both paths
- Tokkit path returns fewer tokens than baseline for every question
- Total savings ratio is > 50x (conservative; likely much higher for dead code and trace)
- Benchmark completes in < 60 seconds (excluding repo clone)
- Results are deterministic across runs (same SHA = same numbers)
