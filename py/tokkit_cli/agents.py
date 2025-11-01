"""Agent detection and MCP configuration."""

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class Agent:
    name: str
    mcp_config_path: Path
    supports_skill: bool


def _home() -> Path:
    import os
    return Path(os.environ.get("HOME", Path.home()))


def detect_agents() -> list[Agent]:
    """Detect which coding agents are installed."""
    home = _home()
    agents = []

    if (home / ".claude").is_dir():
        agents.append(Agent(
            name="claude",
            mcp_config_path=home / ".claude" / "mcp.json",
            supports_skill=True,
        ))

    if (home / ".cursor").is_dir():
        agents.append(Agent(
            name="cursor",
            mcp_config_path=home / ".cursor" / "mcp.json",
            supports_skill=False,
        ))

    if (home / ".codeium").is_dir():
        agents.append(Agent(
            name="windsurf",
            mcp_config_path=home / ".codeium" / "windsurf" / "mcp_config.json",
            supports_skill=False,
        ))

    if (home / ".codex").is_dir():
        agents.append(Agent(
            name="codex",
            mcp_config_path=home / ".codex" / "mcp.json",
            supports_skill=False,
        ))

    return agents


MCP_ENTRY = {
    "command": "uvx",
    "args": ["tokkit-ai", "serve"],
}


def write_mcp_config(agent: Agent) -> None:
    """Write or merge tokkit entry into an agent's MCP config."""
    config = {}
    if agent.mcp_config_path.exists():
        try:
            config = json.loads(agent.mcp_config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}

    servers = config.setdefault("mcpServers", {})
    servers["tokkit"] = MCP_ENTRY

    agent.mcp_config_path.parent.mkdir(parents=True, exist_ok=True)
    agent.mcp_config_path.write_text(json.dumps(config, indent=2) + "\n")


def remove_mcp_config(agent: Agent) -> bool:
    """Remove tokkit entry from an agent's MCP config. Returns True if removed."""
    if not agent.mcp_config_path.exists():
        return False

    try:
        config = json.loads(agent.mcp_config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    servers = config.get("mcpServers", {})
    if "tokkit" not in servers:
        return False

    del servers["tokkit"]
    agent.mcp_config_path.write_text(json.dumps(config, indent=2) + "\n")
# rev-24
    return True
