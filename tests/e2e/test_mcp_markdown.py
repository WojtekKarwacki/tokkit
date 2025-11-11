"""E2E tests for search_markdown MCP tool — full JSON-RPC flow."""

import json
import os
import tempfile


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install to get started.

### Authentication
Set up your API key for authentication.

### Database Setup
Configure your database connection string.

## Configuration
Edit the config file to set your preferences.

# API Reference
Full API documentation below.

## Auth Endpoints
POST /login to authenticate users.

## User Endpoints
GET /users returns the user list.
"""

_tmpfile = None


def _sample_path():
    global _tmpfile
    if _tmpfile is None:
        _tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        _tmpfile.write(SAMPLE_MD)
        _tmpfile.flush()
    return _tmpfile.name


def test_search_markdown_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "search_markdown" in tool_names


def test_search_markdown_with_matches(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"path": _sample_path(), "query": "auth"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "Matches:" in content
    assert "Authentication" in content
    assert "Savings:" in content


def test_search_markdown_no_matches(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"path": _sample_path(), "query": "xyznonexistent"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "No matches" in content
    assert "# Getting Started" in content


def test_search_markdown_empty_query(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"path": _sample_path(), "query": ""},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "Document headers:" in content


def test_search_markdown_saves_tokens(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(SAMPLE_MD) // 4
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"path": _sample_path(), "query": "Authentication"},
    })
    content = resp["result"]["content"][0]["text"]
    result_tokens = len(content) // 4
    assert result_tokens < raw_tokens


def test_search_markdown_has_meta(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"path": _sample_path(), "query": "auth"},
    })
    assert "_meta" in resp["result"]
    meta = resp["result"]["_meta"]["token_savings"]
    assert meta["content_saved"] > 0


def test_search_markdown_missing_path(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"path": "", "query": "test"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "path is required" in content.lower()
