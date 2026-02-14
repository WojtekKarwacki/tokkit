"""Tests for Python ecosystem output parsers: ruff, mypy, pyright, pip, traceback."""

from tokkit_output.parsers.ruff import RuffParser
from tokkit_output.parsers.mypy import MypyParser
from tokkit_output.parsers.pyright import PyrightParser
from tokkit_output.parsers.pip import PipParser
from tokkit_output.parsers.traceback_p import TracebackParser
from tests.output_tests.fixtures import python_tools_output as fx


# ---------------------------------------------------------------------------
# Ruff
# ---------------------------------------------------------------------------

class TestRuffParser:
    def setup_method(self):
        self.parser = RuffParser()

    def test_detect_violations(self):
        assert self.parser.detect(fx.RUFF_VIOLATIONS) >= 0.5

    def test_detect_clean(self):
        assert self.parser.detect(fx.RUFF_CLEAN) >= 0.5

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("Ran 5 tests in 0.003s\n\nOK\n") < 0.3

    def test_parse_violations_row_count(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        assert len(result.rows) == 3

    def test_parse_violations_summary(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        assert "3" in result.summary

    def test_parse_violations_schema(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        assert result.schema == ["file", "line", "col", "rule", "severity", "message"]

    def test_parse_violations_file_field(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        files = [row[0] for row in result.rows]
        assert any("auth.py" in f for f in files)
        assert any("db.py" in f for f in files)

    def test_parse_violations_rule_field(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        rules = [row[3] for row in result.rows]
        assert "E501" in rules
        assert "F401" in rules
        assert "E711" in rules

    def test_parse_violations_severity_error(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        row_e501 = next(r for r in result.rows if r[3] == "E501")
        assert row_e501[4] == "error"

    def test_parse_clean_no_rows(self):
        result = self.parser.parse(fx.RUFF_CLEAN)
        assert result.rows == []

    def test_parse_clean_summary(self):
        result = self.parser.parse(fx.RUFF_CLEAN)
        assert "passed" in result.summary.lower() or "0" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.RUFF_VIOLATIONS)
        assert result.tool == "ruff"


# ---------------------------------------------------------------------------
# Mypy
# ---------------------------------------------------------------------------

class TestMypyParser:
    def setup_method(self):
        self.parser = MypyParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.MYPY_ERRORS) >= 0.5

    def test_detect_clean(self):
        assert self.parser.detect(fx.MYPY_CLEAN) >= 0.5

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        # Notes are skipped in default mode; 2 errors expected
        assert len(result.rows) == 2

    def test_parse_errors_summary(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        assert "2" in result.summary
        assert "error" in result.summary.lower()

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        assert result.schema == ["file", "line", "col", "severity", "code", "message"]

    def test_parse_errors_file_field(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        files = [row[0] for row in result.rows]
        assert all("auth.py" in f or "db.py" in f for f in files)

    def test_parse_errors_code_field(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        codes = [row[4] for row in result.rows]
        assert "arg-type" in codes or "union-attr" in codes

    def test_parse_errors_severity(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        severities = [row[3] for row in result.rows]
        assert all(s == "error" for s in severities)

    def test_parse_verbose_includes_notes(self):
        result = self.parser.parse(fx.MYPY_ERRORS, verbose=True)
        severities = [row[3] for row in result.rows]
        assert "note" in severities

    def test_parse_clean_no_rows(self):
        result = self.parser.parse(fx.MYPY_CLEAN)
        assert result.rows == []

    def test_parse_clean_summary(self):
        result = self.parser.parse(fx.MYPY_CLEAN)
        assert "no issues" in result.summary.lower() or "0" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.MYPY_ERRORS)
        assert result.tool == "mypy"


# ---------------------------------------------------------------------------
# Pyright
# ---------------------------------------------------------------------------

class TestPyrightParser:
    def setup_method(self):
        self.parser = PyrightParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.PYRIGHT_ERRORS) >= 0.5

    def test_detect_clean(self):
        assert self.parser.detect(fx.PYRIGHT_CLEAN) >= 0.5

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.PYRIGHT_ERRORS)
        # 2 errors + 1 warning; informations excluded in default mode
        assert len(result.rows) == 3

    def test_parse_errors_summary(self):
        result = self.parser.parse(fx.PYRIGHT_ERRORS)
        assert "2" in result.summary
        assert "error" in result.summary.lower()

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.PYRIGHT_ERRORS)
        assert result.schema == ["file", "line", "col", "severity", "code", "message"]

    def test_parse_errors_severity_values(self):
        result = self.parser.parse(fx.PYRIGHT_ERRORS)
        severities = set(row[3] for row in result.rows)
        assert "error" in severities

    def test_parse_errors_code_field(self):
        result = self.parser.parse(fx.PYRIGHT_ERRORS)
        codes = [row[4] for row in result.rows]
        assert any("report" in c.lower() for c in codes if c)

    def test_parse_clean_no_rows(self):
        result = self.parser.parse(fx.PYRIGHT_CLEAN)
        assert result.rows == []

    def test_parse_clean_summary(self):
        result = self.parser.parse(fx.PYRIGHT_CLEAN)
        assert "0" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.PYRIGHT_ERRORS)
        assert result.tool == "pyright"


# ---------------------------------------------------------------------------
# Pip
# ---------------------------------------------------------------------------

class TestPipParser:
    def setup_method(self):
        self.parser = PipParser()

    def test_detect_conflicts(self):
        assert self.parser.detect(fx.PIP_CONFLICTS) >= 0.5

    def test_detect_build_failure(self):
        assert self.parser.detect(fx.PIP_BUILD_FAILURE) >= 0.5

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_conflicts_row_count(self):
        result = self.parser.parse(fx.PIP_CONFLICTS)
        # 2 conflict lines + 1 error line
        assert len(result.rows) >= 2

    def test_parse_conflicts_status(self):
        result = self.parser.parse(fx.PIP_CONFLICTS)
        statuses = [row[1] for row in result.rows]
        assert "conflict" in statuses

    def test_parse_conflicts_summary(self):
        result = self.parser.parse(fx.PIP_CONFLICTS)
        assert "issue" in result.summary.lower() or "conflict" in result.summary.lower()

    def test_parse_conflicts_package_field(self):
        result = self.parser.parse(fx.PIP_CONFLICTS)
        packages = [row[0] for row in result.rows]
        assert any("botocore" in p or "requests" in p for p in packages)

    def test_parse_build_failure_has_error(self):
        result = self.parser.parse(fx.PIP_BUILD_FAILURE)
        statuses = [row[1] for row in result.rows]
        assert "error" in statuses

    def test_parse_schema(self):
        result = self.parser.parse(fx.PIP_CONFLICTS)
        assert result.schema == ["package", "status", "message"]

    def test_tool_name(self):
        result = self.parser.parse(fx.PIP_CONFLICTS)
        assert result.tool == "pip"


# ---------------------------------------------------------------------------
# Python traceback
# ---------------------------------------------------------------------------

class TestTracebackParser:
    def setup_method(self):
        self.parser = TracebackParser()

    def test_detect_simple(self):
        assert self.parser.detect(fx.TRACEBACK_SIMPLE) >= 0.9

    def test_detect_chained(self):
        assert self.parser.detect(fx.TRACEBACK_CHAINED) >= 0.9

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_simple_row_count_default(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        # Default: one row per exception (last frame only)
        assert len(result.rows) == 1

    def test_parse_simple_exception_type(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert result.rows[0][0] == "ZeroDivisionError"

    def test_parse_simple_last_frame_file(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert "compute.py" in result.rows[0][1]

    def test_parse_simple_last_frame_line(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert result.rows[0][2] == "17"

    def test_parse_simple_last_frame_function(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert result.rows[0][3] == "compute"

    def test_parse_simple_summary(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert "ZeroDivisionError" in result.summary or "exception" in result.summary.lower()

    def test_parse_simple_verbose_all_frames(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE, verbose=True)
        # 2 frames in simple traceback
        assert len(result.rows) == 2

    def test_parse_chained_default_two_rows(self):
        result = self.parser.parse(fx.TRACEBACK_CHAINED)
        # Two exceptions in chain, one row each in default mode
        assert len(result.rows) == 2

    def test_parse_chained_exception_types(self):
        result = self.parser.parse(fx.TRACEBACK_CHAINED)
        exc_types = [row[0] for row in result.rows]
        assert any("OperationalError" in t or "psycopg2" in t for t in exc_types)
        assert any("DatabaseError" in t for t in exc_types)

    def test_parse_schema(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert result.schema == ["exception", "file", "line", "function", "message"]

    def test_tool_name(self):
        result = self.parser.parse(fx.TRACEBACK_SIMPLE)
        assert result.tool == "python-traceback"
