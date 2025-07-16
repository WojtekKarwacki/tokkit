"""E2E tests for clean_html MCP tool — full JSON-RPC flow."""

import json


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Page</title><style>.x{}</style></head>
<body>
    <nav><a href="/">Home</a><a href="/about">About</a></nav>
    <script>analytics.track('page_view');</script>
    <main>
        <h1>Welcome to Testing</h1>
        <p>This is a <strong>test page</strong> with some content.</p>
        <ul>
            <li>Item one</li>
            <li>Item two</li>
        </ul>
        <table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>Key</td><td>123</td></tr>
        </table>
    </main>
    <footer><p>Copyright 2024</p></footer>
</body>
</html>"""


def test_clean_html_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "clean_html" in tool_names


def test_clean_html_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "clean_html",
        "arguments": {"html": SAMPLE_HTML, "mode": "markdown"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "# Welcome to Testing" in content
    assert "**test page**" in content
    assert "- Item one" in content
    assert "| Name | Value |" in content
    assert "analytics" not in content
    assert "Home" not in content
    assert "Copyright" not in content


def test_clean_html_real_page(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(SAMPLE_HTML) // 4
    resp = mcp_server.send("tools/call", {
        "name": "clean_html",
        "arguments": {"html": SAMPLE_HTML, "mode": "markdown"},
    })
    content = resp["result"]["content"][0]["text"]
    cleaned_tokens = len(content) // 4
    assert cleaned_tokens < raw_tokens
    savings_pct = (1 - cleaned_tokens / raw_tokens) * 100
    assert savings_pct > 40, f"Only {savings_pct:.1f}% savings, expected >40%"
