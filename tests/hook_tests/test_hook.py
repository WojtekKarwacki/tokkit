"""Tests for PreToolUse hook protocol."""

import pytest
from tokkit_hook.hook import handle_hook_request


class TestHookProtocol:
    def test_non_bash_passes_through(self):
        """Non-Bash tool → allow with no params."""
        request = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" not in response

    def test_bash_git_diff_rewrites(self):
        """git diff → decision allow + params with tokkit compress."""
        request = {
            "tool_name": "Bash",
            "tool_input": {"command": "git diff"},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" in response
        assert "tokkit compress" in response["params"]["command"]
        assert "git diff" in response["params"]["command"]

    def test_bash_unknown_passes_through(self):
        """Unknown command → allow, no params."""
        request = {
            "tool_name": "Bash",
            "tool_input": {"command": "whoami"},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" not in response

    def test_bash_cat_source_passes_through(self):
        """cat src/main.py → allow, no params (source file exclusion)."""
        request = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat src/main.py"},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" not in response

    def test_chained_command_rewrites(self):
        """cd src && pytest → rewrite (primary is pytest)."""
        request = {
            "tool_name": "Bash",
            "tool_input": {"command": "cd src && pytest"},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" in response
        assert "tokkit compress" in response["params"]["command"]

    def test_pipe_passes_through(self):
        """git diff | head → allow, no params (pipe exclusion)."""
        request = {
            "tool_name": "Bash",
            "tool_input": {"command": "git diff | head"},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" not in response

    def test_empty_command_passes_through(self):
        """Empty command → allow, no params."""
        request = {
            "tool_name": "Bash",
            "tool_input": {"command": ""},
        }
        response = handle_hook_request(request)
        assert response["decision"] == "allow"
        assert "params" not in response

    def test_missing_tool_name_passes_through(self):
        """Missing tool_name → allow."""
        response = handle_hook_request({})
        assert response["decision"] == "allow"
