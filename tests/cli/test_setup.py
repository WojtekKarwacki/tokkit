"""Tests for the plugin installation logic."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from tokkit_cli.setup import (
    install_plugin,
    uninstall_plugin,
    PLUGIN_KEY,
    MARKETPLACE_NAME,
    PLUGIN_NAME,
)


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

    # Verify .mcp.json content (plugin flat format, not user mcp.json wrapper)
    mcp = json.loads((dest / ".mcp.json").read_text())
    assert "tokkit" in mcp
    assert mcp["tokkit"]["command"] == "uvx"


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


def test_install_plugin_registers_marketplace(tmp_path):
    home = _make_home(tmp_path)

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    plugins = home / ".claude" / "plugins"

    # known_marketplaces.json has a local "tokkit" marketplace
    known = json.loads((plugins / "known_marketplaces.json").read_text())
    assert MARKETPLACE_NAME in known
    entry = known[MARKETPLACE_NAME]
    assert entry["source"]["source"] == "directory"
    mp_dir = plugins / "marketplaces" / MARKETPLACE_NAME
    assert entry["source"]["path"] == str(mp_dir)
    assert entry["installLocation"] == str(mp_dir)
    assert "lastUpdated" in entry

    # marketplace.json lists the plugin under plugins/<name>/
    manifest = json.loads((mp_dir / ".claude-plugin" / "marketplace.json").read_text())
    assert manifest["name"] == MARKETPLACE_NAME
    assert "owner" in manifest
    names = [p["name"] for p in manifest["plugins"]]
    assert PLUGIN_NAME in names
    plugin_entry = next(p for p in manifest["plugins"] if p["name"] == PLUGIN_NAME)
    assert plugin_entry["source"] == f"./plugins/{PLUGIN_NAME}"

    # marketplace root holds only marketplace.json; plugin files live in plugins/
    plugin_dir = mp_dir / "plugins" / PLUGIN_NAME
    assert not (mp_dir / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_dir / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_dir / ".mcp.json").exists()
    assert (plugin_dir / "hooks" / "hook.py").exists()


def test_install_plugin_hook_uses_plugin_root(tmp_path):
    home = _make_home(tmp_path)

    with patch.dict(os.environ, {"HOME": str(home)}):
        dest = install_plugin()

    pj = json.loads((dest / ".claude-plugin" / "plugin.json").read_text())
    hook = pj["hooks"]["PreToolUse"][0]["hooks"][0]
    assert hook["type"] == "command"
    assert "${CLAUDE_PLUGIN_ROOT}" in hook["command"]


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
    (legacy / "references").mkdir()
    (legacy / "references" / "tool-guide.md").write_text("old")

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    # Legacy skill artifacts gone...
    assert not (legacy / "SKILL.md").exists()
    assert not (legacy / "references").exists()


def test_install_plugin_preserves_stats(tmp_path):
    """`setup` must not wipe stats.json (same dir as the legacy skill dir)."""
    home = _make_home(tmp_path)
    legacy = home / ".local" / "share" / "tokkit"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("old")
    stats = legacy / "stats.json"
    stats.write_text('{"total_queries": 42}')

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_plugin()

    assert stats.exists()
    assert json.loads(stats.read_text())["total_queries"] == 42


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

    # Marketplace dir + registration removed
    assert not (home / ".claude" / "plugins" / "marketplaces" / MARKETPLACE_NAME).exists()
    known_path = home / ".claude" / "plugins" / "known_marketplaces.json"
    if known_path.exists():
        known = json.loads(known_path.read_text())
        assert MARKETPLACE_NAME not in known

    # Unregistered
    installed = json.loads((home / ".claude" / "plugins" / "installed_plugins.json").read_text())
    assert PLUGIN_KEY not in installed["plugins"]

    # Disabled
    settings = json.loads((home / ".claude" / "settings.json").read_text())
    assert PLUGIN_KEY not in settings.get("enabledPlugins", {})
