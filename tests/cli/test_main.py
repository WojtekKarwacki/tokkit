"""Tests for the tokkit CLI entry point."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from tokkit_cli.main import main


def test_setup_detects_and_configures_agents(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "plugins").mkdir()
    cursor_dir = home / ".cursor"
    cursor_dir.mkdir()

    with patch.dict(os.environ, {"HOME": str(home)}), \
         patch("sys.argv", ["tokkit", "setup"]):
        main()

    # Claude: plugin installed (not mcp.json)
    installed = json.loads((claude_dir / "plugins" / "installed_plugins.json").read_text())
    assert "tokkit@tokkit" in installed["plugins"]

    # Cursor: MCP config written (no plugin support)
    cursor_mcp = json.loads((cursor_dir / "mcp.json").read_text())
    assert "tokkit" in cursor_mcp["mcpServers"]

    out = capsys.readouterr().out
    assert "claude" in out.lower()
    assert "cursor" in out.lower()


def test_setup_uninstall(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "plugins").mkdir()

    # First install, then uninstall
    with patch.dict(os.environ, {"HOME": str(home)}), \
         patch("sys.argv", ["tokkit", "setup"]):
        main()

    with patch.dict(os.environ, {"HOME": str(home)}), \
         patch("sys.argv", ["tokkit", "setup", "--uninstall"]):
        main()

    installed = json.loads((claude_dir / "plugins" / "installed_plugins.json").read_text())
    assert "tokkit@tokkit" not in installed["plugins"]


def test_default_action_is_setup(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "plugins").mkdir()

    with patch.dict(os.environ, {"HOME": str(home)}), \
         patch("sys.argv", ["tokkit"]):
        main()

    # Should have run setup (claude detected)
    out = capsys.readouterr().out
    assert "claude" in out.lower()


def test_serve_delegates_to_mcp_server(monkeypatch):
    mock_serve = MagicMock()
    monkeypatch.setattr("tokkit_server.main.serve_stdio", mock_serve)
    with patch("sys.argv", ["tokkit", "serve"]):
        main()
    mock_serve.assert_called_once()
