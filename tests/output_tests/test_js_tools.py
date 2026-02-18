"""Tests for JS/TS ecosystem output parsers: jest, vitest, mocha, tsc, eslint, webpack, vite, npm."""

from tokkit_output.parsers.jest import JestParser
from tokkit_output.parsers.vitest import VitestParser
from tokkit_output.parsers.mocha import MochaParser
from tokkit_output.parsers.tsc import TscParser
from tokkit_output.parsers.eslint import EslintParser
from tokkit_output.parsers.webpack import WebpackParser
from tokkit_output.parsers.vite import ViteParser
from tokkit_output.parsers.npm import NpmParser
from tests.output_tests.fixtures import js_tools_output as fx


# ---------------------------------------------------------------------------
# Jest
# ---------------------------------------------------------------------------

class TestJestParser:
    def setup_method(self):
        self.parser = JestParser()

    def test_detect_with_failures(self):
        assert self.parser.detect(fx.JEST_WITH_FAILURES) >= 0.9

    def test_detect_all_pass(self):
        assert self.parser.detect(fx.JEST_ALL_PASS) >= 0.9

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_failures_row_count(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        assert len(result.rows) == 2

    def test_parse_failures_summary(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        assert "2 failed" in result.summary
        assert "6 passed" in result.summary

    def test_parse_failures_schema(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        assert result.schema == ["test", "status", "file", "line", "error"]

    def test_parse_failures_test_name(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        names = [row[0] for row in result.rows]
        assert any("should connect" in n for n in names)

    def test_parse_failures_file_field(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        files = [row[2] for row in result.rows]
        assert any("db.test.ts" in f for f in files)

    def test_parse_failures_line_field(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        lines = [row[3] for row in result.rows]
        assert any(ln.isdigit() for ln in lines if ln)

    def test_parse_failures_status(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        statuses = [row[1] for row in result.rows]
        assert all(s == "FAILED" for s in statuses)

    def test_parse_all_pass_no_rows(self):
        result = self.parser.parse(fx.JEST_ALL_PASS)
        assert len(result.rows) == 0

    def test_parse_all_pass_summary(self):
        result = self.parser.parse(fx.JEST_ALL_PASS)
        assert "0 failed" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.JEST_WITH_FAILURES)
        assert result.tool == "jest"


# ---------------------------------------------------------------------------
# Vitest
# ---------------------------------------------------------------------------

class TestVitestParser:
    def setup_method(self):
        self.parser = VitestParser()

    def test_detect_with_failures(self):
        assert self.parser.detect(fx.VITEST_WITH_FAILURES) >= 0.9

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_failures_row_count(self):
        result = self.parser.parse(fx.VITEST_WITH_FAILURES)
        assert len(result.rows) == 2

    def test_parse_failures_summary(self):
        result = self.parser.parse(fx.VITEST_WITH_FAILURES)
        assert "2 failed" in result.summary
        assert "5 passed" in result.summary

    def test_parse_failures_schema(self):
        result = self.parser.parse(fx.VITEST_WITH_FAILURES)
        assert result.schema == ["test", "status", "file", "line", "error"]

    def test_parse_failures_test_name(self):
        result = self.parser.parse(fx.VITEST_WITH_FAILURES)
        names = [row[0] for row in result.rows]
        assert any("ApiService" in n or "fetch users" in n or "api.test.ts" in n for n in names)

    def test_parse_failures_status(self):
        result = self.parser.parse(fx.VITEST_WITH_FAILURES)
        statuses = [row[1] for row in result.rows]
        assert all(s == "FAILED" for s in statuses)

    def test_tool_name(self):
        result = self.parser.parse(fx.VITEST_WITH_FAILURES)
        assert result.tool == "vitest"


# ---------------------------------------------------------------------------
# Mocha
# ---------------------------------------------------------------------------

class TestMochaParser:
    def setup_method(self):
        self.parser = MochaParser()

    def test_detect_with_failures(self):
        assert self.parser.detect(fx.MOCHA_WITH_FAILURES) >= 0.85

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_failures_row_count(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        assert len(result.rows) == 2

    def test_parse_failures_summary(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        assert "3 passed" in result.summary
        assert "2 failed" in result.summary

    def test_parse_failures_schema(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        assert result.schema == ["test", "status", "file", "line", "error"]

    def test_parse_failures_test_name(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        names = [row[0] for row in result.rows]
        assert any("delete user" in n for n in names)

    def test_parse_failures_file_field(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        files = [row[2] for row in result.rows]
        assert any("user.test.js" in f for f in files)

    def test_parse_failures_line_field(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        lines = [row[3] for row in result.rows]
        assert any(ln.isdigit() for ln in lines if ln)

    def test_parse_failures_status(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        statuses = [row[1] for row in result.rows]
        assert all(s == "FAILED" for s in statuses)

    def test_tool_name(self):
        result = self.parser.parse(fx.MOCHA_WITH_FAILURES)
        assert result.tool == "mocha"


# ---------------------------------------------------------------------------
# tsc
# ---------------------------------------------------------------------------

class TestTscParser:
    def setup_method(self):
        self.parser = TscParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.TSC_ERRORS) >= 0.9

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_detect_clean(self):
        assert self.parser.detect(fx.TSC_CLEAN) < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        assert len(result.rows) == 3

    def test_parse_errors_summary(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        assert "2" in result.summary
        assert "error" in result.summary.lower()

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        assert result.schema == ["file", "line", "col", "severity", "code", "message"]

    def test_parse_errors_file_field(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        files = [row[0] for row in result.rows]
        assert any("api.ts" in f for f in files)

    def test_parse_errors_code_field(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        codes = [row[4] for row in result.rows]
        assert "TS2322" in codes
        assert "TS2345" in codes

    def test_parse_errors_severity(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        severities = [row[3] for row in result.rows]
        assert "error" in severities
        assert "warning" in severities

    def test_parse_clean_no_rows(self):
        result = self.parser.parse(fx.TSC_CLEAN)
        assert result.rows == []

    def test_tool_name(self):
        result = self.parser.parse(fx.TSC_ERRORS)
        assert result.tool == "tsc"


# ---------------------------------------------------------------------------
# eslint
# ---------------------------------------------------------------------------

class TestEslintParser:
    def setup_method(self):
        self.parser = EslintParser()

    def test_detect_violations(self):
        assert self.parser.detect(fx.ESLINT_VIOLATIONS) >= 0.9

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_violations_row_count(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        assert len(result.rows) == 4

    def test_parse_violations_summary(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        assert "4" in result.summary

    def test_parse_violations_schema(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        assert result.schema == ["file", "line", "col", "rule", "severity", "message"]

    def test_parse_violations_file_field(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        files = [row[0] for row in result.rows]
        assert any("auth.ts" in f for f in files)
        assert any("db.ts" in f for f in files)

    def test_parse_violations_rule_field(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        rules = [row[3] for row in result.rows]
        assert "no-unused-vars" in rules

    def test_parse_violations_severity_mix(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        severities = set(row[4] for row in result.rows)
        assert "error" in severities
        assert "warning" in severities

    def test_tool_name(self):
        result = self.parser.parse(fx.ESLINT_VIOLATIONS)
        assert result.tool == "eslint"


# ---------------------------------------------------------------------------
# webpack
# ---------------------------------------------------------------------------

class TestWebpackParser:
    def setup_method(self):
        self.parser = WebpackParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.WEBPACK_ERROR) >= 0.85

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.WEBPACK_ERROR)
        assert len(result.rows) == 2

    def test_parse_errors_summary(self):
        result = self.parser.parse(fx.WEBPACK_ERROR)
        assert "2" in result.summary
        assert "error" in result.summary.lower()

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.WEBPACK_ERROR)
        assert result.schema == ["step", "status", "message"]

    def test_parse_errors_step_field(self):
        result = self.parser.parse(fx.WEBPACK_ERROR)
        steps = [row[0] for row in result.rows]
        assert any("index.ts" in s for s in steps)

    def test_parse_errors_status(self):
        result = self.parser.parse(fx.WEBPACK_ERROR)
        statuses = [row[1] for row in result.rows]
        assert all(s == "error" for s in statuses)

    def test_tool_name(self):
        result = self.parser.parse(fx.WEBPACK_ERROR)
        assert result.tool == "webpack"


# ---------------------------------------------------------------------------
# vite
# ---------------------------------------------------------------------------

class TestViteParser:
    def setup_method(self):
        self.parser = ViteParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.VITE_ERROR) >= 0.85

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.VITE_ERROR)
        assert len(result.rows) == 2

    def test_parse_errors_summary(self):
        result = self.parser.parse(fx.VITE_ERROR)
        assert "2" in result.summary
        assert "error" in result.summary.lower()

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.VITE_ERROR)
        assert result.schema == ["step", "status", "message"]

    def test_parse_errors_step_field(self):
        result = self.parser.parse(fx.VITE_ERROR)
        steps = [row[0] for row in result.rows]
        assert any("api.ts" in s for s in steps)

    def test_parse_errors_status(self):
        result = self.parser.parse(fx.VITE_ERROR)
        statuses = [row[1] for row in result.rows]
        assert all(s == "error" for s in statuses)

    def test_tool_name(self):
        result = self.parser.parse(fx.VITE_ERROR)
        assert result.tool == "vite"


# ---------------------------------------------------------------------------
# npm
# ---------------------------------------------------------------------------

class TestNpmParser:
    def setup_method(self):
        self.parser = NpmParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.NPM_ERROR) >= 0.8

    def test_rejects_unrelated_output(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.NPM_ERROR)
        assert len(result.rows) >= 1

    def test_parse_errors_summary(self):
        result = self.parser.parse(fx.NPM_ERROR)
        assert "issue" in result.summary.lower()

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.NPM_ERROR)
        assert result.schema == ["package", "status", "message"]

    def test_parse_errors_contains_conflict(self):
        result = self.parser.parse(fx.NPM_ERROR)
        statuses = [row[1] for row in result.rows]
        assert "peer-conflict" in statuses or "deprecated" in statuses or "error" in statuses

    def test_parse_errors_package_field(self):
        result = self.parser.parse(fx.NPM_ERROR)
        packages = [row[0] for row in result.rows]
        assert any(p for p in packages)

    def test_tool_name(self):
        result = self.parser.parse(fx.NPM_ERROR)
        assert result.tool == "npm"
