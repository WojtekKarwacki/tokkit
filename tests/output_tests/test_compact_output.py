"""Integration tests for compact_output() public API."""

from tokkit_output import compact_output
from output_tests.fixtures.pytest_output import WITH_FAILURES, ALL_PASS, WITH_ANSI
from output_tests.fixtures.python_tools_output import RUFF_VIOLATIONS, TRACEBACK_SIMPLE
from output_tests.fixtures.js_tools_output import TSC_ERRORS


class TestCompactOutputAPI:
    def test_empty_input(self):
        assert compact_output("") == ""
        assert compact_output("  ") == ""

    def test_with_hint(self):
        result = compact_output(WITH_FAILURES, hint="pytest")
        assert result.startswith("# pytest:")
        assert "2 failed" in result

    def test_auto_detect(self):
        result = compact_output(WITH_FAILURES)
        assert result.startswith("# pytest:")

    def test_verbose_flag(self):
        result = compact_output(WITH_FAILURES, hint="pytest", verbose=True)
        assert "(verbose)" in result
        # Should have all 5 tests as data rows
        lines = result.strip().splitlines()
        data_lines = [l for l in lines if not l.startswith("#") and not l.startswith("[")]
        assert len(data_lines) == 5

    def test_ansi_stripped(self):
        result = compact_output(WITH_ANSI, hint="pytest")
        assert "\x1b" not in result
        assert "# pytest:" in result

    def test_unknown_output_universal_fallback(self):
        raw = "Some random\n\n\n\n\ncommand output\n\x1b[31mwith color\x1b[0m"
        result = compact_output(raw)
        assert "\x1b" not in result
        assert "with color" in result

    def test_ruff_via_auto_detect(self):
        result = compact_output(RUFF_VIOLATIONS)
        # Ratio check may return stripped input for small fixtures; verify content
        assert "E501" in result
        assert "\x1b" not in result

    def test_tsc_via_hint(self):
        result = compact_output(TSC_ERRORS, hint="tsc")
        # Ratio check may return stripped input for small fixtures; verify content
        assert "TS2322" in result
        assert "\x1b" not in result

    def test_traceback_via_auto_detect(self):
        result = compact_output(TRACEBACK_SIMPLE)
        assert "# python-traceback:" in result
        assert "ZeroDivisionError" in result

    def test_all_pass_minimal_output(self):
        result = compact_output(ALL_PASS, hint="pytest")
        assert "# pytest:" in result
        assert "5 passed" in result
        # No schema line when no rows
        assert "[test;" not in result
