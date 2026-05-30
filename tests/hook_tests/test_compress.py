"""Tests for compress CLI (run_and_compress)."""

import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from tokkit_hook.compress import run_and_compress


class TestRunAndCompress:
    def test_echo_passthrough(self, capsys):
        """echo hello → output contains 'hello'."""
        exit_code = run_and_compress("echo hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_preserves_exit_code(self):
        """false → non-zero return code."""
        exit_code = run_and_compress("false")
        assert exit_code != 0

    def test_success_exit_code(self):
        """true → zero return code."""
        exit_code = run_and_compress("true")
        assert exit_code == 0


class TestStatsRecording:
    def test_records_compression_to_stats(self, tmp_path):
        """A compressed command writes a compress:<hint> entry to stats.json."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}):
            # `git status` matches the git-status hint
            run_and_compress("git status")
            stats_path = tmp_path / "tokkit" / "stats.json"
            assert stats_path.exists()
            stats = json.loads(stats_path.read_text())

        assert stats["total_queries"] >= 1
        compress_tools = [k for k in stats["by_tool"] if k.startswith("compress:")]
        assert compress_tools, f"no compress tool key in {list(stats['by_tool'])}"
        # Attributed to the synthetic hook agent
        agents = {c["agent"] for c in stats["chats"].values()}
        assert "hook" in agents

    def test_recording_failure_never_breaks_command(self, tmp_path):
        """If stats recording raises, the command output/exit code is unaffected."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)}), patch(
            "tokkit_server.token_stats.record_bash_compression",
            side_effect=RuntimeError("boom"),
        ):
            exit_code = run_and_compress("true")
        assert exit_code == 0


class TestMainEntrypoint:
    def test_empty_command_fails(self):
        """No args → non-zero exit code."""
        result = subprocess.run(
            [sys.executable, "-m", "tokkit_hook.compress"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_main_runs_command(self):
        """python -m tokkit_hook.compress 'echo world' → output contains 'world'."""
        result = subprocess.run(
            [sys.executable, "-m", "tokkit_hook.compress", "echo world"],
            capture_output=True,
            text=True,
        )
        assert "world" in result.stdout
