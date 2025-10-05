"""Token savings benchmark: compact_json CSV vs YAML paths."""

import os
from datetime import date

import pytest

from e2e.benchmark.config import CHARS_PER_TOKEN

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "json")

_results: list[dict] = []


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path) as f:
        return f.read()


def _baseline_raw_json(json_str: str) -> int:
    return len(json_str) // CHARS_PER_TOKEN


@pytest.mark.benchmark
class TestJsonBenchmark:

    def test_q1_csv_path(self, benchmark_mcp_json):
        json_str = _load_fixture("flat_records.json")
        baseline = _baseline_raw_json(json_str)
        response = benchmark_mcp_json.call_tool("compact_json", {"json": json_str})
        tokkit = len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": "Flat records (CSV path)",
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_q2_yaml_path(self, benchmark_mcp_json):
        json_str = _load_fixture("nested_complex.json")
        baseline = _baseline_raw_json(json_str)
        response = benchmark_mcp_json.call_tool("compact_json", {"json": json_str})
        tokkit = len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": "Nested complex (YAML path)",
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_z_generate_report(self):
        if len(_results) < 2:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in _results)
        total_baseline = sum(r["baseline"] for r in _results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        lines = [
            "# Tokkit JSON Compaction Token Savings Benchmark",
            "",
            f"**Fixtures:** 2 JSON payloads (flat records, nested complex)",
            f"**Date:** {date.today().isoformat()}",
            "",
            "| # | Path | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
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
            "The **Baseline** column is the raw JSON byte count divided by "
            f"{CHARS_PER_TOKEN} (chars-per-token estimate).",
            "This represents the token cost when raw JSON enters the LLM context window,",
            "which happens when:",
            "",
            "- An MCP tool returns JSON data (API responses, database queries)",
            "- A file read loads a `.json` file",
            "- Bash tool output contains JSON (curl, jq, API calls)",
            "",
            "Unlike HTML (where Claude Code's WebFetch already cleans content), there is",
            "no built-in JSON compaction in Claude Code. Raw JSON is passed through as-is.",
            "",
            f"*Token estimate: len(bytes) / {CHARS_PER_TOKEN}. Both paths use the same constant.*",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "JSON_BENCHMARK_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
        assert total_tokkit < total_baseline
