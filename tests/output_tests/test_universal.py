"""Tests for universal fallback (ANSI strip + blank line collapse)."""

from tokkit_output.universal import strip_ansi, collapse_blanks, universal_clean


class TestStripAnsi:
    def test_removes_color_codes(self):
        text = "\x1b[32mPASS\x1b[0m test_foo"
        assert strip_ansi(text) == "PASS test_foo"

    def test_removes_bold(self):
        text = "\x1b[1mBold\x1b[0m"
        assert strip_ansi(text) == "Bold"

    def test_preserves_plain_text(self):
        assert strip_ansi("hello world") == "hello world"

    def test_removes_256_color(self):
        text = "\x1b[38;5;196mred\x1b[0m"
        assert strip_ansi(text) == "red"

    def test_removes_rgb_color(self):
        text = "\x1b[38;2;255;0;0mred\x1b[0m"
        assert strip_ansi(text) == "red"


class TestCollapseBlanks:
    def test_collapses_multiple_blank_lines(self):
        text = "a\n\n\n\nb"
        assert collapse_blanks(text) == "a\n\nb"

    def test_preserves_single_blank(self):
        text = "a\n\nb"
        assert collapse_blanks(text) == "a\n\nb"

    def test_strips_trailing_whitespace_lines(self):
        text = "a\n   \n   \nb"
        assert collapse_blanks(text) == "a\n\nb"


class TestUniversalClean:
    def test_combined(self):
        text = "\x1b[32mPASS\x1b[0m\n\n\n\nDone"
        out = universal_clean(text)
        assert out == "PASS\n\nDone"
