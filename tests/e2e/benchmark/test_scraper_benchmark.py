"""Token savings benchmark: clean_html modes vs raw HTML baseline."""

import os
from datetime import date

import pytest

from e2e.benchmark.config import CHARS_PER_TOKEN

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "html")

FIXTURE_FILES = [
    "python_docs.html",
    "github_readme.html",
    "blog_post.html",
]

QUESTIONS = [
    "Extract main content (markdown mode)",
    "Get plain text (text mode)",
    "Light clean (minimal mode)",
]

MODES = ["markdown", "text", "minimal"]

_results: list[dict] = []


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path) as f:
        return f.read()


def _baseline_raw_html(html: str) -> int:
    return len(html) // CHARS_PER_TOKEN


@pytest.mark.benchmark
class TestScraperBenchmark:

    def test_q1_markdown_mode(self, benchmark_mcp_scraper):
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            html = _load_fixture(fixture_file)
            total_baseline += _baseline_raw_html(html)
            response = benchmark_mcp_scraper.call_tool("clean_html", {
                "html": html,
                "mode": "markdown",
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": QUESTIONS[0],
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q2_text_mode(self, benchmark_mcp_scraper):
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            html = _load_fixture(fixture_file)
            total_baseline += _baseline_raw_html(html)
            response = benchmark_mcp_scraper.call_tool("clean_html", {
                "html": html,
                "mode": "text",
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": QUESTIONS[1],
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q3_minimal_mode(self, benchmark_mcp_scraper):
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            html = _load_fixture(fixture_file)
            total_baseline += _baseline_raw_html(html)
            response = benchmark_mcp_scraper.call_tool("clean_html", {
                "html": html,
                "mode": "minimal",
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": QUESTIONS[2],
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_z_generate_report(self):
        if len(_results) < 3:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in _results)
        total_baseline = sum(r["baseline"] for r in _results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        lines = [
            "# Tokkit Scraper Token Savings Benchmark",
            "",
            f"**Fixtures:** {len(FIXTURE_FILES)} HTML pages (python docs, GitHub README, blog post)",
            f"**Date:** {date.today().isoformat()}",
            "",
            "| # | Mode | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
            "|---|------|----------------:|------------------:|----------:|------:|",
        ]

        for i, r in enumerate(_results, 1):
            savings = (1 - r["tokkit"] / r["baseline"]) * 100 if r["baseline"] > 0 else 0
            ratio = r["baseline"] / r["tokkit"] if r["tokkit"] > 0 else 0
            lines.append(
                f"| {i} | {r['question']} | {r['tokkit']:,} | {r['baseline']:,} | {savings:.1f}% | {ratio:.1f}x |"
            )

        lines.append(
            f"| | **Total** | **{total_tokkit:,}** | **{total_baseline:,}** | **{total_savings:.1f}%** | **{total_ratio:.1f}x** |"
        )
        lines.extend([
            "",
            "## Methodology",
            "",
            "### What the baseline measures",
            "",
            "The **Baseline** column is the raw HTML byte count divided by "
            f"{CHARS_PER_TOKEN} (chars-per-token estimate).",
            "This represents the token cost if raw HTML enters the LLM context window,",
            "which happens when:",
            "",
            "- An MCP tool returns HTML content (e.g., a web scraping tool)",
            "- `curl` via Bash tool fetches a page",
            "- A user pastes HTML into the conversation",
            "- A file read loads an `.html` file",
            "",
            "**Note on Claude Code's built-in WebFetch:** The WebFetch tool already converts",
            "HTML to markdown (via Turndown) and may further summarize via a fast model before",
            "content enters context. For the WebFetch case, the raw HTML baseline overstates",
            "the problem. This benchmark targets scenarios where raw HTML enters context through",
            "other channels (MCP tools, Bash curl, file reads).",
            "",
            f"*Token estimate: len(bytes) / {CHARS_PER_TOKEN}. Both paths use the same constant.*",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "SCRAPER_BENCHMARK_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
        assert total_tokkit < total_baseline
