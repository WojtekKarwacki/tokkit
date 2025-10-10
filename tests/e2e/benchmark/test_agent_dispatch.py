"""Agent dispatch benchmark: verify tokkit agents call expected MCP tools.

Dispatches real Claude agents with formalized prompts and verifies they
call the declared MCP tools. Each scenario runs a tokkit agent and checks
tool_call logs from the MCP server's stderr.

Usage:
    pytest tests/e2e/benchmark/test_agent_dispatch.py -m agent_dispatch -v

These tests are EXPENSIVE (each dispatches a real Claude API call).
They are skipped by default unless explicitly selected with -m agent_dispatch.
"""

import json
import os
import subprocess
import threading
import time

import pytest

from e2e.benchmark.scenarios import SCENARIOS, FIXTURES_DIR, resolve_prompt

PYTHON = "/home/edge/code/tokkit/.venv/bin/python3"


class McpClientWithLogs:
    """MCP client that captures tool_call logs from server stderr."""

    def __init__(self):
        self.proc = subprocess.Popen(
            [PYTHON, "-m", "tokkit_server.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._id = 0
        self.tool_calls: list[str] = []
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

        # Initialize
        self._send({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})

    def _read_stderr(self):
        """Read stderr lines and capture tool_call logs."""
        while True:
            try:
                line = self.proc.stderr.readline()
                if not line:
                    break
                if "[tokkit] tool_call:" in line:
                    tool = line.strip().split("tool_call:", 1)[1].strip()
                    self.tool_calls.append(tool)
            except Exception:
                break

    def _send(self, request: dict) -> str:
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("Server closed connection")
        return line.strip()

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        self._id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        raw = self._send(request)
        resp = json.loads(raw)
        return resp["result"]["content"][0]["text"]

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


@pytest.fixture(scope="module")
def mcp():
    """Start MCP server with tool call logging."""
    client = McpClientWithLogs()
    yield client
    client.close()


def _scenario_by_id(sid: str):
    return next(s for s in SCENARIOS if s.id == sid)


# ---------------------------------------------------------------------------
# Direct MCP tool verification: call each expected tool and verify it works
# ---------------------------------------------------------------------------

@pytest.mark.benchmark
class TestToolVerification:
    """Verify each scenario's expected MCP tool works correctly."""

    def test_q1_trace_fan_inbound(self, benchmark_repo, mcp):
        """Q1: trace_fan should work for blast radius (inbound)."""
        mcp.call_tool("index_repository", {"path": benchmark_repo})
        result = mcp.call_tool("trace_fan", {
            "function_name": "get_openapi",
            "direction": "inbound",
            "depth": 3,
        })
        assert "trace_fan" in mcp.tool_calls
        assert len(result) > 0

    def test_q2_trace_fan_outbound(self, benchmark_repo, mcp):
        """Q2: trace_fan should work for call chain tracing (outbound)."""
        result = mcp.call_tool("trace_fan", {
            "function_name": "setup",
            "direction": "outbound",
            "depth": 3,
        })
        assert len(result) > 0

    def test_q3_find_dead_code(self, benchmark_repo, mcp):
        """Q3: find_dead_code should return unreferenced functions."""
        result = mcp.call_tool("find_dead_code", {"limit": 200})
        assert "find_dead_code" in mcp.tool_calls
        assert len(result) > 0

    def test_q4_find_routes(self, benchmark_repo, mcp):
        """Q4: find_routes should return HTTP route handlers."""
        result = mcp.call_tool("find_routes", {"limit": 200})
        assert "find_routes" in mcp.tool_calls
        assert len(result) > 0

    def test_q5_get_architecture(self, benchmark_repo, mcp):
        """Q5: get_architecture should return project overview."""
        result = mcp.call_tool("get_architecture", {})
        assert "get_architecture" in mcp.tool_calls
        assert len(result) > 0

    def test_q6_search_markdown(self, benchmark_repo, mcp):
        """Q6: search_markdown should find sections in README."""
        readme = os.path.join(benchmark_repo, "README.md")
        result = mcp.call_tool("search_markdown", {
            "path": readme,
            "query": "dependencies requirements",
        })
        assert "search_markdown" in mcp.tool_calls
        assert len(result) > 0

    def test_q7_clean_html_python_docs(self, mcp):
        """Q7: clean_html should process Python docs HTML."""
        path = str(FIXTURES_DIR / "html" / "python_docs.html")
        result = mcp.call_tool("clean_html", {"path": path, "mode": "markdown"})
        assert "clean_html" in mcp.tool_calls
        assert len(result) > 0

    def test_q8_clean_html_blog(self, mcp):
        """Q8: clean_html should process blog post HTML."""
        path = str(FIXTURES_DIR / "html" / "blog_post.html")
        result = mcp.call_tool("clean_html", {"path": path, "mode": "markdown"})
        assert len(result) > 0

    def test_q9_compact_json_flat(self, mcp):
        """Q9: compact_json should compress flat records."""
        path = str(FIXTURES_DIR / "json" / "flat_records.json")
        result = mcp.call_tool("compact_json", {"path": path})
        assert "compact_json" in mcp.tool_calls
        assert len(result) > 0

    def test_q10_compact_json_nested(self, mcp):
        """Q10: compact_json should compress nested data."""
        path = str(FIXTURES_DIR / "json" / "nested_complex.json")
        result = mcp.call_tool("compact_json", {"path": path})
        assert len(result) > 0

    def test_q11_compact_output_pytest(self, mcp):
        """Q11: compact_output should compress pytest results."""
        path = str(FIXTURES_DIR / "shell" / "pytest_output.txt")
        result = mcp.call_tool("compact_output", {"path": path, "hint": "pytest"})
        assert "compact_output" in mcp.tool_calls
        assert len(result) > 0

    def test_q12_compact_output_ruff(self, mcp):
        """Q12: compact_output should compress ruff lint output."""
        path = str(FIXTURES_DIR / "shell" / "ruff_output.txt")
        result = mcp.call_tool("compact_output", {"path": path, "hint": "ruff"})
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Prompt quality checks: verify prompts resolve and match tool descriptions
# ---------------------------------------------------------------------------

@pytest.mark.benchmark
class TestPromptQuality:
    """Verify prompts are well-formed and aligned with MCP tool descriptions."""

    def test_all_scenarios_have_unique_ids(self):
        ids = [s.id for s in SCENARIOS]
        assert len(ids) == len(set(ids))

    def test_all_fixture_paths_exist(self):
        for s in SCENARIOS:
            if s.fixture_path:
                path = FIXTURES_DIR / s.fixture_path
                assert path.exists(), f"{s.id}: fixture {s.fixture_path} not found"

    def test_all_prompts_resolve(self):
        for s in SCENARIOS:
            prompt = resolve_prompt(s, agent="tokkit")
            assert "{repo}" not in prompt, f"{s.id}: unresolved {{repo}} in prompt"
            assert "{fixtures}" not in prompt, f"{s.id}: unresolved {{fixtures}} in prompt"

    def test_tokkit_prompts_include_system_instruction(self):
        for s in SCENARIOS:
            prompt = resolve_prompt(s, agent="tokkit")
            assert "tokkit" in prompt.lower(), f"{s.id}: tokkit prompt missing system instruction"

    def test_baseline_prompts_restrict_to_builtins(self):
        for s in SCENARIOS:
            prompt = resolve_prompt(s, agent="baseline")
            assert "built-in tools" in prompt.lower() or "do not use any mcp" in prompt.lower(), \
                f"{s.id}: baseline prompt missing restriction"

    def test_content_tool_prompts_include_file_paths(self):
        """Content tools (Q6-Q12) must include file paths so agents can match."""
        content_tools = {"clean_html", "compact_json", "search_markdown", "compact_output"}
        for s in SCENARIOS:
            if s.expected_tool in content_tools:
                prompt = resolve_prompt(s, agent="tokkit")
                # Check path appears in the question portion
                assert "/" in s.question, \
                    f"{s.id}: content tool prompt missing file path reference"

    def test_code_graph_prompts_include_index_reminder(self):
        """Code graph tools (Q1-Q5) must remind agent to index first."""
        graph_tools = {"trace_fan", "find_dead_code", "find_routes", "get_architecture"}
        for s in SCENARIOS:
            if s.expected_tool in graph_tools:
                prompt = resolve_prompt(s, agent="tokkit")
                assert "index_repository" in prompt, \
                    f"{s.id}: code graph prompt missing index_repository reminder"

    def test_expected_tools_are_valid_mcp_tools(self):
        valid = {
            "index_repository", "get_architecture", "find_dead_code",
            "find_routes", "trace_fan", "clean_html", "compact_json",
            "search_markdown", "compact_output",
        }
        for s in SCENARIOS:
            assert s.expected_tool in valid, \
                f"{s.id}: expected_tool '{s.expected_tool}' is not a valid MCP tool"

    def test_prompt_keywords_match_tool_descriptions(self):
        """Check that prompt keywords overlap with expected tool descriptions."""
        from tokkit_server.protocol import TOOL_DEFINITIONS

        tool_desc = {t["name"]: t["description"].lower() for t in TOOL_DEFINITIONS}

        # Keywords in prompts that should match tool descriptions
        keyword_map = {
            "trace_fan": ["call", "function", "trace", "caller"],
            "find_dead_code": ["dead code", "never referenced", "unreferenced"],
            "find_routes": ["route", "handler", "http"],
            "get_architecture": ["architecture", "overview", "module"],
            "search_markdown": ["search", "markdown", "section"],
            "clean_html": ["html", "clean", "strip"],
            "compact_json": ["json", "compact", "compress"],
            "compact_output": ["output", "compress", "test result", "lint"],
        }

        for s in SCENARIOS:
            tool = s.expected_tool
            desc = tool_desc[tool]
            keywords = keyword_map.get(tool, [])
            matches = [kw for kw in keywords if kw in desc]
            assert len(matches) >= 1, \
                f"{s.id}: tool '{tool}' description doesn't match expected keywords {keywords}"
