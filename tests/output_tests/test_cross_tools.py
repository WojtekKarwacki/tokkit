"""Tests for cross-ecosystem output parsers: cargo test/build/clippy, docker."""

from tokkit_output.parsers.cargo_test import CargoTestParser
from tokkit_output.parsers.cargo_build import CargoBuildParser
from tokkit_output.parsers.cargo_clippy import CargoClippyParser
from tokkit_output.parsers.docker import DockerParser
from tests.output_tests.fixtures import cross_tools_output as fx


# ---------------------------------------------------------------------------
# CargoTest
# ---------------------------------------------------------------------------

class TestCargoTestParser:
    def setup_method(self):
        self.parser = CargoTestParser()

    def test_detect_pass(self):
        assert self.parser.detect(fx.CARGO_TEST_PASS) >= 0.9

    def test_detect_fail(self):
        assert self.parser.detect(fx.CARGO_TEST_FAIL) >= 0.9

    def test_rejects_unrelated(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_all_pass_no_rows(self):
        result = self.parser.parse(fx.CARGO_TEST_PASS)
        assert len(result.rows) == 0

    def test_parse_all_pass_summary(self):
        result = self.parser.parse(fx.CARGO_TEST_PASS)
        assert "3 passed" in result.summary
        assert "0 failed" in result.summary

    def test_parse_fail_row_count(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        assert len(result.rows) == 1

    def test_parse_fail_test_name(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        names = [row[0] for row in result.rows]
        assert any("test_sub" in n for n in names)

    def test_parse_fail_status(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        statuses = [row[1] for row in result.rows]
        assert all(s == "FAILED" for s in statuses)

    def test_parse_fail_file(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        files = [row[2] for row in result.rows]
        assert any("lib.rs" in f for f in files)

    def test_parse_fail_line(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        lines = [row[3] for row in result.rows]
        assert any(ln.isdigit() for ln in lines if ln)

    def test_parse_fail_error_message(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        errors = [row[4] for row in result.rows]
        assert any("assertion" in e.lower() or e != "" for e in errors)

    def test_parse_fail_summary(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        assert "2 passed" in result.summary
        assert "1 failed" in result.summary

    def test_schema(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        assert result.schema == ["test", "status", "file", "line", "error"]

    def test_tool_name(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL)
        assert result.tool == "cargo-test"

    def test_verbose_includes_passing(self):
        result = self.parser.parse(fx.CARGO_TEST_FAIL, verbose=True)
        statuses = [row[1] for row in result.rows]
        assert "ok" in statuses
        assert "FAILED" in statuses


# ---------------------------------------------------------------------------
# CargoBuild
# ---------------------------------------------------------------------------

class TestCargoBuildParser:
    def setup_method(self):
        self.parser = CargoBuildParser()

    def test_detect_errors(self):
        assert self.parser.detect(fx.CARGO_BUILD_ERRORS) >= 0.85

    def test_rejects_unrelated(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_errors_row_count(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        assert len(result.rows) >= 2

    def test_parse_errors_schema(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        assert result.schema == ["file", "line", "col", "severity", "code", "message"]

    def test_parse_errors_file_field(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        files = [row[0] for row in result.rows]
        assert any("main.rs" in f or "lib.rs" in f for f in files)

    def test_parse_errors_line_field(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        lines = [row[1] for row in result.rows]
        assert any(ln.isdigit() for ln in lines if ln)

    def test_parse_errors_code_field(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        codes = [row[4] for row in result.rows]
        assert "E0308" in codes
        assert "E0425" in codes

    def test_parse_errors_severity(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        severities = [row[3] for row in result.rows]
        assert "error" in severities

    def test_parse_errors_summary_counts(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        assert "2 error" in result.summary
        assert "warning" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.CARGO_BUILD_ERRORS)
        assert result.tool == "cargo-build"


# ---------------------------------------------------------------------------
# CargoClippy
# ---------------------------------------------------------------------------

class TestCargoClippyParser:
    def setup_method(self):
        self.parser = CargoClippyParser()

    def test_detect_warnings(self):
        assert self.parser.detect(fx.CARGO_CLIPPY_WARNINGS) >= 0.85

    def test_rejects_unrelated(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_warnings_row_count(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        assert len(result.rows) >= 2

    def test_parse_warnings_schema(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        assert result.schema == ["file", "line", "col", "rule", "severity", "message"]

    def test_parse_warnings_file_field(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        files = [row[0] for row in result.rows]
        assert any("lib.rs" in f or "main.rs" in f for f in files)

    def test_parse_warnings_line_field(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        lines = [row[1] for row in result.rows]
        assert any(ln.isdigit() for ln in lines if ln)

    def test_parse_warnings_rule_field(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        rules = [row[3] for row in result.rows]
        assert any("clippy::" in r for r in rules)

    def test_parse_warnings_severity(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        severities = [row[4] for row in result.rows]
        assert all(s == "warning" for s in severities)

    def test_parse_warnings_summary(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        assert "warning" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.CARGO_CLIPPY_WARNINGS)
        assert result.tool == "cargo-clippy"


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

class TestDockerParser:
    def setup_method(self):
        self.parser = DockerParser()

    def test_detect_success(self):
        assert self.parser.detect(fx.DOCKER_BUILD_SUCCESS) >= 0.85

    def test_detect_failure(self):
        assert self.parser.detect(fx.DOCKER_BUILD_FAIL) >= 0.85

    def test_rejects_unrelated(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.3

    def test_parse_success_no_error_rows(self):
        result = self.parser.parse(fx.DOCKER_BUILD_SUCCESS)
        error_rows = [r for r in result.rows if r[1] == "ERROR"]
        assert len(error_rows) == 0

    def test_parse_success_summary(self):
        result = self.parser.parse(fx.DOCKER_BUILD_SUCCESS)
        assert "succeed" in result.summary.lower() or "0" in result.summary

    def test_parse_fail_has_error_rows(self):
        result = self.parser.parse(fx.DOCKER_BUILD_FAIL)
        assert len(result.rows) >= 1

    def test_parse_fail_error_status(self):
        result = self.parser.parse(fx.DOCKER_BUILD_FAIL)
        statuses = [r[1] for r in result.rows]
        assert "ERROR" in statuses

    def test_parse_fail_step_field(self):
        result = self.parser.parse(fx.DOCKER_BUILD_FAIL)
        steps = [r[0] for r in result.rows]
        assert any(s for s in steps)

    def test_parse_fail_summary_has_error(self):
        result = self.parser.parse(fx.DOCKER_BUILD_FAIL)
        assert "error" in result.summary.lower()

    def test_schema(self):
        result = self.parser.parse(fx.DOCKER_BUILD_FAIL)
        assert result.schema == ["step", "status", "message"]

    def test_tool_name(self):
        result = self.parser.parse(fx.DOCKER_BUILD_FAIL)
        assert result.tool == "docker"

    def test_verbose_success_includes_ok_steps(self):
        result = self.parser.parse(fx.DOCKER_BUILD_SUCCESS, verbose=True)
        statuses = [r[1] for r in result.rows]
        assert "ok" in statuses
