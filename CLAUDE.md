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
