"""Tests for lint_grouper.group_by_rule()."""

import pytest
from tokkit_output.base import ParseResult
from tokkit_output.lint_grouper import group_by_rule

_RUFF_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]
_MYPY_SCHEMA = ["file", "line", "col", "severity", "code", "message"]
_MINIMAL_SCHEMA = ["file", "line", "message"]


def _make_ruff_result(rows, verbose=False) -> ParseResult:
    return ParseResult(
        tool="ruff",
        summary=f"{len(rows)} violations",
        schema=_RUFF_SCHEMA,
        rows=rows,
        verbose=verbose,
    )


def _make_mypy_result(rows, verbose=False) -> ParseResult:
    return ParseResult(
        tool="mypy",
        summary=f"{len(rows)} errors",
        schema=_MYPY_SCHEMA,
        rows=rows,
        verbose=verbose,
    )


def _ruff_row(file, line, col, rule, severity, message):
    return [file, str(line), str(col), rule, severity, message]


def _mypy_row(file, line, col, severity, code, message):
    return [file, str(line), str(col), severity, code, message]


class TestGroupByRulePassthrough:
    def test_verbose_returns_unchanged(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(10)]
        result = _make_ruff_result(rows, verbose=True)
        out = group_by_rule(result)
        assert out is result

    def test_non_lint_parser_returns_unchanged(self):
        result = ParseResult(
            tool="pytest",
            summary="5 passed",
            schema=["test", "status", "duration"],
            rows=[["test_foo", "PASSED", "0.01"]],
            verbose=False,
        )
        out = group_by_rule(result)
        assert out is result

    def test_no_rule_code_column_returns_unchanged(self):
        result = ParseResult(
            tool="ruff",
            summary="1 violation",
            schema=_MINIMAL_SCHEMA,
            rows=[["a.py", "1", "something"]],
            verbose=False,
        )
        out = group_by_rule(result)
        assert out is result

    def test_empty_rows_returns_unchanged(self):
        result = _make_ruff_result([])
        out = group_by_rule(result)
        assert out is result


class TestGroupByRuleThreshold:
    def test_three_violations_shown_individually(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(3)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        assert out.rows == rows

    def test_exactly_three_violations_no_elision(self):
        rows = [_ruff_row("a.py", i, 1, "W291", "warning", "trailing") for i in range(3)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        # All 3 rows intact, no elision row
        assert len(out.rows) == 3
        assert not any("more" in r[0] for r in out.rows)

    def test_four_violations_triggers_grouping(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(4)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        # header + 2 examples + elision = 4 rows
        assert len(out.rows) == 4

    def test_elision_row_format(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(10)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        elision_rows = [r for r in out.rows if "more" in r[0]]
        assert len(elision_rows) == 1
        assert "8 more" in elision_rows[0][0]


class TestGroupByRuleStructure:
    def test_header_row_has_rule_and_count(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(5)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        # First row is header: rule col = "E501", rule_col+1 = "5 occurrences"
        header = out.rows[0]
        assert header[3] == "E501"
        assert "5 occurrences" in header[4]

    def test_two_example_rows_follow_header(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", f"msg {i}") for i in range(5)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        # rows[0] = header, rows[1] = example1, rows[2] = example2, rows[3] = elision
        assert out.rows[1] == rows[0]
        assert out.rows[2] == rows[1]

    def test_multiple_rules_each_grouped_independently(self):
        rows_e501 = [_ruff_row("a.py", i, 1, "E501", "error", "long") for i in range(5)]
        rows_w291 = [_ruff_row("b.py", i, 1, "W291", "warning", "trailing") for i in range(5)]
        result = _make_ruff_result(rows_e501 + rows_w291)
        out = group_by_rule(result)
        # Each group: header + 2 examples + elision = 4 rows × 2 groups = 8
        assert len(out.rows) == 8

    def test_mixed_threshold_groups(self):
        # 2 rows of F401 (under threshold), 5 rows of E501 (over threshold)
        rows_f401 = [_ruff_row("a.py", i, 1, "F401", "error", "unused") for i in range(2)]
        rows_e501 = [_ruff_row("b.py", i, 1, "E501", "error", "long") for i in range(5)]
        result = _make_ruff_result(rows_f401 + rows_e501)
        out = group_by_rule(result)
        # F401: 2 rows. E501: header + 2 examples + elision = 4. Total = 6
        assert len(out.rows) == 6

    def test_schema_preserved(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(5)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        assert out.schema == _RUFF_SCHEMA

    def test_tool_preserved(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "too long") for i in range(5)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        assert out.tool == "ruff"


class TestGroupByRuleSummary:
    def test_summary_updated_with_rule_count(self):
        rows = [_ruff_row("a.py", i, 1, "E501", "error", "long") for i in range(5)]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        assert "5 issue" in out.summary
        assert "1 rule" in out.summary

    def test_summary_multiple_rules(self):
        rows = (
            [_ruff_row("a.py", i, 1, "E501", "error", "long") for i in range(3)]
            + [_ruff_row("b.py", i, 1, "W291", "warning", "trail") for i in range(3)]
        )
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        assert "6 issue" in out.summary
        assert "2 rule" in out.summary

    def test_summary_singular_forms(self):
        rows = [_ruff_row("a.py", 1, 1, "E501", "error", "long")]
        result = _make_ruff_result(rows)
        out = group_by_rule(result)
        assert "1 issue" in out.summary
        assert "1 rule" in out.summary


class TestGroupByRuleCodeColumn:
    def test_mypy_code_column_grouped(self):
        rows = [_mypy_row("a.py", i, 1, "error", "attr-defined", "no attr") for i in range(5)]
        result = _make_mypy_result(rows)
        out = group_by_rule(result)
        # Should have grouped: header + 2 examples + elision = 4
        assert len(out.rows) == 4
        # Header code col (index 4) should be "attr-defined"
        assert out.rows[0][4] == "attr-defined"

    def test_tsc_code_column_grouped(self):
        rows = [
            ["src/a.ts", str(i), "1", "error", "TS2322", "type mismatch"]
            for i in range(5)
        ]
        result = ParseResult(
            tool="tsc",
            summary="5 errors",
            schema=["file", "line", "col", "severity", "code", "message"],
            rows=rows,
            verbose=False,
        )
        out = group_by_rule(result)
        assert len(out.rows) == 4
        assert out.rows[0][4] == "TS2322"

    def test_eslint_rule_column_grouped(self):
        rows = [
            ["src/a.js", str(i), "1", "no-unused-vars", "error", "unused"]
            for i in range(5)
        ]
        result = ParseResult(
            tool="eslint",
            summary="5 violations",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows,
            verbose=False,
        )
        out = group_by_rule(result)
        assert len(out.rows) == 4
        assert out.rows[0][3] == "no-unused-vars"

    def test_cargo_clippy_rule_column_grouped(self):
        rows = [
            ["src/main.rs", str(i), "1", "clippy::needless_return", "warning", "needless"]
            for i in range(5)
        ]
        result = ParseResult(
            tool="cargo-clippy",
            summary="5 warnings",
            schema=["file", "line", "col", "rule", "severity", "message"],
            rows=rows,
            verbose=False,
        )
        out = group_by_rule(result)
        assert len(out.rows) == 4
        assert out.rows[0][3] == "clippy::needless_return"
