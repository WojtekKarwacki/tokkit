import json
import subprocess
import sys


def test_cli_version():
    result = subprocess.run([sys.executable, "-m", "tokkit_server.main", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "tokkit" in result.stdout


def test_cli_index(sample_project_path):
    result = subprocess.run(
        [sys.executable, "-m", "tokkit_server.main", "cli", "index_repository", json.dumps({"path": sample_project_path})],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["node_count"] > 0
