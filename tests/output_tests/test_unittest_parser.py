"""Tests for unittest output parser."""

from tokkit_output.parsers.unittest_p import UnittestParser
from tests.output_tests.fixtures import unittest_output as fx


class TestUnittestDetect:
    def setup_method(self):
        self.parser = UnittestParser()

    def test_detects_all_pass(self):
        assert self.parser.detect(fx.ALL_PASS) >= 0.7

    def test_detects_with_failure(self):
        assert self.parser.detect(fx.WITH_FAILURE) >= 0.7

    def test_detects_with_error(self):
        assert self.parser.detect(fx.WITH_ERROR) >= 0.7

    def test_detects_failure_and_error(self):
        assert self.parser.detect(fx.WITH_FAILURE_AND_ERROR) >= 0.7

    def test_rejects_pytest_output(self):
        pytest_output = (
            "============================= test session starts ==============================\n"
            "collected 3 items\n"
            "tests/test_foo.py::test_bar PASSED\n"
            "============================== 1 passed in 0.01s ==============================\n"
        )
        assert self.parser.detect(pytest_output) < 0.6

    def test_rejects_empty_string(self):
        assert self.parser.detect("") < 0.6


class TestUnittestParseAllPass:
    def setup_method(self):
        self.parser = UnittestParser()

    def test_no_rows_default(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.rows == []

    def test_summary_shows_passed(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert "passed" in result.summary
        assert "2" in result.summary

    def test_tool_name(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.tool == "unittest"

    def test_schema(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.schema == ["test", "status", "file", "line", "error"]

    def test_verbose_flag_false_by_default(self):
        result = self.parser.parse(fx.ALL_PASS)
        assert result.verbose is False


class TestUnittestParseWithFailure:
    def setup_method(self):
        self.parser = UnittestParser()

    def test_one_row(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert len(result.rows) == 1

    def test_fail_status(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert result.rows[0][1] == "FAIL"

    def test_test_name(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert result.rows[0][0] == "test_addition"

    def test_file_path(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert "test_math.py" in result.rows[0][2]

    def test_line_number(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert result.rows[0][3] == "14"

    def test_error_message(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        error = result.rows[0][4]
        assert "AssertionError" in error or "4 != 5" in error

    def test_summary_shows_failure(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert "failed" in result.summary

    def test_summary_shows_passed(self):
        result = self.parser.parse(fx.WITH_FAILURE)
        assert "passed" in result.summary


class TestUnittestParseWithError:
    def setup_method(self):
        self.parser = UnittestParser()

    def test_one_row(self):
        result = self.parser.parse(fx.WITH_ERROR)
        assert len(result.rows) == 1

    def test_error_status(self):
        result = self.parser.parse(fx.WITH_ERROR)
        assert result.rows[0][1] == "ERROR"

    def test_test_name(self):
        result = self.parser.parse(fx.WITH_ERROR)
        assert result.rows[0][0] == "test_connect"

    def test_file_path(self):
        result = self.parser.parse(fx.WITH_ERROR)
        assert "test_db.py" in result.rows[0][2]

    def test_error_message_extracted(self):
        result = self.parser.parse(fx.WITH_ERROR)
        error = result.rows[0][4]
        assert "ConnectionRefusedError" in error or "Connection refused" in error

    def test_summary_shows_error(self):
        result = self.parser.parse(fx.WITH_ERROR)
        assert "error" in result.summary.lower()


class TestUnittestParseWithFailureAndError:
    def setup_method(self):
        self.parser = UnittestParser()

    def test_two_rows(self):
        result = self.parser.parse(fx.WITH_FAILURE_AND_ERROR)
        assert len(result.rows) == 2

    def test_statuses(self):
        result = self.parser.parse(fx.WITH_FAILURE_AND_ERROR)
        statuses = {row[1] for row in result.rows}
        assert "FAIL" in statuses
        assert "ERROR" in statuses

    def test_summary_counts(self):
        result = self.parser.parse(fx.WITH_FAILURE_AND_ERROR)
        assert "failed" in result.summary
        assert "error" in result.summary.lower()
