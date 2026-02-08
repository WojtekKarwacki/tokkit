"""Tests for auto-detection engine across all parsers."""

from tokkit_output.parsers import all_parsers
from tokkit_output.detect import detect_parser
from output_tests.fixtures.pytest_output import WITH_FAILURES, ALL_PASS
from output_tests.fixtures.python_tools_output import RUFF_VIOLATIONS, MYPY_ERRORS, TRACEBACK_SIMPLE
from output_tests.fixtures.js_tools_output import JEST_WITH_FAILURES, TSC_ERRORS, ESLINT_VIOLATIONS
from output_tests.fixtures.cross_tools_output import CARGO_TEST_FAIL, CARGO_BUILD_ERRORS


class TestAutoDetection:
    def test_detects_pytest(self):
        p = detect_parser(WITH_FAILURES, all_parsers())
        assert p is not None
        assert p.id == "pytest"

    def test_detects_ruff(self):
        p = detect_parser(RUFF_VIOLATIONS, all_parsers())
        assert p is not None
        assert p.id == "ruff"

    def test_detects_mypy(self):
        p = detect_parser(MYPY_ERRORS, all_parsers())
        assert p is not None
        assert p.id == "mypy"

    def test_detects_traceback(self):
        p = detect_parser(TRACEBACK_SIMPLE, all_parsers())
        assert p is not None
        assert p.id == "python-traceback"

    def test_detects_jest(self):
        p = detect_parser(JEST_WITH_FAILURES, all_parsers())
        assert p is not None
        assert p.id == "jest"

    def test_detects_tsc(self):
        p = detect_parser(TSC_ERRORS, all_parsers())
        assert p is not None
        assert p.id == "tsc"

    def test_detects_eslint(self):
        p = detect_parser(ESLINT_VIOLATIONS, all_parsers())
        assert p is not None
        assert p.id == "eslint"

    def test_detects_cargo_test(self):
        p = detect_parser(CARGO_TEST_FAIL, all_parsers())
        assert p is not None
        assert p.id == "cargo-test"

    def test_detects_cargo_build(self):
        p = detect_parser(CARGO_BUILD_ERRORS, all_parsers())
        assert p is not None
        assert p.id == "cargo-build"

    def test_returns_none_for_unknown(self):
        p = detect_parser("hello world\nfoo bar baz\n", all_parsers())
        assert p is None

    def test_no_false_positive_on_plain_text(self):
        p = detect_parser("The quick brown fox\njumps over the lazy dog\n", all_parsers())
        assert p is None
