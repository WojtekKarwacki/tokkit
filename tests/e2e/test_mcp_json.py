"""E2E tests for compact_json MCP tool — full JSON-RPC flow."""

import json


FLAT_JSON = json.dumps([
    {"name": "alice", "age": 30, "role": "eng", "city": "NYC"},
    {"name": "bob", "age": 25, "role": "pm", "city": "SF"},
    {"name": "carol", "age": 35, "role": "eng", "city": "LA"},
])

NESTED_JSON = json.dumps({
    "org": "acme",
    "teams": [
        {
            "name": "engineering",
            "members": [
                {"name": "alice", "skills": ["python", "rust"]},
                {"name": "bob", "skills": ["go"]},
            ],
        },
    ],
})


def test_compact_json_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "compact_json" in tool_names


def test_compact_json_csv_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "compact_json",
        "arguments": {"json": FLAT_JSON},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "[name;age;role;city]" in content
    assert "alice" in content
    assert "bob" in content
    assert "carol" in content


def test_compact_json_nested_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "compact_json",
        "arguments": {"json": NESTED_JSON},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    # Schema header should mention teams and members
    assert "teams:" in content or "teams:[" in content
    assert "alice" in content
    assert "bob" in content


def test_compact_json_saves_tokens(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(FLAT_JSON) // 4
    resp = mcp_server.send("tools/call", {
        "name": "compact_json",
        "arguments": {"json": FLAT_JSON},
    })
    content = resp["result"]["content"][0]["text"]
    compacted_tokens = len(content) // 4
    assert compacted_tokens < raw_tokens
    savings_pct = (1 - compacted_tokens / raw_tokens) * 100
    assert savings_pct > 20, f"Only {savings_pct:.1f}% savings, expected >20%"
