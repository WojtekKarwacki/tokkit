"""Token savings simulation: content-size comparison, tokkit vs estimated baseline.

NOT a real agent benchmark — baselines are computed from grep/read output sizes,
not from actual agent sessions. For real agent measurements, see BENCHMARK_RESULTS.md.
"""

import json
import os
from datetime import date
from pathlib import Path

import pytest

from e2e.benchmark.baselines import (
    baseline_dead_code,
    baseline_list_routes,
    baseline_architecture,
    baseline_search_markdown,
    baseline_compress_pytest,
    baseline_compress_lint,
    _is_default_repo,
)
from e2e.benchmark.config import CHARS_PER_TOKEN, QUESTIONS, REPO_SHA


def _tokkit_tokens(response_text: str) -> int:
    return len(response_text) // CHARS_PER_TOKEN


# Module-level list to collect results across test methods
_results: list[dict] = []


@pytest.mark.benchmark
class TestTokenSimulation:

    def test_q1_dead_code(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_dead_code(benchmark_repo)
        response = benchmark_mcp.call_tool("find_dead_code", {
            "limit": 200,
        })
        tokkit = _tokkit_tokens(response)
        _results.append({
            "question": QUESTIONS[0],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline, f"tokkit ({tokkit}) should be less than baseline ({baseline})"

    def test_q2_list_routes(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_list_routes(benchmark_repo)
        response = benchmark_mcp.call_tool("find_routes", {
            "limit": 200,
        })
        tokkit = _tokkit_tokens(response)
        _results.append({
            "question": QUESTIONS[1],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline, f"tokkit ({tokkit}) should be less than baseline ({baseline})"

    def test_q3_architecture(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_architecture(benchmark_repo)
        response = benchmark_mcp.call_tool("get_architecture", {})
        tokkit = _tokkit_tokens(response)
        _results.append({
            "question": QUESTIONS[2],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline, f"tokkit ({tokkit}) should be less than baseline ({baseline})"

    def test_q4_search_markdown(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_search_markdown(benchmark_repo)
        readme = os.path.join(benchmark_repo, "README.md")
        response = benchmark_mcp.call_tool("search_markdown", {
            "path": readme,
            "query": "dependencies requirements",
        })
        tokkit = _tokkit_tokens(response)
        _results.append({
            "question": QUESTIONS[3],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline, f"tokkit ({tokkit}) should be less than baseline ({baseline})"

    def test_q5_compress_pytest(self, benchmark_repo, benchmark_mcp):
        from e2e.benchmark.baselines import baseline_compress_pytest
        baseline = baseline_compress_pytest(benchmark_repo)

        # Generate realistic pytest output
        raw_output = (
            "============================= test session starts ==============================\n"
            "platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0\n"
            "collected 50 items\n\n"
        )
        for i in range(48):
            raw_output += f"tests/test_{i:03d}.py::test_func PASSED                              [{(i+1)*2}%]\n"
        raw_output += "tests/test_auth.py::test_signup FAILED                              [ 98%]\n"
        raw_output += "tests/test_db.py::test_query FAILED                                 [100%]\n"
        raw_output += "\n=========================== short test summary info ============================\n"
        raw_output += "FAILED tests/test_auth.py::test_signup - AssertionError: assert 401 == 200\n"
        raw_output += "FAILED tests/test_db.py::test_query - KeyError: 'users'\n"
        raw_output += "========================= 48 passed, 2 failed in 1.23s =========================\n"

        response = benchmark_mcp.call_tool("compact_output", {
            "text": raw_output,
            "hint": "pytest",
        })
        tokkit = _tokkit_tokens(response)
        raw_baseline = len(raw_output) // CHARS_PER_TOKEN

        _results.append({
            "question": QUESTIONS[4],
            "tokkit": tokkit,
            "baseline": raw_baseline,
        })
        assert tokkit < raw_baseline

    def test_q6_compress_lint(self, benchmark_repo, benchmark_mcp):
        from e2e.benchmark.baselines import baseline_compress_lint
        baseline = baseline_compress_lint(benchmark_repo)

        # Realistic ruff output with ANSI color codes (as ruff --color produces)
        ESC = "\x1b"
        rules = [
            ("E501", "Line too long (120 > 88 characters)"),
            ("W291", "trailing whitespace"),
            ("E302", "expected 2 blank lines, found 1"),
            ("F401", "'os' imported but unused"),
        ]
        raw_output = ""
        for i in range(20):
            for code, msg in rules:
                raw_output += (
                    f"{ESC}[34msrc/module_{i // 4}.py{ESC}[0m:"
                    f"{ESC}[36m{i * 3 + 1}{ESC}[0m:"
                    f"{ESC}[36m1{ESC}[0m: "
                    f"{ESC}[33m{code}{ESC}[0m "
                    f"{ESC}[37m{msg}{ESC}[0m\n"
                )
        raw_output += f"Found {20 * len(rules)} errors.\n"

        response = benchmark_mcp.call_tool("compact_output", {
            "text": raw_output,
            "hint": "ruff",
        })
        tokkit = _tokkit_tokens(response)
        raw_baseline = len(raw_output) // CHARS_PER_TOKEN

        _results.append({
            "question": QUESTIONS[5],
            "tokkit": tokkit,
            "baseline": raw_baseline,
        })
        assert tokkit < raw_baseline

    def test_z_generate_report(self):
        """Run last (alphabetically). Writes SIMULATION_RESULTS.md."""
        if len(_results) < 6:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in _results)
        total_baseline = sum(r["baseline"] for r in _results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        is_exact = _is_default_repo()
        baseline_mode = "measured grep/read output sizes" if is_exact else "approximate (computed)"

        lines = [
            "# Tokkit Token Savings Simulation",
            "",
            "**Type:** Content-size comparison (NOT real agent measurements)",
            f"**Repo:** fastapi/fastapi @ `{REPO_SHA}`",
            f"**Date:** {date.today().isoformat()}",
            f"**Baselines:** {baseline_mode}",
            "",
            "| # | Question | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
            "|---|----------|----------------:|------------------:|----------:|------:|",
        ]

        for i, r in enumerate(_results, 1):
            savings = (1 - r["tokkit"] / r["baseline"]) * 100 if r["baseline"] > 0 else 0
            ratio = r["baseline"] / r["tokkit"] if r["tokkit"] > 0 else 0
            lines.append(
                f"| {i} | {r['question']} | {r['tokkit']:,} | {r['baseline']:,} | {savings:.1f}% | {ratio:.0f}x |"
            )

        lines.append(
            f"| | **Total** | **{total_tokkit:,}** | **{total_baseline:,}** | **{total_savings:.1f}%** | **{total_ratio:.0f}x** |"
        )
        lines.extend([
            "",
            "## Methodology",
            "",
            "### Baseline accuracy",
            "",
        ])

        if is_exact:
            lines.extend([
                "Baselines are **measured grep/read output sizes** for the default repo (fastapi @ 0.115.6).",
                "Each baseline was obtained by running grep/read commands directly (not through an agent)",
                "and counting the raw bytes of the output. These are NOT agent `total_tokens`.",
                "The tool call sequences modeled are:",
                "",
                "- Q1 (dead code): 1 Grep for definitions (250 lines) + 117 word-boundary reference greps",
                "- Q2 (routes): 1 Grep call (content, -A=1) for route decorators, head_limit=250",
                "- Q3 (architecture): 1 Glob + 1 Read README + 1 Read `__init__.py` + 5 Read (100 lines each)",
                "- Q4 (markdown): 1 Read(README.md) — full 499-line file with cat -n prefix",
                "- Q5 (pytest): raw output byte count (agent reads as-is)",
                "- Q6 (lint): raw output byte count with ANSI codes (agent reads as-is)",
                "",
            ])
        else:
            lines.extend([
                "Baselines are **approximate values** computed by running the same tool call",
                "sequence against the target repo. For exact measured baselines, use the default",
                "repo (fastapi @ 0.115.6).",
                "",
            ])

        lines.extend([
            "### What the baselines measure",
            "",
            "The **Baseline** column represents the minimum tokens a skilled Claude Code",
            "agent would consume to answer each question, assuming optimal tool usage.",
            "These are intentionally **optimistic for Claude Code** (conservative for tokkit),",
            "meaning the true savings in practice are likely higher.",
            "",
            "Optimistic assumptions applied to all baselines:",
            "",
            "- **Grep content mode** — agent uses `output_mode=\"content\"` to get matching",
            "  lines directly, instead of `files_with_matches` followed by full file reads",
            "- **Grep head_limit=250** — Claude Code caps Grep results at 250 lines by default,",
            "  naturally limiting output size",
            "- **Targeted Read with offset/limit** — agent reads ~50-line function bodies",
            "  instead of entire files when tracing code",
            "- **Read tool overhead** — each line gets ~8 bytes of `cat -n` line-number prefix",
            "  that enters the context window",
            "- **Core-module scoping** — agent focuses on `fastapi/` source code, not",
            "  tests, docs, or examples (1,200+ files ignored)",
            "- **Selective call tracing** — agent follows 3 calls per function level,",
            "  not every function-call-like pattern in the file",
            "- **Word-boundary matching** — reference greps use `-w` (whole word) to avoid",
            "  substring false positives; generic names (get, set, post, etc.) are skipped",
            "",
            "A real Claude Code agent would often consume **more** tokens through:",
            "",
            "- Reading full files instead of targeted sections (Read defaults to 2,000 lines)",
            "- Multiple iterative grep searches to refine results",
            "- Reading README, config files, and other supporting context",
            "- Trial-and-error exploration before finding the right approach",
            "- Re-reading files across conversation turns as context compresses",
            "",
            "### Per-question agent strategy",
            "",
            "| # | Question | Optimistic Claude Code strategy |",
            "|---|----------|--------------------------------|",
            "| 1 | Dead code | `Grep(content)` definitions in core module only. Word-boundary `Grep(-w, files_with_matches)` per function. Skips generic/short names. |",
            "| 2 | List routes | `Grep(content, -A=1)` for route decorators. Decorator lines ARE the answer. No file reads. |",
            "| 3 | Architecture | `Glob` file listing + `Read` README + core `__init__.py` + first 100 lines of 5 key modules. |",
            "| 4 | Search markdown | `Read(README.md)` — full file with cat -n overhead. Minimum: one Read call on the file containing the answer. |",
            "| 5 | Compress pytest | Raw pytest output enters context as-is. Agent reads and summarizes. |",
            "| 6 | Compress lint | Raw ruff output enters context as-is (with ANSI codes). Agent reads and summarizes. |",
            "",
            "### Token estimation",
            "",
            f"Both columns use `len(bytes) / {CHARS_PER_TOKEN}` (Anthropic's published approximation",
            "for English text). For Python source code, the actual ratio is closer to 3.0-3.5",
            "chars/token, meaning absolute numbers slightly understate true token consumption.",
            "Since both paths use the same constant, **savings percentages and ratios are unaffected**.",
            "",
            "### Agent overhead (not included)",
            "",
            "These numbers measure **content tokens only** — the tool result payloads.",
            "Every agent session also pays fixed infrastructure overhead: ~27K tokens for",
            "baseline agents, ~32K for tokkit agents (extra MCP tool definitions). This",
            "overhead is not captured here. Real-world total savings are significantly",
            "lower than these content ratios. For real agent measurements, see `BENCHMARK_RESULTS.md`.",
            "",
            "### What this simulation is NOT",
            "",
            "- NOT real agent measurements — no model inference, no API calls",
            "- NOT total token counts — only tool output sizes",
            "- NOT counting agent overhead, reasoning, or decision-making tokens",
            "- NOT measuring accuracy — only content compression ratios",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "SIMULATION_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
        assert total_tokkit < total_baseline
