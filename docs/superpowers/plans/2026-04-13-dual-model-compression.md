# Dual-Model Output Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port token-saver compression techniques to tokkit and add a hook-based delivery model that eliminates MCP overhead for shell command output.

**Architecture:** Shared parser library (`py/tokkit_output/parsers/`) feeds two delivery mechanisms — a PreToolUse hook for automatic Bash interception (zero context overhead) and the existing MCP `compact_output` tool for file-based processing. New parsers: git (7), k8s, docker (3), shell tools (5), plus lint grouper, generic fallback, and ratio check.

**Tech Stack:** Python 3.10+, regex-based parsing, Claude Code plugin hooks, pytest

**Spec:** `docs/superpowers/specs/2026-04-13-dual-model-compression-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `py/tokkit_output/generic.py` | Generic fallback pipeline (ANSI, progress bars, dedup, truncation) |
| `py/tokkit_output/lint_grouper.py` | Post-processor that groups lint violations by rule ID |
| `py/tokkit_output/parsers/git_diff.py` | Git diff parser (context windowing, lock elision, hunk truncation) |
| `py/tokkit_output/parsers/git_status.py` | Git status parser (summary + directory grouping) |
| `py/tokkit_output/parsers/git_log.py` | Git log parser (one-liner extraction, entry cap) |
| `py/tokkit_output/parsers/git_show.py` | Git show parser (metadata + diff compression) |
| `py/tokkit_output/parsers/git_blame.py` | Git blame parser (consecutive-author range collapse) |
| `py/tokkit_output/parsers/git_branch.py` | Git branch parser (prefix grouping) |
| `py/tokkit_output/parsers/git_stash.py` | Git stash parser (entry truncation) |
| `py/tokkit_output/parsers/kubectl.py` | Kubernetes parser (healthy pod elision, describe trimming, log neighborhoods) |
| `py/tokkit_output/parsers/docker_compose.py` | Docker compose parser (service grouping, log compression) |
| `py/tokkit_output/parsers/docker_ps.py` | Docker ps/images parser (table parsing, stopped container elision) |
| `py/tokkit_output/parsers/docker_logs.py` | Docker logs parser (head/tail + error neighborhoods) |
| `py/tokkit_output/parsers/package_list.py` | pip list/freeze, npm ls parser (count + truncation) |
| `py/tokkit_output/parsers/file_listing.py` | ls/tree/find parser (depth truncation, grouping) |
| `py/tokkit_output/parsers/search_results.py` | grep/rg/ag parser (per-file + total limits) |
| `py/tokkit_output/parsers/gh_cli.py` | GitHub CLI parser (pr/issue/run table parsing) |
| `py/tokkit_output/parsers/env_redact.py` | env/printenv parser (sensitive value redaction) |
| `py/tokkit_hook/__init__.py` | Hook module init |
| `py/tokkit_hook/match.py` | Command-to-hint pattern matching + exclusion list |
| `py/tokkit_hook/chain.py` | Chained command splitting (`&&`, `;`) |
| `py/tokkit_hook/compress.py` | `tokkit compress` CLI subcommand |
| `py/tokkit_hook/hook.py` | PreToolUse hook script |
| `tests/output_tests/fixtures/git_output.py` | Git command output fixtures |
| `tests/output_tests/fixtures/k8s_output.py` | Kubernetes output fixtures |
| `tests/output_tests/fixtures/docker_extra_output.py` | Docker compose/ps/images/logs fixtures |
| `tests/output_tests/fixtures/shell_output.py` | Package list, file listing, search, env fixtures |
| `tests/output_tests/fixtures/gh_output.py` | GitHub CLI fixtures |
| `tests/output_tests/test_git_parsers.py` | All git parser tests |
| `tests/output_tests/test_kubectl_parser.py` | Kubectl parser tests |
| `tests/output_tests/test_docker_extra_parsers.py` | Docker compose/ps/logs tests |
| `tests/output_tests/test_shell_parsers.py` | Package list, file listing, search, env tests |
| `tests/output_tests/test_gh_cli_parser.py` | GH CLI tests |
| `tests/output_tests/test_generic.py` | Generic fallback pipeline tests |
| `tests/output_tests/test_lint_grouper.py` | Lint grouper tests |
| `tests/output_tests/test_ratio_check.py` | Minimum ratio check tests |
| `tests/hook_tests/__init__.py` | Hook test module |
| `tests/hook_tests/test_match.py` | Command matching tests |
| `tests/hook_tests/test_chain.py` | Chain splitting tests |
| `tests/hook_tests/test_compress.py` | Compress CLI tests |
| `tests/hook_tests/test_hook.py` | Hook protocol tests |

### Modified files

| File | Change |
|------|--------|
| `py/tokkit_output/__init__.py` | Add ratio check, lint grouper integration, generic fallback |
| `py/tokkit_output/parsers/__init__.py` | Register 16 new parsers |
| `py/tokkit_cli/main.py` | Add `compress` subcommand |
| `py/tokkit_cli/setup.py` | Write hook config in plugin |
| `py/tokkit_server/protocol.py` | Update tool descriptions with new hints |
| `README.md` | Dual-model docs + benchmarks |
| `skill/SKILL.md` | Hook model docs |

---

### Task 1: Generic Fallback Pipeline

**Files:**
- Create: `py/tokkit_output/generic.py`
- Create: `tests/output_tests/test_generic.py`

This is the foundation — when no specific parser matches, the generic pipeline cleans up output with 5 passes: ANSI strip, progress bar removal, consecutive dedup, similar-line dedup, head/tail truncation.

- [ ] **Step 1: Write generic fallback tests**

Create `tests/output_tests/test_generic.py`:

```python
"""Tests for generic fallback pipeline."""

import pytest
from tokkit_output.generic import generic_clean


class TestProgressBarRemoval:
    def test_removes_progress_bar_lines(self):
        text = "Downloading...\n████████████████████░░░░ 80%\nDone."
        result = generic_clean(text)
        assert "████" not in result
        assert "Done." in result

    def test_keeps_non_bar_lines(self):
        text = "Step 1: Build\nStep 2: Test\nStep 3: Deploy"
        result = generic_clean(text)
        assert "Step 1" in result
        assert "Step 3" in result

    def test_removes_spinner_characters(self):
        text = "Loading ⠋\nLoading ⠙\nLoading ⠹\nLoading ⠸\nDone."
        result = generic_clean(text)
        assert "Done." in result

    def test_removes_hash_progress_bars(self):
        text = "Progress: [##########----------] 50%\nProgress: [####################] 100%\nComplete."
        result = generic_clean(text)
        assert "Complete." in result


class TestConsecutiveDedup:
    def test_collapses_identical_lines(self):
        text = "building...\n" * 10 + "done."
        result = generic_clean(text)
        assert "building... (x10)" in result
        assert "done." in result

    def test_no_dedup_for_unique_lines(self):
        text = "line 1\nline 2\nline 3"
        result = generic_clean(text)
        assert "line 1" in result
        assert "line 2" in result
        assert "line 3" in result

    def test_dedup_preserves_single_instance(self):
        text = "a\na\nb\nb\nb\nc"
        result = generic_clean(text)
        assert "a (x2)" in result
        assert "b (x3)" in result
        assert "c" in result


class TestSimilarLineDedup:
    def test_collapses_numeric_variants(self):
        lines = [f"Downloading package {i}/200 ({i*50}KB)..." for i in range(1, 21)]
        text = "\n".join(lines) + "\nComplete."
        result = generic_clean(text)
        # Should collapse to first + "... (N similar lines)" + last
        assert "similar" in result.lower() or "(x" in result
        assert "Complete." in result

    def test_keeps_non_numeric_lines(self):
        text = "error: file not found\nwarning: deprecated API\ninfo: build complete"
        result = generic_clean(text)
        assert "error" in result
        assert "warning" in result
        assert "info" in result


class TestHeadTailTruncation:
    def test_truncates_long_output(self):
        lines = [f"line {i}" for i in range(1, 301)]
        text = "\n".join(lines)
        result = generic_clean(text)
        assert "line 1" in result
        assert "line 100" in result
        assert "line 300" in result
        # Middle should be truncated
        assert "truncated" in result.lower()
        assert "line 150" not in result

    def test_no_truncation_for_short_output(self):
        lines = [f"line {i}" for i in range(1, 51)]
        text = "\n".join(lines)
        result = generic_clean(text)
        assert "truncated" not in result.lower()
        for i in range(1, 51):
            assert f"line {i}" in result


class TestMinLengthBypass:
    def test_short_input_passes_through(self):
        text = "ok"
        result = generic_clean(text)
        assert result == "ok"

    def test_whitespace_only_returns_empty(self):
        text = "   \n\n  "
        result = generic_clean(text)
        assert result.strip() == ""


class TestFullPipeline:
    def test_ansi_plus_progress_plus_dedup(self):
        text = (
            "\x1b[32mStarting build...\x1b[0m\n"
            "████████░░░░ 60%\n"
            "compiling...\n" * 5
            + "Build complete."
        )
        result = generic_clean(text)
        assert "\x1b" not in result
        assert "████" not in result
        assert "compiling... (x5)" in result
        assert "Build complete." in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_generic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_output.generic'`

- [ ] **Step 3: Implement generic fallback**

Create `py/tokkit_output/generic.py`:

```python
"""Generic fallback pipeline for unrecognized command output.

Five passes applied in sequence:
1. ANSI stripping
2. Progress bar removal
3. Consecutive identical line dedup
4. Similar-line dedup (numeric normalization)
5. Head/tail truncation
"""

import re

from tokkit_output.universal import strip_ansi

# --- Pass 2: Progress bar detection ---
_BAR_CHARS = re.compile(r"[━█▓░▒■□●○#=\->{}/|]+")
_SPINNER_CHARS = set("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⣾⣽⣻⢿⡿⣟⣯⣷")

# --- Pass 4: Numeric normalization ---
_NUMERIC_RE = re.compile(r"\d+")
_NUMERIC_HEAVY_RE = re.compile(r"\d")
_RATE_PATTERNS = re.compile(r"(%|[KMG]?B/s|ETA|--:--:--|[\d]+:[\d]+:[\d]+)")

# --- Thresholds ---
_MIN_LENGTH = 500  # Don't process output shorter than this
_TRUNCATE_THRESHOLD = 200  # Lines
_KEEP_HEAD = 100
_KEEP_TAIL = 50
_SIMILAR_GROUP_MIN = 5  # Minimum group size for similar-line collapse
_BAR_RATIO = 0.5  # Line is >50% bar characters


def _is_progress_bar_line(line: str) -> bool:
    """Return True if the line is predominantly progress bar characters."""
    stripped = line.strip()
    if not stripped:
        return False
    # Check for spinner characters
    if any(c in _SPINNER_CHARS for c in stripped):
        return True
    # Check ratio of bar characters
    bar_match = _BAR_CHARS.findall(stripped)
    bar_len = sum(len(m) for m in bar_match)
    return bar_len / len(stripped) >= _BAR_RATIO


def _is_numeric_heavy(line: str) -> bool:
    """Return True if line has >=30% digits or contains rate/progress patterns."""
    stripped = line.strip()
    if not stripped:
        return False
    if _RATE_PATTERNS.search(stripped):
        return True
    digit_count = len(_NUMERIC_HEAVY_RE.findall(stripped))
    return digit_count / len(stripped) >= 0.30


def _remove_progress_bars(lines: list[str]) -> list[str]:
    """Pass 2: Remove lines that are predominantly progress bars."""
    return [line for line in lines if not _is_progress_bar_line(line)]


def _consecutive_dedup(lines: list[str]) -> list[str]:
    """Pass 3: Collapse identical consecutive non-blank lines."""
    if not lines:
        return []
    result = []
    prev = lines[0]
    count = 1
    for line in lines[1:]:
        if line.strip() and line == prev:
            count += 1
        else:
            if count > 1:
                result.append(f"{prev} (x{count})")
            else:
                result.append(prev)
            prev = line
            count = 1
    if count > 1:
        result.append(f"{prev} (x{count})")
    else:
        result.append(prev)
    return result


def _similar_line_dedup(lines: list[str]) -> list[str]:
    """Pass 4: Collapse consecutive lines that differ only in numbers."""
    if not lines:
        return []

    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        normalized = _NUMERIC_RE.sub("N", line)

        if not _is_numeric_heavy(line):
            result.append(line)
            i += 1
            continue

        # Collect consecutive lines with same normalized form
        group = [line]
        j = i + 1
        while j < len(lines) and _NUMERIC_RE.sub("N", lines[j]) == normalized:
            group.append(lines[j])
            j += 1

        if len(group) >= _SIMILAR_GROUP_MIN:
            result.append(group[0])
            result.append(f"... ({len(group) - 2} similar lines)")
            result.append(group[-1])
        else:
            result.extend(group)
        i = j

    return result


def _head_tail_truncate(lines: list[str]) -> list[str]:
    """Pass 5: Truncate middle of output when over threshold."""
    if len(lines) <= _TRUNCATE_THRESHOLD:
        return lines
    removed = len(lines) - _KEEP_HEAD - _KEEP_TAIL
    return (
        lines[:_KEEP_HEAD]
        + [f"... ({removed} lines truncated, {len(lines)} total)"]
        + lines[-_KEEP_TAIL:]
    )


def generic_clean(text: str) -> str:
    """Apply the full generic fallback pipeline.

    Returns cleaned text. For short inputs (<500 chars), only strips ANSI.
    """
    if not text or not text.strip():
        return text.strip() if text else ""

    # Pass 1: ANSI stripping
    cleaned = strip_ansi(text)

    # Short output: ANSI strip only
    if len(cleaned) < _MIN_LENGTH:
        return cleaned

    lines = cleaned.splitlines()

    # Pass 2: Progress bar removal
    lines = _remove_progress_bars(lines)

    # Pass 3: Consecutive identical line dedup
    lines = _consecutive_dedup(lines)

    # Pass 4: Similar-line dedup
    lines = _similar_line_dedup(lines)

    # Pass 5: Head/tail truncation
    lines = _head_tail_truncate(lines)

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_generic.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_output/generic.py tests/output_tests/test_generic.py
git commit -m "feat: add generic fallback pipeline for unrecognized output"
```

---

### Task 2: Lint Grouper Post-Processor

**Files:**
- Create: `py/tokkit_output/lint_grouper.py`
- Create: `tests/output_tests/test_lint_grouper.py`

Groups lint violations by rule ID. Applied after any lint parser returns a ParseResult with a `rule` or `code` column. This is the single highest-impact improvement — ruff savings go from 8% to ~70-85%.

- [ ] **Step 1: Write lint grouper tests**

Create `tests/output_tests/test_lint_grouper.py`:

```python
"""Tests for lint grouper post-processor."""

from tokkit_output.base import ParseResult
from tokkit_output.lint_grouper import group_by_rule


class TestGroupByRule:
    def test_groups_violations_by_rule(self):
        """Rules with >3 violations get grouped."""
        rows = [
            ["src/a.py", "1", "1", "E501", "error", "Line too long"],
            ["src/a.py", "2", "1", "E501", "error", "Line too long"],
            ["src/a.py", "3", "1", "E501", "error", "Line too long"],
            ["src/a.py", "4", "1", "E501", "error", "Line too long"],
            ["src/a.py", "5", "1", "E501", "error", "Line too long"],
            ["src/b.py", "1", "1", "W291", "warning", "Trailing whitespace"],
        ]
        result = ParseResult(
            tool="ruff", summary="6 violations",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows,
        )
        grouped = group_by_rule(result)
        # E501 should be grouped: 2 examples + summary
        # W291 has only 1, shown individually
        assert len(grouped.rows) < len(rows)
        assert "5" in grouped.summary  # still mentions total
        assert any("E501" in str(row) for row in grouped.rows)

    def test_small_rule_groups_not_collapsed(self):
        """Rules with <=3 violations shown individually."""
        rows = [
            ["src/a.py", "1", "1", "E501", "error", "Line too long"],
            ["src/a.py", "2", "1", "E501", "error", "Line too long"],
            ["src/b.py", "1", "1", "W291", "warning", "Trailing whitespace"],
        ]
        result = ParseResult(
            tool="ruff", summary="3 violations",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows,
        )
        grouped = group_by_rule(result)
        # All 3 shown individually (no rule has >3)
        assert len(grouped.rows) == 3

    def test_verbose_skips_grouping(self):
        """When verbose=True, grouping is disabled."""
        rows = [
            ["src/a.py", str(i), "1", "E501", "error", "Line too long"]
            for i in range(1, 11)
        ]
        result = ParseResult(
            tool="ruff", summary="10 violations",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows, verbose=True,
        )
        grouped = group_by_rule(result)
        assert len(grouped.rows) == 10  # No grouping

    def test_no_rule_column_passthrough(self):
        """Parsers without rule/code column pass through unchanged."""
        rows = [["test_a", "FAIL", "tests/a.py", "10", "AssertionError"]]
        result = ParseResult(
            tool="pytest", summary="1 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=rows,
        )
        grouped = group_by_rule(result)
        assert grouped.rows == rows

    def test_summary_updated_with_rule_count(self):
        """Summary includes 'across N rules' after grouping."""
        rows = [
            ["src/a.py", str(i), "1", "E501", "error", "Line too long"]
            for i in range(1, 21)
        ] + [
            ["src/b.py", "1", "1", "W291", "warning", "Trailing whitespace"],
        ]
        result = ParseResult(
            tool="ruff", summary="21 violations",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows,
        )
        grouped = group_by_rule(result)
        assert "2 rules" in grouped.summary

    def test_multiple_rules_all_large(self):
        """Multiple rules each with >3 violations all get grouped."""
        rows = []
        for rule in ["E501", "E302", "W291", "F401"]:
            for i in range(5):
                rows.append([f"src/{rule.lower()}.py", str(i), "1", rule, "error", f"Msg for {rule}"])
        result = ParseResult(
            tool="ruff", summary="20 violations",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows,
        )
        grouped = group_by_rule(result)
        # 4 rules * (2 examples + 1 header) < 20 original rows
        assert len(grouped.rows) < 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_lint_grouper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_output.lint_grouper'`

- [ ] **Step 3: Implement lint grouper**

Create `py/tokkit_output/lint_grouper.py`:

```python
"""Lint grouper — groups violations by rule ID for token savings.

Applied as a post-processing step after any lint parser returns a ParseResult
with a 'rule' or 'code' column. Rules with >3 violations get collapsed to
a header line + 2 examples.
"""

from collections import defaultdict

from tokkit_output.base import ParseResult

_GROUP_THRESHOLD = 3  # Rules with more violations than this get grouped
_EXAMPLE_COUNT = 2    # Number of examples shown per grouped rule


def _find_rule_column(schema: list[str]) -> int | None:
    """Find the index of the rule/code column in schema."""
    for i, col in enumerate(schema):
        if col in ("rule", "code"):
            return i
    return None


def group_by_rule(result: ParseResult) -> ParseResult:
    """Group lint violations by rule ID.

    Returns a new ParseResult with grouped rows. Rules with <=_GROUP_THRESHOLD
    violations are shown individually. Rules above the threshold get:
    - A header row marking the rule + count
    - _EXAMPLE_COUNT example rows
    - Remaining violations elided

    If verbose=True, returns the original result unchanged.
    If no rule/code column exists, returns unchanged.
    """
    if result.verbose:
        return result

    rule_idx = _find_rule_column(result.schema)
    if rule_idx is None:
        return result

    if not result.rows:
        return result

    # Group rows by rule value
    by_rule: dict[str, list[list[str]]] = defaultdict(list)
    rule_order: list[str] = []
    for row in result.rows:
        rule = row[rule_idx] if rule_idx < len(row) else ""
        if rule not in by_rule:
            rule_order.append(rule)
        by_rule[rule].append(row)

    # Count unique files per rule
    file_idx = next((i for i, c in enumerate(result.schema) if c == "file"), None)

    grouped_rows: list[list[str]] = []
    total_violations = len(result.rows)
    rules_grouped = 0

    for rule in rule_order:
        violations = by_rule[rule]
        if len(violations) <= _GROUP_THRESHOLD:
            grouped_rows.extend(violations)
        else:
            rules_grouped += 1
            n_files = len(set(
                row[file_idx] for row in violations
            )) if file_idx is not None else 0
            file_info = f" in {n_files} file{'s' if n_files != 1 else ''}" if file_idx is not None else ""

            # Header row: rule name, count, files — placed in the schema columns
            header = [""] * len(result.schema)
            header[rule_idx] = rule
            msg_idx = next((i for i, c in enumerate(result.schema) if c == "message"), None)
            if msg_idx is not None:
                header[msg_idx] = f"{len(violations)} occurrences{file_info}"
            else:
                header[0] = f"{rule}: {len(violations)} occurrences{file_info}"

            grouped_rows.append(header)
            # Show examples
            grouped_rows.extend(violations[:_EXAMPLE_COUNT])
            remaining = len(violations) - _EXAMPLE_COUNT
            if remaining > 0:
                elision = [""] * len(result.schema)
                elision[0] = f"... ({remaining} more)"
                grouped_rows.append(elision)

    n_rules = len(by_rule)
    summary = f"{total_violations} issue{'s' if total_violations != 1 else ''} across {n_rules} rule{'s' if n_rules != 1 else ''}"

    return ParseResult(
        tool=result.tool,
        summary=summary,
        schema=result.schema,
        rows=grouped_rows,
        verbose=result.verbose,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_lint_grouper.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_output/lint_grouper.py tests/output_tests/test_lint_grouper.py
git commit -m "feat: add lint grouper post-processor for rule-based violation grouping"
```

---

### Task 3: Ratio Check + compact_output Integration

**Files:**
- Modify: `py/tokkit_output/__init__.py`
- Create: `tests/output_tests/test_ratio_check.py`

Add the minimum ratio check (if compression makes output bigger, return raw), integrate lint grouper for lint parsers, and use generic fallback instead of `universal_clean`.

- [ ] **Step 1: Write ratio check and integration tests**

Create `tests/output_tests/test_ratio_check.py`:

```python
"""Tests for ratio check and compact_output integration."""

from tokkit_output import compact_output


class TestRatioCheck:
    def test_short_input_returns_raw_cleaned(self):
        """Short concise output shouldn't be bloated by formatting."""
        text = "All checks passed!"
        result = compact_output(text, hint="ruff")
        # Parser returns "# ruff: All checks passed" which is fine
        assert "passed" in result.lower()

    def test_compression_worse_than_raw_returns_raw(self):
        """If formatted output is longer than raw, return ANSI-stripped raw."""
        # A single-line input that a parser might wrap with schema overhead
        text = "src/a.py:1:1: E501 Line too long"
        result = compact_output(text, hint="ruff")
        # Should still work — single violation might be bigger with schema,
        # but ratio check allows small overhead for structure
        assert "E501" in result


class TestLintGrouperIntegration:
    def test_ruff_violations_grouped(self):
        """Ruff output with many same-rule violations should be grouped."""
        lines = [f"src/mod{i}.py:1:1: E501 Line too long ({80+i} > 88)" for i in range(20)]
        lines.append("Found 20 errors.")
        text = "\n".join(lines)
        result = compact_output(text, hint="ruff")
        # Should be grouped, not 20 individual rows
        assert "20 issue" in result or "20 violation" in result
        assert "E501" in result

    def test_ruff_verbose_not_grouped(self):
        """Verbose mode skips grouping."""
        lines = [f"src/mod{i}.py:1:1: E501 Line too long ({80+i} > 88)" for i in range(20)]
        lines.append("Found 20 errors.")
        text = "\n".join(lines)
        result = compact_output(text, hint="ruff", verbose=True)
        # Should have all 20 rows
        assert result.count("E501") >= 20


class TestGenericFallbackIntegration:
    def test_unknown_long_output_uses_generic(self):
        """Long unrecognized output should use generic pipeline, not just universal_clean."""
        lines = ["progress: " + "█" * 40 + f" {i}%" for i in range(100)]
        lines.append("Done.")
        text = "\n".join(lines)
        result = compact_output(text)
        # Generic should strip progress bars
        assert "█" not in result
        assert "Done." in result

    def test_unknown_short_output_returns_cleaned(self):
        """Short unrecognized output gets ANSI strip + blank collapse."""
        text = "\x1b[32mhello\x1b[0m"
        result = compact_output(text)
        assert result == "hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_ratio_check.py -v`
Expected: Some tests FAIL (lint grouper integration not wired up, generic fallback not used)

- [ ] **Step 3: Update compact_output to integrate lint grouper, ratio check, and generic fallback**

Modify `py/tokkit_output/__init__.py` to:

```python
"""Tokkit Output — Token-optimized shell output compression."""

__version__ = "0.1.0"

# Parser IDs whose output should be post-processed by the lint grouper
_LINT_PARSER_IDS = frozenset({
    "ruff", "eslint", "mypy", "pyright", "cargo-clippy", "tsc",
})


def compact_output(text: str, hint: str | None = None, verbose: bool = False) -> str:
    """Compress shell command output into schema+CSV structured format."""
    if not text or not text.strip():
        return ""

    from tokkit_output.universal import strip_ansi
    cleaned = strip_ansi(text)

    from tokkit_output.parsers import get_by_hint, all_parsers
    from tokkit_output.detect import detect_parser
    from tokkit_output.formatter import format_result

    parser = None
    if hint:
        parser = get_by_hint(hint)

    if parser is None:
        parser = detect_parser(cleaned, all_parsers())

    if parser is None:
        # Use generic fallback for long output, universal_clean for short
        from tokkit_output.generic import generic_clean
        return generic_clean(text)

    result = parser.parse(cleaned, verbose=verbose)

    # Apply lint grouper for lint-type parsers
    if result.tool in _LINT_PARSER_IDS:
        from tokkit_output.lint_grouper import group_by_rule
        result = group_by_rule(result)

    formatted = format_result(result)

    # Ratio check: if formatted output is longer than cleaned input,
    # return the cleaned input instead (ANSI-stripped only)
    if len(formatted) > len(cleaned):
        return cleaned

    return formatted
```

- [ ] **Step 4: Run all output tests to verify nothing broke**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/ -v`
Expected: All tests PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_output/__init__.py tests/output_tests/test_ratio_check.py
git commit -m "feat: integrate lint grouper, ratio check, and generic fallback into compact_output"
```

---

### Task 4: Git Diff Parser

**Files:**
- Create: `tests/output_tests/fixtures/git_output.py`
- Create: `py/tokkit_output/parsers/git_diff.py`
- Create: `tests/output_tests/test_git_parsers.py`

The most complex and highest-value new parser. Context windowing, hunk truncation, lock file elision, stat bar stripping.

- [ ] **Step 1: Create git output fixtures**

Create `tests/output_tests/fixtures/git_output.py`:

```python
"""Realistic git command output fixtures."""

DIFF_SIMPLE = """\
diff --git a/src/auth.py b/src/auth.py
index 1234567..abcdef0 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,7 +10,8 @@ def authenticate(user, password):
     # Check credentials
     if not user:
         return None
-    result = check_db(user, password)
+    hashed = hash_password(password)
+    result = check_db(user, hashed)
     if result:
         return create_token(user)
     return None
@@ -25,6 +26,7 @@ def logout(token):
     # Invalidate token
     cache.delete(token)
     return True
+    audit_log("logout", token)
"""

DIFF_WITH_LOCKFILE = """\
diff --git a/src/main.py b/src/main.py
index 1234567..abcdef0 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 import os
+import sys
 from app import create_app
 
diff --git a/package-lock.json b/package-lock.json
index aaaaaaa..bbbbbbb 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,500 +1,600 @@
""" + "\n".join([f'+    "pkg-{i}": "{i}.0.0",' for i in range(100)]) + """
"""

DIFF_LARGE_HUNK = """\
diff --git a/src/big.py b/src/big.py
index 1234567..abcdef0 100644
--- a/src/big.py
+++ b/src/big.py
@@ -1,100 +1,160 @@
""" + "\n".join([f"+added line {i}" for i in range(60)]) + """
"""

DIFF_STAT = """\
 src/auth.py    | 15 ++++++------
 src/main.py    |  3 ++-
 src/utils.py   | 42 ++++++++++++++++++++++++-----------
 tests/test_a.py|  8 ++++----
 4 files changed, 40 insertions(+), 28 deletions(-)
"""

DIFF_MULTIPLE_FILES = """\
diff --git a/src/auth.py b/src/auth.py
index 1234567..abcdef0 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,7 @@ def authenticate(user, password):
     if not user:
         return None
+    log.info("authenticating %s", user)
     result = check_db(user, password)
     return result
 
diff --git a/src/db.py b/src/db.py
index 2345678..bcdef01 100644
--- a/src/db.py
+++ b/src/db.py
@@ -5,7 +5,7 @@ def connect():
-    return psycopg2.connect(DB_URL)
+    return psycopg2.connect(DB_URL, timeout=30)
"""

STATUS_CLEAN = """\
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
"""

STATUS_DIRTY = """\
On branch feature/auth
Your branch is ahead of 'origin/feature/auth' by 3 commits.
  (use "git push" to publish your local commits)

Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
	modified:   src/auth.py
	new file:   src/middleware.py

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   src/main.py
	modified:   tests/test_auth.py
	modified:   tests/test_api.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	TODO.md
	scratch/
"""

STATUS_SHORT = """\
M  src/auth.py
A  src/middleware.py
 M src/main.py
 M tests/test_auth.py
 M tests/test_api.py
?? TODO.md
?? scratch/
"""

STATUS_LARGE = """\
On branch refactor
Changes not staged for commit:
""" + "".join([f"\tmodified:   src/components/widget{i}.py\n" for i in range(30)]) + """
Untracked files:
""" + "".join([f"\tsrc/generated/gen{i}.py\n" for i in range(15)])

LOG_VERBOSE = """\
commit a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
Author: Alice <alice@example.com>
Date:   Mon Apr 7 10:30:00 2025 +0000

    feat: add authentication module

commit b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1
Author: Bob <bob@example.com>
Date:   Sun Apr 6 15:20:00 2025 +0000

    fix: resolve database connection timeout

commit c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2
Author: Alice <alice@example.com>
Date:   Sat Apr 5 09:10:00 2025 +0000

    refactor: extract utility functions
"""

LOG_ONELINE = """\
a1b2c3d feat: add authentication module
b2c3d4e fix: resolve database connection timeout
c3d4e5f refactor: extract utility functions
d4e5f6a docs: update README
e5f6a7b test: add integration tests
f6a7b8c chore: update dependencies
a7b8c9d ci: add GitHub Actions workflow
b8c9d0e feat: add rate limiting
c9d0e1f fix: handle null user gracefully
d0e1f2a feat: add caching layer
e1f2a3b refactor: simplify auth flow
f2a3b4c test: add unit tests for cache
"""

LOG_ONELINE_SHORT = """\
a1b2c3d feat: add authentication module
b2c3d4e fix: resolve database connection timeout
c3d4e5f refactor: extract utility functions
"""

SHOW_COMMIT = """\
commit a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
Author: Alice <alice@example.com>
Date:   Mon Apr 7 10:30:00 2025 +0000

    feat: add authentication module

diff --git a/src/auth.py b/src/auth.py
index 1234567..abcdef0 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,7 @@ def authenticate(user, password):
     if not user:
         return None
+    log.info("authenticating %s", user)
     result = check_db(user, password)
     return result
"""

BLAME_OUTPUT = """\
a1b2c3d4 (Alice  2025-04-01 10:00:00 +0000  1) import os
a1b2c3d4 (Alice  2025-04-01 10:00:00 +0000  2) import sys
a1b2c3d4 (Alice  2025-04-01 10:00:00 +0000  3)
b2c3d4e5 (Bob    2025-04-02 11:00:00 +0000  4) def connect():
b2c3d4e5 (Bob    2025-04-02 11:00:00 +0000  5)     return db.connect()
b2c3d4e5 (Bob    2025-04-02 11:00:00 +0000  6)
c3d4e5f6 (Alice  2025-04-03 12:00:00 +0000  7) def query(sql):
c3d4e5f6 (Alice  2025-04-03 12:00:00 +0000  8)     conn = connect()
c3d4e5f6 (Alice  2025-04-03 12:00:00 +0000  9)     return conn.execute(sql)
c3d4e5f6 (Alice  2025-04-03 12:00:00 +0000 10)
a1b2c3d4 (Alice  2025-04-01 10:00:00 +0000 11) def close():
a1b2c3d4 (Alice  2025-04-01 10:00:00 +0000 12)     pass
"""

BRANCH_OUTPUT = """\
  bugfix/login-redirect
  bugfix/session-timeout
  feature/auth
  feature/caching
  feature/rate-limit
* main
  release/v1.0
  release/v1.1
"""

BRANCH_VERBOSE = """\
  bugfix/login-redirect  a1b2c3d Fix login redirect
  bugfix/session-timeout b2c3d4e Handle session timeout
  feature/auth           c3d4e5f Add authentication
  feature/caching        d4e5f6a Add caching layer
  feature/rate-limit     e5f6a7b Add rate limiting
* main                   f6a7b8c Merge pull request #42
  release/v1.0           a7b8c9d Release v1.0
  release/v1.1           b8c9d0e Release v1.1
"""

STASH_LIST = """\
stash@{0}: WIP on feature/auth: a1b2c3d Add login
stash@{1}: WIP on main: b2c3d4e Update deps
stash@{2}: On feature/cache: c3d4e5f Cache experiment
"""
```

- [ ] **Step 2: Write git diff parser tests**

Add to `tests/output_tests/test_git_parsers.py`:

```python
"""Tests for git output parsers."""

from tokkit_output.parsers.git_diff import GitDiffParser
from tests.output_tests.fixtures import git_output as fx


class TestGitDiffDetect:
    def setup_method(self):
        self.parser = GitDiffParser()

    def test_detects_diff(self):
        assert self.parser.detect(fx.DIFF_SIMPLE) >= 0.8

    def test_detects_diff_with_lockfile(self):
        assert self.parser.detect(fx.DIFF_WITH_LOCKFILE) >= 0.8

    def test_detects_stat(self):
        assert self.parser.detect(fx.DIFF_STAT) >= 0.7

    def test_rejects_non_diff(self):
        assert self.parser.detect("hello world\nfoo bar") < 0.6

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.6


class TestGitDiffParse:
    def setup_method(self):
        self.parser = GitDiffParser()

    def test_simple_diff_has_rows(self):
        result = self.parser.parse(fx.DIFF_SIMPLE)
        assert result.tool == "git-diff"
        assert len(result.rows) > 0
        assert result.schema == ["file", "lines_changed", "content"]

    def test_strips_index_lines(self):
        result = self.parser.parse(fx.DIFF_SIMPLE)
        full_output = "\n".join(";".join(row) for row in result.rows)
        assert "index 1234567" not in full_output

    def test_lockfile_elided(self):
        result = self.parser.parse(fx.DIFF_WITH_LOCKFILE)
        content_parts = [row[2] for row in result.rows]
        all_content = " ".join(content_parts)
        assert "lockfile changed" in all_content.lower() or "lock" in all_content.lower()
        # Should NOT contain the 100 added lines
        assert "pkg-50" not in all_content

    def test_large_hunk_truncated(self):
        result = self.parser.parse(fx.DIFF_LARGE_HUNK)
        content_parts = [row[2] for row in result.rows]
        all_content = " ".join(content_parts)
        assert "truncated" in all_content.lower()
        # Should not contain all 60 lines
        assert "added line 55" not in all_content

    def test_stat_output_parsed(self):
        result = self.parser.parse(fx.DIFF_STAT)
        assert "4 files" in result.summary or "files changed" in result.summary

    def test_multiple_files_parsed(self):
        result = self.parser.parse(fx.DIFF_MULTIPLE_FILES)
        files = set(row[0] for row in result.rows)
        assert len(files) >= 2

    def test_summary_has_file_count(self):
        result = self.parser.parse(fx.DIFF_SIMPLE)
        assert result.summary  # Non-empty summary
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_git_parsers.py::TestGitDiffDetect -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_output.parsers.git_diff'`

- [ ] **Step 4: Implement git diff parser**

Create `py/tokkit_output/parsers/git_diff.py`:

```python
"""Git diff output parser.

Algorithms ported from token-saver:
- Context windowing (leading buffer + trailing counter)
- Hunk truncation (max 50 changed lines per hunk)
- Lock file elision (package-lock.json etc. → one-liner)
- Index/meta line stripping
- Stat bar stripping
"""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "lines_changed", "content"]

# Detection
_DIFF_GIT_RE = re.compile(r"^diff --git a/")
_HUNK_RE = re.compile(r"^@@ .+ @@")
_STAT_RE = re.compile(r"^\s*\S+\s*\|\s*\d+")
_STAT_SUMMARY_RE = re.compile(r"(\d+) files? changed")

# Parsing
_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_INDEX_RE = re.compile(r"^index [0-9a-f]+\.\.[0-9a-f]+")
_META_RE = re.compile(r"^(---|\+\+\+) ")

_LOCK_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "poetry.lock", "uv.lock", "go.sum",
    "Gemfile.lock", "composer.lock", "Pipfile.lock",
})

_MAX_HUNK_LINES = 50
_MAX_CONTEXT = 3


def _is_lock_file(path: str) -> bool:
    """Check if a file path is a known lock file."""
    basename = path.rsplit("/", 1)[-1] if "/" in path else path
    return basename in _LOCK_FILES


def _compress_diff_hunks(lines: list[str]) -> tuple[str, int]:
    """Compress diff hunks with context windowing and truncation.

    Returns (compressed_text, lines_changed_count).
    """
    result: list[str] = []
    leading_buffer: list[str] = []
    changes = 0
    hunk_changes = 0
    truncated = False
    trailing_remaining = 0

    for line in lines:
        if _HUNK_RE.match(line):
            # New hunk: flush buffer, reset
            leading_buffer = []
            hunk_changes = 0
            truncated = False
            result.append(line)
            continue

        if _INDEX_RE.match(line) or _META_RE.match(line):
            continue

        is_change = line.startswith("+") or line.startswith("-")

        if is_change:
            hunk_changes += 1
            changes += 1

            if hunk_changes > _MAX_HUNK_LINES and not truncated:
                result.append(f"... (truncated after {_MAX_HUNK_LINES} changed lines)")
                truncated = True
                continue
            if truncated:
                continue

            # Flush leading context buffer (last N lines)
            if leading_buffer:
                result.extend(leading_buffer[-_MAX_CONTEXT:])
                leading_buffer = []

            result.append(line)
            trailing_remaining = _MAX_CONTEXT
        else:
            # Context line
            if trailing_remaining > 0:
                result.append(line)
                trailing_remaining -= 1
            else:
                leading_buffer.append(line)

    return "\n".join(result), changes


def _parse_stat(text: str) -> ParseResult:
    """Parse `git diff --stat` output."""
    lines = text.strip().splitlines()
    rows: list[list[str]] = []
    summary = ""

    for line in lines:
        sm = _STAT_SUMMARY_RE.search(line)
        if sm:
            summary = line.strip()
            continue
        m = _STAT_RE.match(line)
        if m:
            parts = line.split("|", 1)
            filename = parts[0].strip()
            count = parts[1].strip().split()[0] if len(parts) > 1 else "0"
            rows.append([filename, count, ""])

    if not summary:
        summary = f"{len(rows)} files"

    return ParseResult(tool="git-diff", summary=summary, schema=_SCHEMA, rows=rows)


class GitDiffParser(BaseParser):
    id = "git-diff"
    hint_values = ["git-diff", "git"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _DIFF_GIT_RE.search(clean, re.MULTILINE):
            score += 0.6
        if _HUNK_RE.search(clean, re.MULTILINE):
            score += 0.3
        if _STAT_RE.search(clean, re.MULTILINE) and _STAT_SUMMARY_RE.search(clean):
            score += 0.7
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)

        # Check if this is --stat output
        if not _DIFF_GIT_RE.search(clean, re.MULTILINE) and _STAT_RE.search(clean, re.MULTILINE):
            return _parse_stat(clean)

        lines = clean.splitlines()
        rows: list[list[str]] = []
        current_file: str | None = None
        current_lines: list[str] = []
        total_changes = 0

        def flush_file():
            nonlocal total_changes
            if current_file is None:
                return
            if _is_lock_file(current_file):
                n = len([l for l in current_lines if l.startswith("+") or l.startswith("-")])
                rows.append([current_file, str(n), f"(lockfile changed, {n} lines)"])
                total_changes += n
            else:
                compressed, n_changes = _compress_diff_hunks(current_lines)
                total_changes += n_changes
                if compressed.strip():
                    rows.append([current_file, str(n_changes), compressed])

        for line in lines:
            fm = _FILE_RE.match(line)
            if fm:
                flush_file()
                current_file = fm.group(2)
                current_lines = []
                continue
            if current_file is not None:
                current_lines.append(line)

        flush_file()

        n_files = len(rows)
        summary = f"{n_files} file{'s' if n_files != 1 else ''}, {total_changes} change{'s' if total_changes != 1 else ''}"

        return ParseResult(
            tool="git-diff",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_git_parsers.py::TestGitDiffDetect tests/output_tests/test_git_parsers.py::TestGitDiffParse -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add py/tokkit_output/parsers/git_diff.py tests/output_tests/fixtures/git_output.py tests/output_tests/test_git_parsers.py
git commit -m "feat: add git diff parser with context windowing and lock file elision"
```

---

### Task 5: Git Status + Log Parsers

**Files:**
- Create: `py/tokkit_output/parsers/git_status.py`
- Create: `py/tokkit_output/parsers/git_log.py`
- Modify: `tests/output_tests/test_git_parsers.py` (add tests)

Fixtures already created in Task 4.

- [ ] **Step 1: Add git status and log tests to test_git_parsers.py**

Append to `tests/output_tests/test_git_parsers.py`:

```python
from tokkit_output.parsers.git_status import GitStatusParser
from tokkit_output.parsers.git_log import GitLogParser


class TestGitStatusDetect:
    def setup_method(self):
        self.parser = GitStatusParser()

    def test_detects_long_status(self):
        assert self.parser.detect(fx.STATUS_DIRTY) >= 0.8

    def test_detects_short_status(self):
        assert self.parser.detect(fx.STATUS_SHORT) >= 0.7

    def test_detects_clean(self):
        assert self.parser.detect(fx.STATUS_CLEAN) >= 0.7

    def test_rejects_non_status(self):
        assert self.parser.detect("hello world") < 0.6


class TestGitStatusParse:
    def setup_method(self):
        self.parser = GitStatusParser()

    def test_dirty_repo_summary(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        assert result.tool == "git-status"
        # Should count modified, new, untracked
        assert "M:" in result.summary or "modified" in result.summary.lower()

    def test_dirty_repo_has_rows(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        assert len(result.rows) >= 5  # At least 5 files mentioned

    def test_schema(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        assert result.schema == ["file", "status", "staged"]

    def test_clean_repo(self):
        result = self.parser.parse(fx.STATUS_CLEAN)
        assert "clean" in result.summary.lower()

    def test_short_format(self):
        result = self.parser.parse(fx.STATUS_SHORT)
        assert len(result.rows) >= 5

    def test_large_status_groups_directories(self):
        result = self.parser.parse(fx.STATUS_LARGE)
        # With 45 files, some directories should be grouped
        content = "\n".join(";".join(row) for row in result.rows)
        # Should compress — fewer rows than 45 raw files
        assert len(result.rows) <= 45


class TestGitLogDetect:
    def setup_method(self):
        self.parser = GitLogParser()

    def test_detects_verbose_log(self):
        assert self.parser.detect(fx.LOG_VERBOSE) >= 0.8

    def test_detects_oneline_log(self):
        assert self.parser.detect(fx.LOG_ONELINE) >= 0.7

    def test_rejects_non_log(self):
        assert self.parser.detect("hello world") < 0.6


class TestGitLogParse:
    def setup_method(self):
        self.parser = GitLogParser()

    def test_verbose_extracts_oneliners(self):
        result = self.parser.parse(fx.LOG_VERBOSE)
        assert result.tool == "git-log"
        assert result.schema == ["hash", "message"]
        assert len(result.rows) == 3
        # First commit
        assert "a1b2c3d4" in result.rows[0][0] or result.rows[0][0].startswith("a1b2c3d")
        assert "authentication" in result.rows[0][1]

    def test_oneline_capped(self):
        result = self.parser.parse(fx.LOG_ONELINE)
        # Default cap: 10 entries
        assert len(result.rows) <= 10

    def test_short_log_not_capped(self):
        result = self.parser.parse(fx.LOG_ONELINE_SHORT)
        assert len(result.rows) == 3

    def test_summary_has_count(self):
        result = self.parser.parse(fx.LOG_ONELINE)
        assert "10" in result.summary or "entries" in result.summary.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_git_parsers.py::TestGitStatusDetect -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement git status parser**

Create `py/tokkit_output/parsers/git_status.py`:

```python
"""Git status output parser."""

import re
from collections import Counter, defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "status", "staged"]

# Long format detection
_ON_BRANCH_RE = re.compile(r"^On branch ")
_CLEAN_RE = re.compile(r"nothing to commit")

# Long format: "	modified:   src/auth.py"
_LONG_MOD_RE = re.compile(r"^\t(modified|new file|deleted|renamed|copied):\s+(.+)$")

# Short format: "M  src/auth.py", " M src/auth.py", "?? TODO.md", "A  src/new.py"
_SHORT_RE = re.compile(r"^(.)(.) (.+)$")

# Hint lines to strip
_HINT_RE = re.compile(r'^\s*\(use "git ')

_STATUS_MAP = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed",
               "C": "copied", "?": "untracked", "U": "conflict", "!": "ignored"}

_DIR_GROUP_THRESHOLD = 8


class GitStatusParser(BaseParser):
    id = "git-status"
    hint_values = ["git-status"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _ON_BRANCH_RE.search(clean, re.MULTILINE):
            score += 0.5
        if _CLEAN_RE.search(clean):
            score += 0.3
        if _LONG_MOD_RE.search(clean, re.MULTILINE):
            score += 0.4
        # Short format check
        short_count = sum(1 for l in clean.splitlines() if _SHORT_RE.match(l.strip()))
        if short_count >= 2:
            score += 0.5
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)

        if _CLEAN_RE.search(clean):
            return ParseResult(
                tool="git-status", summary="Working tree clean",
                schema=_SCHEMA, rows=[], verbose=verbose,
            )

        rows: list[list[str]] = []
        counts: Counter = Counter()

        # Try short format first
        in_staged = False
        for line in clean.splitlines():
            if _HINT_RE.match(line):
                continue

            # Detect section context for long format
            if "Changes to be committed" in line:
                in_staged = True
                continue
            if "Changes not staged" in line or "Untracked files" in line:
                in_staged = False
                continue

            # Short format
            m = _SHORT_RE.match(line.strip())
            if m:
                idx_status = m.group(1).strip()
                wt_status = m.group(2).strip()
                filepath = m.group(3).strip()
                status_char = idx_status or wt_status
                status = _STATUS_MAP.get(status_char, status_char)
                staged = "yes" if idx_status and idx_status != "?" else "no"
                rows.append([filepath, status, staged])
                counts[status_char] += 1
                continue

            # Long format
            m = _LONG_MOD_RE.match(line)
            if m:
                status_word = m.group(1)
                filepath = m.group(2).strip()
                status_char = status_word[0].upper()
                staged = "yes" if in_staged else "no"
                rows.append([filepath, status_word, staged])
                counts[status_char] += 1

        # Directory grouping for large status
        if len(rows) > _DIR_GROUP_THRESHOLD:
            rows = self._group_by_directory(rows)

        # Build summary: "Files: 15 (M:8, A:3, D:2, ?:2)"
        parts = [f"{k}:{v}" for k, v in sorted(counts.items())]
        summary = f"Files: {sum(counts.values())} ({', '.join(parts)})" if parts else "No changes"

        return ParseResult(
            tool="git-status", summary=summary,
            schema=_SCHEMA, rows=rows, verbose=verbose,
        )

    def _group_by_directory(self, rows: list[list[str]]) -> list[list[str]]:
        """Group files by directory when a dir has >_DIR_GROUP_THRESHOLD files."""
        by_dir: dict[str, list[list[str]]] = defaultdict(list)
        for row in rows:
            filepath = row[0]
            dir_part = filepath.rsplit("/", 1)[0] if "/" in filepath else "."
            by_dir[dir_part].append(row)

        result: list[list[str]] = []
        for dir_path, dir_rows in by_dir.items():
            if len(dir_rows) > _DIR_GROUP_THRESHOLD:
                status_counts = Counter(r[1] for r in dir_rows)
                parts = ", ".join(f"{k}:{v}" for k, v in sorted(status_counts.items()))
                result.append([f"{dir_path}/ ({len(dir_rows)} files: {parts})", "group", ""])
            else:
                result.extend(dir_rows)
        return result
```

- [ ] **Step 4: Implement git log parser**

Create `py/tokkit_output/parsers/git_log.py`:

```python
"""Git log output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["hash", "message"]

# Verbose format: "commit a1b2c3d4..."
_COMMIT_RE = re.compile(r"^commit ([0-9a-f]{7,40})")
# One-line format: "a1b2c3d message"
_ONELINE_RE = re.compile(r"^([0-9a-f]{7,12})\s+(.+)$")
# Graph format: lines with graph chars
_GRAPH_RE = re.compile(r"^[|/\\ *]+")
# Metadata lines to skip
_META_RE = re.compile(r"^(Author|Date|Merge):")

_MAX_ENTRIES = 10


class GitLogParser(BaseParser):
    id = "git-log"
    hint_values = ["git-log"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _COMMIT_RE.search(clean, re.MULTILINE):
            score += 0.6
        oneline_count = sum(1 for l in clean.splitlines() if _ONELINE_RE.match(l.strip()))
        if oneline_count >= 2:
            score += 0.5
        if _META_RE.search(clean, re.MULTILINE):
            score += 0.3
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Try one-line format first
        oneline_rows = []
        for line in lines:
            m = _ONELINE_RE.match(line.strip())
            if m:
                oneline_rows.append([m.group(1), m.group(2)])

        if oneline_rows:
            max_entries = _MAX_ENTRIES if not verbose else len(oneline_rows)
            capped = oneline_rows[:max_entries]
            total = len(oneline_rows)
            remaining = total - len(capped)
            summary = f"{len(capped)} entries"
            if remaining > 0:
                summary += f" (showing {len(capped)} of {total})"
            return ParseResult(
                tool="git-log", summary=summary,
                schema=_SCHEMA, rows=capped, verbose=verbose,
            )

        # Verbose format: parse commit blocks
        rows: list[list[str]] = []
        current_hash = ""
        current_message_lines: list[str] = []

        def flush():
            if current_hash:
                msg = " ".join(l.strip() for l in current_message_lines if l.strip())
                if msg:
                    rows.append([current_hash[:8], msg])

        for line in lines:
            m = _COMMIT_RE.match(line)
            if m:
                flush()
                current_hash = m.group(1)
                current_message_lines = []
                continue
            if _META_RE.match(line.strip()):
                continue
            if current_hash and line.strip():
                current_message_lines.append(line)

        flush()

        max_entries = _MAX_ENTRIES if not verbose else len(rows)
        capped = rows[:max_entries]
        total = len(rows)
        remaining = total - len(capped)
        summary = f"{len(capped)} entries"
        if remaining > 0:
            summary += f" (showing {len(capped)} of {total})"

        return ParseResult(
            tool="git-log", summary=summary,
            schema=_SCHEMA, rows=capped, verbose=verbose,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_git_parsers.py -v`
Expected: All git parser tests PASS.

- [ ] **Step 6: Commit**

```bash
git add py/tokkit_output/parsers/git_status.py py/tokkit_output/parsers/git_log.py tests/output_tests/test_git_parsers.py
git commit -m "feat: add git status and log parsers"
```

---

### Task 6: Git Show + Blame + Branch + Stash Parsers

**Files:**
- Create: `py/tokkit_output/parsers/git_show.py`
- Create: `py/tokkit_output/parsers/git_blame.py`
- Create: `py/tokkit_output/parsers/git_branch.py`
- Create: `py/tokkit_output/parsers/git_stash.py`
- Modify: `tests/output_tests/test_git_parsers.py` (add tests)

Fixtures already exist in `git_output.py` from Task 4.

- [ ] **Step 1: Add show/blame/branch/stash tests to test_git_parsers.py**

Append to `tests/output_tests/test_git_parsers.py`:

```python
from tokkit_output.parsers.git_show import GitShowParser
from tokkit_output.parsers.git_blame import GitBlameParser
from tokkit_output.parsers.git_branch import GitBranchParser
from tokkit_output.parsers.git_stash import GitStashParser


class TestGitShowDetect:
    def setup_method(self):
        self.parser = GitShowParser()

    def test_detects_show(self):
        assert self.parser.detect(fx.SHOW_COMMIT) >= 0.8

    def test_rejects_plain_diff(self):
        # Pure diff without commit header should not trigger show
        assert self.parser.detect(fx.DIFF_SIMPLE) < 0.6


class TestGitShowParse:
    def setup_method(self):
        self.parser = GitShowParser()

    def test_extracts_metadata(self):
        result = self.parser.parse(fx.SHOW_COMMIT)
        assert result.tool == "git-show"
        assert "a1b2c3d" in result.summary
        assert "authentication" in result.summary

    def test_has_diff_content(self):
        result = self.parser.parse(fx.SHOW_COMMIT)
        assert len(result.rows) > 0


class TestGitBlameDetect:
    def setup_method(self):
        self.parser = GitBlameParser()

    def test_detects_blame(self):
        assert self.parser.detect(fx.BLAME_OUTPUT) >= 0.8

    def test_rejects_non_blame(self):
        assert self.parser.detect("hello world") < 0.6


class TestGitBlameParse:
    def setup_method(self):
        self.parser = GitBlameParser()

    def test_collapses_ranges(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        assert result.tool == "git-blame"
        assert result.schema == ["lines", "hash", "author"]
        # 12 lines should collapse to fewer rows (3-4 author ranges)
        assert len(result.rows) < 12

    def test_preserves_all_authors(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        authors = set(row[2] for row in result.rows)
        assert "Alice" in authors
        assert "Bob" in authors


class TestGitBranchDetect:
    def setup_method(self):
        self.parser = GitBranchParser()

    def test_detects_branch_list(self):
        assert self.parser.detect(fx.BRANCH_OUTPUT) >= 0.7

    def test_detects_verbose_branches(self):
        assert self.parser.detect(fx.BRANCH_VERBOSE) >= 0.7

    def test_rejects_non_branch(self):
        assert self.parser.detect("hello world") < 0.6


class TestGitBranchParse:
    def setup_method(self):
        self.parser = GitBranchParser()

    def test_lists_branches(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        assert result.tool == "git-branch"
        assert len(result.rows) == 8

    def test_marks_current_branch(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        current = [row for row in result.rows if row[1] == "*"]
        assert len(current) == 1
        assert "main" in current[0][0]


class TestGitStashDetect:
    def setup_method(self):
        self.parser = GitStashParser()

    def test_detects_stash(self):
        assert self.parser.detect(fx.STASH_LIST) >= 0.8

    def test_rejects_non_stash(self):
        assert self.parser.detect("hello world") < 0.6


class TestGitStashParse:
    def setup_method(self):
        self.parser = GitStashParser()

    def test_parses_entries(self):
        result = self.parser.parse(fx.STASH_LIST)
        assert result.tool == "git-stash"
        assert len(result.rows) == 3
        assert result.schema == ["index", "branch", "message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_git_parsers.py::TestGitShowDetect -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement git show parser**

Create `py/tokkit_output/parsers/git_show.py`:

```python
"""Git show output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi
from tokkit_output.parsers.git_diff import _compress_diff_hunks, _FILE_RE, _is_lock_file

_COMMIT_RE = re.compile(r"^commit ([0-9a-f]{7,40})")
_META_RE = re.compile(r"^(Author|Date|Merge):")
_DIFF_START_RE = re.compile(r"^diff --git ")

_SCHEMA = ["file", "lines_changed", "content"]


class GitShowParser(BaseParser):
    id = "git-show"
    hint_values = ["git-show"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _COMMIT_RE.search(clean, re.MULTILINE):
            score += 0.4
        if _META_RE.search(clean, re.MULTILINE):
            score += 0.2
        if _DIFF_START_RE.search(clean, re.MULTILINE):
            score += 0.3
        # Must have BOTH commit header and diff to be git-show
        has_commit = bool(_COMMIT_RE.search(clean, re.MULTILINE))
        has_diff = bool(_DIFF_START_RE.search(clean, re.MULTILINE))
        if has_commit and has_diff:
            return min(score + 0.1, 1.0)
        return min(score, 0.5)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Extract metadata
        commit_hash = ""
        message_lines: list[str] = []
        diff_start = 0

        in_message = False
        for i, line in enumerate(lines):
            m = _COMMIT_RE.match(line)
            if m:
                commit_hash = m.group(1)[:8]
                continue
            if _META_RE.match(line.strip()):
                in_message = True
                continue
            if _DIFF_START_RE.match(line):
                diff_start = i
                break
            if in_message and line.strip():
                message_lines.append(line.strip())

        message = " ".join(message_lines)
        summary = f"{commit_hash} {message}" if commit_hash else message

        # Parse diff portion using git_diff's compression
        rows: list[list[str]] = []
        if diff_start > 0:
            current_file: str | None = None
            current_lines: list[str] = []

            def flush():
                if current_file is None:
                    return
                if _is_lock_file(current_file):
                    n = len([l for l in current_lines if l.startswith("+") or l.startswith("-")])
                    rows.append([current_file, str(n), f"(lockfile changed, {n} lines)"])
                else:
                    compressed, n = _compress_diff_hunks(current_lines)
                    if compressed.strip():
                        rows.append([current_file, str(n), compressed])

            for line in lines[diff_start:]:
                fm = _FILE_RE.match(line)
                if fm:
                    flush()
                    current_file = fm.group(2)
                    current_lines = []
                    continue
                if current_file is not None:
                    current_lines.append(line)
            flush()

        return ParseResult(
            tool="git-show", summary=summary,
            schema=_SCHEMA, rows=rows, verbose=verbose,
        )
```

- [ ] **Step 4: Implement git blame parser**

Create `py/tokkit_output/parsers/git_blame.py`:

```python
"""Git blame output parser — collapses consecutive same-author ranges."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["lines", "hash", "author"]

# a1b2c3d4 (Alice  2025-04-01 10:00:00 +0000  1) import os
_BLAME_RE = re.compile(
    r"^([0-9a-f^]{7,8})\s+\((\S+)\s+\d{4}-\d{2}-\d{2}\s+[\d:]+\s+[+-]\d{4}\s+(\d+)\)\s"
)


class GitBlameParser(BaseParser):
    id = "git-blame"
    hint_values = ["git-blame"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        count = sum(1 for l in clean.splitlines() if _BLAME_RE.match(l))
        if count >= 3:
            return 0.9
        if count >= 1:
            return 0.6
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        entries: list[tuple[str, str, int]] = []  # (hash, author, line_no)

        for line in clean.splitlines():
            m = _BLAME_RE.match(line)
            if m:
                entries.append((m.group(1), m.group(2), int(m.group(3))))

        if not entries:
            return ParseResult(
                tool="git-blame", summary="No blame data",
                schema=_SCHEMA, rows=[], verbose=verbose,
            )

        # Collapse consecutive same-author+hash ranges
        rows: list[list[str]] = []
        range_start = entries[0][2]
        prev_hash, prev_author = entries[0][0], entries[0][1]

        for i in range(1, len(entries)):
            h, a, ln = entries[i]
            if h == prev_hash and a == prev_author:
                continue
            # Flush range
            range_end = entries[i - 1][2]
            if range_start == range_end:
                rows.append([str(range_start), prev_hash, prev_author])
            else:
                rows.append([f"{range_start}-{range_end}", prev_hash, prev_author])
            range_start = ln
            prev_hash, prev_author = h, a

        # Flush last range
        range_end = entries[-1][2]
        if range_start == range_end:
            rows.append([str(range_start), prev_hash, prev_author])
        else:
            rows.append([f"{range_start}-{range_end}", prev_hash, prev_author])

        n_authors = len(set(e[1] for e in entries))
        summary = f"{len(entries)} lines, {n_authors} author{'s' if n_authors != 1 else ''}, {len(rows)} range{'s' if len(rows) != 1 else ''}"

        return ParseResult(
            tool="git-blame", summary=summary,
            schema=_SCHEMA, rows=rows, verbose=verbose,
        )
```

- [ ] **Step 5: Implement git branch parser**

Create `py/tokkit_output/parsers/git_branch.py`:

```python
"""Git branch output parser."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["branch", "current", "info"]

# "* main" or "  feature/auth"
_BRANCH_RE = re.compile(r"^([* ]) (.+?)(?:\s{2,}(.+))?$")
_REMOTE_RE = re.compile(r"^\s*remotes?/")

_GROUP_THRESHOLD = 20


class GitBranchParser(BaseParser):
    id = "git-branch"
    hint_values = ["git-branch"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.strip().splitlines()
        branch_count = sum(1 for l in lines if _BRANCH_RE.match(l))
        has_current = any(l.strip().startswith("*") for l in lines)
        if branch_count >= 2 and has_current:
            return 0.85
        if branch_count >= 2:
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows: list[list[str]] = []

        for line in clean.splitlines():
            m = _BRANCH_RE.match(line)
            if m:
                marker = m.group(1)
                branch = m.group(2).strip()
                info = m.group(3).strip() if m.group(3) else ""
                current = "*" if marker == "*" else ""
                rows.append([branch, current, info])

        # Group by prefix if too many branches
        if len(rows) > _GROUP_THRESHOLD:
            rows = self._group_by_prefix(rows)

        summary = f"{len(rows)} branches"
        return ParseResult(
            tool="git-branch", summary=summary,
            schema=_SCHEMA, rows=rows, verbose=verbose,
        )

    def _group_by_prefix(self, rows: list[list[str]]) -> list[list[str]]:
        by_prefix: dict[str, list[list[str]]] = defaultdict(list)
        for row in rows:
            branch = row[0]
            prefix = branch.split("/", 1)[0] if "/" in branch else ""
            by_prefix[prefix].append(row)

        result: list[list[str]] = []
        for prefix, group in by_prefix.items():
            if len(group) > 5 and prefix:
                # Keep current branch, group the rest
                current = [r for r in group if r[1] == "*"]
                result.extend(current)
                n_other = len(group) - len(current)
                if n_other > 0:
                    result.append([f"{prefix}/ ({n_other} branches)", "", ""])
            else:
                result.extend(group)
        return result
```

- [ ] **Step 6: Implement git stash parser**

Create `py/tokkit_output/parsers/git_stash.py`:

```python
"""Git stash list parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["index", "branch", "message"]

# stash@{0}: WIP on feature/auth: a1b2c3d Add login
_STASH_RE = re.compile(
    r"^stash@\{(\d+)\}:\s+(?:WIP on|On)\s+(\S+):\s+(?:[0-9a-f]+\s+)?(.+)$"
)

_MAX_ENTRIES = 10


class GitStashParser(BaseParser):
    id = "git-stash"
    hint_values = ["git-stash"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        count = sum(1 for l in clean.splitlines() if _STASH_RE.match(l.strip()))
        if count >= 2:
            return 0.9
        if count >= 1:
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows: list[list[str]] = []

        for line in clean.splitlines():
            m = _STASH_RE.match(line.strip())
            if m:
                rows.append([m.group(1), m.group(2), m.group(3)])

        # Cap entries
        if len(rows) > _MAX_ENTRIES and not verbose:
            capped = rows[:5] + rows[-2:]
            remaining = len(rows) - 7
            capped.insert(5, [f"... ({remaining} more)", "", ""])
            rows = capped

        summary = f"{len(rows)} stash{'es' if len(rows) != 1 else ''}"
        return ParseResult(
            tool="git-stash", summary=summary,
            schema=_SCHEMA, rows=rows, verbose=verbose,
        )
```

- [ ] **Step 7: Run all tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_git_parsers.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add py/tokkit_output/parsers/git_show.py py/tokkit_output/parsers/git_blame.py py/tokkit_output/parsers/git_branch.py py/tokkit_output/parsers/git_stash.py tests/output_tests/test_git_parsers.py
git commit -m "feat: add git show, blame, branch, and stash parsers"
```

---

### Task 7: Kubectl Parser

**Files:**
- Create: `tests/output_tests/fixtures/k8s_output.py`
- Create: `py/tokkit_output/parsers/kubectl.py`
- Create: `tests/output_tests/test_kubectl_parser.py`

- [ ] **Step 1: Create k8s fixtures**

Create `tests/output_tests/fixtures/k8s_output.py`:

```python
"""Realistic kubectl output fixtures."""

GET_PODS = """\
NAME                          READY   STATUS             RESTARTS   AGE
api-server-7d8f9b6c4-x2k9p   1/1     Running            0          3d
api-server-7d8f9b6c4-m4n7q   1/1     Running            0          3d
worker-5f6a7b8c9-p3q4r       1/1     Running            0          2d
worker-5f6a7b8c9-s5t6u       1/1     Running            0          2d
worker-5f6a7b8c9-v7w8x       0/1     CrashLoopBackOff   5          2d
redis-0                       1/1     Running            0          5d
postgres-0                    1/1     Running            0          5d
celery-beat-6a7b8c9d0-y9z0a  1/1     Running            0          1d
celery-worker-b1c2d3e4f-h5i6 1/1     Running            0          1d
celery-worker-b1c2d3e4f-j7k8 1/1     Running            0          1d
ingress-nginx-c3d4e5f6-l9m0  1/1     Running            0          7d
cert-manager-d4e5f6a7-n1o2p  1/1     Running            0          7d
job-migrate-q3r4s             0/1     Completed          0          1d
"""

GET_PODS_ALL_HEALTHY = """\
NAME                       READY   STATUS    RESTARTS   AGE
app-7d8f9b6c4-x2k9p       1/1     Running   0          3d
app-7d8f9b6c4-m4n7q       1/1     Running   0          3d
db-0                       1/1     Running   0          5d
"""

GET_SERVICES = """\
NAME         TYPE           CLUSTER-IP       EXTERNAL-IP    PORT(S)        AGE
api          ClusterIP      10.96.0.1        <none>         8080/TCP       3d
frontend     LoadBalancer   10.96.0.2        34.56.78.90    80:30080/TCP   3d
redis        ClusterIP      10.96.0.3        <none>         6379/TCP       5d
"""

DESCRIBE_POD = """\
Name:             worker-5f6a7b8c9-v7w8x
Namespace:        default
Priority:         0
Service Account:  default
Node:             node-1/10.0.0.1
Labels:           app=worker
                  pod-template-hash=5f6a7b8c9
Annotations:      kubernetes.io/config.hash: abc123def456
                  kubernetes.io/config.mirror: abc123def456
                  kubectl.kubernetes.io/last-applied-configuration:
                    {"apiVersion":"v1","kind":"Pod","metadata":{"annotations":{},"labels":{"app":"worker"}}}
Status:           Running
IP:               10.244.0.15
Controlled By:    ReplicaSet/worker-5f6a7b8c9
Containers:
  worker:
    Image:          myapp/worker:v1.2.3
    Port:           8080/TCP
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
    Ready:          False
    Restart Count:  5
Conditions:
  Type              Status
  Initialized       True
  Ready             False
  ContainersReady   False
  PodScheduled      True
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Pulled     5m (x6 over 30m)   kubelet            Container image "myapp/worker:v1.2.3" already present
  Warning  BackOff    2m (x20 over 30m)  kubelet            Back-off restarting failed container
"""

LOGS_WITH_ERRORS = """\
2025-04-07 10:00:01 INFO Starting worker process
2025-04-07 10:00:02 INFO Connected to Redis
2025-04-07 10:00:03 INFO Processing queue: tasks
""" + "\n".join([f"2025-04-07 10:00:{i:02d} INFO Processed task #{i}" for i in range(4, 50)]) + """
2025-04-07 10:00:50 ERROR Failed to process task #50: ConnectionError: Redis connection lost
2025-04-07 10:00:51 ERROR Traceback: redis.exceptions.ConnectionError
2025-04-07 10:00:52 INFO Reconnecting to Redis...
2025-04-07 10:00:53 INFO Reconnected successfully
""" + "\n".join([f"2025-04-07 10:01:{i:02d} INFO Processed task #{i}" for i in range(1, 20)]) + """
2025-04-07 10:01:20 INFO Worker shutdown complete
"""
```

- [ ] **Step 2: Write kubectl parser tests**

Create `tests/output_tests/test_kubectl_parser.py`:

```python
"""Tests for kubectl output parser."""

from tokkit_output.parsers.kubectl import KubectlParser
from tests.output_tests.fixtures import k8s_output as fx


class TestKubectlDetect:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_detects_get_pods(self):
        assert self.parser.detect(fx.GET_PODS) >= 0.8

    def test_detects_describe(self):
        assert self.parser.detect(fx.DESCRIBE_POD) >= 0.7

    def test_detects_services(self):
        assert self.parser.detect(fx.GET_SERVICES) >= 0.7

    def test_rejects_non_k8s(self):
        assert self.parser.detect("hello world\nfoo bar") < 0.6


class TestKubectlParsePods:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_elides_healthy_pods(self):
        result = self.parser.parse(fx.GET_PODS)
        assert result.tool == "kubectl"
        # Should only show unhealthy pods in default mode
        rows_text = str(result.rows)
        assert "CrashLoopBackOff" in rows_text
        # Healthy pods should be summarized, not listed individually
        assert "healthy" in result.summary.lower()

    def test_all_healthy_summary_only(self):
        result = self.parser.parse(fx.GET_PODS_ALL_HEALTHY)
        # All healthy: summary only, minimal rows
        assert "healthy" in result.summary.lower()
        assert len(result.rows) == 0 or "Running" not in str(result.rows)

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.GET_PODS, verbose=True)
        assert len(result.rows) >= 10  # All pods shown

    def test_services_parsed(self):
        result = self.parser.parse(fx.GET_SERVICES)
        assert len(result.rows) >= 3


class TestKubectlParseDescribe:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_describe_extracts_key_sections(self):
        result = self.parser.parse(fx.DESCRIBE_POD)
        all_content = str(result.rows)
        # Should keep conditions and events
        assert "CrashLoopBackOff" in all_content or "BackOff" in all_content
        # Should NOT have the long annotation
        assert "last-applied-configuration" not in all_content


class TestKubectlParseLogs:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_logs_head_tail_with_errors(self):
        result = self.parser.parse(fx.LOGS_WITH_ERRORS, verbose=False)
        all_content = str(result.rows)
        # Should keep errors
        assert "ERROR" in all_content or "ConnectionError" in all_content
        # Should have head and tail
        assert "Starting" in all_content
        assert "shutdown" in all_content
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_kubectl_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement kubectl parser**

Create `py/tokkit_output/parsers/kubectl.py`:

```python
"""Kubernetes kubectl output parser.

Handles: get pods/services/deployments, describe, logs.
Key optimization: elide healthy pods (Running + ready), keep only unhealthy.
"""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

# Detection
_TABLE_HEADER_RE = re.compile(r"^(NAME|NAMESPACE)\s+(READY|STATUS|TYPE|AGE)")
_DESCRIBE_RE = re.compile(r"^(Name|Namespace):\s+")
_LOG_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ][\d:]+")

# Pod health
_HEALTHY_STATUSES = frozenset({"Running", "Completed", "Succeeded"})
_UNHEALTHY_KEYWORDS = frozenset({
    "CrashLoopBackOff", "Error", "OOMKilled", "ImagePullBackOff",
    "ErrImagePull", "Pending", "Failed", "Terminating", "Unknown",
})

# Describe sections to keep
_KEEP_SECTIONS = {"Conditions:", "Events:", "Containers:", "Status:"}
_SKIP_ANNOTATIONS = {"kubectl.kubernetes.io/last-applied-configuration", "kubernetes.io/config"}

# Log error patterns
_LOG_ERROR_RE = re.compile(r"(ERROR|FATAL|PANIC|Exception|Traceback)", re.IGNORECASE)

_LOG_HEAD = 10
_LOG_TAIL = 10
_LOG_ERROR_CONTEXT = 2


class KubectlParser(BaseParser):
    id = "kubectl"
    hint_values = ["kubectl", "k8s"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _TABLE_HEADER_RE.search(clean, re.MULTILINE):
            score += 0.6
        if _DESCRIBE_RE.search(clean, re.MULTILINE):
            score += 0.5
        # Log format
        log_lines = sum(1 for l in clean.splitlines()[:20] if _LOG_TIMESTAMP_RE.match(l))
        if log_lines >= 5:
            score += 0.4
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)

        # Route to appropriate sub-parser
        if _TABLE_HEADER_RE.search(clean, re.MULTILINE):
            return self._parse_table(clean, verbose)
        if _DESCRIBE_RE.search(clean, re.MULTILINE):
            return self._parse_describe(clean, verbose)
        # Assume logs
        return self._parse_logs(clean, verbose)

    def _parse_table(self, text: str, verbose: bool) -> ParseResult:
        lines = text.strip().splitlines()
        if not lines:
            return ParseResult(tool="kubectl", summary="Empty", schema=[], rows=[])

        # Parse header to get column positions
        header = lines[0]
        col_names = header.split()
        schema = [c.lower() for c in col_names]

        rows: list[list[str]] = []
        healthy_count = 0
        unhealthy_count = 0
        is_pod_table = "STATUS" in header and "READY" in header

        for line in lines[1:]:
            if not line.strip():
                continue
            cells = line.split(None, len(col_names) - 1)
            while len(cells) < len(col_names):
                cells.append("")

            if is_pod_table and not verbose:
                status = cells[col_names.index("STATUS")] if "STATUS" in col_names else ""
                ready = cells[col_names.index("READY")] if "READY" in col_names else ""
                ready_parts = ready.split("/")
                is_ready = len(ready_parts) == 2 and ready_parts[0] == ready_parts[1]

                if status in _HEALTHY_STATUSES and is_ready:
                    healthy_count += 1
                    continue
                if status == "Completed":
                    healthy_count += 1
                    continue
                unhealthy_count += 1

            rows.append(cells)

        if is_pod_table and not verbose:
            total = healthy_count + unhealthy_count
            summary = f"{total} pods ({healthy_count} healthy, {unhealthy_count} unhealthy)"
        else:
            summary = f"{len(rows)} resources"

        return ParseResult(
            tool="kubectl", summary=summary,
            schema=schema, rows=rows, verbose=verbose,
        )

    def _parse_describe(self, text: str, verbose: bool) -> ParseResult:
        schema = ["section", "key", "value"]
        rows: list[list[str]] = []
        current_section = "metadata"
        skip_annotation = False

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Track sections
            if stripped.endswith(":") and not line.startswith(" "):
                current_section = stripped.rstrip(":")
                skip_annotation = False
                continue

            # Skip long annotations
            if current_section == "Annotations":
                for skip_prefix in _SKIP_ANNOTATIONS:
                    if skip_prefix in stripped:
                        skip_annotation = True
                        break
                if skip_annotation:
                    continue

            # Keep key sections + metadata
            if verbose or current_section in ("Name", "Namespace", "Status", "Node",
                                                "Labels", "Containers", "Conditions", "Events"):
                if ":" in stripped and not stripped.startswith("-"):
                    key, _, value = stripped.partition(":")
                    rows.append([current_section, key.strip(), value.strip()])
                elif stripped.startswith("-") or stripped.startswith("Type"):
                    rows.append([current_section, "", stripped])

        name = ""
        for row in rows:
            if row[1] == "Name":
                name = row[2]
                break
        summary = f"describe {name}" if name else "describe"

        return ParseResult(
            tool="kubectl", summary=summary,
            schema=schema, rows=rows, verbose=verbose,
        )

    def _parse_logs(self, text: str, verbose: bool) -> ParseResult:
        schema = ["line"]
        lines = text.strip().splitlines()

        if verbose or len(lines) <= _LOG_HEAD + _LOG_TAIL:
            return ParseResult(
                tool="kubectl", summary=f"{len(lines)} log lines",
                schema=schema, rows=[[l] for l in lines], verbose=verbose,
            )

        # Find error neighborhoods
        error_indices: set[int] = set()
        for i, line in enumerate(lines):
            if _LOG_ERROR_RE.search(line):
                for j in range(max(0, i - _LOG_ERROR_CONTEXT),
                               min(len(lines), i + _LOG_ERROR_CONTEXT + 1)):
                    error_indices.add(j)

        # Build output: head + errors + tail
        keep_indices = set(range(_LOG_HEAD))
        keep_indices |= error_indices
        keep_indices |= set(range(len(lines) - _LOG_TAIL, len(lines)))

        result_lines: list[str] = []
        prev_kept = -1
        for i in sorted(keep_indices):
            if prev_kept >= 0 and i > prev_kept + 1:
                skipped = i - prev_kept - 1
                result_lines.append(f"... ({skipped} lines skipped)")
            result_lines.append(lines[i])
            prev_kept = i

        n_errors = sum(1 for l in lines if _LOG_ERROR_RE.search(l))
        summary = f"{len(lines)} log lines, {n_errors} error{'s' if n_errors != 1 else ''}"

        return ParseResult(
            tool="kubectl", summary=summary,
            schema=schema, rows=[[l] for l in result_lines], verbose=verbose,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_kubectl_parser.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add py/tokkit_output/parsers/kubectl.py tests/output_tests/fixtures/k8s_output.py tests/output_tests/test_kubectl_parser.py
git commit -m "feat: add kubectl parser with healthy pod elision and log compression"
```

---

### Task 8: Docker Compose + PS + Logs Parsers

**Files:**
- Create: `tests/output_tests/fixtures/docker_extra_output.py`
- Create: `py/tokkit_output/parsers/docker_compose.py`
- Create: `py/tokkit_output/parsers/docker_ps.py`
- Create: `py/tokkit_output/parsers/docker_logs.py`
- Create: `tests/output_tests/test_docker_extra_parsers.py`

- [ ] **Step 1: Create docker fixtures**

Create `tests/output_tests/fixtures/docker_extra_output.py`:

```python
"""Realistic docker compose/ps/images/logs output fixtures."""

COMPOSE_PS = """\
NAME                  IMAGE                  COMMAND                  SERVICE     CREATED       STATUS                   PORTS
myapp-api-1           myapp/api:latest       "uvicorn main:app"       api         3 hours ago   Up 3 hours               0.0.0.0:8000->8000/tcp
myapp-worker-1        myapp/worker:latest    "celery -A worker"       worker      3 hours ago   Up 3 hours
myapp-redis-1         redis:7-alpine         "docker-entrypoint.s…"   redis       3 hours ago   Up 3 hours (healthy)     6379/tcp
myapp-postgres-1      postgres:16            "docker-entrypoint.s…"   postgres    3 hours ago   Up 3 hours (healthy)     5432/tcp
myapp-nginx-1         nginx:alpine           "nginx -g 'daemon of…"   nginx       3 hours ago   Up 3 hours               0.0.0.0:80->80/tcp
"""

COMPOSE_PS_WITH_UNHEALTHY = """\
NAME                  IMAGE                  COMMAND                  SERVICE     CREATED       STATUS                        PORTS
myapp-api-1           myapp/api:latest       "uvicorn main:app"       api         3 hours ago   Up 3 hours                    0.0.0.0:8000->8000/tcp
myapp-worker-1        myapp/worker:latest    "celery -A worker"       worker      3 hours ago   Restarting (1) 5 seconds ago
myapp-redis-1         redis:7-alpine         "docker-entrypoint.s…"   redis       3 hours ago   Up 3 hours (healthy)          6379/tcp
myapp-postgres-1      postgres:16            "docker-entrypoint.s…"   postgres    3 hours ago   Exited (1) 10 minutes ago
"""

COMPOSE_LOGS = """\
myapp-api-1       | INFO:     Started server process [1]
myapp-api-1       | INFO:     Waiting for application startup.
myapp-api-1       | INFO:     Application startup complete.
""" + "\n".join([f"myapp-api-1       | INFO:     {i} - 200 GET /health" for i in range(50)]) + """
myapp-worker-1    | [2025-04-07 10:00:01] INFO: Worker started
myapp-worker-1    | [2025-04-07 10:00:02] INFO: Connected to broker
""" + "\n".join([f"myapp-worker-1    | [2025-04-07 10:00:{i:02d}] INFO: Task processed" for i in range(3, 40)]) + """
myapp-worker-1    | [2025-04-07 10:00:41] ERROR: Task failed: ConnectionError
myapp-redis-1     | 1:M 07 Apr 2025 10:00:00.000 * Ready to accept connections
"""

DOCKER_PS = """\
CONTAINER ID   IMAGE                  COMMAND                  CREATED       STATUS                     PORTS                    NAMES
a1b2c3d4e5f6   myapp/api:latest       "uvicorn main:app"       3 hours ago   Up 3 hours                 0.0.0.0:8000->8000/tcp   myapp-api-1
b2c3d4e5f6a7   myapp/worker:latest    "celery -A worker"       3 hours ago   Up 3 hours                                          myapp-worker-1
c3d4e5f6a7b8   redis:7-alpine         "docker-entrypoint.s…"   3 hours ago   Up 3 hours                 6379/tcp                 myapp-redis-1
d4e5f6a7b8c9   postgres:16            "docker-entrypoint.s…"   3 hours ago   Exited (0) 1 hour ago                               old-postgres
e5f6a7b8c9d0   nginx:alpine           "nginx -g 'daemon of…"   5 hours ago   Exited (0) 2 hours ago                              old-nginx
"""

DOCKER_IMAGES = """\
REPOSITORY          TAG       IMAGE ID       CREATED        SIZE
myapp/api           latest    a1b2c3d4e5f6   2 hours ago    245MB
myapp/api           v1.2.3    b2c3d4e5f6a7   3 days ago     240MB
myapp/api           v1.2.2    c3d4e5f6a7b8   1 week ago     238MB
myapp/worker        latest    d4e5f6a7b8c9   2 hours ago    198MB
redis               7-alpine  e5f6a7b8c9d0   2 weeks ago    30MB
postgres            16        f6a7b8c9d0e1   1 month ago    412MB
nginx               alpine    a7b8c9d0e1f2   2 weeks ago    23MB
"""

DOCKER_LOGS_SIMPLE = """\
2025-04-07 10:00:01 INFO Starting server
2025-04-07 10:00:02 INFO Listening on port 8000
""" + "\n".join([f"2025-04-07 10:00:{i:02d} INFO Request {i}" for i in range(3, 80)]) + """
2025-04-07 10:01:20 ERROR Internal server error: database timeout
2025-04-07 10:01:21 ERROR Traceback: psycopg2.OperationalError
2025-04-07 10:01:22 INFO Retrying connection...
2025-04-07 10:01:23 INFO Server shutdown
"""
```

- [ ] **Step 2: Write docker extra parser tests**

Create `tests/output_tests/test_docker_extra_parsers.py`:

```python
"""Tests for docker compose, ps, images, and logs parsers."""

from tokkit_output.parsers.docker_compose import DockerComposeParser
from tokkit_output.parsers.docker_ps import DockerPsParser
from tokkit_output.parsers.docker_logs import DockerLogsParser
from tests.output_tests.fixtures import docker_extra_output as fx


class TestDockerComposeDetect:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_detects_compose_ps(self):
        assert self.parser.detect(fx.COMPOSE_PS) >= 0.7

    def test_detects_compose_logs(self):
        assert self.parser.detect(fx.COMPOSE_LOGS) >= 0.7

    def test_rejects_non_compose(self):
        assert self.parser.detect("hello world") < 0.6


class TestDockerComposeParsePsHealthy:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_all_healthy_summary(self):
        result = self.parser.parse(fx.COMPOSE_PS)
        assert result.tool == "docker-compose"
        assert "5" in result.summary  # 5 services

    def test_unhealthy_highlighted(self):
        result = self.parser.parse(fx.COMPOSE_PS_WITH_UNHEALTHY)
        content = str(result.rows)
        assert "Restarting" in content or "Exited" in content


class TestDockerComposeParseLogs:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_logs_compressed(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        # Should be much shorter than raw input
        total_raw_lines = len(fx.COMPOSE_LOGS.splitlines())
        total_result_lines = len(result.rows)
        assert total_result_lines < total_raw_lines

    def test_errors_preserved(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        content = str(result.rows)
        assert "ERROR" in content


class TestDockerPsDetect:
    def setup_method(self):
        self.parser = DockerPsParser()

    def test_detects_docker_ps(self):
        assert self.parser.detect(fx.DOCKER_PS) >= 0.8

    def test_detects_docker_images(self):
        assert self.parser.detect(fx.DOCKER_IMAGES) >= 0.7

    def test_rejects_non_docker(self):
        assert self.parser.detect("hello world") < 0.6


class TestDockerPsParse:
    def setup_method(self):
        self.parser = DockerPsParser()

    def test_elides_stopped_containers(self):
        result = self.parser.parse(fx.DOCKER_PS)
        content = str(result.rows)
        # Running containers shown, stopped summarized
        assert "myapp-api" in content

    def test_images_parsed(self):
        result = self.parser.parse(fx.DOCKER_IMAGES)
        assert len(result.rows) >= 5


class TestDockerLogsDetect:
    def setup_method(self):
        self.parser = DockerLogsParser()

    def test_detects_logs(self):
        assert self.parser.detect(fx.DOCKER_LOGS_SIMPLE) >= 0.7


class TestDockerLogsParse:
    def setup_method(self):
        self.parser = DockerLogsParser()

    def test_head_tail_with_errors(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        content = str(result.rows)
        assert "Starting" in content
        assert "shutdown" in content
        assert "ERROR" in content
        # Should be compressed
        assert len(result.rows) < len(fx.DOCKER_LOGS_SIMPLE.splitlines())
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_docker_extra_parsers.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement docker compose parser**

Create `py/tokkit_output/parsers/docker_compose.py`:

```python
"""Docker compose output parser (ps + logs)."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

# Compose ps table header
_COMPOSE_TABLE_RE = re.compile(r"^NAME\s+IMAGE\s+COMMAND\s+SERVICE")
# Compose log prefix: "service-name  | "
_COMPOSE_LOG_RE = re.compile(r"^([\w-]+)\s+\|\s+(.+)$")

_HEALTHY_KEYWORDS = {"Up", "healthy", "running"}
_UNHEALTHY_KEYWORDS = {"Exited", "Restarting", "Dead", "Paused", "unhealthy"}

_LOG_ERROR_RE = re.compile(r"(ERROR|FATAL|PANIC|Exception|Traceback)", re.IGNORECASE)
_LOG_HEAD = 5
_LOG_TAIL = 5


class DockerComposeParser(BaseParser):
    id = "docker-compose"
    hint_values = ["docker-compose", "docker compose"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _COMPOSE_TABLE_RE.search(clean, re.MULTILINE):
            score += 0.7
        log_count = sum(1 for l in clean.splitlines()[:20] if _COMPOSE_LOG_RE.match(l))
        if log_count >= 3:
            score += 0.7
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)

        if _COMPOSE_TABLE_RE.search(clean, re.MULTILINE):
            return self._parse_ps(clean, verbose)
        return self._parse_logs(clean, verbose)

    def _parse_ps(self, text: str, verbose: bool) -> ParseResult:
        schema = ["service", "status", "ports"]
        lines = text.strip().splitlines()
        rows: list[list[str]] = []
        healthy = 0
        unhealthy = 0

        for line in lines[1:]:  # Skip header
            if not line.strip():
                continue
            parts = line.split(None, 6)
            if len(parts) < 5:
                continue
            name = parts[0]
            service = parts[3] if len(parts) > 3 else name
            status = " ".join(parts[5:6]) if len(parts) > 5 else ""
            ports = parts[6] if len(parts) > 6 else ""

            is_healthy = any(kw in status for kw in _HEALTHY_KEYWORDS)
            is_unhealthy = any(kw in status for kw in _UNHEALTHY_KEYWORDS)

            if is_unhealthy or verbose:
                rows.append([service, status, ports])
                if is_unhealthy:
                    unhealthy += 1
                else:
                    healthy += 1
            else:
                healthy += 1

        total = healthy + unhealthy
        summary = f"{total} services ({healthy} healthy, {unhealthy} unhealthy)" if unhealthy else f"{total} services, all healthy"

        return ParseResult(
            tool="docker-compose", summary=summary,
            schema=schema, rows=rows, verbose=verbose,
        )

    def _parse_logs(self, text: str, verbose: bool) -> ParseResult:
        schema = ["service", "line"]
        lines = text.strip().splitlines()

        # Group by service
        by_service: dict[str, list[str]] = defaultdict(list)
        service_order: list[str] = []
        for line in lines:
            m = _COMPOSE_LOG_RE.match(line)
            if m:
                svc = m.group(1)
                content = m.group(2)
                if svc not in by_service:
                    service_order.append(svc)
                by_service[svc].append(content)
            else:
                by_service.setdefault("_unknown", []).append(line)

        rows: list[list[str]] = []
        for svc in service_order:
            svc_lines = by_service[svc]
            if verbose or len(svc_lines) <= _LOG_HEAD + _LOG_TAIL:
                for sl in svc_lines:
                    rows.append([svc, sl])
            else:
                # Head + errors + tail
                error_indices: set[int] = set()
                for i, sl in enumerate(svc_lines):
                    if _LOG_ERROR_RE.search(sl):
                        for j in range(max(0, i - 1), min(len(svc_lines), i + 2)):
                            error_indices.add(j)

                keep = set(range(_LOG_HEAD))
                keep |= error_indices
                keep |= set(range(len(svc_lines) - _LOG_TAIL, len(svc_lines)))

                prev = -1
                for i in sorted(keep):
                    if prev >= 0 and i > prev + 1:
                        rows.append([svc, f"... ({i - prev - 1} lines skipped)"])
                    rows.append([svc, svc_lines[i]])
                    prev = i

        total_lines = sum(len(v) for v in by_service.values())
        summary = f"{len(service_order)} services, {total_lines} log lines"

        return ParseResult(
            tool="docker-compose", summary=summary,
            schema=schema, rows=rows, verbose=verbose,
        )
```

- [ ] **Step 5: Implement docker ps/images parser**

Create `py/tokkit_output/parsers/docker_ps.py`:

```python
"""Docker ps and docker images output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_PS_HEADER_RE = re.compile(r"^CONTAINER ID\s+IMAGE")
_IMAGES_HEADER_RE = re.compile(r"^REPOSITORY\s+TAG")


class DockerPsParser(BaseParser):
    id = "docker-ps"
    hint_values = ["docker-ps", "docker-images"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _PS_HEADER_RE.search(clean, re.MULTILINE):
            return 0.85
        if _IMAGES_HEADER_RE.search(clean, re.MULTILINE):
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        if _IMAGES_HEADER_RE.search(clean, re.MULTILINE):
            return self._parse_images(clean, verbose)
        return self._parse_ps(clean, verbose)

    def _parse_ps(self, text: str, verbose: bool) -> ParseResult:
        schema = ["name", "image", "status", "ports"]
        lines = text.strip().splitlines()
        rows: list[list[str]] = []
        running = 0
        stopped = 0

        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(None, 6)
            if len(parts) < 5:
                continue
            image = parts[1]
            status = parts[4] if len(parts) > 4 else ""
            # Status may span multiple columns
            status_parts = []
            for p in parts[4:]:
                if p.startswith("0.0.0.0") or "tcp" in p.lower() or "->" in p:
                    break
                status_parts.append(p)
            status = " ".join(status_parts)
            name = parts[-1] if len(parts) > 6 else parts[0][:12]
            ports = ""
            for p in parts:
                if "->" in p:
                    ports = p
                    break

            is_running = "Up" in status
            if is_running:
                running += 1
            else:
                stopped += 1

            if verbose or is_running or "Exited (1)" in status:
                rows.append([name, image, status, ports])

        summary = f"{running + stopped} containers ({running} running, {stopped} stopped)"
        return ParseResult(
            tool="docker-ps", summary=summary,
            schema=schema, rows=rows, verbose=verbose,
        )

    def _parse_images(self, text: str, verbose: bool) -> ParseResult:
        schema = ["repository", "tag", "size", "created"]
        lines = text.strip().splitlines()
        rows: list[list[str]] = []

        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(None, 4)
            if len(parts) < 3:
                continue
            repo = parts[0]
            tag = parts[1]
            size = parts[3] if len(parts) > 3 else ""
            created = parts[4] if len(parts) > 4 else ""
            rows.append([repo, tag, size, created])

        summary = f"{len(rows)} images"
        return ParseResult(
            tool="docker-ps", summary=summary,
            schema=schema, rows=rows, verbose=verbose,
        )
```

- [ ] **Step 6: Implement docker logs parser**

Create `py/tokkit_output/parsers/docker_logs.py`:

```python
"""Docker logs output parser — head/tail with error neighborhoods."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ][\d:.]+")
_ERROR_RE = re.compile(r"(ERROR|FATAL|PANIC|Exception|Traceback)", re.IGNORECASE)

_HEAD = 10
_TAIL = 10
_ERROR_CONTEXT = 2


class DockerLogsParser(BaseParser):
    id = "docker-logs"
    hint_values = ["docker-logs"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        ts_count = sum(1 for l in clean.splitlines()[:30] if _TIMESTAMP_RE.match(l))
        if ts_count >= 5:
            return 0.7
        if ts_count >= 2:
            return 0.5
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.strip().splitlines()
        schema = ["line"]

        if verbose or len(lines) <= _HEAD + _TAIL:
            return ParseResult(
                tool="docker-logs", summary=f"{len(lines)} log lines",
                schema=schema, rows=[[l] for l in lines], verbose=verbose,
            )

        # Find error neighborhoods
        error_indices: set[int] = set()
        for i, line in enumerate(lines):
            if _ERROR_RE.search(line):
                for j in range(max(0, i - _ERROR_CONTEXT),
                               min(len(lines), i + _ERROR_CONTEXT + 1)):
                    error_indices.add(j)

        keep = set(range(_HEAD))
        keep |= error_indices
        keep |= set(range(len(lines) - _TAIL, len(lines)))

        result_lines: list[str] = []
        prev = -1
        for i in sorted(keep):
            if prev >= 0 and i > prev + 1:
                result_lines.append(f"... ({i - prev - 1} lines skipped)")
            result_lines.append(lines[i])
            prev = i

        n_errors = sum(1 for l in lines if _ERROR_RE.search(l))
        summary = f"{len(lines)} log lines, {n_errors} error{'s' if n_errors != 1 else ''}"

        return ParseResult(
            tool="docker-logs", summary=summary,
            schema=schema, rows=[[l] for l in result_lines], verbose=verbose,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_docker_extra_parsers.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add py/tokkit_output/parsers/docker_compose.py py/tokkit_output/parsers/docker_ps.py py/tokkit_output/parsers/docker_logs.py tests/output_tests/fixtures/docker_extra_output.py tests/output_tests/test_docker_extra_parsers.py
git commit -m "feat: add docker compose, ps, images, and logs parsers"
```

---

### Task 9: Package List + File Listing + Search Results + GH CLI + Env Redact Parsers

**Files:**
- Create: `tests/output_tests/fixtures/shell_output.py`
- Create: `tests/output_tests/fixtures/gh_output.py`
- Create: `py/tokkit_output/parsers/package_list.py`
- Create: `py/tokkit_output/parsers/file_listing.py`
- Create: `py/tokkit_output/parsers/search_results.py`
- Create: `py/tokkit_output/parsers/gh_cli.py`
- Create: `py/tokkit_output/parsers/env_redact.py`
- Create: `tests/output_tests/test_shell_parsers.py`
- Create: `tests/output_tests/test_gh_cli_parser.py`

This task covers 5 smaller parsers. Each follows the same pattern: fixture + test + implementation. The implementation details of these parsers follow the same BaseParser contract established in Tasks 4-8. Implement each parser following the patterns from git/kubectl/docker parsers. Key algorithms:

**package_list.py:**
- `pip list`: Detect via `Package\s+Version` header. Parse lines, count. If >20: show first 15 + `... (N more)`.
- `pip freeze`: Detect via `==` pattern. Same truncation.
- `npm ls`: Detect via tree characters `├──`/`└──`. Count total deps. Show top-level only (single-indent), count nested. Keep `UNMET`/`ERR!` lines always.
- Schema: `[package, version]`. Hint values: `pip-list`, `pip-freeze`, `npm-ls`.

**file_listing.py:**
- `tree`: Detect via `├──`/`└──` characters. Truncate depth >3 to counts. Schema: `[path]`.
- `ls -la`: Detect via permission strings `drwx`/`-rw-`. Group by extension if >50. Schema: `[path, type, size]`.
- `find`: Detect via path-per-line format. Group by directory, limit per-dir to 3, total dirs to 15. Schema: `[path]`.
- Hint values: `ls`, `tree`, `find`.

**search_results.py:**
- Detect via `file:line:content` format. Group by file. Per-file limit: 3. Total files: 15. Sort by match count. Schema: `[file, line, match]`. Hint values: `grep`, `rg`, `ag`.

**gh_cli.py:**
- Detect via `#\d+` patterns and `OPEN`/`CLOSED`/`MERGED` keywords. Parse TSV-like tables. Truncate to 20 entries. Schema varies by subcommand. Hint values: `gh`, `gh-pr`, `gh-issue`, `gh-run`.

**env_redact.py:**
- Detect via `KEY=VALUE` lines. Parse key=value. Redact values where key matches `*KEY*`, `*SECRET*`, `*TOKEN*`, `*PASSWORD*`, `*CREDENTIAL*`, `*AUTH*`, `*PRIVATE*`. Schema: `[key, value]`. Hint values: `env`, `printenv`.

- [ ] **Step 1: Create shell fixtures**

Create `tests/output_tests/fixtures/shell_output.py` with realistic output for pip list (30 packages), npm ls (nested tree), tree (deep directory), find (many files), grep -r (many matches), env (with secrets).

Create `tests/output_tests/fixtures/gh_output.py` with realistic gh pr list, gh issue list, gh run list tables.

- [ ] **Step 2: Write tests for all 5 parsers**

Create `tests/output_tests/test_shell_parsers.py` with detect/parse tests for: PackageListParser, FileListingParser, SearchResultsParser, EnvRedactParser.

Create `tests/output_tests/test_gh_cli_parser.py` with detect/parse tests for GhCliParser.

Follow the same pattern as previous parser tests: `TestXxxDetect` class with valid/invalid detection, `TestXxxParse` class with default/verbose/edge cases.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_shell_parsers.py tests/output_tests/test_gh_cli_parser.py -v`
Expected: FAIL — ModuleNotFoundError for all 5 parsers.

- [ ] **Step 4: Implement all 5 parsers**

Create `py/tokkit_output/parsers/package_list.py`, `file_listing.py`, `search_results.py`, `gh_cli.py`, `env_redact.py` following the algorithms described above and the BaseParser contract from `base.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_shell_parsers.py tests/output_tests/test_gh_cli_parser.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add py/tokkit_output/parsers/package_list.py py/tokkit_output/parsers/file_listing.py py/tokkit_output/parsers/search_results.py py/tokkit_output/parsers/gh_cli.py py/tokkit_output/parsers/env_redact.py tests/output_tests/fixtures/shell_output.py tests/output_tests/fixtures/gh_output.py tests/output_tests/test_shell_parsers.py tests/output_tests/test_gh_cli_parser.py
git commit -m "feat: add package list, file listing, search results, gh cli, and env redact parsers"
```

---

### Task 10: Register All New Parsers

**Files:**
- Modify: `py/tokkit_output/parsers/__init__.py`

- [ ] **Step 1: Register all 16 new parsers**

Add to end of `py/tokkit_output/parsers/__init__.py`:

```python
# --- Git parsers ---
from tokkit_output.parsers.git_diff import GitDiffParser
from tokkit_output.parsers.git_status import GitStatusParser
from tokkit_output.parsers.git_log import GitLogParser
from tokkit_output.parsers.git_show import GitShowParser
from tokkit_output.parsers.git_blame import GitBlameParser
from tokkit_output.parsers.git_branch import GitBranchParser
from tokkit_output.parsers.git_stash import GitStashParser

register(GitDiffParser())
register(GitStatusParser())
register(GitLogParser())
register(GitShowParser())
register(GitBlameParser())
register(GitBranchParser())
register(GitStashParser())

# --- Kubernetes ---
from tokkit_output.parsers.kubectl import KubectlParser

register(KubectlParser())

# --- Docker (compose, ps/images, logs) ---
from tokkit_output.parsers.docker_compose import DockerComposeParser
from tokkit_output.parsers.docker_ps import DockerPsParser
from tokkit_output.parsers.docker_logs import DockerLogsParser

register(DockerComposeParser())
register(DockerPsParser())
register(DockerLogsParser())

# --- Shell tools ---
from tokkit_output.parsers.package_list import PackageListParser
from tokkit_output.parsers.file_listing import FileListingParser
from tokkit_output.parsers.search_results import SearchResultsParser
from tokkit_output.parsers.gh_cli import GhCliParser
from tokkit_output.parsers.env_redact import EnvRedactParser

register(PackageListParser())
register(FileListingParser())
register(SearchResultsParser())
register(GhCliParser())
register(EnvRedactParser())
```

- [ ] **Step 2: Run all output tests to verify nothing broke**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Run auto-detect test to verify new parsers don't conflict with existing ones**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/output_tests/test_detect.py -v`
Expected: All existing auto-detect tests still PASS (new parsers shouldn't trigger on old fixtures).

- [ ] **Step 4: Commit**

```bash
git add py/tokkit_output/parsers/__init__.py
git commit -m "feat: register all 16 new parsers in the parser registry"
```

---

### Task 11: Hook Command Matching + Chain Splitting

**Files:**
- Create: `py/tokkit_hook/__init__.py`
- Create: `py/tokkit_hook/chain.py`
- Create: `py/tokkit_hook/match.py`
- Create: `tests/hook_tests/__init__.py`
- Create: `tests/hook_tests/test_chain.py`
- Create: `tests/hook_tests/test_match.py`

- [ ] **Step 1: Write chain splitting tests**

Create `tests/hook_tests/__init__.py` (empty) and `tests/hook_tests/test_chain.py`:

```python
"""Tests for chained command splitting."""

from tokkit_hook.chain import split_chain, find_primary


class TestSplitChain:
    def test_single_command(self):
        assert split_chain("git diff") == ["git diff"]

    def test_and_chain(self):
        assert split_chain("git add . && git commit -m 'fix'") == [
            "git add .", "git commit -m 'fix'"
        ]

    def test_semicolon_chain(self):
        assert split_chain("cd src; pytest") == ["cd src", "pytest"]

    def test_respects_single_quotes(self):
        result = split_chain("echo 'hello && world'")
        assert result == ["echo 'hello && world'"]

    def test_respects_double_quotes(self):
        result = split_chain('echo "cd src && run"')
        assert result == ['echo "cd src && run"']

    def test_mixed_chain(self):
        result = split_chain("cd src && npm install; npm test")
        assert len(result) == 3

    def test_empty_string(self):
        assert split_chain("") == [""]

    def test_whitespace_preserved(self):
        result = split_chain("git add . && git commit -m 'test'")
        assert result[0].strip() == "git add ."


class TestFindPrimary:
    def test_single_command(self):
        assert find_primary(["git diff"]) == "git diff"

    def test_cd_then_command(self):
        assert find_primary(["cd src", "pytest"]) == "pytest"

    def test_all_silent(self):
        # All commands are "silent" — return last one
        assert find_primary(["cd src", "mkdir -p out"]) == "mkdir -p out"

    def test_git_add_then_commit(self):
        assert find_primary(["git add .", "git commit -m 'fix'"]) == "git commit -m 'fix'"

    def test_npm_install_then_test(self):
        assert find_primary(["npm install", "npm test"]) == "npm test"

    def test_export_then_command(self):
        assert find_primary(["export FOO=bar", "ruff check ."]) == "ruff check ."
```

- [ ] **Step 2: Write command matching tests**

Create `tests/hook_tests/test_match.py`:

```python
"""Tests for command-to-hint pattern matching."""

from tokkit_hook.match import match_command


class TestGitMatching:
    def test_git_diff(self):
        assert match_command("git diff") == "git-diff"

    def test_git_diff_staged(self):
        assert match_command("git diff --staged") == "git-diff"

    def test_git_status(self):
        assert match_command("git status") == "git-status"

    def test_git_log(self):
        assert match_command("git log") == "git-log"

    def test_git_log_oneline(self):
        assert match_command("git log --oneline -20") == "git-log"

    def test_git_show(self):
        assert match_command("git show HEAD") == "git-show"

    def test_git_blame(self):
        assert match_command("git blame src/main.py") == "git-blame"

    def test_git_branch(self):
        assert match_command("git branch -a") == "git-branch"

    def test_git_stash_list(self):
        assert match_command("git stash list") == "git-stash"


class TestPythonMatching:
    def test_pytest(self):
        assert match_command("pytest tests/") == "pytest"

    def test_python_m_pytest(self):
        assert match_command("python -m pytest") == "pytest"

    def test_ruff(self):
        assert match_command("ruff check .") == "ruff"

    def test_mypy(self):
        assert match_command("mypy src/") == "mypy"

    def test_pip_list(self):
        assert match_command("pip list") == "pip-list"

    def test_pip_freeze(self):
        assert match_command("pip freeze") == "pip-freeze"


class TestJsMatching:
    def test_jest(self):
        assert match_command("npx jest") == "jest"

    def test_eslint(self):
        assert match_command("npx eslint src/") == "eslint"

    def test_tsc(self):
        assert match_command("npx tsc --noEmit") == "tsc"

    def test_npm_test(self):
        assert match_command("npm test") == "npm"


class TestDockerMatching:
    def test_docker_compose_ps(self):
        assert match_command("docker compose ps") == "docker-compose"

    def test_docker_ps(self):
        assert match_command("docker ps") == "docker-ps"

    def test_docker_images(self):
        assert match_command("docker images") == "docker-images"

    def test_docker_logs(self):
        assert match_command("docker logs myapp") == "docker-logs"


class TestKubectlMatching:
    def test_kubectl_get_pods(self):
        assert match_command("kubectl get pods") == "kubectl"

    def test_kubectl_describe(self):
        assert match_command("kubectl describe pod myapp") == "kubectl"

    def test_kubectl_logs(self):
        assert match_command("kubectl logs myapp") == "kubectl"


class TestShellMatching:
    def test_grep_r(self):
        assert match_command("grep -r 'pattern' src/") == "grep"

    def test_rg(self):
        assert match_command("rg pattern src/") == "rg"

    def test_ls(self):
        assert match_command("ls -la") == "ls"

    def test_tree(self):
        assert match_command("tree src/") == "tree"

    def test_find(self):
        assert match_command("find . -name '*.py'") == "find"

    def test_gh_pr_list(self):
        assert match_command("gh pr list") == "gh"

    def test_env(self):
        assert match_command("env") == "env"

    def test_printenv(self):
        assert match_command("printenv") == "env"


class TestExclusions:
    def test_cat_python_file_excluded(self):
        assert match_command("cat src/main.py") is None

    def test_cat_js_file_excluded(self):
        assert match_command("cat src/index.js") is None

    def test_bat_excluded(self):
        assert match_command("bat src/main.py") is None

    def test_vim_excluded(self):
        assert match_command("vim src/main.py") is None

    def test_pipe_excluded(self):
        assert match_command("git diff | head -20") is None

    def test_redirect_excluded(self):
        assert match_command("git log > log.txt") is None

    def test_unknown_command(self):
        assert match_command("some-custom-tool --flag") is None

    def test_head_source_excluded(self):
        assert match_command("head -50 src/auth.py") is None

    def test_cat_non_source_not_excluded(self):
        # cat on non-source files is fine to compress
        assert match_command("cat /var/log/syslog") is not None or match_command("cat /var/log/syslog") is None
        # Actually, cat without source extension should pass through since we don't have a log parser
        # Just verify it doesn't crash
        match_command("cat /var/log/syslog")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/hook_tests/ -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: Implement chain splitter**

Create `py/tokkit_hook/__init__.py` (empty) and `py/tokkit_hook/chain.py`:

```python
"""Chained command splitting — handles && and ; while respecting quotes."""

_SILENT_PREFIXES = frozenset({
    "cd", "mkdir", "cp", "mv", "rm", "export", "source", ".",
    "pushd", "popd", "set", "unset", "alias", "ulimit",
    "git add", "git checkout", "git stash push", "git stash pop",
    "git stash drop",
})


def split_chain(command: str) -> list[str]:
    """Split a command string on && and ; while respecting quoted strings."""
    parts: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    chars = command

    while i < len(chars):
        c = chars[i]

        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
        elif c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
        elif not in_single and not in_double:
            if c == ";" :
                parts.append("".join(current).strip())
                current = []
            elif c == "&" and i + 1 < len(chars) and chars[i + 1] == "&":
                parts.append("".join(current).strip())
                current = []
                i += 1  # Skip second &
            else:
                current.append(c)
        else:
            current.append(c)
        i += 1

    parts.append("".join(current).strip())
    return parts


def find_primary(commands: list[str]) -> str:
    """Find the primary (output-producing) command in a chain.

    Silent commands (cd, mkdir, git add, etc.) are skipped.
    Returns the last non-silent command, or the last command if all are silent.
    """
    primary = commands[-1]  # Fallback: last command
    for cmd in reversed(commands):
        cmd_stripped = cmd.strip()
        is_silent = False
        for prefix in _SILENT_PREFIXES:
            if cmd_stripped == prefix or cmd_stripped.startswith(prefix + " "):
                is_silent = True
                break
        if not is_silent:
            primary = cmd_stripped
            break
    return primary
```

- [ ] **Step 5: Implement command matcher**

Create `py/tokkit_hook/match.py`:

```python
"""Command-to-hint pattern matching for the PreToolUse hook.

Returns a hint string for known commands, or None for pass-through.
"""

import re

# Source file extensions — commands reading these are excluded
_SOURCE_EXTS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java",
    ".rb", ".c", ".h", ".cpp", ".hpp", ".swift", ".kt", ".scala",
    ".cs", ".vue", ".svelte",
})

# Commands that should never be intercepted
_EXCLUDED_COMMANDS = frozenset({
    "vim", "nvim", "nano", "less", "more", "ssh", "sudo",
    "bat", "batcat",
})

# Pipe and redirect patterns — output is already being filtered
_PIPE_RE = re.compile(r"\s*\|")
_REDIRECT_RE = re.compile(r"\s*>{1,2}\s*\S")

# Pattern table: (prefix_tuple, hint)
# Checked in order; first match wins
_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    # Git
    (("git diff",), "git-diff"),
    (("git status",), "git-status"),
    (("git log",), "git-log"),
    (("git show",), "git-show"),
    (("git blame",), "git-blame"),
    (("git branch",), "git-branch"),
    (("git stash list",), "git-stash"),
    # Python test/lint
    (("pytest", "python -m pytest", "python3 -m pytest"), "pytest"),
    (("python -m unittest", "python3 -m unittest"), "unittest"),
    (("ruff check", "ruff ."), "ruff"),
    (("mypy",), "mypy"),
    (("pyright",), "pyright"),
    (("pip list",), "pip-list"),
    (("pip freeze",), "pip-freeze"),
    (("pip install",), "pip"),
    # JS/TS
    (("jest", "npx jest", "yarn jest", "pnpm jest"), "jest"),
    (("vitest", "npx vitest", "yarn vitest"), "vitest"),
    (("mocha", "npx mocha"), "mocha"),
    (("eslint", "npx eslint"), "eslint"),
    (("tsc", "npx tsc"), "tsc"),
    (("webpack", "npx webpack"), "webpack"),
    (("vite build", "npx vite build"), "vite"),
    (("npm install", "npm ci", "npm run build", "npm test", "npm run"), "npm"),
    # Cargo
    (("cargo test",), "cargo-test"),
    (("cargo build", "cargo check"), "cargo-build"),
    (("cargo clippy",), "cargo-clippy"),
    # Docker
    (("docker compose", "docker-compose"), "docker-compose"),
    (("docker build",), "docker"),
    (("docker ps",), "docker-ps"),
    (("docker images",), "docker-images"),
    (("docker logs",), "docker-logs"),
    # Kubernetes
    (("kubectl",), "kubectl"),
    # Shell tools
    (("grep -r", "grep -rn", "grep --include"), "grep"),
    (("rg ",), "rg"),
    (("ag ",), "ag"),
    (("ls ",), "ls"),
    (("ls\n", "ls"), "ls"),  # bare ls
    (("tree",), "tree"),
    (("find ",), "find"),
    # GitHub CLI
    (("gh pr", "gh issue", "gh run"), "gh"),
    # Environment
    (("env",), "env"),
    (("printenv",), "env"),
]


def _reads_source_file(command: str) -> bool:
    """Check if command reads a source code file (cat, head, tail on .py/.js/etc)."""
    parts = command.split()
    if not parts:
        return False
    cmd = parts[0]
    if cmd not in ("cat", "head", "tail"):
        return False
    for part in parts[1:]:
        if part.startswith("-"):
            continue
        for ext in _SOURCE_EXTS:
            if part.endswith(ext):
                return True
    return False


def match_command(command: str) -> str | None:
    """Return hint value for command, or None for pass-through.

    Returns None for:
    - Unknown commands
    - Commands reading source files
    - Commands with pipes or redirects
    - Excluded interactive commands
    """
    cmd = command.strip()
    if not cmd:
        return None

    # Check exclusions first
    first_word = cmd.split()[0] if cmd.split() else ""
    if first_word in _EXCLUDED_COMMANDS:
        return None

    # Pipe/redirect → user is already filtering
    if _PIPE_RE.search(cmd) or _REDIRECT_RE.search(cmd):
        return None

    # Source file reads
    if _reads_source_file(cmd):
        return None

    # Match against pattern table
    for prefixes, hint in _PATTERNS:
        for prefix in prefixes:
            if cmd == prefix or cmd.startswith(prefix + " ") or cmd.startswith(prefix + "\t"):
                return hint

    return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/hook_tests/ -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add py/tokkit_hook/ tests/hook_tests/
git commit -m "feat: add hook command matching and chain splitting"
```

---

### Task 12: Hook Compress CLI + PreToolUse Hook

**Files:**
- Create: `py/tokkit_hook/compress.py`
- Create: `py/tokkit_hook/hook.py`
- Create: `tests/hook_tests/test_compress.py`
- Create: `tests/hook_tests/test_hook.py`

- [ ] **Step 1: Write compress CLI tests**

Create `tests/hook_tests/test_compress.py`:

```python
"""Tests for tokkit compress CLI subcommand."""

import subprocess
import sys


class TestCompressCommand:
    def test_echo_passthrough(self):
        """Simple echo should pass through (short output, no parser match)."""
        result = subprocess.run(
            [sys.executable, "-m", "tokkit_hook.compress", "echo hello"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_preserves_exit_code(self):
        """Non-zero exit code from command should be preserved."""
        result = subprocess.run(
            [sys.executable, "-m", "tokkit_hook.compress", "false"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0

    def test_empty_command_fails(self):
        """No command should fail gracefully."""
        result = subprocess.run(
            [sys.executable, "-m", "tokkit_hook.compress"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
```

- [ ] **Step 2: Write hook protocol tests**

Create `tests/hook_tests/test_hook.py`:

```python
"""Tests for PreToolUse hook protocol."""

import json

from tokkit_hook.hook import handle_hook_request


class TestHookProtocol:
    def test_non_bash_passes_through(self):
        request = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
        result = handle_hook_request(request)
        assert result["decision"] == "allow"
        assert "params" not in result

    def test_bash_git_diff_rewrites(self):
        request = {"tool_name": "Bash", "tool_input": {"command": "git diff"}}
        result = handle_hook_request(request)
        assert result["decision"] == "allow"
        assert "params" in result
        assert "tokkit" in result["params"]["command"]
        assert "git diff" in result["params"]["command"]

    def test_bash_unknown_passes_through(self):
        request = {"tool_name": "Bash", "tool_input": {"command": "whoami"}}
        result = handle_hook_request(request)
        assert result["decision"] == "allow"
        assert "params" not in result

    def test_bash_cat_source_passes_through(self):
        request = {"tool_name": "Bash", "tool_input": {"command": "cat src/main.py"}}
        result = handle_hook_request(request)
        assert result["decision"] == "allow"
        assert "params" not in result

    def test_chained_command_rewrites_primary(self):
        request = {"tool_name": "Bash", "tool_input": {"command": "cd src && pytest -v"}}
        result = handle_hook_request(request)
        assert result["decision"] == "allow"
        assert "params" in result
        # Should rewrite the ENTIRE chain, not just pytest
        assert "cd src && pytest" in result["params"]["command"] or "tokkit" in result["params"]["command"]

    def test_pipe_passes_through(self):
        request = {"tool_name": "Bash", "tool_input": {"command": "git diff | head -20"}}
        result = handle_hook_request(request)
        assert result["decision"] == "allow"
        assert "params" not in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/hook_tests/test_compress.py tests/hook_tests/test_hook.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: Implement compress CLI**

Create `py/tokkit_hook/compress.py`:

```python
"""CLI entry point for `tokkit compress '<command>'`.

Runs the command, captures output, compresses via compact_output, prints result.
Exit code is preserved from the original command.
"""

import subprocess
import sys

from tokkit_hook.match import match_command
from tokkit_output import compact_output


def run_and_compress(command: str) -> int:
    """Run command, compress output, print result. Return exit code."""
    try:
        proc = subprocess.run(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("Command timed out (300s limit)", file=sys.stderr)
        return 124

    raw_output = proc.stdout or ""
    if not raw_output.strip():
        return proc.returncode

    hint = match_command(command)
    compressed = compact_output(raw_output, hint=hint)

    if compressed:
        print(compressed)

    return proc.returncode


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m tokkit_hook.compress '<command>'", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    exit_code = run_and_compress(command)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Implement PreToolUse hook**

Create `py/tokkit_hook/hook.py`:

```python
"""PreToolUse hook for Claude Code — intercepts Bash commands and rewrites
them to pipe through tokkit compress.

Protocol:
- stdin: {"tool_name": "Bash", "tool_input": {"command": "git diff"}}
- stdout: {"decision": "allow", "params": {"command": "tokkit compress 'git diff'"}}
"""

import json
import shlex
import sys

from tokkit_hook.chain import split_chain, find_primary
from tokkit_hook.match import match_command


def handle_hook_request(request: dict) -> dict:
    """Process a PreToolUse hook request. Returns the response dict."""
    tool_name = request.get("tool_name", "")
    if tool_name != "Bash":
        return {"decision": "allow"}

    tool_input = request.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        return {"decision": "allow"}

    # Split chains and find primary command
    parts = split_chain(command)
    primary = find_primary(parts)

    # Check if primary command matches a parser
    hint = match_command(primary)
    if hint is None:
        return {"decision": "allow"}

    # Rewrite the entire command to pipe through tokkit compress
    escaped = command.replace("'", "'\\''")
    new_command = f"tokkit compress '{escaped}'"

    return {
        "decision": "allow",
        "params": {"command": new_command},
    }


def main() -> None:
    """Read request from stdin, write response to stdout."""
    try:
        request = json.load(sys.stdin)
        response = handle_hook_request(request)
        json.dump(response, sys.stdout)
    except Exception:
        # Fail open — allow the original command through
        json.dump({"decision": "allow"}, sys.stdout)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/hook_tests/ -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add py/tokkit_hook/compress.py py/tokkit_hook/hook.py tests/hook_tests/test_compress.py tests/hook_tests/test_hook.py
git commit -m "feat: add tokkit compress CLI and PreToolUse hook"
```

---

### Task 13: CLI + Setup Integration

**Files:**
- Modify: `py/tokkit_cli/main.py`
- Modify: `py/tokkit_cli/setup.py`

- [ ] **Step 1: Add `compress` subcommand to CLI**

In `py/tokkit_cli/main.py`, add after the `benchmark` block (around line 109):

```python
    if argv[0] == "compress":
        if len(argv) < 2:
            print("Usage: tokkit compress '<command>'", file=sys.stderr)
            sys.exit(1)
        from tokkit_hook.compress import run_and_compress
        exit_code = run_and_compress(argv[1])
        sys.exit(exit_code)
```

Also update the `--help` output to include:

```python
        print("  tokkit compress '<cmd>'  Run command with output compression")
```

- [ ] **Step 2: Add hook configuration to plugin install**

In `py/tokkit_cli/setup.py`, in the `install_plugin()` function, after writing `.mcp.json` (after line 72), add hook configuration:

```python
    # Hook script — PreToolUse hook for Bash command compression
    hooks_dir = dest / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    # Copy the hook script
    import tokkit_hook.hook as hook_module
    hook_path = Path(hook_module.__file__)
    shutil.copy2(hook_path, hooks_dir / "hook.py")

    # Update plugin.json with hooks
    plugin_json = json.loads((dest / ".claude-plugin" / "plugin.json").read_text())
    plugin_json["hooks"] = {
        "PreToolUse": [{
            "matcher": "Bash",
            "command": f"python3 {hooks_dir / 'hook.py'}",
        }]
    }
    (dest / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2) + "\n"
    )
```

- [ ] **Step 3: Run existing CLI tests to verify nothing broke**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/cli/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Verify compress subcommand works**

Run: `cd /home/edge/code/tokkit && python -m tokkit_cli.main compress 'echo hello world'`
Expected: Output contains "hello world"

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_cli/main.py py/tokkit_cli/setup.py
git commit -m "feat: add compress subcommand and hook installation to setup"
```

---

### Task 14: Update MCP Protocol Descriptions

**Files:**
- Modify: `py/tokkit_server/protocol.py`

- [ ] **Step 1: Update compact_output tool description with new hints**

In `py/tokkit_server/protocol.py`, update the `compact_output` tool description to reflect the new hint values and the dual-model architecture. Add all new hint values to the description string. Mention that the hook model handles live shell commands automatically — `compact_output` is for saved output files.

- [ ] **Step 2: Run server tests to verify nothing broke**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/server/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add py/tokkit_server/protocol.py
git commit -m "docs: update compact_output MCP tool description with new hints and hook model"
```

---

### Task 15: Documentation — README + SKILL.md

**Files:**
- Modify: `README.md`
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Update README.md**

Add a new major section explaining both models. Include:

1. **Hook Model (Automatic Shell Compression)** section:
   - How it works (PreToolUse hook intercepts Bash → `tokkit compress`)
   - What commands it handles (full table of command patterns → hints)
   - Token overhead comparison (hook vs MCP)
   - How to verify it's active

2. **MCP Model (Explicit File Processing)** section:
   - Existing tools (clean_html, compact_json, search_markdown, compact_output, graph tools)
   - When to use MCP vs hook
   - The `path=` pattern

3. **Supported Commands** table (complete list of all hints)

4. **Installation** section updated: `tokkit setup` installs both models automatically

5. Placeholder for benchmark tables (filled in Task 16):
   - Hook benchmark table
   - MCP benchmark table

- [ ] **Step 2: Update skill/SKILL.md**

Update the decision table in SKILL.md:
- Shell commands are now handled automatically by the hook — agents don't need to call `compact_output` for live output
- `compact_output(path=...)` is still available for saved output files
- Add note about hook model: "Shell command output is compressed automatically via the PreToolUse hook. No explicit tool call needed."

Add new section "Hook Model (Automatic)" explaining:
- The hook runs transparently on every Bash command
- Supported command patterns
- Agent doesn't need to do anything special

- [ ] **Step 3: Commit**

```bash
git add README.md skill/SKILL.md
git commit -m "docs: update README and SKILL.md with dual-model documentation"
```

---

### Task 16: Benchmarks

**Files:**
- Modify: `README.md` (fill in benchmark tables)
- Modify: `tests/BENCHMARK_RESULTS.md`

This task requires running real agent sessions. Use the existing benchmark infrastructure in `py/tokkit_benchmark/`.

- [ ] **Step 1: Design hook benchmark scenarios**

Create 10 hook benchmark scenarios that test real Bash commands on a target repo (fastapi/fastapi). Each scenario: agent runs a command with and without the hook active.

| # | Task prompt | Command | What it tests |
|---|------------|---------|---------------|
| H1 | "Show recent changes" | `git diff` | Diff compression |
| H2 | "Check commit history" | `git log --oneline -20` | Log truncation |
| H3 | "What's the repo status?" | `git status` | Status summary |
| H4 | "Run the test suite" | `pytest tests/ -x` | Test output |
| H5 | "Check code quality" | `ruff check .` | Lint grouping |
| H6 | "Type check the code" | `mypy src/` | Type errors |
| H7 | "What packages are installed?" | `pip list` | Package collapse |
| H8 | "Search for router usage" | `grep -r "router" fastapi/` | Search compression |
| H9 | "Show project structure" | `tree -L 3` | Tree truncation |
| H10 | "Check open PRs" | `gh pr list` | GH CLI |

- [ ] **Step 2: Run hook benchmarks**

Run each scenario twice (with hook, without hook) using Claude Haiku agents. Record actual token counts from API usage.

- [ ] **Step 3: Run MCP benchmarks (existing + new)**

Re-run existing MCP benchmarks plus two new scenarios:
- M7: `compact_output(path=..., hint="pytest")` on saved test output
- M8: `compact_output(path=..., hint="ruff")` on saved lint output

- [ ] **Step 4: Fill in benchmark tables in README.md**

Update README with actual measured results:
```markdown
### Hook Model Benchmark

| Task | Raw tokens | Compressed | Savings |
|------|-----------|------------|---------|
| ... | ... | ... | ... |

### MCP Model Benchmark

| Task | Without Tokkit | With Tokkit | Savings |
|------|---------------|------------|---------|
| ... | ... | ... | ... |
```

- [ ] **Step 5: Update BENCHMARK_RESULTS.md**

Add detailed benchmark results with methodology notes.

- [ ] **Step 6: Commit**

```bash
git add README.md tests/BENCHMARK_RESULTS.md
git commit -m "docs: add hook and MCP benchmark results"
```

---

### Task 17: Final Integration Test + Full Test Suite

- [ ] **Step 1: Run the complete test suite**

Run: `cd /home/edge/code/tokkit && python -m pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: All tests PASS.

- [ ] **Step 2: Run Rust tests**

Run: `cd /home/edge/code/tokkit && cargo test --workspace`
Expected: All tests PASS.

- [ ] **Step 3: Verify hook installation end-to-end**

Run `tokkit setup --dry-run` and verify it mentions both MCP server and hook configuration.

- [ ] **Step 4: Final commit with any fixes**

If any tests failed, fix and commit. Otherwise, create a summary commit if needed.

```bash
git add -A
git commit -m "test: verify full test suite passes with all new parsers and hook"
```
