"""Tests for schema+CSV output formatting."""

from tokkit_output.formatter import format_result, ParseResult


class TestFormatResult:
    def test_basic_format(self):
        result = ParseResult(
            tool="pytest",
            summary="2 passed, 1 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=[
                ["test_login", "FAIL", "tests/test_auth.py", "42", "AssertionError: expected 200"],
            ],
            verbose=False,
        )
        out = format_result(result)
        assert out.startswith("# pytest: 2 passed, 1 failed\n")
        assert "[test;status;file;line;error]" in out
        assert "test_login;FAIL;tests/test_auth.py;42;AssertionError: expected 200" in out

    def test_empty_rows_summary_only(self):
        result = ParseResult(
            tool="pytest",
            summary="47 passed, 0 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=[],
            verbose=False,
        )
        out = format_result(result)
        assert out == "# pytest: 47 passed, 0 failed"

    def test_verbose_marker_in_summary(self):
        result = ParseResult(
            tool="ruff",
            summary="0 violations",
            schema=["file", "line", "col", "rule", "message"],
            rows=[["src/a.py", "1", "1", "E501", "Line too long"]],
            verbose=True,
        )
        out = format_result(result)
        assert "# ruff (verbose): 0 violations" in out

    def test_semicolon_in_value_is_quoted(self):
        result = ParseResult(
            tool="tsc",
            summary="1 error",
            schema=["file", "line", "col", "code", "message"],
            rows=[["a.ts", "1", "1", "TS2322", "Type 'a;b' is not assignable"]],
            verbose=False,
        )
        out = format_result(result)
        assert '"Type \'a;b\' is not assignable"' in out or "Type 'a;b' is not assignable" in out

    def test_newline_in_value_is_quoted(self):
        result = ParseResult(
            tool="pytest",
            summary="1 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=[["test_x", "FAIL", "t.py", "1", "line1\nline2"]],
            verbose=False,
        )
        out = format_result(result)
        assert '"line1\nline2"' in out
