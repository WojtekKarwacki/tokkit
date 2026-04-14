"""Tests for ratio check and compact_output integration changes."""

import pytest
from tokkit_output import compact_output
from tokkit_output.universal import strip_ansi


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RUFF_MANY_VIOLATIONS = "\n".join(
    [f"src/module.py:{i}:1: E501 Line too long (100 > 88)" for i in range(1, 50)]
    + ["Found 49 errors."]
)

_RUFF_FEW_VIOLATIONS = "\n".join(
    [
        "src/a.py:1:1: E501 Line too long",
        "src/a.py:2:1: E501 Line too long",
        "Found 2 errors.",
    ]
)

_RUFF_MULTI_RULE = "\n".join(
    [f"src/a.py:{i}:1: E501 Line too long (100 > 88)" for i in range(1, 6)]
    + [f"src/b.py:{i}:1: W291 Trailing whitespace" for i in range(1, 6)]
    + ["Found 10 errors."]
)

# Output that is genuinely smaller when left as-is (short, no noise)
_SHORT_CLEAN_OUTPUT = "All checks passed!\n"

# Output with ANSI that expands if formatted
_ANSI_OUTPUT = "\x1b[32mAll checks passed!\x1b[0m\n"

# Unknown output that should fall through to generic_clean
_UNKNOWN_OUTPUT = (
    "Some random command output\n"
    "that no parser recognizes\n"
    "and has no structure at all\n" * 10
)

# Unknown output with ANSI
_UNKNOWN_ANSI = "\x1b[31mError:\x1b[0m something went wrong\n" * 5


class TestGenericFallback:
    def test_unknown_output_no_ansi_in_result(self):
        result = compact_output(_UNKNOWN_ANSI)
        assert "\x1b" not in result

    def test_unknown_output_content_preserved(self):
        result = compact_output(_UNKNOWN_OUTPUT)
        assert "Some random command output" in result

    def test_unknown_output_does_not_start_with_hash(self):
        result = compact_output(_UNKNOWN_OUTPUT)
        assert not result.startswith("# ")


class TestLintGrouperIntegration:
    def test_ruff_many_violations_grouped(self):
        result = compact_output(_RUFF_MANY_VIOLATIONS, hint="ruff")
        assert "# ruff:" in result
        # Should have elision markers for the E501 group
        assert "more" in result

    def test_ruff_few_violations_not_grouped(self):
        result = compact_output(_RUFF_FEW_VIOLATIONS, hint="ruff")
        # Only 2 violations: no elision regardless of output form
        assert "more" not in result
        # Either structured format or ratio-check fallback — no ANSI either way
        assert "\x1b" not in result

    def test_ruff_multi_rule_summary_updated(self):
        result = compact_output(_RUFF_MULTI_RULE, hint="ruff")
        assert "# ruff:" in result
        assert "across" in result
        assert "rule" in result

    def test_ruff_verbose_no_grouping(self):
        result = compact_output(_RUFF_MANY_VIOLATIONS, hint="ruff", verbose=True)
        # Verbose mode disables grouping; ratio check may still apply
        # No elision markers (grouper is skipped)
        assert "more" not in result
        # All 49 violation messages should be present
        assert "E501" in result

    def test_ruff_grouped_summary_in_header(self):
        result = compact_output(_RUFF_MANY_VIOLATIONS, hint="ruff")
        header_line = result.splitlines()[0]
        assert "49 issue" in header_line
        assert "1 rule" in header_line


class TestRatioCheck:
    def test_formatted_longer_than_input_returns_stripped(self):
        # Craft input where structured output would be longer than the cleaned input.
        # A single short violation: schema+CSV overhead makes it longer.
        short_ruff = "src/a.py:1:1: E501 Line too long\nFound 1 error.\n"
        cleaned = strip_ansi(short_ruff)
        result = compact_output(short_ruff, hint="ruff")
        # Result must be no longer than the ANSI-stripped input
        assert len(result) <= len(cleaned)

    def test_ratio_check_does_not_truncate_when_shorter(self):
        # 49 violations: formatted output should be much shorter due to grouping
        result = compact_output(_RUFF_MANY_VIOLATIONS, hint="ruff")
        cleaned = strip_ansi(_RUFF_MANY_VIOLATIONS)
        assert len(result) < len(cleaned)

    def test_ansi_stripped_fallback_has_no_ansi(self):
        # If ratio check triggers, the returned fallback must have no ANSI
        ansi_short = "\x1b[31msrc/a.py:1:1: E501 Line too long\x1b[0m\nFound 1 error.\n"
        result = compact_output(ansi_short, hint="ruff")
        assert "\x1b" not in result

    def test_empty_input_unchanged(self):
        assert compact_output("") == ""
        assert compact_output("   ") == ""

    def test_generic_fallback_ratio_check(self):
        # Generic fallback output should never be longer than stripped input
        for _ in range(3):
            result = compact_output(_UNKNOWN_ANSI)
            cleaned = strip_ansi(_UNKNOWN_ANSI)
            assert len(result) <= len(cleaned)
