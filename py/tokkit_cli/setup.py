"""Plugin installation and removal for Claude Code."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import os


PLUGIN_KEY = "tokkit@tokkit"
MARKETPLACE_NAME = "tokkit"
PLUGIN_NAME = "tokkit"
LEGACY_SKILL_REF = "@~/.local/share/tokkit/SKILL.md"


def _home() -> Path:
    return Path(os.environ.get("HOME", Path.home()))


def _version() -> str:
    from tokkit_server import __version__
    return __version__


def _plugin_install_dir(version: str) -> Path:
    return _home() / ".claude" / "plugins" / "cache" / "tokkit" / "tokkit" / version


def _installed_plugins_path() -> Path:
    return _home() / ".claude" / "plugins" / "installed_plugins.json"


def _settings_path() -> Path:
    return _home() / ".claude" / "settings.json"


def _marketplace_dir() -> Path:
    return _home() / ".claude" / "plugins" / "marketplaces" / MARKETPLACE_NAME


def _known_marketplaces_path() -> Path:
    return _home() / ".claude" / "plugins" / "known_marketplaces.json"


def install_plugin() -> Path:
    """Install tokkit as a Claude Code plugin with skill + MCP server.

    Returns the plugin install directory.
    """
    from tokkit_skill import SKILL_DIR

    version = _version()
    dest = _plugin_install_dir(version)

    # Create plugin structure
    (dest / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    skills_dir = dest / "skills" / "tokkit-code-intelligence"
    (skills_dir / "references").mkdir(parents=True, exist_ok=True)

    # plugin.json
    (dest / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "tokkit",
        "version": version,
        "description": "Token-optimized code intelligence for LLM agents",
    }, indent=2) + "\n")

    # Skill files
    shutil.copy2(SKILL_DIR / "SKILL.md", skills_dir / "SKILL.md")
    shutil.copy2(
        SKILL_DIR / "references" / "tool-guide.md",
        skills_dir / "references" / "tool-guide.md",
    )

    # .mcp.json — plugin-scoped MCP server (flat format per plugin spec)
    (dest / ".mcp.json").write_text(json.dumps({
        "tokkit": {
            "command": "uvx",
            "args": ["tokkit-ai", "serve"],
        }
    }, indent=2) + "\n")

    # Hook script — PreToolUse hook for Bash command compression
    hooks_dir = dest / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    import tokkit_hook.hook as hook_module
    hook_path = Path(hook_module.__file__)
    shutil.copy2(hook_path, hooks_dir / "hook.py")

    # Also copy dependencies the hook script needs
    import tokkit_hook.chain as chain_module
    import tokkit_hook.match as match_module
    shutil.copy2(Path(chain_module.__file__), hooks_dir / "chain.py")
    shutil.copy2(Path(match_module.__file__), hooks_dir / "match.py")

    # Update plugin.json with hooks (nested format required by plugin schema)
    plugin_json = json.loads((dest / ".claude-plugin" / "plugin.json").read_text())
    plugin_json["hooks"] = {
        "PreToolUse": [{
            "matcher": "Bash",
            "hooks": [{
                "type": "command",
                "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/hook.py",
            }],
        }]
    }
    (dest / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2) + "\n"
    )

    # Register a local marketplace so Claude Code's plugin loader can resolve
    # the plugin. Without this, the plugin is "orphaned": present in
    # installed_plugins.json and enabledPlugins but never loaded, because the
    # loader resolves enabled plugins through their marketplace.
    _register_marketplace(dest)

    # Register + enable
    _register_plugin(version, dest)
    _enable_plugin()

    # Drop stale failed-load cache from prior invalid manifests
    unknown = dest.parent / "unknown"
    if unknown.exists():
        shutil.rmtree(unknown)

    # Migrate away from old approach
    _remove_legacy_skill_ref()
    _remove_legacy_skill_dir()
    _remove_mcp_from_user_config()

    return dest


def uninstall_plugin() -> None:
    """Remove tokkit plugin, registration, and enablement."""
    # Remove all cached versions
    cache_dir = _home() / ".claude" / "plugins" / "cache" / "tokkit"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    # Remove the local marketplace + its registration
    _unregister_marketplace()

    # Unregister
    path = _installed_plugins_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        data.get("plugins", {}).pop(PLUGIN_KEY, None)
        path.write_text(json.dumps(data, indent=2) + "\n")

    # Disable
    path = _settings_path()
    if path.exists():
        try:
            settings = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            settings = {}
        settings.get("enabledPlugins", {}).pop(PLUGIN_KEY, None)
        path.write_text(json.dumps(settings, indent=2) + "\n")

    # Also clean up legacy artifacts
    _remove_legacy_skill_ref()
    _remove_legacy_skill_dir()
    _remove_mcp_from_user_config()


# --- registration helpers ---

def _register_plugin(version: str, install_path: Path) -> None:
    path = _installed_plugins_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {"version": 2, "plugins": {}}
    else:
        data = {"version": 2, "plugins": {}}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    existing = data.get("plugins", {}).get(PLUGIN_KEY, [{}])
    installed_at = existing[0].get("installedAt", now) if existing else now

    data.setdefault("plugins", {})[PLUGIN_KEY] = [{
        "scope": "user",
        "installPath": str(install_path),
        "version": version,
        "installedAt": installed_at,
        "lastUpdated": now,
    }]

    path.write_text(json.dumps(data, indent=2) + "\n")


def _enable_plugin() -> None:
    path = _settings_path()
    if path.exists():
        try:
            settings = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            settings = {}
    else:
        settings = {}

    settings.setdefault("enabledPlugins", {})[PLUGIN_KEY] = True
    path.write_text(json.dumps(settings, indent=2) + "\n")


def _register_marketplace(plugin_dir: Path) -> None:
    """Create a local marketplace that lists the tokkit plugin and register it.

    Claude Code resolves enabled plugins through a marketplace. The marketplace
    root holds only marketplace.json; the plugin lives under plugins/<name>/,
    matching the layout used by official and third-party marketplaces.
    """
    mp = _marketplace_dir()
    plugin_source = f"./plugins/{PLUGIN_NAME}"

    if mp.exists():
        shutil.rmtree(mp)

    plugin_dest = mp / "plugins" / PLUGIN_NAME
    shutil.copytree(plugin_dir, plugin_dest)

    (mp / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (mp / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": MARKETPLACE_NAME,
        "owner": {"name": "tokkit"},
        "plugins": [{
            "name": PLUGIN_NAME,
            "source": plugin_source,
            "description": "Token-optimized code intelligence for LLM agents",
        }],
    }, indent=2) + "\n")

    # Record the marketplace in known_marketplaces.json.
    path = _known_marketplaces_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    data[MARKETPLACE_NAME] = {
        "source": {"source": "directory", "path": str(mp)},
        "installLocation": str(mp),
        "lastUpdated": now,
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def _unregister_marketplace() -> None:
    """Remove the local marketplace directory and its known_marketplaces entry."""
    mp = _marketplace_dir()
    if mp.exists():
        shutil.rmtree(mp)

    path = _known_marketplaces_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        if data.pop(MARKETPLACE_NAME, None) is not None:
            path.write_text(json.dumps(data, indent=2) + "\n")


# --- legacy migration helpers ---

def _remove_legacy_skill_ref() -> None:
    """Remove old @~/.local/share/tokkit/SKILL.md from CLAUDE.md."""
    claude_md = _home() / ".claude" / "CLAUDE.md"
    if not claude_md.exists():
        return
    content = claude_md.read_text()
    if LEGACY_SKILL_REF not in content:
        return
    lines = [l for l in content.splitlines(keepends=True) if LEGACY_SKILL_REF not in l]
    # Strip trailing blank lines left behind
    text = "".join(lines).rstrip("\n")
    claude_md.write_text(text + "\n" if text else "")


def _remove_legacy_skill_dir() -> None:
    """Remove old ~/.local/share/tokkit/ skill files."""
    legacy = _home() / ".local" / "share" / "tokkit"
    if legacy.exists():
        shutil.rmtree(legacy)


def _remove_mcp_from_user_config() -> None:
    """Remove tokkit entry from ~/.claude/mcp.json (plugin provides it now)."""
    mcp_path = _home() / ".claude" / "mcp.json"
    if not mcp_path.exists():
        return
    try:
        config = json.loads(mcp_path.read_text())
    except (json.JSONDecodeError, OSError):
        return
    servers = config.get("mcpServers", {})
    if "tokkit" not in servers:
        return
    del servers["tokkit"]
    mcp_path.write_text(json.dumps(config, indent=2) + "\n")
