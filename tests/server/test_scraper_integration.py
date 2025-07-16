"""Integration tests for clean_html MCP tool dispatch."""

import json
from unittest.mock import patch

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_clean_html_tool_dispatch():
    _reset_session()
    html = "<html><body><h1>Title</h1><script>x</script><p>Content</p></body></html>"
    result = handle_tool_call("clean_html", {"html": html, "mode": "markdown"})
    assert not result.get("isError")
    text = result["content"][0]["text"]
    assert "# Title" in text
    assert "Content" in text
    assert "script" not in text.lower()


def test_clean_html_no_session_required():
    _reset_session()
    html = "<p>Hello</p>"
    result = handle_tool_call("clean_html", {"html": html})
    assert not result.get("isError")
    assert "Hello" in result["content"][0]["text"]


def test_clean_html_token_stats_recorded():
    _reset_session()
    html = "<html><body>" + "<p>Content</p>" * 100 + "</body></html>"
    result = handle_tool_call("clean_html", {"html": html})
    assert not result.get("isError")
    meta = result.get("_meta", {}).get("token_savings", {})
    assert meta.get("baseline_tokens", 0) > 0
    assert meta.get("content_tokens", 0) > 0
    assert meta["baseline_tokens"] >= meta["content_tokens"]


def test_clean_html_error_on_missing_html():
    result = handle_tool_call("clean_html", {})
    assert result.get("isError") is True
    assert "html" in result["content"][0]["text"]
    assert "required" in result["content"][0]["text"]


def test_clean_html_show_savings_appends_line(monkeypatch):
    _reset_session()
    monkeypatch.setenv("TOKKIT_SHOW_SAVINGS", "1")
    html = "<html><body>" + "<p>Content</p>" * 100 + "</body></html>"
    result = handle_tool_call("clean_html", {"html": html})
    text = result["content"][0]["text"]
    assert "[tokkit:" in text
    assert "tokens saved]" in text


def test_clean_html_no_savings_line_by_default():
    _reset_session()
    html = "<html><body><p>Content</p></body></html>"
    result = handle_tool_call("clean_html", {"html": html})
    text = result["content"][0]["text"]
    assert "[tokkit:" not in text
