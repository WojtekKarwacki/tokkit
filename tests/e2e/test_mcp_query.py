import json

def test_index_status_before_indexing(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {"name": "index_status", "arguments": {}})
    content = resp["result"]["content"][0]["text"]
    status = json.loads(content)
    assert status["indexed"] is False

def test_get_graph_schema(mcp_server, sample_project_path):
    mcp_server.send("initialize", {})
    mcp_server.send("tools/call", {"name": "index_repository", "arguments": {"path": sample_project_path}})
    resp = mcp_server.send("tools/call", {"name": "get_graph_schema", "arguments": {}})
    content = resp["result"]["content"][0]["text"]
    schema = json.loads(content)
    assert len(schema["node_labels"]) > 0
    assert schema["node_count"] > 0


def test_get_token_stats(mcp_server, sample_project_path):
    """Token stats tool returns savings data."""
    mcp_server.send("initialize", {})
    # Index to generate some stats
    mcp_server.send("tools/call", {"name": "index_repository", "arguments": {"path": sample_project_path}})
    # Search to generate savings
    mcp_server.send("tools/call", {"name": "search_graph", "arguments": {"query": "helper"}})
    # Check stats
    resp = mcp_server.send("tools/call", {"name": "get_token_stats", "arguments": {}})
    content = resp["result"]["content"][0]["text"]
    stats = json.loads(content)
    assert stats["total_queries"] >= 2
    assert stats["total_content_saved"] >= 0
    assert "savings_pct" in stats
