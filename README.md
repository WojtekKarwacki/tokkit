# Tokkit

The complete token saving kit — one plugin for all your coding workflows.
Code exploration, data compaction, content cleaning, and output compression,
delivered as a single MCP server.

| Task | Without Tokkit | With Tokkit | Savings |
|------|---------------:|-----------:|--------:|
| Compress pytest output (13.7KB) | 13,604 tokens | 2,486 tokens | 82% |
| Dead code detection | 19,316 tokens | 6,868 tokens | 64% |
| Clean blog post (24KB HTML) | 10,634 tokens | 3,420 tokens | 68% |
| Search README | 10,807 tokens | 3,725 tokens | 66% |
| List route handlers | 22,722 tokens | 8,554 tokens | 62% |
| Architecture overview | 18,277 tokens | 11,341 tokens | 38% |

Real agent sessions, actual API token usage minus measured ~23,350 fixed
overhead ([how this was measured](#overhead-breakdown)).
19% total savings, 49% content savings across 12 scenarios.
Measured on fastapi/fastapi @ 0.115.6. Full [methodology](#methodology) below.

## Install and setup

```bash
uvx tokkit-ai
```

One command. Installs the package, detects which agents are on the machine,
and configures each one:

| Agent | What gets written |
|-------|-------------------|
| Claude Code | Plugin at `~/.claude/plugins/cache/tokkit/` -- includes skill docs, MCP config, and tool reference. Registers in `~/.claude/plugins/installed_plugins.json` and `~/.claude/settings.json`. |
| Cursor | `tokkit` entry in `~/.cursor/mcp.json` |
| Windsurf | `tokkit` entry in `~/.codeium/windsurf/mcp_config.json` |
| Codex | `tokkit` entry in `~/.codex/mcp.json` |

For non-Claude agents, the MCP entry points to `uvx tokkit-ai serve` so
the server is fetched on demand with no persistent install required.

```bash
tokkit setup --claude      # configure only Claude Code
tokkit setup --cursor      # configure only Cursor
tokkit setup --dry-run     # show what would be configured, write nothing
tokkit setup --uninstall   # remove all written files and config entries
tokkit init                # write .mcp.json in current directory only
```

### Token savings stats

Every tool call records its token savings to `~/.local/share/tokkit/stats.json`.
Stats persist across sessions and reboots.

To see savings inline on every tool response, set `TOKKIT_SHOW_SAVINGS=1`
in your MCP config:

```
[tokkit: saved ~4,858 tokens (97.2%) | session total: 12,340 tokens saved]
```

## Tools

### Code graph

Parses Python, JavaScript, and TypeScript with tree-sitter, builds a knowledge
graph (functions, classes, calls, imports, types, routes, tests), and stores it
in redb. Indexing takes 1-5 seconds and persists to disk.

| Tool | What it does |
|------|--------------|
| `index_repository` | Parse source files, build graph |
| `get_architecture` | Languages, packages, entry points, key files |
| `find_dead_code` | Functions with zero inbound references |
| `find_routes` | HTTP route handlers (method, path, function name) |
| `trace_fan` | Fan-out or fan-in from a function; accepts plain function names |

### Data transformation

No indexing required. Transform raw content before it enters context.

| Tool | Input | Output | Typical savings |
|------|-------|--------|----------------:|
| `clean_html` | Raw HTML | Markdown or plain text | 60-90% |
| `compact_json` | JSON | Schema + CSV or YAML | 50-70% |
| `compact_output` | Shell output | Summary + failures only | 70-85% |
| `search_markdown` | Markdown + query | Matching sections only | 70-85% |

### `compact_output` parsers

pytest, unittest, ruff, mypy, pyright, jest, vitest, mocha, tsc, eslint,
webpack, vite, npm, pip, cargo test/build/clippy, docker build, Python
tracebacks. Auto-detected or specified via `hint` parameter.

## Benchmarks

Two independent Claude Haiku agents per scenario, same question. One uses
standard tools (Grep, Read, Glob), one uses tokkit. Token counts from
actual API usage on fastapi/fastapi @ 0.115.6.

### Total token usage (including agent overhead)

Every agent session carries fixed overhead: system prompt, tool
definitions, conversation framing. This overhead is identical for both
agents. See [overhead breakdown](#overhead-breakdown) for the measured
23,350 token figure used in the content table.

| # | Category | Task | Baseline | Tokkit | Savings |
|---|----------|------|---------|--------|---------|
| 1 | Code graph | Blast radius analysis | 56,054 | 45,271 | 19% |
| 2 | Code graph | Trace setup call chain | 38,427 | 35,766 | 7% |
| 3 | Code graph | Dead code detection | 42,666 | 30,218 | 29% |
| 4 | Code graph | List route handlers | 46,072 | 31,904 | 31% |
| 5 | Code graph | Architecture overview | 41,627 | 34,691 | 17% |
| 6 | Markdown | Search README | 34,157 | 27,075 | 21% |
| 7 | HTML | Clean Python docs (14KB) | 30,392 | 27,000 | 11% |
| 8 | HTML | Clean blog post (24KB) | 33,984 | 26,770 | 21% |
| 9 | JSON | Compact flat records (14KB) | 33,000 | 27,304 | 17% |
| 10 | JSON | Compact nested data (10KB) | 29,214 | 26,366 | 10% |
| 11 | Shell output | Compress pytest (13.7KB) | 36,954 | 25,836 | 30% |
| 12 | Shell output | Compress ruff lint (8.3KB) | 28,748 | 28,292 | 2% |
| | **Total** | | **451,295** | **367,493** | **19%** |

### Content token usage (excluding estimated overhead)

Subtracting the measured 23,350 fixed overhead from both sides isolates
what each agent consumed for the task itself. Does not affect total
savings above.

| # | Task | Baseline | Tokkit | Savings |
|---|------|---------|--------|---------|
| 1 | Blast radius analysis | 32,704 | 21,921 | 33% |
| 2 | Trace setup call chain | 15,077 | 12,416 | 18% |
| 3 | Dead code detection | 19,316 | 6,868 | 64% |
| 4 | List route handlers | 22,722 | 8,554 | 62% |
| 5 | Architecture overview | 18,277 | 11,341 | 38% |
| 6 | Search README | 10,807 | 3,725 | 66% |
| 7 | Clean Python docs | 7,042 | 3,650 | 48% |
| 8 | Clean blog post | 10,634 | 3,420 | 68% |
| 9 | Compact flat records | 9,650 | 3,954 | 59% |
| 10 | Compact nested data | 5,864 | 3,016 | 49% |
| 11 | Compress pytest output | 13,604 | 2,486 | 82% |
| 12 | Compress ruff lint output | 5,398 | 4,942 | 8% |
| | **Total** | **171,095** | **87,293** | **49%** |

Tokkit pays off most on high-redundancy shell output (Q11), multi-step
graph tasks (Q3, Q4), and large content (Q6, Q8). Structured lint output
(Q12) compresses poorly — every violation is distinct. In multi-turn
sessions the fixed overhead amortizes and total savings approach the
content-only figure.

## Methodology

### How agents were run

Each scenario dispatched two independent Claude Haiku subagents with the
same question. One used standard tools (Grep, Read, Glob), one used tokkit
MCP tools. `total_tokens` measured from actual API usage reports.

### What "baseline" means

The minimum tokens a skilled agent would consume using standard tools
(Grep, Read, Glob). Baselines are **optimistic for the standard approach**
-- the agent knows exactly what to search for and reads only what it needs.

For code graph tasks: Grep + targeted Read calls. For content tasks
(HTML, JSON, markdown, shell): `Read(path)` which loads the full file
into context with cat -n line-number prefix.

Real agents typically consume more: full-file reads (2,000 lines default),
iterative searches, re-reading files as context compresses.

### Path-based reading for content tools

Content-processing tools (`clean_html`, `compact_json`, `search_markdown`,
`compact_output`) accept a `path=` parameter so the MCP server reads the
file directly. The raw content never enters the agent's context — only
the compressed output is returned. Baseline agents use `Read`, which
loads the full file content into context.

### What is excluded

- **Agent overhead** (~23,350 tokens, measured): system prompt, tool
  definitions, conversation framing. See [overhead breakdown](#overhead-breakdown).
- **Reasoning tokens**: not tracked separately in `total_tokens`.
- **Accuracy**: benchmarks measure token efficiency, not answer quality.

### Overhead breakdown

The 23,350 token overhead subtracted in the content table is a **measured
value**, derived from first-turn `cache_creation + cache_read` across all
benchmark agents (measured 2026-04-10).

| Component | Tokens |
|-----------|-------:|
| Claude Code system prompt | ~17,660 |
| Subagent framing (context, prompt, CLAUDE.md, MCP defs) | ~5,690 |
| **Total** | **~23,350** |

MCP tool definitions add ~50 tokens to subagent framing — negligible.
The overhead is identical for baseline and tokkit agents (±50 tokens).
Total token savings (19%) are measured directly and are unaffected by
this figure.

### Per-tool baseline strategies

| Tool | Baseline strategy | Rationale |
|------|-------------------|-----------|
| `find_dead_code` | Grep all defs + per-function `Grep(-w)` | O(N) reference checks across repo |
| `find_routes` | `Grep(content, -A=1)` for decorators | Decorator line + signature |
| `trace_fan` | Per hop: `Grep` + `Read(50 lines)` | Cost scales with trace depth |
| `get_architecture` | `Glob` + `Read` README + init + 5 modules | Minimum a skilled agent would read |
| `clean_html` | `Read(path)` — full HTML with cat -n prefix | Agent would load entire file |
| `compact_json` | `Read(path)` — full JSON with cat -n prefix | Agent would load entire file |
| `compact_output` | `Read(path)` — full output with cat -n prefix | Agent would load entire file |
| `search_markdown` | `Read(path)` — full markdown with cat -n prefix | Agent would read the whole file |

## Supported languages

| Language | Extensions |
|----------|-----------|
| Python | `.py` |
| JavaScript | `.js`, `.mjs`, `.cjs` |
| TypeScript | `.ts`, `.tsx`, `.jsx` |

## Hook Model — Automatic Shell Compression

Tokkit installs a PreToolUse hook in Claude Code that intercepts every Bash
tool call and rewrites it to `tokkit compress '<command>'`. The command runs
normally, but its output passes through the parser library before entering the
agent's context window.

```
Agent issues Bash("git diff HEAD~1")
  → hook rewrites to: tokkit compress 'git diff HEAD~1'
  → command runs, output compressed, compressed result returned
  → raw diff never enters context
```

### Token overhead comparison

| Delivery model | What the agent sees | Tool calls |
|---------------|---------------------|:----------:|
| Hook (compressed) | Compressed output only | 1 |
| MCP `compact_output(text=...)` | Raw text in call + compressed result | 2 |
| MCP `compact_output(path=...)` | Compressed result + framing | 2 |

The hook model is strictly lower overhead: the raw output never touches the
context window and requires no extra tool call.

### Supported commands

| Category | Commands | Hint |
|----------|----------|------|
| Git | `git diff` | `git-diff` |
| Git | `git status` | `git-status` |
| Git | `git log` | `git-log` |
| Git | `git show` | `git-show` |
| Git | `git blame` | `git-blame` |
| Git | `git branch` | `git-branch` |
| Git | `git stash` | `git-stash` |
| Kubernetes | `kubectl get`, `kubectl describe`, `kubectl logs` | `kubectl` |
| Docker | `docker-compose ps/logs` | `docker-compose` |
| Docker | `docker ps`, `docker images` | `docker-ps` |
| Docker | `docker logs` | `docker-logs` |
| Python test | `pytest`, `unittest` | `pytest`, `unittest` |
| Python lint/type | `ruff`, `mypy`, `pyright` | `ruff`, `mypy`, `pyright` |
| Python other | `pip list/freeze`, tracebacks | `package-list`, `traceback` |
| JS/TS test | `jest`, `vitest`, `mocha` | `jest`, `vitest`, `mocha` |
| JS/TS lint/type | `tsc`, `eslint` | `tsc`, `eslint` |
| JS/TS build | `webpack`, `vite` | `webpack`, `vite` |
| JS/TS package | `npm ls` | `npm`, `package-list` |
| Rust | `cargo test/build/clippy` | `cargo-test`, `cargo-build`, `cargo-clippy` |
| Container | `docker build` | `docker` |
| Shell | `tree`, `ls`, `find` | `file-listing` |
| Search | `grep`, `rg`, `ag` | `search-results` |
| GitHub | `gh` | `gh-cli` |
| Environment | Any command with env vars | `env-redact` |
| Any other | Generic fallback (always active) | — |

The hint is auto-detected from the command name. The generic fallback applies
to all unrecognized commands: ANSI strip, progress bar removal, deduplication,
similar-line dedup, and head/tail truncation.

### Lint grouping

Rules with more than 3 violations are collapsed to a header with 2 examples:

```
# Before (ruff, 47 violations of E501)
src/foo.py:12:89: E501 Line too long (92 > 88 characters)
src/foo.py:34:89: E501 Line too long (95 > 88 characters)
... (45 more)

# After
E501: 47 violations (line too long)
  src/foo.py:12  Line too long (92 > 88 characters)
  src/foo.py:34  Line too long (95 > 88 characters)
```

This collapses repetitive lint output from 8% savings to 70-85%.

### Hook content compression benchmarks

Content compression ratios measured by running `compact_output()` on realistic
output fixtures. Token counts use chars/4. These measure the content savings
only — the hook model adds zero additional overhead (1 tool call, compressed
output only).

| Scenario | Raw | Compressed | Savings |
|----------|----:|----------:|--------:|
| git diff (with lockfile) | 1,532 | 80 | **95%** |
| git status (30+ files) | 429 | 169 | **61%** |
| git log (verbose, 3 commits) | 219 | 40 | **82%** |
| git blame (12 lines) | 247 | 68 | **72%** |
| kubectl get pods (13 pods, 1 unhealthy) | 291 | 36 | **88%** |
| kubectl logs (72 lines, 2 errors) | 1,283 | 520 | **59%** |
| docker compose ps (5 healthy) | 205 | 10 | **95%** |
| docker compose logs (3 services) | 1,157 | 591 | **49%** |
| docker ps (3 running, 2 stopped) | 219 | 59 | **73%** |
| docker logs (85 lines, 2 errors) | 1,278 | 491 | **62%** |
| pip list (30 packages) | 262 | 75 | **71%** |
| npm ls (nested tree) | 280 | 50 | **82%** |
| ls -la (60 entries) | 822 | 173 | **79%** |
| grep -r (5 files, many matches) | 445 | 307 | **31%** |
| ruff (200 violations, 5 rules) | 2,951 | 242 | **92%** |
| **Total** | **11,832** | **4,991** | **58%** |

Agent-level benchmarks (total tokens including overhead) require the hook to
be active in a real Claude Code session. Run `tokkit setup`, then use the
agent normally — the hook activates on every Bash command automatically.

## Using Both Models Together

The hook and MCP models cover different surfaces:

- **Hook**: live shell commands (git, cargo, pytest, kubectl, etc.) — automatic, zero overhead
- **MCP**: files on disk (HTML, JSON, markdown) and code intelligence (graph tools) — explicit calls

Both are installed with a single command:

```bash
uvx tokkit-ai
```

`tokkit setup` writes the MCP server config and the PreToolUse hook into the
Claude Code plugin directory. Both activate on the next Claude Code session.

## Complete Command Coverage

All command patterns and their corresponding hint values:

| Category | Commands | Hint |
|----------|----------|------|
| Git | `git diff` | `git-diff` |
| Git | `git status` | `git-status` |
| Git | `git log` | `git-log` |
| Git | `git show` | `git-show` |
| Git | `git blame` | `git-blame` |
| Git | `git branch` | `git-branch` |
| Git | `git stash` | `git-stash` |
| Kubernetes | `kubectl get/describe/logs` | `kubectl` |
| Docker | `docker-compose ps/logs` | `docker-compose` |
| Docker | `docker ps`, `docker images` | `docker-ps` |
| Docker | `docker logs` | `docker-logs` |
| Docker | `docker build` | `docker` |
| Python test | `pytest`, `python -m unittest` | `pytest`, `unittest` |
| Python lint | `ruff check` | `ruff` |
| Python type | `mypy`, `pyright` | `mypy`, `pyright` |
| Python packages | `pip list`, `pip freeze` | `package-list` |
| Python errors | Exception tracebacks | `traceback` |
| JS/TS test | `jest`, `vitest`, `mocha` | `jest`, `vitest`, `mocha` |
| JS/TS lint | `eslint` | `eslint` |
| JS/TS type | `tsc` | `tsc` |
| JS/TS build | `webpack`, `vite` | `webpack`, `vite` |
| JS/TS packages | `npm ls` | `package-list` |
| Rust | `cargo test` | `cargo-test` |
| Rust | `cargo build` | `cargo-build` |
| Rust | `cargo clippy` | `cargo-clippy` |
| Shell | `tree`, `ls -la`, `find` | `file-listing` |
| Search | `grep`, `rg`, `ag` | `search-results` |
| GitHub | `gh issue/pr/repo` | `gh-cli` |
| Environment | Commands printing env vars | `env-redact` |
| Lint grouper | Post-processor for all lint output | *(automatic)* |
| Generic | Any other command | *(automatic fallback)* |

## Tokkit and RTK

[RTK](https://github.com/rtk-ai/rtk) saves tokens by intercepting Bash commands
(e.g., `git status`, `ls`, `find`) and filtering their output before it enters
context. Tokkit now covers the same surface through its built-in hook model, plus
HTML pages, JSON payloads, code graph queries, and markdown documents through MCP.

If you already use RTK, both tools can run side by side — they operate
independently. Tokkit's hook takes precedence for commands it recognizes; RTK
handles any gaps.

## Development

```bash
# Build and install in dev mode (requires Rust toolchain)
maturin develop

# Run MCP server
tokkit serve

# Run tests
cargo test --workspace                              # Rust
pytest tests/ -v --ignore=tests/e2e/benchmark       # Python
```

## License

MIT
