"""Integration tests for compact_output MCP tool dispatch."""

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_compact_output_tool_dispatch():
    _reset_session()
    text = """\
============================= test session starts ==============================
tests/test_auth.py::test_login PASSED
tests/test_auth.py::test_signup FAILED
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError
========================= 1 passed, 1 failed in 0.10s =========================
"""
    result = handle_tool_call("compact_output", {"text": text, "hint": "pytest"})
    assert not result.get("isError")
    content = result["content"][0]["text"]
    assert "# pytest:" in content
    assert "1 failed" in content


def test_compact_output_no_session_required():
    _reset_session()
    text = "src/a.py:1:1: E501 Line too long\nFound 1 error.\n"
    result = handle_tool_call("compact_output", {"text": text, "hint": "ruff"})
    assert not result.get("isError")
    assert "ruff" in result["content"][0]["text"]


def test_compact_output_token_stats_recorded():
    _reset_session()
    text = "x\n" * 100
    result = handle_tool_call("compact_output", {"text": text})
    assert not result.get("isError")
    meta = result.get("_meta", {}).get("token_savings", {})
    assert meta.get("baseline_tokens", 0) > 0


def test_compact_output_verbose_flag():
    _reset_session()
    text = """\
============================= test session starts ==============================
tests/test_a.py::test_x PASSED
tests/test_a.py::test_y PASSED
========================= 2 passed in 0.01s ===================================
"""
    result = handle_tool_call("compact_output", {"text": text, "hint": "pytest", "verbose": True})
    assert not result.get("isError")
    content = result["content"][0]["text"]
    assert "(verbose)" in content


def test_compact_output_error_on_missing_text():
    result = handle_tool_call("compact_output", {})
    assert result.get("isError") is True
    assert "text" in result["content"][0]["text"]
    assert "required" in result["content"][0]["text"]
