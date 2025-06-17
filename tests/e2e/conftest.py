import json
import os
import subprocess
import sys
import pytest


@pytest.fixture
def sample_project_path():
    return os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


@pytest.fixture
def mcp_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def send(self, method, params=None):
            self._id += 1
            request = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            response_line = self.proc.stdout.readline()
            if not response_line:
                raise RuntimeError("Server closed connection")
            return json.loads(response_line)

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    client = McpClient(proc)
    yield client
    try:
        client.close()
    except Exception:
        proc.kill()
