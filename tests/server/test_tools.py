"""Tests for tools.py tool dispatch."""
import json
from unittest.mock import patch

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_unknown_tool_returns_error():
    result = handle_tool_call("nonexistent_tool", {})
    assert result.get("isError") is True
    text = result["content"][0]["text"]
    assert "Unknown tool" in text


def test_index_repository_calls_rust():
    _reset_session()
    with patch.object(tools_module, "_call_rust", return_value='{"project_name":"test","node_count":10,"edge_count":5,"elapsed_ms":10}') as mock_rust:
        result = handle_tool_call("index_repository", {"path": "/tmp/myrepo"})
    assert not result.get("isError")
    assert mock_rust.called
    mock_rust.assert_called_once_with("index_repository", "/tmp/myrepo", "full")
    assert tools_module._session_project_path == "/tmp/myrepo"


def test_find_dead_code_requires_indexed_project():
    _reset_session()
    result = handle_tool_call("find_dead_code", {})
    assert result.get("isError") is True
    assert "index_repository" in result["content"][0]["text"]


def test_text_result_format():
    _reset_session()
    with patch.object(tools_module, "_call_rust", return_value='{"ok":true}'):
        result = handle_tool_call("index_repository", {"path": "/tmp/r"})
    assert "content" in result
    assert result["content"][0]["type"] == "text"
    assert isinstance(result["content"][0]["text"], str)


def test_error_result_format():
    result = handle_tool_call("unknown_xyz", {})
    assert "content" in result
    assert result["content"][0]["type"] == "text"
    assert result.get("isError") is True


