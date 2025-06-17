"""Tests for agent detection and configuration."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from tokkit_cli.agents import detect_agents, Agent


def test_detect_claude_code(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    names = [a.name for a in agents]
    assert "claude" in names


def test_detect_cursor(tmp_path):
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    names = [a.name for a in agents]
    assert "cursor" in names


def test_detect_windsurf(tmp_path):
    codeium_dir = tmp_path / ".codeium"
    codeium_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    names = [a.name for a in agents]
    assert "windsurf" in names


def test_detect_nothing(tmp_path):
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    assert agents == []


def test_agent_mcp_config_path_claude(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    claude = [a for a in agents if a.name == "claude"][0]
    assert claude.mcp_config_path == tmp_path / ".claude" / "mcp.json"


def test_agent_mcp_config_path_cursor(tmp_path):
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    cursor = [a for a in agents if a.name == "cursor"][0]
    assert cursor.mcp_config_path == tmp_path / ".cursor" / "mcp.json"


def test_agent_mcp_config_path_windsurf(tmp_path):
    codeium_dir = tmp_path / ".codeium"
    codeium_dir.mkdir()
    with patch.dict(os.environ, {"HOME": str(tmp_path)}):
        agents = detect_agents()
    ws = [a for a in agents if a.name == "windsurf"][0]
    assert ws.mcp_config_path == tmp_path / ".codeium" / "windsurf" / "mcp_config.json"


def test_write_mcp_config_new_file(tmp_path):
    agent = Agent(name="test", mcp_config_path=tmp_path / "mcp.json", supports_skill=False)
    from tokkit_cli.agents import write_mcp_config, MCP_ENTRY
    write_mcp_config(agent)
    config = json.loads(agent.mcp_config_path.read_text())
    assert config["mcpServers"]["tokkit"] == MCP_ENTRY


def test_write_mcp_config_preserves_existing(tmp_path):
    mcp_path = tmp_path / "mcp.json"
    existing = {"mcpServers": {"other-server": {"command": "other"}}}
    mcp_path.write_text(json.dumps(existing))
    agent = Agent(name="test", mcp_config_path=mcp_path, supports_skill=False)
    from tokkit_cli.agents import write_mcp_config
    write_mcp_config(agent)
    config = json.loads(mcp_path.read_text())
    assert "other-server" in config["mcpServers"]
    assert "tokkit" in config["mcpServers"]


def test_remove_mcp_config(tmp_path):
    mcp_path = tmp_path / "mcp.json"
    config = {"mcpServers": {"tokkit": {"command": "uvx"}, "other": {"command": "x"}}}
    mcp_path.write_text(json.dumps(config))
    agent = Agent(name="test", mcp_config_path=mcp_path, supports_skill=False)
    from tokkit_cli.agents import remove_mcp_config
    assert remove_mcp_config(agent) is True
    result = json.loads(mcp_path.read_text())
    assert "tokkit" not in result["mcpServers"]
    assert "other" in result["mcpServers"]


def test_remove_mcp_config_not_present(tmp_path):
    mcp_path = tmp_path / "mcp.json"
    config = {"mcpServers": {"other": {"command": "x"}}}
    mcp_path.write_text(json.dumps(config))
    agent = Agent(name="test", mcp_config_path=mcp_path, supports_skill=False)
    from tokkit_cli.agents import remove_mcp_config
    assert remove_mcp_config(agent) is False
