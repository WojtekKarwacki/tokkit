"""Tests for pytest output parser."""

from tokkit_output.parsers.pytest_p import PytestParser
from tests.output_tests.fixtures import pytest_output as fx


class TestPytestDetect:
    def setup_method(self):
        self.parser = PytestParser()

    def test_detects_pytest_all_pass(self):
        assert self.parser.detect(fx.ALL_PASS) >= 0.8

    def test_detects_pytest_with_failures(self):
        assert self.parser.detect(fx.WITH_FAILURES) >= 0.8

    def test_detects_pytest_with_errors(self):
        assert self.parser.detect(fx.WITH_ERRORS) >= 0.8

    def test_detects_ansi_output(self):
        assert self.parser.detect(fx.WITH_ANSI) >= 0.8

    def test_rejects_non_pytest_output(self):
        non_pytest = "Ran 5 tests in 0.003s\n\nOK\n"
        assert self.parser.detect(non_pytest) < 0.6

    def test_rejects_empty_string(self):
        assert self.parser.detect("") < 0.6

    def test_rejects_random_text(self):
        assert self.parser.detect("hello world\nfoo bar\n") < 0.6


class TestPytestParseAllPass:
    def setup_method(self):
        self.parser = PytestParser()

    def test_default_no_rows(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.rows == []

    def test_default_summary_contains_passed(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert "passed" in result.summary
        assert "5" in result.summary

    def test_default_summary_zero_failed(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert "failed" not in result.summary or "0 failed" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.tool == "pytest"

    def test_schema(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.schema == ["test", "status", "file", "line", "error"]

    def test_verbose_five_rows(self):
        result = self.parser.parse(fx.ALL_PASS, verbose=True)
        assert len(result.rows) == 5

    def test_verbose_all_pass_status(self):
        result = self.parser.parse(fx.ALL_PASS, verbose=True)
        for row in result.rows:
            assert row[1] == "PASSED"

    def test_verbose_flag_set(self):
        result = self.parser.parse(fx.ALL_PASS, verbose=True)
        assert result.verbose is True


class TestPytestParseWithFailures:
    def setup_method(self):
        self.parser = PytestParser()

    def test_default_two_failure_rows(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        assert len(result.rows) == 2

    def test_default_failure_statuses(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        statuses = [row[1] for row in result.rows]
        assert all(s == "FAILED" for s in statuses)

    def test_default_test_names(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        test_names = [row[0] for row in result.rows]
        assert "test_get_users" in test_names
        assert "test_post_user" in test_names

    def test_default_error_messages(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        errors = [row[4] for row in result.rows]
        assert any("assert 404" in e for e in errors)
        assert any("assert 500" in e for e in errors)

    def test_default_file_paths(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        for row in result.rows:
            assert "test_api.py" in row[2]

    def test_default_line_numbers(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        for row in result.rows:
            assert row[3].isdigit()

    def test_default_summary_counts(self):
        result = self.parser.parse(fx.WITH_FAILURES)
        assert "2 failed" in result.summary
        assert "3 passed" in result.summary

    def test_verbose_five_rows(self):
        result = self.parser.parse(fx.WITH_FAILURES, verbose=True)
        assert len(result.rows) == 5

    def test_verbose_mixed_statuses(self):
        result = self.parser.parse(fx.WITH_FAILURES, verbose=True)
        statuses = [row[1] for row in result.rows]
        assert "PASSED" in statuses
        assert "FAILED" in statuses


class TestPytestParseWithErrors:
    def setup_method(self):
        self.parser = PytestParser()

    def test_default_one_error_row(self):
        result = self.parser.parse(fx.WITH_ERRORS)
        assert len(result.rows) == 1

    def test_error_status(self):
        result = self.parser.parse(fx.WITH_ERRORS)
        assert result.rows[0][1] == "ERROR"

    def test_error_message_extracted(self):
        result = self.parser.parse(fx.WITH_ERRORS)
        error_msg = result.rows[0][4]
        assert "ConnectionRefusedError" in error_msg or "Connection refused" in error_msg

    def test_summary_contains_error(self):
        result = self.parser.parse(fx.WITH_ERRORS)
        assert "error" in result.summary.lower()


class TestPytestParseAnsi:
    def setup_method(self):
        self.parser = PytestParser()

    def test_ansi_stripped_and_parses(self):
        result = self.parser.parse(fx.WITH_ANSI)
        assert result.tool == "pytest"

    def test_ansi_failure_extracted(self):
        result = self.parser.parse(fx.WITH_ANSI)
        assert len(result.rows) == 1
        assert result.rows[0][1] == "FAILED"

    def test_ansi_test_name(self):
        result = self.parser.parse(fx.WITH_ANSI)
        assert result.rows[0][0] == "test_baz"
