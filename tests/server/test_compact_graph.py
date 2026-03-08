"""Tests for graph output compaction in the MCP layer."""
import json

from tokkit_server.tools import _try_compact


def test_try_compact_reduces_json_array():
    raw = json.dumps([
        {"id": 1, "name": "foo", "label": "Function", "file": "a.py"},
        {"id": 2, "name": "bar", "label": "Function", "file": "b.py"},
    ])
    result = _try_compact(raw)
    assert len(result) < len(raw)
    assert "foo" in result
    assert "bar" in result


def test_try_compact_passthrough_on_invalid_json():
    raw = "not json at all"
    result = _try_compact(raw)
    assert result == raw


def test_try_compact_passthrough_on_empty():
    assert _try_compact("") == ""
    assert _try_compact("[]") == "[]"


def test_try_compact_passthrough_when_larger():
    # Single small object — compact header overhead exceeds savings
    raw = '{"a":1}'
    result = _try_compact(raw)
    # Should return whichever is smaller (or raw if equal)
    assert len(result) <= len(raw) or result == raw


from unittest.mock import patch
import tokkit_server.tools as tools_module


def _reset():
    tools_module._session_project_path = "/tmp/repo"
    tools_module._session_db_path = "/tmp/tokkit/repo.redb"


_MOCK_NODES = json.dumps([
    {"id": 1, "label": "Function", "name": "setup", "qualified_name": "proj::main.py::setup",
     "file_path": "/tmp/repo/main.py", "line_start": 1, "line_end": 20, "properties": {}},
    {"id": 2, "label": "Function", "name": "init", "qualified_name": "proj::main.py::init",
     "file_path": "/tmp/repo/main.py", "line_start": 22, "line_end": 40, "properties": {}},
])

_MOCK_STEPS = json.dumps([
    {"node": {"id": 1, "label": "Function", "name": "setup", "qualified_name": "proj::main.py::setup",
              "file_path": "/tmp/repo/main.py", "line_start": 1, "line_end": 20, "properties": {}},
     "edge": None, "depth": 0},
    {"node": {"id": 2, "label": "Function", "name": "init", "qualified_name": "proj::main.py::init",
              "file_path": "/tmp/repo/main.py", "line_start": 22, "line_end": 40, "properties": {}},
     "edge": {"source_id": 1, "target_id": 2, "edge_type": "Calls", "confidence": 0.9, "properties": {}},
     "depth": 1},
])


def test_search_graph_returns_compact():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_NODES):
        result = tools_module.handle_tool_call("find_dead_code", {})
    text = result["content"][0]["text"]
    try:
        json.loads(text)
        is_json = True
    except json.JSONDecodeError:
        is_json = False
    assert not is_json, f"Expected compact format, got JSON: {text[:200]}"
    assert "setup" in text
    assert "proj::main.py::setup" in text


def test_trace_fan_returns_compact():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_STEPS):
        result = tools_module.handle_tool_call("trace_fan", {
            "function_name": "proj::main.py::setup",
            "direction": "outbound",
            "depth": 3,
        })
    text = result["content"][0]["text"]
    assert "setup" in text
    assert "init" in text
    assert len(text) < len(_MOCK_STEPS)


def test_search_graph_compact_smaller_than_raw():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_NODES):
        result = tools_module.handle_tool_call("find_dead_code", {})
    text = result["content"][0]["text"]
    assert len(text) < len(_MOCK_NODES)


def test_meta_reflects_compact_size():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_NODES):
        result = tools_module.handle_tool_call("find_dead_code", {})
    text = result["content"][0]["text"]
    meta = result.get("_meta", {}).get("token_savings", {})
    expected_content = len(text.encode("utf-8")) // 4
    assert meta["content_tokens"] == expected_content
