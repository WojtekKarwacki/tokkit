"""Tests for the plugin installation logic."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from tokkit_cli.setup import install_plugin, uninstall_plugin, PLUGIN_KEY


def _make_home(tmp_path):
    """Create a minimal fake home with ~/.claude/ directory."""
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    plugins_dir = claude_dir / "plugins"
    plugins_dir.mkdir()
    return home


def test_install_plugin_creates_structure(tmp_path):
    home = _make_home(tmp_path)

    with patch.dict(os.environ, {"HOME": str(home)}):
        dest = install_plugin()

    assert (dest / ".claude-plugin" / "plugin.json").exists()
    assert (dest / "skills" / "tokkit-code-intelligence" / "SKILL.md").exists()
    assert (dest / "skills" / "tokkit-code-intelligence" / "references" / "tool-guide.md").exists()
    assert (dest / ".mcp.json").exists()

    # Verify plugin.json content
    pj = json.loads((dest / ".claude-plugin" / "plugin.json").read_text())
    assert pj["name"] == "tokkit"
    assert "version" in pj

    # Verify .mcp.json content
    mcp = json.loads((dest / ".mcp.json").read_text())
    assert "tokkit" in mcp["mcpServers"]


def test_install_plugin_registers(tmp_path):
    home = _make_home(tmp_path)

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    installed = json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())
    assert PLUGIN_KEY in installed["plugins"]
    entry = installed["plugins"][PLUGIN_KEY][0]
    assert entry["scope"] == "user"
    assert "installPath" in entry


def test_install_plugin_enables(tmp_path):
    home = _make_home(tmp_path)
    # Pre-existing settings
    (home / ".claude" / "settings.json").write_text(json.dumps({"effortLevel": "high"}))

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    settings = json.loads((home / ".claude" / "settings.json").read_text())
    assert settings["enabledPlugins"][PLUGIN_KEY] is True
    # Didn't clobber existing settings
    assert settings["effortLevel"] == "high"


def test_install_plugin_removes_legacy_skill_ref(tmp_path):
    home = _make_home(tmp_path)
    (home / ".claude" / "CLAUDE.md").write_text("@RTK.md\n@~/.local/share/tokkit/SKILL.md\n")

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    content = (home / ".claude" / "CLAUDE.md").read_text()
    assert "@~/.local/share/tokkit/SKILL.md" not in content
    assert "@RTK.md" in content


def test_install_plugin_removes_legacy_skill_dir(tmp_path):
    home = _make_home(tmp_path)
    legacy = home / ".local" / "share" / "tokkit"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("old")

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    assert not legacy.exists()


def test_install_plugin_removes_mcp_from_user_config(tmp_path):
    home = _make_home(tmp_path)
    mcp = {"mcpServers": {"tokkit": {"command": "uvx", "args": ["tokkit", "serve"]}, "other": {"command": "foo"}}}
    (home / ".claude" / "mcp.json").write_text(json.dumps(mcp))

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    config = json.loads((home / ".claude" / "mcp.json").read_text())
    assert "tokkit" not in config["mcpServers"]
    assert "other" in config["mcpServers"]


def test_install_plugin_idempotent(tmp_path):
    home = _make_home(tmp_path)

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()
        install_plugin()

    installed = json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())
    assert len(installed["plugins"][PLUGIN_KEY]) == 1


def test_uninstall_plugin(tmp_path):
    home = _make_home(tmp_path)

    with patch.dict(os.environ, {"HOME": str(home)}):
        dest = install_plugin()
        assert dest.exists()
        uninstall_plugin()

    # Plugin cache removed
    assert not (home / ".claude" / "plugins" / "cache" / "tokkit").exists()

    # Unregistered
    installed = json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())
    assert PLUGIN_KEY not in installed["plugins"]

    # Disabled
    settings = json.loads((home / ".claude" / "settings.json").read_text())
    assert PLUGIN_KEY not in settings.get("enabledPlugins", {})
