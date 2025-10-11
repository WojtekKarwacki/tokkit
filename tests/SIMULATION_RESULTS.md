# Tokkit Token Savings Simulation

**Type:** Content-size comparison (NOT real agent measurements)
**Repo:** fastapi/fastapi @ `0.115.6`
**Date:** 2026-04-11
**Baselines:** measured grep/read output sizes

| # | Question | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |
|---|----------|----------------:|------------------:|----------:|------:|
| 1 | Dead code detection | 0 | 66,791 | 100.0% | 0x |
| 2 | List all routes | 1,201 | 5,702 | 78.9% | 5x |
| 3 | Architecture overview | 5,785 | 25,606 | 77.4% | 4x |
| 4 | Search markdown documentation | 1,312 | 6,924 | 81.1% | 5x |
| 5 | Compress pytest output | 48 | 1,002 | 95.2% | 21x |
| 6 | Compress lint output | 1,251 | 2,006 | 37.6% | 2x |
| | **Total** | **9,597** | **108,031** | **91.1%** | **11x** |

## Methodology

### Baseline accuracy

Baselines are **measured grep/read output sizes** for the default repo (fastapi @ 0.115.6).
Each baseline was obtained by running grep/read commands directly (not through an agent)
and counting the raw bytes of the output. These are NOT agent `total_tokens`.
The tool call sequences modeled are:

- Q1 (dead code): 1 Grep for definitions (250 lines) + 117 word-boundary reference greps
- Q2 (routes): 1 Grep call (content, -A=1) for route decorators, head_limit=250
- Q3 (architecture): 1 Glob + 1 Read README + 1 Read `__init__.py` + 5 Read (100 lines each)
- Q4 (markdown): 1 Read(README.md) — full 499-line file with cat -n prefix
- Q5 (pytest): raw output byte count (agent reads as-is)
- Q6 (lint): raw output byte count with ANSI codes (agent reads as-is)

### What the baselines measure

The **Baseline** column represents the minimum tokens a skilled Claude Code
agent would consume to answer each question, assuming optimal tool usage.
These are intentionally **optimistic for Claude Code** (conservative for tokkit),
meaning the true savings in practice are likely higher.

Optimistic assumptions applied to all baselines:

- **Grep content mode** — agent uses `output_mode="content"` to get matching
  lines directly, instead of `files_with_matches` followed by full file reads
- **Grep head_limit=250** — Claude Code caps Grep results at 250 lines by default,
  naturally limiting output size
- **Targeted Read with offset/limit** — agent reads ~50-line function bodies
  instead of entire files when tracing code
- **Read tool overhead** — each line gets ~8 bytes of `cat -n` line-number prefix
  that enters the context window
- **Core-module scoping** — agent focuses on `fastapi/` source code, not
  tests, docs, or examples (1,200+ files ignored)
- **Selective call tracing** — agent follows 3 calls per function level,
  not every function-call-like pattern in the file
- **Word-boundary matching** — reference greps use `-w` (whole word) to avoid
  substring false positives; generic names (get, set, post, etc.) are skipped

A real Claude Code agent would often consume **more** tokens through:

- Reading full files instead of targeted sections (Read defaults to 2,000 lines)
- Multiple iterative grep searches to refine results
- Reading README, config files, and other supporting context
- Trial-and-error exploration before finding the right approach
- Re-reading files across conversation turns as context compresses

### Per-question agent strategy

| # | Question | Optimistic Claude Code strategy |
|---|----------|--------------------------------|
| 1 | Dead code | `Grep(content)` definitions in core module only. Word-boundary `Grep(-w, files_with_matches)` per function. Skips generic/short names. |
| 2 | List routes | `Grep(content, -A=1)` for route decorators. Decorator lines ARE the answer. No file reads. |
| 3 | Architecture | `Glob` file listing + `Read` README + core `__init__.py` + first 100 lines of 5 key modules. |
| 4 | Search markdown | `Read(README.md)` — full file with cat -n overhead. Minimum: one Read call on the file containing the answer. |
| 5 | Compress pytest | Raw pytest output enters context as-is. Agent reads and summarizes. |
| 6 | Compress lint | Raw ruff output enters context as-is (with ANSI codes). Agent reads and summarizes. |

### Token estimation

Both columns use `len(bytes) / 4` (Anthropic's published approximation
for English text). For Python source code, the actual ratio is closer to 3.0-3.5
chars/token, meaning absolute numbers slightly understate true token consumption.
Since both paths use the same constant, **savings percentages and ratios are unaffected**.

### Agent overhead (not included)

These numbers measure **content tokens only** — the tool result payloads.
Every agent session also pays fixed infrastructure overhead: ~27K tokens for
baseline agents, ~32K for tokkit agents (extra MCP tool definitions). This
overhead is not captured here. Real-world total savings are significantly
lower than these content ratios. For real agent measurements, see `BENCHMARK_RESULTS.md`.

### What this simulation is NOT

- NOT real agent measurements — no model inference, no API calls
- NOT total token counts — only tool output sizes
- NOT counting agent overhead, reasoning, or decision-making tokens
- NOT measuring accuracy — only content compression ratios
