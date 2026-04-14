"""Tests for generic fallback pipeline."""

import pytest
from tokkit_output.generic import generic_clean

# Padding to push inputs past the 500-char short-circuit threshold.
_PAD = "\npadding line here\n" * 30


class TestProgressBarRemoval:
    def test_removes_progress_bar_lines(self):
        text = "Downloading...\n████████████████████░░░░ 80%\nDone." + _PAD
        result = generic_clean(text)
        assert "████" not in result
        assert "Done." in result

    def test_keeps_non_bar_lines(self):
        text = "Step 1: Build\nStep 2: Test\nStep 3: Deploy" + _PAD
        result = generic_clean(text)
        assert "Step 1" in result
        assert "Step 3" in result

    def test_removes_spinner_characters(self):
        text = "Loading ⠋\nLoading ⠙\nLoading ⠹\nLoading ⠸\nDone." + _PAD
        result = generic_clean(text)
        assert "Done." in result

    def test_removes_hash_progress_bars(self):
        text = (
            "Progress: [##########----------] 50%\n"
            "Progress: [####################] 100%\n"
            "Complete."
            + _PAD
        )
        result = generic_clean(text)
        assert "Complete." in result


class TestConsecutiveDedup:
    def test_collapses_identical_lines(self):
        text = "building...\n" * 10 + "done." + _PAD
        result = generic_clean(text)
        assert "building... (x10)" in result
        assert "done." in result

    def test_no_dedup_for_unique_lines(self):
        text = "line alpha\nline beta\nline gamma" + _PAD
        result = generic_clean(text)
        assert "line alpha" in result
        assert "line beta" in result
        assert "line gamma" in result

    def test_dedup_preserves_single_instance(self):
        text = "alpha\nalpha\nbeta\nbeta\nbeta\ngamma" + _PAD
        result = generic_clean(text)
        assert "alpha (x2)" in result
        assert "beta (x3)" in result
        assert "gamma" in result


class TestSimilarLineDedup:
    def test_collapses_numeric_variants(self):
        # Lines with % trigger numeric-heavy check; normalized form is identical.
        lines = [f"Progress: {i}% ETA 00:0{i % 10}:00" for i in range(1, 21)]
        text = "\n".join(lines) + "\nComplete."
        result = generic_clean(text)
        # Should collapse to first + "... (N similar lines)" + last
        assert "similar" in result.lower()
        assert "Complete." in result

    def test_keeps_non_numeric_lines(self):
        text = "error: file not found\nwarning: deprecated API\ninfo: build complete" + _PAD
        result = generic_clean(text)
        assert "error" in result
        assert "warning" in result
        assert "info" in result


class TestHeadTailTruncation:
    def test_truncates_long_output(self):
        # Use non-numeric-heavy lines so similar-line dedup doesn't collapse them first.
        lines = [f"step-{i:03d}: running build task for component alpha" for i in range(1, 301)]
        text = "\n".join(lines)
        result = generic_clean(text)
        assert "step-001" in result
        assert "step-100" in result
        assert "step-300" in result
        # Middle should be truncated
        assert "truncated" in result.lower()
        assert "step-150" not in result

    def test_no_truncation_for_short_output(self):
        lines = [f"step-{i:03d}: running build task for component alpha" for i in range(1, 51)]
        text = "\n".join(lines)
        result = generic_clean(text)
        assert "truncated" not in result.lower()
        for i in range(1, 51):
            assert f"step-{i:03d}" in result


class TestMinLengthBypass:
    def test_short_input_passes_through(self):
        text = "ok"
        result = generic_clean(text)
        assert result == "ok"

    def test_whitespace_only_returns_empty(self):
        text = "   \n\n  "
        result = generic_clean(text)
        assert result.strip() == ""


class TestFullPipeline:
    def test_ansi_plus_progress_plus_dedup(self):
        text = (
            "\x1b[32mStarting build...\x1b[0m\n"
            + "████████░░░░ 60%\n"
            + "compiling...\n" * 5
            + "Build complete."
            + _PAD
        )
        result = generic_clean(text)
        assert "\x1b" not in result
        assert "████" not in result
        assert "compiling... (x5)" in result
        assert "Build complete." in result
