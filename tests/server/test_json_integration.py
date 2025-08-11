"""Integration tests for compact_json MCP tool dispatch."""

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_compact_json_tool_dispatch():
    _reset_session()
    json_str = '[{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]'
    result = handle_tool_call("compact_json", {"json": json_str})
    assert not result.get("isError")
    text = result["content"][0]["text"]
    assert "name" in text
    assert "alice" in text


def test_compact_json_no_session_required():
    _reset_session()
    json_str = '{"name": "alice"}'
    result = handle_tool_call("compact_json", {"json": json_str})
    assert not result.get("isError")
    assert "alice" in result["content"][0]["text"]


def test_compact_json_token_stats_recorded():
    _reset_session()
    json_str = '[' + ','.join(['{"name": "user", "age": 30}'] * 50) + ']'
    result = handle_tool_call("compact_json", {"json": json_str})
    assert not result.get("isError")
    meta = result.get("_meta", {}).get("token_savings", {})
    assert meta.get("baseline_tokens", 0) > 0
    assert meta.get("content_tokens", 0) > 0
    assert meta["baseline_tokens"] >= meta["content_tokens"]


def test_compact_json_error_on_missing_json():
    result = handle_tool_call("compact_json", {})
    assert result.get("isError") is True
    assert "json" in result["content"][0]["text"]
    assert "required" in result["content"][0]["text"]
