import json

def test_initialize_handshake(mcp_server):
    resp = mcp_server.send("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    })
    assert "result" in resp
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "tokkit"

def test_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "index_repository" in tool_names
    assert "search_graph" in tool_names
    assert len(tools) >= 10

def test_index_and_search(mcp_server, sample_project_path):
    mcp_server.send("initialize", {})
    # Index
    resp = mcp_server.send("tools/call", {
        "name": "index_repository",
        "arguments": {"path": sample_project_path},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    result = json.loads(content)
    assert result["node_count"] > 0
    # Search
    resp = mcp_server.send("tools/call", {
        "name": "search_graph",
        "arguments": {"query": "helper"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    nodes = json.loads(content)
    assert len(nodes) > 0
