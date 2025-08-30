# Tokkit Distribution Design

**Date:** 2026-04-07
**Status:** Draft
**Goal:** Distribute tokkit as a single-command install (`uvx tokkit`) that auto-configures MCP server and skill for Claude Code, Cursor, Windsurf, and Codex.

---

## 1. Package Strategy

Single PyPI package named `tokkit`, built with maturin. Consolidates all current sub-packages into one distributable unit.

**Package contents:**

| Module | Source | Purpose |
|--------|--------|---------|
| `tokkit_py` | Rust (PyO3) | Graph engine — tree-sitter parsing, redb storage, call resolution |
| `tokkit_server` | Python | MCP server — JSON-RPC over stdio |
| `tokkit_scraper` | Python | HTML cleaning — selectolax-based |
| `tokkit_json` | Python | JSON compaction — CSV/YAML output |
| `tokkit_cli` | Python (new) | CLI — setup, serve, init commands |
| `tokkit_skill` | Package data | Bundled SKILL.md + tool-guide.md |

**Dependencies:**
- `selectolax>=0.3.21`
- `PyYAML>=6.0`

No other runtime dependencies. The Rust extension is compiled into the wheel.

## 2. User Experience

### Primary install (one command):
```bash
uvx tokkit              # installs from PyPI + runs setup
```

### Fallback:
```bash
pip install tokkit       # install
tokkit setup             # configure agents
```

### Removal:
```bash
tokkit setup --uninstall # remove from all agent configs
pip uninstall tokkit
```

### Project-level (for teams):
```bash
tokkit init              # creates .mcp.json + project CLAUDE.md reference
```

## 3. CLI Design

Entry point: `tokkit = "tokkit_cli.main:main"`

### `tokkit` / `tokkit setup`

Default action. Auto-detects installed coding agents and configures each one.

**Steps:**
1. Detect which agents are installed (check config directories)
2. For each detected agent:
   - Read existing MCP config (if any)
   - Merge tokkit server entry (preserve other servers)
   - Write updated config
3. For Claude Code specifically:
   - Copy `SKILL.md` and `tool-guide.md` to `~/.local/share/tokkit/`
   - Add `@~/.local/share/tokkit/SKILL.md` to `~/.claude/CLAUDE.md` (if not already present)
4. Print summary of what was configured

**Flags:**
- `--claude` / `--cursor` / `--windsurf` / `--codex` — configure specific agent only
- `--uninstall` — remove tokkit from all agent configs
- `--dry-run` — show what would be configured without writing

### `tokkit serve`

Runs the MCP server. This is what agent configs point to.

Equivalent to current `python -m tokkit_server.main` but exposed as a proper entry point.

### `tokkit init`

Project-level setup for team sharing.

**Creates:**
- `.mcp.json` in project root with tokkit server config
- Adds `@` reference to project-level `CLAUDE.md` (creates if absent)

## 4. Agent Auto-Configuration

### Detection and config locations:

| Agent | Detection | MCP Config Path | Skill Support |
|-------|-----------|----------------|---------------|
| Claude Code | `~/.claude/` exists | `~/.claude/mcp.json` | Yes — `@` ref in `~/.claude/CLAUDE.md` |
| Cursor | `~/.cursor/` exists | `~/.cursor/mcp.json` | No — relies on tool descriptions |
| Windsurf | `~/.codeium/` exists | `~/.codeium/windsurf/mcp_config.json` | No — relies on tool descriptions |
| Codex | `codex` on PATH | `~/.codex/mcp.json` | No — relies on tool descriptions |

### MCP server entry (same for all agents):
```json
{
  "tokkit": {
    "command": "uvx",
    "args": ["tokkit", "serve"]
  }
}
```

Using `uvx` as the command means:
- No hardcoded Python paths
- Works even if tokkit isn't permanently installed
- Auto-fetches correct version from PyPI

### Config merge strategy:
- Read existing config as JSON
- Add/update `tokkit` key under `mcpServers`
- Never modify other server entries
- Write back with consistent formatting
- If config file doesn't exist, create with just the tokkit entry

## 5. Skill Distribution

Two-tier approach based on agent capabilities:

### Tier 1: Claude Code (full skill)

Claude Code supports `@` file references in `CLAUDE.md`, which inject full documents into the agent's context. This is the richest integration.

**Files copied to `~/.local/share/tokkit/`:**
- `SKILL.md` — workflow guide, tool selection, confidence scores, anti-patterns
- `references/tool-guide.md` — parameter reference, response formats

**Why `~/.local/share/tokkit/` and not the package install path:**
- `uvx` runs from a temporary virtualenv — the package path is ephemeral
- `~/.local/share/` is the XDG standard for application data
- Survives package upgrades and `uvx` cache eviction

**Reference added to `~/.claude/CLAUDE.md`:**
```
@~/.local/share/tokkit/SKILL.md
```

**Update on reinstall:** `tokkit setup` always overwrites the skill files, so upgrading tokkit automatically updates the skill content.

### Tier 2: Other agents (enriched tool descriptions)

Cursor, Windsurf, and Codex don't have a skill injection mechanism. Instead, the MCP tool descriptions in `protocol.py` are enriched to include key usage patterns:

- Each tool description includes its purpose, required parameters, and a brief usage note
- The `index_repository` tool description explicitly states it must be called before other graph tools
- The `search_graph` description notes the qualified name format
- Tool descriptions are self-contained — no external docs needed

This is "good enough" for agents without skill support. They'll use the tools correctly, just without the full optimization guidance.

## 6. Repository Restructure

Current layout → maturin conventional layout:

```
tokkit/
├── Cargo.toml                    # workspace root
├── pyproject.toml                # single build config (maturin)
├── py/                           # all Python source
│   ├── tokkit_cli/
│   │   ├── __init__.py
│   │   ├── main.py              # CLI entry point (setup, serve, init)
│   │   └── agents.py            # agent detection + config writing
│   ├── tokkit_server/
│   │   ├── __init__.py
│   │   ├── main.py              # MCP server entry (serve_stdio)
│   │   ├── protocol.py          # JSON-RPC message handling
│   │   └── tools.py             # tool dispatch to Rust
│   ├── tokkit_scraper/
│   │   ├── __init__.py
│   │   └── scraper.py           # HTML cleaning
│   ├── tokkit_json/
│   │   ├── __init__.py
│   │   └── compact.py           # JSON compaction
│   └── tokkit_skill/
│       ├── SKILL.md             # bundled skill document
│       └── references/
│           └── tool-guide.md    # parameter reference
├── crates/
│   ├── tokkit-core/
│   │   ├── Cargo.toml
│   │   └── src/                 # graph engine, parsers, storage
│   └── tokkit-py/
│       ├── Cargo.toml
│       └── src/lib.rs           # PyO3 bindings
├── tests/
│   ├── rust/                    # cargo test (run from crates/)
│   ├── server/                  # pytest for MCP server
│   └── e2e/                     # end-to-end tests
└── .github/
    └── workflows/
        └── release.yml          # build + publish workflow
```

### Key changes from current layout:
- `core/code/crates/` → `crates/` (at root)
- `core/web/` → `py/tokkit_scraper/`
- `core/json/` → `py/tokkit_json/`
- `server/` → `py/tokkit_server/`
- `skill/` → `py/tokkit_skill/` (bundled as package data)
- `e2e/` → `tests/e2e/`
- New: `py/tokkit_cli/` (setup + agent configuration)
- New: `.github/workflows/release.yml`
- Removed: `install.sh` (replaced by `tokkit setup`)
- Removed: all sub-package `pyproject.toml` files (single root config)

## 7. Build Configuration

### `pyproject.toml` (root):
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
readme = "README.md"
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
features = ["pyo3/extension-module"]
include = [
    {path = "py/tokkit_skill/**/*", format = "sdist"},
]
```

### `Cargo.toml` (root workspace):
```toml
[workspace]
members = ["crates/tokkit-core", "crates/tokkit-py"]
resolver = "2"

[workspace.package]
version = "0.1.0"
edition = "2021"

[workspace.dependencies]
tokkit-core = { path = "crates/tokkit-core" }
pyo3 = { version = "0.23", features = ["extension-module"] }
```

## 8. CI/CD

### GitHub Actions workflow (`.github/workflows/release.yml`):

**Triggers:**
- Push tag `v*` → build + publish to PyPI
- Pull request → build + test (no publish)

**Build matrix:**

| Target | Runner | Wheel |
|--------|--------|-------|
| Linux x86_64 | `ubuntu-latest` | `manylinux_2_17_x86_64` |
| macOS x86_64 | `macos-13` | `macosx_10_12_x86_64` |
| macOS ARM | `macos-14` | `macosx_11_0_arm64` |
| Source dist | `ubuntu-latest` | `tokkit-0.1.0.tar.gz` |

**Steps per target:**
1. Checkout code
2. Set up Python 3.11
3. `maturin build --release` (or `maturin sdist` for source)
4. Run tests
5. Upload wheel as artifact

**Publish job (tag only):**
1. Download all wheel artifacts
2. `maturin publish` to PyPI (uses `PYPI_API_TOKEN` secret)

**Tooling:** `maturin-action` GitHub Action — handles manylinux containers, cross-compilation automatically.

## 9. Version Management

Single source of truth: `pyproject.toml` version field.

`maturin` syncs the Python package version with `Cargo.toml` workspace version automatically. Both read from the same `version = "0.1.0"` in `pyproject.toml`.

Release flow:
1. Bump version in `pyproject.toml`
2. `git tag v0.2.0 && git push --tags`
3. CI builds wheels and publishes to PyPI

## 10. Testing Strategy

All tests run against the built package, not source tree:

```bash
# Rust unit tests
cd crates && cargo test --workspace

# Python tests (after maturin develop)
maturin develop
pytest tests/ -v
```

**CI runs both** on every PR. Publish only happens on tag.

## 11. What's NOT in Scope

- **Windows support** — no Windows wheels. Source build may work but untested.
- **npm package** — not needed. `uvx` covers the single-command UX.
- **Claude Code plugin** — can be layered on later for deeper integration.
- **Auto-update mechanism** — users re-run `uvx tokkit` to update.
- **GUI installer** — CLI only.
