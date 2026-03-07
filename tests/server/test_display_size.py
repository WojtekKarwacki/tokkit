"""Tests for make_meta display_size parameter."""
from unittest.mock import patch

from tokkit_server.token_stats import make_meta, CHARS_PER_TOKEN


def test_make_meta_uses_display_size_for_content_tokens():
    raw_json = '{"id":1,"name":"foo","label":"Function","file":"a.py","line_start":1,"line_end":10}'
    display_size = 40

    with patch("tokkit_server.token_stats.record_query"):
        meta = make_meta(
            "find_dead_code", raw_json, "/tmp/repo",
            display_size=display_size, args={},
        )

    assert meta["content_tokens"] == display_size // CHARS_PER_TOKEN
    assert meta["baseline_tokens"] >= 0


def test_make_meta_without_display_size_unchanged():
    raw_json = '{"id":1,"name":"foo"}'

    with patch("tokkit_server.token_stats.record_query"):
        meta = make_meta(
            "find_dead_code", raw_json, "/tmp/repo",
            args={},
        )

    assert meta["content_tokens"] == len(raw_json.encode("utf-8")) // CHARS_PER_TOKEN
