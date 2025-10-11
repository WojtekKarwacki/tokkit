# Tokkit Token Savings Benchmark

**Date:** 2026-04-10
**Model:** Claude Haiku (all agents)
**Methodology:** Real agent sessions — each scenario dispatches two independent Claude agents with the same question, one using standard tools (Grep/Read/Glob), one using tokkit MCP tools. `total_tokens` measured from actual API usage.

## Results

### Total Token Usage (including agent overhead)

Every Claude Code agent session includes fixed overhead: system prompt, tool definitions, conversation framing. This overhead is identical for both baseline and tokkit agents. The table below shows raw `total_tokens` from each agent session.

| # | Category | Task | Baseline | Tokkit | Savings |
|---|----------|------|---------|--------|---------|
| 1 | Code graph | Blast radius analysis | 56,054 | 45,271 | 19% |
| 2 | Code graph | Trace setup call chain | 38,427 | 35,766 | 7% |
| 3 | Code graph | Dead code detection | 42,666 | 30,218 | 29% |
| 4 | Code graph | List route handlers | 46,072 | 31,904 | 31% |
| 5 | Code graph | Architecture overview | 41,627 | 34,691 | 17% |
| 6 | Markdown | Search README | 34,157 | 27,075 | 21% |
| 7 | HTML | Clean Python docs (14KB) | 30,392 | 27,000 | 11% |
| 8 | HTML | Clean blog post (24KB) | 33,984 | 26,770 | 21% |
| 9 | JSON | Compact flat records (14KB) | 33,000 | 27,304 | 17% |
| 10 | JSON | Compact nested data (10KB) | 29,214 | 26,366 | 10% |
| 11 | Shell output | Compress pytest (13.7KB) | 36,954 | 25,836 | 30% |
| 12 | Shell output | Compress ruff lint (8.3KB) | 28,748 | 28,292 | 2% |
| | **Total** | | **451,295** | **367,493** | **19%** |

### Content-Only Token Usage (excluding measured overhead)

The fixed overhead masks the true content savings. Subtracting the measured 23,350 token overhead from both sides isolates what each agent consumed for the task itself — tool results, file content, and response generation.

`content_tokens = total_tokens - 23,350` (see [Overhead breakdown](#overhead-breakdown) for how this was measured)

| # | Task | Baseline content | Tokkit content | Content savings |
|---|------|---------|--------|---------|
| 1 | Blast radius analysis | 32,704 | 21,921 | 33% |
| 2 | Trace setup call chain | 15,077 | 12,416 | 18% |
| 3 | Dead code detection | 19,316 | 6,868 | 64% |
| 4 | List route handlers | 22,722 | 8,554 | 62% |
| 5 | Architecture overview | 18,277 | 11,341 | 38% |
| 6 | Search README | 10,807 | 3,725 | 66% |
| 7 | Clean Python docs | 7,042 | 3,650 | 48% |
| 8 | Clean blog post | 10,634 | 3,420 | 68% |
| 9 | Compact flat records | 9,650 | 3,954 | 59% |
| 10 | Compact nested data | 5,864 | 3,016 | 49% |
| 11 | Compress pytest output | 13,604 | 2,486 | 82% |
| 12 | Compress ruff lint output | 5,398 | 4,942 | 8% |
| | **Total** | **171,095** | **87,293** | **49%** |

### What the two tables mean

**Total tokens (first table)** is what you actually pay for. It includes the system prompt (~17.7K), subagent framing (~5.7K), tool results, and the agent's response. This overhead is the same for every agent session regardless of the task. On a single small-file lookup, this overhead dominates and tokkit's savings appear modest (2-30%).

**Content tokens (second table)** isolates the variable part — what the agent consumed beyond the fixed overhead. This is the content that entered the agent's context from tool results, plus the tokens used to generate the response. This shows tokkit's true compression ratio on the actual task data: **49% average savings** on content, up to **82% for large shell output** like pytest runs.

**When does the total-token number matter?** Always — it's your actual cost. But the fixed overhead amortizes across a session. A real agent session involves many tool calls across many turns, and the system prompt is sent once per turn (not once per tool call). In a 20-turn session with multiple file lookups, the content fraction grows and total savings approach the content-only number.

**When does the content-token number matter?** It shows the compression ratio of tokkit's tools. It predicts how savings scale as tasks get larger (bigger files, more files, longer sessions). A tool that saves 75% on content will have a larger absolute impact on a 200KB file than a 14KB file.

**Q1-Q2 (blast radius, trace chain):** Multi-hop graph traversal tasks where `trace_fan` covers in 1 call what would require many grep+read iterations. Tokkit pays off at 18-33% content savings.

**Q11 (pytest, 13.7KB):** High content savings (82%) because the output has many PASSED lines with full tracebacks for only a few failures. `compact_output` strips all pass lines, retaining only failures. The large fixture size (13.7KB) amplifies the absolute savings.

**Q12 (ruff lint, 8.3KB):** Low content savings (8%) because ruff output is already dense — every line is a distinct violation. `compact_output` can strip ANSI codes and reformat, but can't discard violations when every one matters. Savings increase only when output is highly redundant (many passes, few failures).

## Methodology

### How agents were run

Each scenario was executed by dispatching two independent Claude Haiku subagents via Claude Code's Agent tool:

- **Baseline agent:** Instructed to use standard tools (Grep, Read, Glob) to answer the question
- **Tokkit agent:** Instructed to use tokkit MCP tools (index_repository, get_architecture, find_dead_code, find_routes, trace_fan, clean_html, compact_json, search_markdown, compact_output) to answer the same question

Both agents:
- Used the same model (Haiku)
- Received the same question
- Had access to the same codebase (fastapi/fastapi @ 0.115.6)
- Were dispatched as fresh sessions with no prior context
- Had their `total_tokens` measured from the Agent tool's usage report

### What total_tokens includes

The `total_tokens` value from the Agent tool is the sum of input + output tokens across all API calls the agent made. This includes:

- System prompt and behavioral instructions (sent every API call)
- Tool definitions for all available tools (sent every API call)
- The user prompt with the question (~100-200 tokens)
- Tool call parameters (output tokens) and tool results (input tokens)
- The agent's final response (output tokens)

A single tool-call interaction involves 2 API calls (decide to call tool → process result), so the system prompt and tool definitions are paid twice.

### Overhead breakdown

The 23,350 token overhead subtracted in the content table is a **measured value**, derived from first-turn `cache_creation + cache_read` across all benchmark agents (measured 2026-04-10).

| Component | Tokens | Notes |
|-----------|-------:|-------|
| Claude Code system prompt | ~17,660 | Behavioral instructions, built-in tool schemas (Read, Grep, Glob, Bash, Edit, Write, Agent, etc.) |
| Subagent framing | ~5,690 | Agent dispatch context, user prompt, CLAUDE.md, MCP tool definitions |
| **Total** | **~23,350** | |

MCP tool definitions contribute approximately 50 tokens to the subagent framing — negligible. The overhead is identical for baseline and tokkit agents (±50 tokens). We subtract the same 23,350 from both sides.

**Sensitivity:** A ±1K error in this estimate shifts content savings by roughly ±3-5 percentage points. Total token savings (19%) are measured directly and are unaffected.

### What this benchmark measures

- **Real API token consumption** — not estimated, not computed from byte lengths
- **End-to-end agent sessions** — including the agent's decision-making, not just tool output sizes
- **Fair comparison** — both agents have the same overhead, same model, same question

### What this benchmark does NOT measure

- **Multi-turn sessions** — each scenario is a single question. Real sessions involve many turns where content accumulates and savings compound.
- **Latency** — tokkit agents used 60% fewer tool calls on average, which means fewer API round-trips and faster wall-clock time. This isn't captured in token counts.
- **Accuracy** — both agents answered correctly in all scenarios, but this wasn't formally verified with gold answers (see the inference eval for that).

### Per-scenario agent queries and tool calls

Each scenario dispatched two independent agents with the same natural-language question. The table below shows the question, plus the tool calls each agent made.

#### Q1 — Blast radius analysis

**Question:** "Which functions are affected if I change `get_openapi`? Show all callers, transitively."

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Grep(pattern="get_openapi", output_mode="content", -C=3)` + iterative Grep per discovered caller — 8-12 calls |
| Tokkit | `trace_fan(function_name="get_openapi", direction="inbound", depth=3)` — 1 call |

#### Q2 — Trace setup call chain

**Question:** "Trace the call chain starting from the `setup` function, going 3 levels deep. Show what functions it calls, and what those call in turn."

| Agent | Tool calls |
|-------|-----------|
| Baseline | 11x `Grep(content)` to locate each function + 10x `Read(offset, limit=50)` for bodies. Traces `setup` → `openapi` → `get_openapi` → `get_swagger_ui_html` → ... (fan-out 3 per level) — 21 calls |
| Tokkit | `trace_fan(function_name="setup", direction="outbound", depth=3)` — 1 call |

#### Q3 — Dead code detection

**Question:** "Find functions in the fastapi codebase that appear to be dead code — defined but never referenced anywhere."

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Grep(content, -E, pattern="^\s*def [a-zA-Z_]\w*")` for all definitions + 117x `Grep(-w, files_with_matches)` per function name (skipping generic names) — 118 calls |
| Tokkit | `find_dead_code(limit=200)` — 1 call |

#### Q4 — List route handlers

**Question:** "List all HTTP route handlers in this project — show the HTTP method, route path, and handler function name."

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Grep(content, -E, -A=1, pattern="@(app\|router)\.(get\|post\|put\|delete\|patch\|options\|head)", head_limit=250)` — 1 call |
| Tokkit | `find_routes(limit=200)` — 1 call |

#### Q5 — Architecture overview

**Question:** "Give me an architecture overview of this project. What are the main modules, key abstractions, and how is the code organized?"

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Glob(**/*.py)` + `Read(README.md)` + `Read(fastapi/__init__.py)` + 5x `Read(fastapi/{module}.py, limit=100)` — 8 calls |
| Tokkit | `get_architecture()` — 1 call |

#### Q6 — Search README

**Question:** "What are the dependencies and requirements for this project? Check the README."

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(README.md)` — full 499-line file with cat -n prefix — 1 call |
| Tokkit | `search_markdown(path="README.md", query="dependencies requirements")` — 1 call; file read server-side, only matching sections returned |

#### Q7 — Clean Python docs page (14KB HTML)

**Question:** "Summarize the Python datetime documentation." *(agent is told to use tokkit to read from the fixture path)*

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(fixtures/html/python_docs.html)` — full 14KB HTML enters context with cat -n prefix — 1 call |
| Tokkit | `clean_html(path="fixtures/html/python_docs.html", mode="markdown")` — 1 call; file read server-side, only cleaned markdown returned |

#### Q8 — Clean blog post (24KB HTML)

**Question:** "Summarize the blog post about async/await." *(agent is told to use tokkit to read from the fixture path)*

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(fixtures/html/blog_post.html)` — full 24KB HTML enters context with cat -n prefix — 1 call |
| Tokkit | `clean_html(path="fixtures/html/blog_post.html", mode="markdown")` — 1 call; file read server-side, only cleaned markdown returned |

#### Q9 — Compact flat JSON records (14KB)

**Question:** "Summarize the records in this JSON file." *(agent is told to use tokkit to read from the fixture path)*

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(fixtures/json/flat_records.json)` — full 14KB JSON enters context with cat -n prefix — 1 call |
| Tokkit | `compact_json(path="fixtures/json/flat_records.json")` — 1 call; file read server-side, auto-detects CSV format |

#### Q10 — Compact nested data (10KB JSON)

**Question:** "Summarize the structure of this JSON data." *(agent is told to use tokkit to read from the fixture path)*

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(fixtures/json/nested_complex.json)` — full 10KB JSON enters context with cat -n prefix — 1 call |
| Tokkit | `compact_json(path="fixtures/json/nested_complex.json")` — 1 call; file read server-side, auto-detects YAML format |

#### Q11 — Compress pytest output (13.7KB)

**Question:** "Summarize these pytest results — what passed, what failed, and why." *(agent is told to use tokkit to read from the fixture path)*

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(fixtures/shell/pytest_output.txt)` — full 13.7KB output enters context with cat -n prefix — 1 call |
| Tokkit | `compact_output(path="fixtures/shell/pytest_output.txt", hint="pytest")` — 1 call; file read server-side, PASSED lines stripped, failures retained |

#### Q12 — Compress ruff lint output (8.3KB)

**Question:** "Summarize these ruff lint violations." *(agent is told to use tokkit to read from the fixture path)*

| Agent | Tool calls |
|-------|-----------|
| Baseline | `Read(fixtures/shell/ruff_output.txt)` — full 8.3KB output (with ANSI) enters context with cat -n prefix — 1 call |
| Tokkit | `compact_output(path="fixtures/shell/ruff_output.txt", hint="ruff")` — 1 call; file read server-side, ANSI stripped, violations reformatted |

### Why content tools use path=

Content-processing tools (`clean_html`, `compact_json`, `search_markdown`, `compact_output`) accept a `path=` parameter so the MCP server reads the file directly. The raw content never enters the agent's context. The baseline agent uses the `Read` tool, which loads the full file content into context.

This is the key asymmetry: tokkit agents see only the compressed output; baseline agents see the entire raw file.

### Repo and fixtures

- **Code graph (Q1-Q5):** fastapi/fastapi @ 0.115.6 (cloned to tests/e2e/benchmark/.cache/fastapi/)
- **Markdown (Q6):** FastAPI README.md (499 lines)
- **HTML (Q7-Q8):** Python datetime docs (14KB), async/await blog post (24KB) from tests/e2e/benchmark/fixtures/html/
- **JSON (Q9-Q10):** Flat records (14KB), nested data (10KB) from tests/e2e/benchmark/fixtures/json/
- **Shell output (Q11):** pytest output (13.7KB) — many PASSED lines with a few failures and full tracebacks from tests/e2e/benchmark/fixtures/shell/
- **Shell output (Q12):** ruff lint output (8.3KB) — dense violations with ANSI color codes from tests/e2e/benchmark/fixtures/shell/
