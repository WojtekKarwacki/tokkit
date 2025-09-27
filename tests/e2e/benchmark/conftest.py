"""Benchmark fixtures: clone repo, start MCP server."""

import json
import os
import subprocess
import pytest

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
PYTHON = "/home/edge/code/tokkit/.venv/bin/python3"


def _repo_url():
    from e2e.benchmark.config import REPO_URL
    return REPO_URL


def _repo_sha():
    from e2e.benchmark.config import REPO_SHA
    return REPO_SHA


def _repo_dir():
    from e2e.benchmark.config import REPO_DIR_NAME
    return REPO_DIR_NAME


@pytest.fixture(scope="session")
def benchmark_repo():
    """Clone fastapi at pinned version, return path."""
    repo_path = os.path.join(CACHE_DIR, _repo_dir())
    if not os.path.isdir(repo_path):
        os.makedirs(CACHE_DIR, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", _repo_sha(), _repo_url(), repo_path],
            check=True,
            capture_output=True,
        )
    return repo_path


@pytest.fixture(scope="session")
def benchmark_mcp(benchmark_repo):
    """Start MCP server and index the benchmark repo."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def call_tool(self, name, arguments=None):
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection")
            resp = json.loads(line)
            content = resp["result"]["content"][0]["text"]
            return content

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)

    client = McpClient(proc)

    # Initialize
    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()  # consume response

    # Index the benchmark repo
    client.call_tool("index_repository", {"path": benchmark_repo})

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def benchmark_mcp_scraper():
    """Start MCP server for scraper benchmarks (no repo indexing needed)."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def call_tool(self, name, arguments=None):
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection")
            resp = json.loads(line)
            content = resp["result"]["content"][0]["text"]
            return content

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)

    client = McpClient(proc)

    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def benchmark_mcp_markdown():
    """Start MCP server for markdown search benchmarks (no repo indexing needed)."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def call_tool(self, name, arguments=None):
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection")
            resp = json.loads(line)
            content = resp["result"]["content"][0]["text"]
            return content

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)

    client = McpClient(proc)

    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def benchmark_mcp_json():
    """Start MCP server for JSON compaction benchmarks (no repo indexing needed)."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def call_tool(self, name, arguments=None):
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection")
            resp = json.loads(line)
            content = resp["result"]["content"][0]["text"]
            return content

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)

    client = McpClient(proc)

    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()
