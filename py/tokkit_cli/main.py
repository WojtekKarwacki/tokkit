"""CLI entry point for tokkit."""

import sys

from tokkit_cli.agents import detect_agents, write_mcp_config, remove_mcp_config


def _run_setup(uninstall: bool = False, dry_run: bool = False, only: str | None = None) -> None:
    """Detect agents and configure/unconfigure tokkit."""
    agents = detect_agents()

    if only:
        agents = [a for a in agents if a.name == only]

    if not agents:
        print("No coding agents detected (Claude Code, Cursor, Windsurf, Codex).")
        print("Install one and re-run `tokkit setup`.")
        return

    if uninstall:
        for agent in agents:
            if agent.supports_skill:
                from tokkit_cli.setup import uninstall_plugin
                uninstall_plugin()
                print(f"  {agent.name}: plugin removed")
            else:
                removed = remove_mcp_config(agent)
                status = "removed" if removed else "not configured"
                print(f"  {agent.name}: {status}")
        print("\nTokkit uninstalled from all agents.")
        return

    for agent in agents:
        if agent.supports_skill:
            # Claude Code: install as plugin (includes MCP + skill)
            if dry_run:
                print(f"  {agent.name}: would install plugin")
            else:
                from tokkit_cli.setup import install_plugin
                dest = install_plugin()
                print(f"  {agent.name}: plugin installed ({dest})")
        else:
            # Other agents: MCP config only
            if dry_run:
                print(f"  {agent.name}: would write {agent.mcp_config_path}")
            else:
                write_mcp_config(agent)
                print(f"  {agent.name}: configured ({agent.mcp_config_path})")

    print("\nDone. Restart your agent to pick up the changes.")


def _run_serve() -> None:
    """Run the MCP server on stdio."""
    import tokkit_server.main as _srv_main
    _srv_main.serve_stdio(sys.stdin, sys.stdout)


def _run_init() -> None:
    """Initialize tokkit in the current project."""
    import json
    from pathlib import Path

    project_root = Path.cwd()

    # Write .mcp.json
    mcp_path = project_root / ".mcp.json"
    config = {}
    if mcp_path.exists():
        try:
            config = json.loads(mcp_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}

    servers = config.setdefault("mcpServers", {})
    servers["tokkit"] = {"command": "uvx", "args": ["tokkit-ai", "serve"]}
    mcp_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"  wrote {mcp_path}")

    print("  note: run `tokkit setup` to install the Claude Code plugin (skill + MCP)")


def main() -> None:
    argv = sys.argv[1:]

    if not argv or argv[0] == "setup":
        flags = argv[1:] if argv else []
        uninstall = "--uninstall" in flags
        dry_run = "--dry-run" in flags
        only = None
        for flag in ("--claude", "--cursor", "--windsurf", "--codex"):
            if flag in flags:
                only = flag.lstrip("-")
                break
        _run_setup(uninstall=uninstall, dry_run=dry_run, only=only)
        return

    if argv[0] == "serve":
        _run_serve()
        return

    if argv[0] == "init":
        _run_init()
        return

    if argv[0] == "benchmark":
        from tokkit_benchmark.main import main as benchmark_main
        benchmark_main(repo=argv[1] if len(argv) > 1 else None)
        return

    if argv[0] == "--version":
        from tokkit_server import __version__
        print(f"tokkit {__version__}")
        return

    if argv[0] == "--help":
        print("Usage:")
        print("  tokkit              Auto-detect agents and configure tokkit")
        print("  tokkit setup        Same as above")
        print("  tokkit serve        Run MCP server on stdio")
        print("  tokkit init         Configure tokkit for current project")
        print("  tokkit benchmark [owner/repo]  Run showcase benchmark (default: fastapi/fastapi)")
        print("  tokkit --version    Print version")
        print("  tokkit --help       Print this message")
        print()
        print("Flags for setup:")
        print("  --uninstall         Remove tokkit from all agent configs")
        print("  --dry-run           Show what would be configured")
        print("  --claude/--cursor/--windsurf/--codex  Configure specific agent only")
        return

    print(f"Unknown command: {argv[0]}", file=sys.stderr)
    sys.exit(1)
