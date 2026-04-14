"""Tests for compress CLI (run_and_compress)."""

import subprocess
import sys
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
