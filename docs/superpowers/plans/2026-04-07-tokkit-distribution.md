# Tokkit Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure tokkit into a maturin-built PyPI package with a `tokkit` CLI that auto-configures MCP server + skill for Claude Code, Cursor, Windsurf, and Codex.

**Architecture:** Single PyPI package built with maturin. Rust extension (PyO3) compiled into platform wheels. Python CLI handles agent detection and configuration. Skill docs bundled as package data and copied to `~/.local/share/tokkit/` during setup.

**Tech Stack:** maturin (build), PyO3 (Rust-Python bridge), GitHub Actions + maturin-action (CI/CD)

**Spec:** `docs/superpowers/specs/2026-04-07-tokkit-distribution-design.md`

---

## File Structure

```
tokkit/
├── Cargo.toml                         # workspace root (moved from core/code/)
├── Cargo.lock                         # lock file (moved from core/code/)
├── pyproject.toml                     # maturin build config (rewritten)
├── .gitignore                         # updated paths
├── CLAUDE.md                          # updated paths
├── crates/                            # Rust source (moved from core/code/crates/)
│   ├── tokkit-core/
│   │   ├── Cargo.toml
│   │   ├── src/                       # unchanged
│   │   └── tests/                     # unchanged (integration tests + fixtures)
│   └── tokkit-py/
│       ├── Cargo.toml                 # updated: workspace dep path
│       └── src/lib.rs                 # unchanged
├── py/                                # all Python source
│   ├── tokkit_cli/                    # NEW
│   │   ├── __init__.py
│   │   ├── main.py                    # CLI entry: setup, serve, init
│   │   └── agents.py                  # agent detection + config writing
│   ├── tokkit_server/                 # moved from server/tokkit_server/
│   │   ├── __init__.py                # unchanged
│   │   ├── main.py                    # serve_stdio (setup/CLI logic removed)
│   │   ├── protocol.py               # enriched tool descriptions
│   │   ├── tools.py                   # unchanged
│   │   ├── token_stats.py            # unchanged
│   │   └── watcher.py                # unchanged
│   ├── tokkit_scraper/                # moved from core/web/tokkit_scraper/
│   │   ├── __init__.py               # unchanged
│   │   ├── pipeline.py               # unchanged
│   │   └── markdown.py               # unchanged
│   ├── tokkit_json/                   # moved from core/json/tokkit_json/
│   │   ├── __init__.py               # unchanged
│   │   ├── detect.py                 # unchanged
│   │   ├── csv_conv.py               # unchanged
│   │   └── yaml_conv.py              # unchanged
│   └── tokkit_skill/                  # NEW: bundled skill docs
│       ├── __init__.py
│       ├── SKILL.md                   # copied from skill/SKILL.md
│       └── references/
│           └── tool-guide.md          # copied from skill/references/tool-guide.md
├── tests/                             # consolidated test tree
│   ├── conftest.py                    # root conftest (empty or shared fixtures)
│   ├── server/                        # moved from server/tests/
│   │   ├── __init__.py
│   │   ├── test_protocol.py
│   │   ├── test_tools.py
│   │   ├── test_token_stats.py
│   │   ├── test_scraper_integration.py
│   │   └── test_json_integration.py
│   ├── scraper/                       # moved from core/web/tests/
│   │   ├── __init__.py
│   │   └── test_clean_html.py
│   ├── json/                          # moved from core/json/tests/
│   │   ├── __init__.py
│   │   └── test_compact_json.py
│   ├── cli/                           # NEW: tests for tokkit_cli
│   │   ├── __init__.py
│   │   ├── test_agents.py
│   │   ├── test_setup.py
│   │   └── test_main.py
│   └── e2e/                           # moved from e2e/
│       ├── __init__.py
│       ├── conftest.py                # updated Python path
│       ├── test_cli_smoke.py
│       ├── test_mcp_index.py
│       ├── test_mcp_query.py
│       ├── test_mcp_json.py
│       ├── test_mcp_scraper.py
│       ├── fixtures/
│       │   └── sample_project/
│       └── benchmark/                 # unchanged internally
├── skill/                             # kept for development reference
│   ├── SKILL.md
│   └── references/tool-guide.md
├── docs/                              # unchanged
└── .github/
    └── workflows/
        └── release.yml                # NEW: build + publish
```

---

### Task 1: Move Rust crates to root level

**Files:**
- Move: `core/code/Cargo.toml` → root `Cargo.toml`
- Move: `core/code/Cargo.lock` → root `Cargo.lock`
- Move: `core/code/crates/` → `crates/`

- [ ] **Step 1: Move the Rust workspace to root**

```bash
# Move workspace files to root
mv core/code/Cargo.lock ./Cargo.lock
mv core/code/crates ./crates

# Replace root Cargo.toml with workspace config
cat > Cargo.toml << 'TOML'
[workspace]
resolver = "2"
members = [
    "crates/tokkit-core",
    "crates/tokkit-py",
]

[workspace.package]
version = "0.1.0"
edition = "2024"
license = "MIT"

[workspace.dependencies]
tokkit-core = { path = "crates/tokkit-core" }
TOML
```

- [ ] **Step 2: Remove the old core/code directory**

```bash
rm -rf core/code
```

- [ ] **Step 3: Verify Rust build**

Run: `cargo test --workspace`
Expected: All 70 tests pass

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move Rust workspace to project root"
```

---

### Task 2: Move Python packages to py/ directory

**Files:**
- Move: `server/tokkit_server/` → `py/tokkit_server/`
- Move: `core/web/tokkit_scraper/` → `py/tokkit_scraper/`
- Move: `core/json/tokkit_json/` → `py/tokkit_json/`

- [ ] **Step 1: Create py/ directory and move Python packages**

```bash
mkdir -p py
mv server/tokkit_server py/tokkit_server
mv core/web/tokkit_scraper py/tokkit_scraper
mv core/json/tokkit_json py/tokkit_json
```

- [ ] **Step 2: Remove old sub-package configs and egg-info**

```bash
rm -rf server/tokkit_server.egg-info
rm -f server/pyproject.toml
rm -rf core/web/tokkit_scraper.egg-info
rm -f core/web/pyproject.toml
rm -rf core/json/tokkit_json.egg-info
rm -f core/json/pyproject.toml
rm -f install.sh
```

Note: do NOT delete `server/`, `core/web/`, or `core/json/` yet — their `tests/` subdirectories are moved in Task 3.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: move Python packages to py/ directory"
```

---

### Task 3: Move tests to consolidated tests/ directory

**Files:**
- Move: `server/tests/` → `tests/server/`
- Move: `core/web/tests/` → `tests/scraper/`
- Move: `core/json/tests/` → `tests/json/`
- Move: `e2e/` → `tests/e2e/`

- [ ] **Step 1: Create tests/ directory and move test files**

```bash
mkdir -p tests/server tests/scraper tests/json

# Server tests
cp -r server/tests/* tests/server/

# Scraper tests
cp -r core/web/tests/* tests/scraper/

# JSON tests
cp -r core/json/tests/* tests/json/

# E2E tests (entire directory)
mv e2e tests/e2e

# Ensure __init__.py exists in each test dir
touch tests/__init__.py tests/server/__init__.py tests/scraper/__init__.py tests/json/__init__.py

# Create root conftest
touch tests/conftest.py

# Now safe to clean up old directories
rm -rf server core
```

- [ ] **Step 2: Update e2e conftest.py — remove hardcoded Python path**

In `tests/e2e/conftest.py`, replace the hardcoded Python path with `sys.executable`:

```python
import json
import os
import subprocess
import sys
import pytest


@pytest.fixture
def sample_project_path():
    return os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


@pytest.fixture
def mcp_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def send(self, method, params=None):
            self._id += 1
            request = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            response_line = self.proc.stdout.readline()
            if not response_line:
                raise RuntimeError("Server closed connection")
            return json.loads(response_line)

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    client = McpClient(proc)
    yield client
    try:
        client.close()
    except Exception:
        proc.kill()
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: consolidate tests into tests/ directory"
```

---

### Task 4: Bundle skill docs as package data

**Files:**
- Create: `py/tokkit_skill/__init__.py`
- Copy: `skill/SKILL.md` → `py/tokkit_skill/SKILL.md`
- Copy: `skill/references/tool-guide.md` → `py/tokkit_skill/references/tool-guide.md`

- [ ] **Step 1: Create tokkit_skill package with bundled docs**

```bash
mkdir -p py/tokkit_skill/references
cp skill/SKILL.md py/tokkit_skill/SKILL.md
cp skill/references/tool-guide.md py/tokkit_skill/references/tool-guide.md
```

- [ ] **Step 2: Create `__init__.py` with helper to locate skill files**

Write `py/tokkit_skill/__init__.py`:

```python
"""Bundled skill documentation for tokkit."""

from pathlib import Path

SKILL_DIR = Path(__file__).parent


def skill_path() -> Path:
    """Return the path to the bundled SKILL.md."""
    return SKILL_DIR / "SKILL.md"


def tool_guide_path() -> Path:
    """Return the path to the bundled tool-guide.md."""
    return SKILL_DIR / "references" / "tool-guide.md"
```

- [ ] **Step 3: Commit**

```bash
git add py/tokkit_skill/
git commit -m "feat: bundle skill docs as package data"
```

---

### Task 5: Rewrite build configuration for maturin

**Files:**
- Rewrite: `pyproject.toml`
- Modify: `crates/tokkit-py/Cargo.toml` (add `manifest-path` note)
- Update: `.gitignore`

- [ ] **Step 1: Rewrite root pyproject.toml for maturin**

```toml
[build-system]
requires = ["maturin>=1.7"]
build-backend = "maturin"

[project]
name = "tokkit"
version = "0.1.0"
description = "Token-optimized code intelligence for LLM agents"
requires-python = ">=3.11"
license = {text = "MIT"}
keywords = ["mcp", "code-intelligence", "llm", "tokens"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Rust",
    "Programming Language :: Python :: 3",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "selectolax>=0.3.21",
    "PyYAML>=6.0",
]

[project.scripts]
tokkit = "tokkit_cli.main:main"

[tool.maturin]
python-source = "py"
module-name = "tokkit_py"
manifest-path = "crates/tokkit-py/Cargo.toml"
features = ["pyo3/extension-module"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

- [ ] **Step 2: Update .gitignore**

```gitignore
# Rust
target/
*.so
*.pyd

# Python
__pycache__/
*.pyc
*.egg-info/
.pytest_cache/
dist/
build/

# IDE
.vscode/
.idea/

# OS
.DS_Store

# Benchmark cache
tests/e2e/benchmark/.cache/
```

- [ ] **Step 3: Verify maturin can find the crate**

Run: `maturin develop`
Expected: Builds tokkit_py extension and installs all Python packages into the current venv.

If maturin is not installed: `pip install maturin` first.

- [ ] **Step 4: Verify tests pass after restructure**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: All non-benchmark tests pass (33 tests).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "build: configure maturin for single-package distribution"
```

---

### Task 6: Write agent detection module (TDD)

**Files:**
- Create: `py/tokkit_cli/__init__.py`
- Create: `py/tokkit_cli/agents.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_agents.py`

- [ ] **Step 1: Write failing tests for agent detection**

Write `tests/cli/__init__.py` (empty file).

Write `tests/cli/test_agents.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_agents.py -v`
Expected: FAIL with ImportError (tokkit_cli.agents doesn't exist yet)

- [ ] **Step 3: Implement agent detection**

Write `py/tokkit_cli/__init__.py` (empty file).

Write `py/tokkit_cli/agents.py`:

```python
"""Agent detection and MCP configuration."""

from dataclasses import dataclass
from pathlib import Path
import json
import shutil


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

    if shutil.which("codex"):
        agents.append(Agent(
            name="codex",
            mcp_config_path=home / ".codex" / "mcp.json",
            supports_skill=False,
        ))

    return agents


MCP_ENTRY = {
    "command": "uvx",
    "args": ["tokkit", "serve"],
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
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_agents.py -v`
Expected: All 7 tests pass

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_cli/ tests/cli/
git commit -m "feat: agent detection for Claude Code, Cursor, Windsurf, Codex"
```

---

### Task 7: Write MCP config read/write tests and skill install (TDD)

**Files:**
- Modify: `tests/cli/test_agents.py`
- Modify: `py/tokkit_cli/agents.py`

- [ ] **Step 1: Write failing tests for MCP config writing**

Append to `tests/cli/test_agents.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/cli/test_agents.py -v`
Expected: All 11 tests pass (these functions are already implemented in the previous task)

- [ ] **Step 3: Commit**

```bash
git add tests/cli/test_agents.py
git commit -m "test: MCP config read/write and removal"
```

---

### Task 8: Write skill installation for Claude Code (TDD)

**Files:**
- Create: `tests/cli/test_setup.py`
- Create: `py/tokkit_cli/setup.py`

- [ ] **Step 1: Write failing tests for skill installation**

Write `tests/cli/test_setup.py`:

```python
"""Tests for the setup command logic."""

import os
from pathlib import Path
from unittest.mock import patch

from tokkit_cli.setup import install_skill, uninstall_skill, SKILL_INSTALL_DIR_NAME


def test_install_skill_copies_files(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# My config\n")

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_skill()

    skill_dir = home / ".local" / "share" / SKILL_INSTALL_DIR_NAME
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "references" / "tool-guide.md").exists()


def test_install_skill_adds_claude_md_reference(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# My config\n")

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_skill()

    content = (claude_dir / "CLAUDE.md").read_text()
    assert "@~/.local/share/tokkit/SKILL.md" in content


def test_install_skill_idempotent(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# My config\n")

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_skill()
        install_skill()

    content = (claude_dir / "CLAUDE.md").read_text()
    assert content.count("@~/.local/share/tokkit/SKILL.md") == 1


def test_install_skill_creates_claude_md_if_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()

    with patch.dict(os.environ, {"HOME": str(home)}):
        install_skill()

    assert (claude_dir / "CLAUDE.md").exists()
    content = (claude_dir / "CLAUDE.md").read_text()
    assert "@~/.local/share/tokkit/SKILL.md" in content


def test_uninstall_skill(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("# Config\n@~/.local/share/tokkit/SKILL.md\n")

    skill_dir = home / ".local" / "share" / SKILL_INSTALL_DIR_NAME
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    with patch.dict(os.environ, {"HOME": str(home)}):
        uninstall_skill()

    assert not skill_dir.exists()
    content = (claude_dir / "CLAUDE.md").read_text()
    assert "@~/.local/share/tokkit/SKILL.md" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_setup.py -v`
Expected: FAIL with ImportError (tokkit_cli.setup doesn't exist yet)

- [ ] **Step 3: Implement skill installation**

Write `py/tokkit_cli/setup.py`:

```python
"""Skill installation and removal for Claude Code."""

import shutil
from pathlib import Path
import os


SKILL_INSTALL_DIR_NAME = "tokkit"
SKILL_REF = "@~/.local/share/tokkit/SKILL.md"


def _home() -> Path:
    return Path(os.environ.get("HOME", Path.home()))


def _skill_install_dir() -> Path:
    return _home() / ".local" / "share" / SKILL_INSTALL_DIR_NAME


def install_skill() -> Path:
    """Copy bundled skill docs to ~/.local/share/tokkit/ and add CLAUDE.md reference.

    Returns the install directory path.
    """
    from tokkit_skill import SKILL_DIR

    dest = _skill_install_dir()
    dest.mkdir(parents=True, exist_ok=True)

    # Copy skill files
    shutil.copy2(SKILL_DIR / "SKILL.md", dest / "SKILL.md")
    refs_dest = dest / "references"
    refs_dest.mkdir(exist_ok=True)
    shutil.copy2(SKILL_DIR / "references" / "tool-guide.md", refs_dest / "tool-guide.md")

    # Add reference to CLAUDE.md
    claude_md = _home() / ".claude" / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
    else:
        content = ""

    if SKILL_REF not in content:
        line = f"\n{SKILL_REF}\n" if content and not content.endswith("\n") else f"{SKILL_REF}\n"
        claude_md.write_text(content + line)

    return dest


def uninstall_skill() -> None:
    """Remove skill files and CLAUDE.md reference."""
    dest = _skill_install_dir()
    if dest.exists():
        shutil.rmtree(dest)

    claude_md = _home() / ".claude" / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        lines = [l for l in content.splitlines(keepends=True) if SKILL_REF not in l]
        claude_md.write_text("".join(lines))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_setup.py -v`
Expected: All 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_cli/setup.py tests/cli/test_setup.py
git commit -m "feat: skill installation and removal for Claude Code"
```

---

### Task 9: Write CLI entry point (TDD)

**Files:**
- Create: `tests/cli/test_main.py`
- Create: `py/tokkit_cli/main.py`

- [ ] **Step 1: Write failing tests for CLI commands**

Write `tests/cli/test_main.py`:

```python
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
    cursor_dir = home / ".cursor"
    cursor_dir.mkdir()

    with patch.dict(os.environ, {"HOME": str(home)}), \
         patch("sys.argv", ["tokkit", "setup"]):
        main()

    # Claude MCP config written
    mcp = json.loads((claude_dir / "mcp.json").read_text())
    assert "tokkit" in mcp["mcpServers"]

    # Cursor MCP config written
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
    mcp_path = claude_dir / "mcp.json"
    mcp_path.write_text(json.dumps({"mcpServers": {"tokkit": {"command": "uvx"}}}))

    with patch.dict(os.environ, {"HOME": str(home)}), \
         patch("sys.argv", ["tokkit", "setup", "--uninstall"]):
        main()

    config = json.loads(mcp_path.read_text())
    assert "tokkit" not in config["mcpServers"]


def test_default_action_is_setup(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    claude_dir = home / ".claude"
    claude_dir.mkdir()

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_main.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement CLI entry point**

Write `py/tokkit_cli/main.py`:

```python
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
            removed = remove_mcp_config(agent)
            status = "removed" if removed else "not configured"
            print(f"  {agent.name}: {status}")
            if agent.supports_skill:
                from tokkit_cli.setup import uninstall_skill
                uninstall_skill()
                print(f"  {agent.name}: skill removed")
        print("\nTokkit uninstalled from all agents.")
        return

    for agent in agents:
        if dry_run:
            print(f"  {agent.name}: would write {agent.mcp_config_path}")
            if agent.supports_skill:
                print(f"  {agent.name}: would install skill to ~/.local/share/tokkit/")
        else:
            write_mcp_config(agent)
            print(f"  {agent.name}: configured ({agent.mcp_config_path})")
            if agent.supports_skill:
                from tokkit_cli.setup import install_skill
                dest = install_skill()
                print(f"  {agent.name}: skill installed ({dest})")

    print("\nDone. Restart your agent to pick up the changes.")


def _run_serve() -> None:
    """Run the MCP server on stdio."""
    from tokkit_server.main import serve_stdio
    serve_stdio(sys.stdin, sys.stdout)


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
    servers["tokkit"] = {"command": "uvx", "args": ["tokkit", "serve"]}
    mcp_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"  wrote {mcp_path}")

    # Add skill ref to project CLAUDE.md
    claude_md = project_root / "CLAUDE.md"
    skill_ref = "@~/.local/share/tokkit/SKILL.md"
    if claude_md.exists():
        content = claude_md.read_text()
    else:
        content = ""

    if skill_ref not in content:
        line = f"\n{skill_ref}\n" if content and not content.endswith("\n") else f"{skill_ref}\n"
        claude_md.write_text(content + line)
        print(f"  added skill reference to {claude_md}")
    else:
        print(f"  skill reference already in {claude_md}")


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_main.py -v`
Expected: All 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_cli/main.py tests/cli/test_main.py
git commit -m "feat: tokkit CLI with setup, serve, and init commands"
```

---

### Task 10: Simplify tokkit_server main.py

Now that CLI routing is handled by `tokkit_cli.main`, the server's `main.py` only needs `serve_stdio` and `run_cli` (for backwards compat). Remove the CLI arg parsing that duplicates `tokkit_cli`.

**Files:**
- Modify: `py/tokkit_server/main.py`

- [ ] **Step 1: Simplify server main.py**

Replace `py/tokkit_server/main.py` with:

```python
"""MCP server entry point — JSON-RPC over stdio."""

import json
import signal
import sys
from typing import IO

from tokkit_server import __version__
from tokkit_server.protocol import (
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    build_error,
    build_initialize_response,
    build_tools_list_response,
    parse_request,
)
from tokkit_server.tools import handle_tool_call
from tokkit_server.watcher import Watcher


def dispatch(method: str, params: dict, request_id, watcher: Watcher) -> str | None:
    """Dispatch a JSON-RPC method and return a response string or None."""
    if method == "initialize":
        return build_initialize_response(request_id)

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return build_tools_list_response(request_id)

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = handle_tool_call(tool_name, tool_args)
        if tool_name == "index_repository" and not result.get("isError"):
            from tokkit_server.tools import _session_project_path  # noqa: PLC0415
            if _session_project_path:
                watcher.set_project(_session_project_path)
        from tokkit_server.protocol import build_response  # noqa: PLC0415
        return build_response(request_id, result)

    return build_error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")


def serve_stdio(stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    """Run the JSON-RPC event loop over stdio."""
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    watcher = Watcher()
    watcher.start()

    shutdown = False

    def _handle_signal(signum, frame):  # noqa: ARG001
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    content_length: int | None = None

    try:
        while not shutdown:
            try:
                line = stdin.readline()
            except (KeyboardInterrupt, EOFError):
                break

            if not line:
                break

            stripped = line.strip()

            if stripped.startswith("Content-Length:"):
                try:
                    content_length = int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    content_length = None
                continue

            if stripped == "" and content_length is not None:
                try:
                    body = stdin.read(content_length)
                except (EOFError, OSError):
                    break
                content_length = None
                stripped = body.strip()
            elif stripped == "":
                continue

            try:
                req = parse_request(stripped)
            except ValueError as exc:
                response = build_error(None, PARSE_ERROR, str(exc))
                stdout.write(response + "\n")
                stdout.flush()
                continue

            try:
                response = dispatch(req["method"] or "", req["params"] or {}, req["id"], watcher)
            except Exception as exc:  # noqa: BLE001
                response = build_error(req.get("id"), INTERNAL_ERROR, str(exc))

            if response is not None:
                stdout.write(response + "\n")
                stdout.flush()
    finally:
        watcher.stop()

    return 0


def main() -> None:
    """Entry point for `python -m tokkit_server.main` (backwards compat)."""
    argv = sys.argv[1:]

    if not argv:
        sys.exit(serve_stdio())

    if argv[0] == "--version":
        print(f"tokkit {__version__}")
        sys.exit(0)

    if argv[0] == "cli":
        if len(argv) < 3:
            print("Usage: tokkit cli <tool_name> <json_args>", file=sys.stderr)
            sys.exit(1)
        tool_name = argv[1]
        try:
            tool_args = json.loads(argv[2])
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON args: {exc}", file=sys.stderr)
            sys.exit(1)
        result = handle_tool_call(tool_name, tool_args)
        for block in result.get("content", []):
            if block.get("type") == "text":
                print(block["text"])
        sys.exit(0 if not result.get("isError") else 1)

    print(f"Unknown argument: {argv[0]}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
```

Key change: `serve_stdio` now defaults `stdin`/`stdout` to `sys.stdin`/`sys.stdout` so `tokkit_cli.main._run_serve()` can call it without arguments.

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add py/tokkit_server/main.py
git commit -m "refactor: simplify server main.py, delegate CLI to tokkit_cli"
```

---

### Task 11: Enrich MCP tool descriptions

Make tool descriptions self-documenting so agents without skill support (Cursor, Windsurf) can use tools correctly.

**Files:**
- Modify: `py/tokkit_server/protocol.py`

- [ ] **Step 1: Update TOOL_DEFINITIONS with enriched descriptions**

In `py/tokkit_server/protocol.py`, replace `TOOL_DEFINITIONS` list:

```python
TOOL_DEFINITIONS = [
    {
        "name": "index_repository",
        "description": (
            "Index a repository to build a code intelligence graph. "
            "MUST be called before any other graph tool (search_graph, trace_path, etc.). "
            "Parses Python, JavaScript, and TypeScript files using tree-sitter, "
            "builds a knowledge graph of functions, classes, calls, and imports, "
            "and stores it for fast querying. Indexing takes 1-5 seconds for typical repos."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the repository root."},
                "force": {"type": "boolean", "description": "Force re-indexing even if already indexed."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_graph",
        "description": (
            "Search the code graph for symbols (functions, classes, methods). "
            "Returns qualified names in the format project::file_path::symbol_name. "
            "Use these qualified names with get_code_snippet and trace_path. "
            "Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string (matches symbol names)."},
                "label": {"type": "string", "description": "Filter by node label: Function, Class, Method, Module, Route."},
                "limit": {"type": "integer", "description": "Maximum number of results (default: 20)."},
                "name_pattern": {"type": "string", "description": "Regex pattern to match node names."},
                "max_degree": {"type": "integer", "description": "Filter nodes with total degree <= N. Use 0 for dead code."},
                "exclude_entry_points": {"type": "boolean", "description": "Exclude main, __init__, test functions, route handlers."},
                "relationship": {"type": "string", "description": "Filter to nodes participating in this edge type (CALLS, HANDLES, TESTS, CO_CHANGED, SIMILAR_TO)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "trace_path",
        "description": (
            "Trace the call or dependency path between two code entities. "
            "Uses BFS across the knowledge graph. Returns each step with edge type and confidence score. "
            "Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_node": {"type": "string", "description": "Starting node qualified name (from search_graph results)."},
                "to_node": {"type": "string", "description": "Ending node qualified name (from search_graph results)."},
            },
            "required": ["from_node", "to_node"],
        },
    },
    {
        "name": "trace_fan",
        "description": (
            "Fan-out/fan-in trace from a starting node. Shows what a function calls (outbound) "
            "or what calls it (inbound). Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_name": {"type": "string", "description": "Starting node qualified name (from search_graph results)."},
                "direction": {"type": "string", "enum": ["inbound", "outbound", "both"], "description": "Edge direction to follow (default: both)."},
                "depth": {"type": "integer", "description": "Maximum traversal depth (default: 3)."},
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "get_code_snippet",
        "description": (
            "Retrieve the source code for a specific function or class. "
            "Returns just the symbol body, not the entire file — much more token-efficient than reading files. "
            "Use search_graph first to find the exact qualified name. "
            "Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Qualified name (project::file::symbol) from search_graph results."},
                "context_lines": {"type": "integer", "description": "Number of context lines around the snippet (default: 0)."},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_architecture",
        "description": (
            "Get a high-level architectural overview: languages, packages, key files, entry points. "
            "Much more efficient than reading the entire repo. "
            "Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_code",
        "description": "Search for code patterns within the indexed repository. (Currently stubbed — use grep/ripgrep for text search.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern (regex or literal)."},
                "file_glob": {"type": "string", "description": "Optional glob to restrict files searched."},
                "limit": {"type": "integer", "description": "Maximum results to return."},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "detect_changes",
        "description": (
            "Detect files changed since the last index. Useful to know when to re-index. "
            "Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "index_status",
        "description": "Check whether a repository is indexed and get node/edge counts.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_projects",
        "description": "List all indexed projects in the cache.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "delete_project",
        "description": "Delete the index for a project from the cache.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name to delete."},
            },
            "required": ["project"],
        },
    },
    {
        "name": "get_graph_schema",
        "description": (
            "Return available node labels (Function, Class, etc.) and edge types "
            "(CALLS, IMPORTS, TESTS, CO_CHANGED, etc.) in the graph. "
            "Requires index_repository to be called first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_token_stats",
        "description": "Get aggregate token savings statistics — total queries, tokens saved, savings percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "clean_html",
        "description": (
            "Strip noise from HTML and convert to token-optimized markdown or text. "
            "Removes scripts, styles, navigation, ads, and other irrelevant content. "
            "Typically saves 60-90%% of tokens. Does NOT require index_repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "Raw HTML content to clean.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["markdown", "text", "minimal"],
                    "description": "Output mode. 'markdown' (default): semantic markdown. 'text': plain text. 'minimal': light clean, keep HTML.",
                },
            },
            "required": ["html"],
        },
    },
    {
        "name": "compact_json",
        "description": (
            "Convert JSON to a token-optimized format (CSV or YAML). "
            "Auto-detects: CSV for flat/tabular data (saves 50-70%%), YAML for nested data (saves 20-30%%). "
            "Does NOT require index_repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "json": {
                    "type": "string",
                    "description": "Raw JSON string to compact.",
                },
            },
            "required": ["json"],
        },
    },
]
```

- [ ] **Step 2: Run protocol tests**

Run: `pytest tests/server/test_protocol.py -v`
Expected: All tests pass (tests check structure, not description text)

- [ ] **Step 3: Commit**

```bash
git add py/tokkit_server/protocol.py
git commit -m "docs: enrich MCP tool descriptions for agents without skill support"
```

---

### Task 12: Create GitHub Actions release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create workflow directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Write the release workflow**

Write `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'
  pull_request:

permissions:
  contents: read

jobs:
  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo test --workspace

  test-python:
    runs-on: ubuntu-latest
    needs: [build-linux]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/download-artifact@v4
        with:
          name: wheels-linux-x86_64
          path: dist/
      - run: pip install dist/*.whl
      - run: pip install pytest
      - run: pytest tests/ -v --ignore=tests/e2e/benchmark

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: PyO3/maturin-action@v1
        with:
          target: x86_64
          args: --release --out dist
          manylinux: auto
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-linux-x86_64
          path: dist/

  build-macos-x86:
    runs-on: macos-13
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: PyO3/maturin-action@v1
        with:
          target: x86_64
          args: --release --out dist
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-macos-x86_64
          path: dist/

  build-macos-arm:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: PyO3/maturin-action@v1
        with:
          target: aarch64-apple-darwin
          args: --release --out dist
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-macos-arm64
          path: dist/

  sdist:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: PyO3/maturin-action@v1
        with:
          command: sdist
          args: --out dist
      - uses: actions/upload-artifact@v4
        with:
          name: sdist
          path: dist/

  publish:
    if: startsWith(github.ref, 'refs/tags/v')
    needs: [test-rust, test-python, build-linux, build-macos-x86, build-macos-arm, sdist]
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist/
          merge-multiple: true
      - uses: PyO3/maturin-action@v1
        with:
          command: upload
          args: --non-interactive --skip-existing dist/*
```

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "ci: GitHub Actions workflow for building wheels and publishing to PyPI"
```

---

### Task 13: Update CLAUDE.md and .gitignore

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.gitignore`

- [ ] **Step 1: Update CLAUDE.md with new paths and commands**

Replace `CLAUDE.md`:

```markdown
# Tokkit

Token-optimized code intelligence for LLM agents.

## Code Intelligence Skill

@skill/SKILL.md — Use tokkit graph tools for codebase exploration instead of reading raw files. Saves 90%+ tokens on Python/JS/TS repositories.

## Project Structure

- `crates/tokkit-core/` — Rust engine (graph, parsers, storage)
- `crates/tokkit-py/` — PyO3 Python bindings
- `py/tokkit_cli/` — CLI (setup, serve, init)
- `py/tokkit_server/` — MCP server (JSON-RPC over stdio)
- `py/tokkit_scraper/` — HTML cleaning
- `py/tokkit_json/` — JSON compaction
- `py/tokkit_skill/` — Bundled skill docs
- `tests/` — All tests (server, scraper, json, cli, e2e)
- `skill/` — Skill source docs

## Running

```bash
# Development build
maturin develop

# MCP server
tokkit serve
# or: python -m tokkit_server.main

# Setup (configure agents)
tokkit setup

# Tests
cargo test --workspace                    # Rust tests
pytest tests/ -v --ignore=tests/e2e/benchmark  # Python tests
```

## Distribution

Built with maturin. Single PyPI package.

```bash
maturin build --release    # build wheel
maturin develop            # install in dev mode
uvx tokkit                 # install + configure (end user)
```
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new project structure"
```

---

### Task 14: Full verification

- [ ] **Step 1: Verify Rust tests pass**

Run: `cargo test --workspace`
Expected: All ~70 tests pass

- [ ] **Step 2: Build with maturin**

Run: `maturin develop`
Expected: Builds successfully, installs tokkit_py + all Python packages

- [ ] **Step 3: Verify Python tests pass**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: All tests pass (server, scraper, json, cli, e2e)

- [ ] **Step 4: Verify CLI works**

Run: `tokkit --version`
Expected: `tokkit 0.1.0`

Run: `tokkit --help`
Expected: Shows usage with setup, serve, init commands

- [ ] **Step 5: Verify setup in dry-run mode**

Run: `tokkit setup --dry-run`
Expected: Lists detected agents and what would be configured

- [ ] **Step 6: Build a wheel**

Run: `maturin build --release`
Expected: Creates a `.whl` file in `target/wheels/`

- [ ] **Step 7: Commit any final fixes**

If any tests needed fixing, commit the fixes:

```bash
git add -A
git commit -m "fix: final adjustments for distribution build"
```
