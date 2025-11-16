"""Tests for protocol.py JSON-RPC helpers."""
import json

import pytest

from tokkit_server.protocol import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    build_error,
    build_initialize_response,
    build_response,
    build_tools_list_response,
    parse_request,
)


def test_parses_valid_request():
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    req = parse_request(line)
    assert req["id"] == 1
    assert req["method"] == "tools/list"
    assert req["params"] == {}


def test_parses_request_without_params():
    line = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    req = parse_request(line)
    assert req["id"] == 2
    assert req["method"] == "initialize"
    assert req["params"] == {}


def test_raises_on_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_request("not valid json {")


def test_raises_on_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_request(json.dumps([1, 2, 3]))


def test_success_response():
    resp = json.loads(build_response(42, {"ok": True}))
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 42
    assert resp["result"] == {"ok": True}
    assert "error" not in resp


def test_error_response():
    resp = json.loads(build_error(1, METHOD_NOT_FOUND, "Method not found: foo"))
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["error"]["code"] == METHOD_NOT_FOUND
    assert resp["error"]["message"] == "Method not found: foo"
    assert "data" not in resp["error"]


def test_error_with_data():
    resp = json.loads(build_error(None, PARSE_ERROR, "bad json", data={"detail": "x"}))
    assert resp["id"] is None
    assert resp["error"]["data"] == {"detail": "x"}


def test_initialize_response():
    resp = json.loads(build_initialize_response(10))
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert "tools" in result["capabilities"]
    assert result["serverInfo"]["name"] == "tokkit"
    from tokkit_server import __version__
    assert result["serverInfo"]["version"] == __version__


def test_tools_list_response():
    resp = json.loads(build_tools_list_response(5))
    tools = resp["result"]["tools"]
    assert len(tools) == 9
    names = {t["name"] for t in tools}
    assert "index_repository" in names
    assert "get_architecture" in names
# rev-25
    assert "trace_fan" in names
