"""E2E tests for compact_output MCP tool — full JSON-RPC flow."""

SAMPLE_PYTEST_OUTPUT = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
collected 3 items

tests/test_auth.py::test_login PASSED                                    [ 33%]
tests/test_auth.py::test_signup FAILED                                   [ 66%]
tests/test_auth.py::test_logout PASSED                                   [100%]

=================================== FAILURES ===================================
_________________________________ test_signup __________________________________

    def test_signup():
>       assert False
E       AssertionError

tests/test_auth.py:10: AssertionError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError
========================= 2 passed, 1 failed in 0.10s =========================
"""


def test_compact_output_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "compact_output" in tool_names


def test_compact_output_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "compact_output",
        "arguments": {"text": SAMPLE_PYTEST_OUTPUT, "hint": "pytest"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "# pytest:" in content
    assert "1 failed" in content
    assert "test_signup" in content


def test_compact_output_token_savings(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(SAMPLE_PYTEST_OUTPUT) // 4
    resp = mcp_server.send("tools/call", {
        "name": "compact_output",
        "arguments": {"text": SAMPLE_PYTEST_OUTPUT, "hint": "pytest"},
    })
    content = resp["result"]["content"][0]["text"]
    cleaned_tokens = len(content) // 4
    assert cleaned_tokens < raw_tokens
    savings_pct = (1 - cleaned_tokens / raw_tokens) * 100
    assert savings_pct > 40, f"Only {savings_pct:.1f}% savings"
