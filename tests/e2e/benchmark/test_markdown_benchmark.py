"""Token savings benchmark: search_markdown vs reading full document."""

import os
from datetime import date

import pytest

from e2e.benchmark.config import CHARS_PER_TOKEN

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "markdown")

FIXTURE_FILES = [
    "project_readme.md",
    "api_documentation.md",
    "claude_md.md",
]

# Targeted queries that should match specific sections, not the whole doc
QUERIES = [
    ("authentication", "Find auth-related sections"),
    ("testing", "Find testing documentation"),
    ("deployment docker", "Find deployment/Docker setup"),
    ("error", "Find error handling docs"),
    ("websocket", "Find WebSocket documentation"),
]

_results: list[dict] = []


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path) as f:
        return f.read()


def _baseline_full_doc(md: str) -> int:
    """Baseline: reading the entire document."""
    return len(md) // CHARS_PER_TOKEN


@pytest.mark.benchmark
class TestMarkdownBenchmark:

    def test_q1_authentication(self, benchmark_mcp_markdown):
        query, description = QUERIES[0]
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            md = _load_fixture(fixture_file)
            total_baseline += _baseline_full_doc(md)
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            response = benchmark_mcp_markdown.call_tool("search_markdown", {
                "path": fixture_path,
                "query": query,
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": description,
            "query": query,
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q2_testing(self, benchmark_mcp_markdown):
        query, description = QUERIES[1]
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            md = _load_fixture(fixture_file)
            total_baseline += _baseline_full_doc(md)
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            response = benchmark_mcp_markdown.call_tool("search_markdown", {
                "path": fixture_path,
                "query": query,
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": description,
            "query": query,
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q3_deployment(self, benchmark_mcp_markdown):
        query, description = QUERIES[2]
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            md = _load_fixture(fixture_file)
            total_baseline += _baseline_full_doc(md)
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            response = benchmark_mcp_markdown.call_tool("search_markdown", {
                "path": fixture_path,
                "query": query,
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": description,
            "query": query,
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q4_errors(self, benchmark_mcp_markdown):
        query, description = QUERIES[3]
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            md = _load_fixture(fixture_file)
            total_baseline += _baseline_full_doc(md)
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            response = benchmark_mcp_markdown.call_tool("search_markdown", {
                "path": fixture_path,
                "query": query,
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": description,
            "query": query,
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q5_websocket(self, benchmark_mcp_markdown):
        query, description = QUERIES[4]
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            md = _load_fixture(fixture_file)
            total_baseline += _baseline_full_doc(md)
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            response = benchmark_mcp_markdown.call_tool("search_markdown", {
                "path": fixture_path,
                "query": query,
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": description,
            "query": query,
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_z_generate_report(self):
        if len(_results) < 5:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in _results)
        total_baseline = sum(r["baseline"] for r in _results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        lines = [
            "# Tokkit Markdown Search Token Savings Benchmark",
            "",
            f"**Fixtures:** {len(FIXTURE_FILES)} markdown documents (project README, API docs, CLAUDE.md)",
            f"**Date:** {date.today().isoformat()}",
            "",
            "| # | Query | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
            "|---|-------|----------------:|------------------:|----------:|------:|",
        ]

        for i, r in enumerate(_results, 1):
            savings = (1 - r["tokkit"] / r["baseline"]) * 100 if r["baseline"] > 0 else 0
            ratio = r["baseline"] / r["tokkit"] if r["tokkit"] > 0 else 0
            lines.append(
                f"| {i} | {r['question']} (`{r['query']}`) | {r['tokkit']:,} | {r['baseline']:,} | {savings:.1f}% | {ratio:.1f}x |"
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
            "The **Baseline** column is the total token cost of reading all 3 markdown documents "
            "in full for each query. This represents the cost when an agent reads entire files "
            "to find specific information.",
            "",
            "The **Tokkit** column is the token cost of the `search_markdown` response, which "
            "returns only the matching sections with ranking metadata.",
            "",
            "Each query is run against all 3 fixtures. Not every fixture will have matching "
            "content for every query — in those cases `search_markdown` returns the header tree "
            "(~50-100 tokens) instead of the full document.",
            "",
            f"*Token estimate: len(chars) / {CHARS_PER_TOKEN}. Both paths use the same constant.*",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "MARKDOWN_BENCHMARK_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
        assert total_tokkit < total_baseline
