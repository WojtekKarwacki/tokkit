# Dual-Model Output Compression — Hook + MCP

**Date:** 2026-04-13
**Status:** Draft

## Purpose

Port token-saving techniques from token-saver to tokkit and introduce a hook-based delivery model that eliminates MCP overhead for shell command output. The result: two complementary compression models in a single package.

- **Hook model** (automatic): PreToolUse hook intercepts Bash commands, compresses output before it enters agent context. Zero overhead — raw output never touches the context window.
- **MCP model** (explicit): Agent calls `compact_output(path=...)` for output files already on disk. Also retains `clean_html`, `compact_json`, `search_markdown`, and graph tools unchanged.

Single install via `tokkit setup`. Both models active by default.

## Architecture

```
┌─────────────────────────────────────────────────┐
│            Shared Parser Library                 │
│  py/tokkit_output/parsers/*.py                  │
│  py/tokkit_output/generic.py                    │
│  py/tokkit_output/lint_grouper.py               │
└──────────┬──────────────────────┬───────────────┘
           │                      │
    ┌──────▼──────┐        ┌──────▼──────┐
    │  Hook Model  │        │  MCP Model  │
    │  (automatic) │        │  (explicit) │
    │              │        │             │
    │  PreToolUse  │        │ compact_out │
    │  hook.py     │        │ put(path=)  │
    │  ↓           │        │             │
    │  tokkit      │        │ clean_html  │
    │  compress    │        │ compact_json│
    │  '<cmd>'     │        │ search_md   │
    │  ↓           │        │ graph tools │
    │  subprocess  │        │             │
    │  + compress  │        │             │
    │  ↓           │        │             │
    │  compressed  │        │             │
    │  stdout only │        │             │
    └──────────────┘        └─────────────┘
```

### Token overhead comparison

| Scenario | Hook model | MCP model (text=) | MCP model (path=) |
|----------|-----------|-------------------|-------------------|
| 2,270-token git diff → 909 compressed | 909 tokens, 1 tool call | 5,449 tokens (2x raw + compressed), 2 tool calls | 909 + ~1,200 framing, 2 tool calls |
| 500-line pytest → 308 compressed | 308 tokens, 1 tool call | ~13,796 tokens, 2 tool calls | 308 + ~1,200 framing, 2 tool calls |

Hook model is strictly better for live shell commands.

## New Parsers

### From token-saver (ported algorithms)

#### 1. git-diff

**Hint values:** `git-diff`, `git`
**Schema:** `[file;lines_changed;content]`
**Detection:** Lines starting with `diff --git`, `@@`, `+`, `-`

Algorithms:
- **Context windowing**: Keep a leading buffer of unchanged lines. Only emit the last N (default 3) when a `+`/`-` line follows. After a change, emit up to N trailing context lines via counter.
- **Hunk truncation**: Once changed lines in a hunk exceed 50, replace remainder with `... (truncated after 50 lines)`.
- **Lock file elision**: Diffs to `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`, `uv.lock`, `go.sum`, `Gemfile.lock` are replaced with `(lockfile changed, N lines)`.
- **Index/meta stripping**: Remove `index`, `---`, `+++` lines entirely.
- **Stat bar stripping**: `--stat` output drops visual `+/-` bars, keeps `file | count`. >20 files groups by directory.

Output format: one row per file. `content` contains the compressed diff hunks for that file (newlines escaped). Summary line has file count + insertions/deletions. For lock files, `content` is the one-liner elision message.

#### 2. git-status

**Hint values:** `git-status`
**Schema:** `[file;status;staged]`
**Detection:** `On branch` or short-format status codes (`M`, `A`, `D`, `??`, `UU`)

Algorithms:
- Parse both long-format and short-format status
- Summary header: `Files: 15 (M:8, A:3, D:2, ?:2)`
- Directory grouping: when a dir has >8 files, collapse to `dir/ (12 files: M:8, A:4)`
- Strip hint lines (lines starting with `(use "git`)

#### 3. git-log

**Hint values:** `git-log`
**Schema:** `[hash;message]`
**Detection:** Lines starting with `commit ` followed by 40-char hex, or one-line format

Algorithms:
- Verbose format: extract 8-char hash + first non-metadata line as message, drop Author/Date/Merge lines
- One-line format: pass through, truncate to 10 entries (configurable)
- Graph format: preserve structure, truncate to 40 lines
- Always cap at `max_entries` (default 10)

#### 4. git-show

**Hint values:** `git-show`
**Schema:** reuses git-diff schema for the diff portion
**Detection:** `commit ` header + diff content

Algorithms:
- Extract commit metadata (hash, author, message) as summary
- Apply git-diff compression to the diff portion
- Strip Author/Date metadata

#### 5. git-blame

**Hint values:** `git-blame`
**Schema:** `[line;hash;author;content]`
**Detection:** Lines matching `^hash (author date line)` pattern

Algorithms:
- Consecutive lines by same author+hash collapse to range: `lines 10-45: a1b2c3d4 (alice)`
- Only show unique author+hash groups with line ranges

#### 6. git-branch

**Hint values:** `git-branch`
**Schema:** `[branch;current;remote]`
**Detection:** Lines with `*` prefix (current branch indicator) or `remotes/`

Algorithms:
- List branches, mark current with `*`
- If >20 branches: group by prefix (feature/, bugfix/, etc.) with counts
- Remote branches summarized as counts per remote

#### 7. git-stash

**Hint values:** `git-stash`
**Schema:** `[index;branch;message]`
**Detection:** Lines matching `stash@{N}:`

Algorithms:
- Parse stash entries
- If >10 entries: show first 5 + last 2 + count

#### 8. kubectl

**Hint values:** `kubectl`, `k8s`
**Schema varies by subcommand:**
- `get pods`: `[name;status;restarts;age;node]`
- `get services`: `[name;type;cluster_ip;ports;age]`
- `get deployments`: `[name;ready;up_to_date;available;age]`
- `describe`: `[section;key;value]`
- `logs`: `[line]` (head/tail + error neighborhoods)

**Detection:** Table headers with `NAME`, `STATUS`, `READY`, `AGE` columns; or `Name:`, `Namespace:` describe format

Algorithms:
- **get pods/deployments**: Elide healthy rows (Running + all containers ready, Completed). Keep unhealthy (CrashLoopBackOff, Error, Pending, ImagePullBackOff, OOMKilled). Summary: `45 pods (42 healthy, 3 unhealthy)`.
- **get services/nodes/etc.**: Straight table parse, keep all rows (tables are usually small).
- **describe**: Keep metadata (Name, Namespace, Labels), Conditions section, Events section (last 10). Drop managed-fields, annotations with long values.
- **logs**: Head 10 + tail 10 + error neighborhoods (ERROR|FATAL|PANIC|Exception + 2 lines context). Middle: `... (N lines skipped)`.

#### 9. docker-compose

**Hint values:** `docker-compose`, `docker compose`
**Schema:** `[service;status;ports;health]`
**Detection:** `Container `, `docker compose`, service table with `NAME`, `IMAGE`, `STATUS`

Algorithms:
- **ps**: Parse service table. Elide healthy (running + healthy). Keep unhealthy/exited.
- **logs**: Group by service name (prefix `service-1 |`). Per-service: head 5 + tail 5 + error neighborhoods. Summary: `4 services, 847 log lines`.
- **up/build**: Strip pull progress bars, layer download progress. Keep error steps + final status.

Extends existing docker parser (currently handles build only).

#### 10. docker-ps / docker-images

**Hint values:** `docker-ps`, `docker-images`
**Schema:** `[id;image;status;ports;names]` / `[repository;tag;size;created]`
**Detection:** Table headers with `CONTAINER ID` or `REPOSITORY`

Algorithms:
- Parse table format
- `docker ps`: Elide stopped containers in default mode, show counts. Keep running + unhealthy.
- `docker images`: Group by repository when >20 images. Show `repo (N tags, total size)`.

#### 11. docker-logs

**Hint values:** `docker-logs`
**Schema:** `[line]`
**Detection:** Timestamp-prefixed lines or raw log output after `docker logs` command

Algorithms:
- Head 10 + tail 10 + error neighborhoods
- Same as kubectl logs algorithm

#### 12. package-list (hook-only)

**Hint values:** `pip-list`, `pip-freeze`, `npm-ls`
**Schema:** `[package;version]` or `[package;version;status]`
**Detection:** `pip list` header format or `npm ls` tree format

Algorithms:
- **pip list/freeze**: Count packages. If >20: show first 15 + `... (N more)`.
- **npm ls**: Parse tree. Top-level deps shown. Nested deps counted. Lines with `UNMET|invalid|ERR!` always kept. Summary: `347 total deps (12 top-level, 3 issues)`.

#### 13. file-listing (hook-only)

**Hint values:** `ls`, `tree`, `find`
**Schema:** `[path;type;size]` or `[path]`
**Detection:** `tree` output with `├──`/`└──` characters, or file-per-line format

Algorithms:
- **tree**: Truncate depth >3 levels to directory counts. Show full tree up to depth 3, then `dir/ (N files, M subdirs)`.
- **ls -la**: Parse columns. If >50 entries: group by extension with counts. Show first 30 + `... (N more)`.
- **find**: Group by directory. If >30 files total: show top 15 directories with file counts. Per-directory: first 3 files + `... (N more)`.

#### 14. search-results (hook-only)

**Hint values:** `grep`, `rg`, `ag`
**Schema:** `[file;line;match]`
**Detection:** `file:line:content` or `file:content` format, or `--` separators between file groups

Algorithms:
- Group by file path
- Per-file limit: 3 matches (configurable)
- Total file limit: 15 (configurable), sorted by match count (most matches first)
- >30 files: group by directory, show top 3 files per directory
- Strip binary file warnings
- Summary: `124 matches across 38 files`

#### 15. gh-cli

**Hint values:** `gh`, `gh-pr`, `gh-issue`, `gh-run`
**Schema varies:**
- `pr list`: `[number;title;author;status;updated]`
- `issue list`: `[number;title;labels;status;updated]`
- `run list`: `[status;conclusion;name;branch;elapsed]`

**Detection:** Table format with `#`, `TITLE`, `BRANCH` headers, or `gh` specific output patterns

Algorithms:
- Parse table format (gh outputs TSV-like tables)
- Truncate to 20 entries (default)
- For `pr view`/`issue view`: keep title, body (first 500 chars), status, labels, reviewers. Strip timeline events.

#### 16. env-redact (hook-only)

**Hint values:** `env`, `printenv`
**Schema:** `[key;value]`
**Detection:** `KEY=VALUE` per-line format

Algorithms:
- Parse key=value lines
- Redact values where key matches `*KEY*`, `*SECRET*`, `*TOKEN*`, `*PASSWORD*`, `*CREDENTIAL*`, `*AUTH*`, `*PRIVATE*`
- Redacted values become `[REDACTED]`
- Summary: `87 vars (12 redacted)`

### Lint Grouper (post-processing layer)

**File:** `py/tokkit_output/lint_grouper.py`

Not a parser — a post-processing step applied after any lint parser returns a `ParseResult` with a `rule` or `code` column.

Algorithm:
1. Identify the rule/code column index from schema
2. Group rows by rule/code value
3. For rules with >3 violations:
   - Emit: `{rule}: {count} occurrences in {file_count} files`
   - Show first 2 examples as normal rows
   - Append: `... ({count - 2} more)`
4. Rules with <=3 violations: emit all rows normally
5. Update summary: `47 issues across 12 rules`

Applied automatically in default mode. Disabled when `verbose=True`.

Affected parsers: ruff, eslint, mypy, pyright, clippy, tsc.

Expected improvement: ruff savings from 8% → 70-85%.

### Generic Fallback

**File:** `py/tokkit_output/generic.py`

Applied when no parser matches (confidence <0.6) AND output exceeds a minimum length (default 500 chars). Five passes in sequence:

1. **ANSI stripping**: `\x1b\[[0-9;]*[a-zA-Z]` and OSC sequences. (Already exists in `universal.py`, reuse.)
2. **Progress bar removal**: Lines where >50% of content is bar characters (`━█▓░▒■□●○#=\->`) are removed. Also catches spinner characters (braille dots).
3. **Consecutive dedup**: Identical adjacent non-blank lines collapse to `{line} (x{N})`.
4. **Similar-line dedup**: Normalize all digits to `N`. Group consecutive lines with identical normalized forms. Only apply when line is "numeric-heavy" (>=30% digits, or contains `%`, `MB/s`, `ETA`, `--:--:--`). Groups of >=5 similar lines collapse to: first line + `... ({N-2} similar lines)` + last line.
5. **Head/tail truncation**: When total lines exceed 200: keep first 100 + `... ({removed} lines truncated, {total} total)` + last 50.

Returns `ParseResult(tool="generic", summary="...", schema=["line"], rows=[[line] for line in surviving_lines])`.

### Minimum Ratio Check

After any parser (including generic) produces output, compare compressed size to raw size. If compressed >= raw (compression made it bigger or equal), return raw text with ANSI stripping only. This prevents pathological cases where structured format adds overhead to already-concise output.

Implemented in `compact_output()` in `py/tokkit_output/__init__.py`.

### Source Code Pass-Through

The hook must NOT compress output of commands that display source code:
- `cat *.py`, `cat *.js`, `cat *.ts`, `cat *.rs`, etc.
- `head`/`tail` on source files
- `bat` (syntax-highlighted cat)

The model needs exact source content for patches. The hook's `match.py` maintains an exclusion list of source file extensions. If the command reads a source file, the hook allows pass-through (no rewrite).

### Chained Command Support

The hook must handle compound commands:
- `git add . && git commit -m "foo"` — identify `git commit` as the primary command
- `cd src && pytest` — identify `pytest` as the primary command
- `npm install && npm test` — identify `npm test` as the primary command

Algorithm:
1. Split on `&&` and `;` (respecting quoted strings)
2. Identify "silent" commands that produce no/minimal output: `cd`, `mkdir`, `cp`, `mv`, `rm`, `export`, `source`, `git add`, `git checkout`, `git stash`, `pushd`, `popd`
3. The last non-silent command is the "primary" — use its hint for compression
4. If all commands are silent, pass through (no compression)
5. The entire chain is still executed as-is — only the output is compressed using the primary command's parser

## Hook Implementation

### New module: `py/tokkit_hook/`

#### `match.py` — Command pattern matching

Maps shell commands to parser hints. Returns `None` for unmatched/excluded commands.

```python
def match_command(command: str) -> str | None:
    """Return hint value for command, or None for pass-through."""
```

Pattern table (prefix matching):

| Command prefix | Hint | Notes |
|---------------|------|-------|
| `git diff` | `git-diff` | |
| `git status` | `git-status` | |
| `git log` | `git-log` | |
| `git show` | `git-show` | |
| `git blame` | `git-blame` | |
| `git branch` | `git-branch` | Including `-a`, `-r` |
| `git stash list` | `git-stash` | Only `list` subcommand |
| `pytest` / `python -m pytest` | `pytest` | |
| `python -m unittest` | `unittest` | |
| `ruff check` / `ruff .` | `ruff` | |
| `mypy` | `mypy` | |
| `pyright` | `pyright` | |
| `pip list` / `pip freeze` | `pip-list` / `pip-freeze` | |
| `pip install` | `pip` | |
| `jest` / `npx jest` | `jest` | |
| `vitest` / `npx vitest` | `vitest` | |
| `mocha` / `npx mocha` | `mocha` | |
| `eslint` / `npx eslint` | `eslint` | |
| `tsc` / `npx tsc` | `tsc` | |
| `webpack` / `npx webpack` | `webpack` | |
| `vite build` / `npx vite build` | `vite` | |
| `npm install` / `npm ci` / `npm run build` / `npm test` | `npm` | |
| `cargo test` | `cargo-test` | |
| `cargo build` / `cargo check` | `cargo-build` | |
| `cargo clippy` | `cargo-clippy` | |
| `docker build` / `docker compose build` | `docker` | |
| `docker compose up` / `docker compose logs` | `docker-compose` | |
| `docker ps` | `docker-ps` | |
| `docker images` | `docker-images` | |
| `docker logs` | `docker-logs` | |
| `kubectl get` / `kubectl describe` / `kubectl logs` | `kubectl` | |
| `ls` / `exa` / `eza` | `ls` | |
| `tree` | `tree` | |
| `find` | `find` | |
| `grep -r` / `rg` / `ag` | `grep` | |
| `gh pr` / `gh issue` / `gh run` | `gh` | |
| `env` / `printenv` | `env` | |

Exclusions (never compress):
- Commands reading source files: `cat *.py`, `cat *.js`, `cat *.ts`, `cat *.rs`, `cat *.go`, `cat *.java`, `cat *.rb`, `cat *.c`, `cat *.h`, `cat *.cpp`, `cat *.swift`
- `head`/`tail` on source files
- `bat` / `batcat`
- Interactive commands: `vim`, `nano`, `less`, `more`, `ssh`, `sudo`
- Piped output: commands with `| head`, `| tail`, `| wc`, `| grep`, `| sort` — the user is already filtering
- Output redirects: commands with `> file` or `>> file`

#### `compress.py` — CLI entry point

New subcommand: `tokkit compress '<command>'`

```python
def compress_command(command: str) -> int:
    """Run command, compress output, print result. Return exit code."""
```

Flow:
1. Run command via `subprocess.Popen(command, shell=True, stdout=PIPE, stderr=STDOUT)`
2. Capture all output
3. Determine hint from `match_command(command)`
4. Run through `compact_output(text, hint=hint)`
5. Apply minimum ratio check — if compressed >= raw, print raw (ANSI-stripped only)
6. Print result to stdout
7. Return original command's exit code

Stderr handling: merge stderr into stdout (most tools mix them). If the command fails (non-zero exit), still compress the output — error messages are the most valuable part.

#### `hook.py` — PreToolUse hook script

Reads JSON from stdin per Claude Code hook protocol. Writes JSON to stdout.

```python
# stdin: {"tool_name": "Bash", "tool_input": {"command": "git diff"}}
# stdout: {"decision": "allow", "params": {"command": "tokkit compress 'git diff'"}}
```

Logic:
1. Parse JSON from stdin
2. If `tool_name != "Bash"` → `{"decision": "allow"}` (pass through)
3. Extract `command` from `tool_input`
4. Handle chained commands: split on `&&`/`;`, find primary command
5. Check exclusion list (source files, interactive, pipes, redirects)
6. Run `match_command(primary_command)`
7. If no match → `{"decision": "allow"}` (pass through)
8. Rewrite: `{"decision": "allow", "params": {"command": "tokkit compress '<escaped_command>'"}}`

Must be fast — runs on every Bash tool call. Pattern matching only, no imports of heavy modules.

### Setup integration

`tokkit setup` updated to also write hook configuration into the plugin:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/hook.py"
      }
    ]
  }
}
```

The hook script is bundled in the plugin directory at install time.

## Changes to Existing Code

### `py/tokkit_output/__init__.py`

- Add minimum ratio check after parser produces output
- Add lint grouper post-processing step for lint parsers
- Generic fallback replaces current `universal_clean()` fallback

### `py/tokkit_output/parsers/__init__.py`

- Register all new parsers
- New hint values added to `_HINT_MAP`

### `py/tokkit_output/formatter.py`

- Support lint grouper output format (grouped rows with `... (N more)` lines)

### `py/tokkit_cli/main.py`

- Add `tokkit compress '<command>'` subcommand routing to `compress.py`

### `py/tokkit_cli/setup.py`

- Write hook configuration alongside MCP config
- Bundle hook.py in plugin directory

### `py/tokkit_server/protocol.py`

- Update `compact_output` tool description to mention hook model as primary for live commands
- Add new hint values to description

## Testing Strategy

### Parser tests (per parser)

Each new parser gets:

**Fixture file:** `tests/output_tests/fixtures/<category>_output.py`
- Realistic output samples (copied/adapted from real command output)
- Multiple variants: normal, error, empty, large

**Unit test file:** `tests/output_tests/test_<parser>_parser.py`
- `test_detect_valid()` — confidence >= 0.8 for valid output
- `test_detect_invalid()` — confidence < 0.6 for unrelated output
- `test_parse_default()` — correct schema, rows, summary in default mode
- `test_parse_verbose()` — includes all items in verbose mode
- `test_parse_empty()` — handles empty/minimal output gracefully
- `test_parse_large()` — handles large output without error

**Fixture grouping:**
- `git_output.py` — diff, status, log, show, blame, branch, stash
- `k8s_output.py` — kubectl get pods/services/deployments, describe, logs
- `docker_output.py` — compose ps/logs, ps, images, logs, build
- `shell_output.py` — package lists, file listings, search results, env
- `gh_output.py` — gh pr/issue/run list

### Lint grouper tests

- `tests/output_tests/test_lint_grouper.py`
- Test with ruff output: 200 violations → grouped by rule, verify savings
- Test with eslint output: same
- Test threshold: rules with <=3 violations shown individually
- Test verbose bypass: grouping disabled when verbose=True
- Test parsers without rule column: grouper is a no-op

### Generic fallback tests

- `tests/output_tests/test_generic.py`
- Test ANSI stripping (already tested, extend)
- Test progress bar removal
- Test consecutive dedup with counts
- Test similar-line dedup (numeric normalization)
- Test head/tail truncation at boundary
- Test minimum length threshold (short output passes through)

### Hook tests

- `tests/hook_tests/test_match.py`
  - Test every command prefix → correct hint
  - Test exclusions (source files, interactive, pipes, redirects)
  - Test chained commands (`&&`, `;`)
  - Test quoted strings in chains
  - Test unknown commands → None

- `tests/hook_tests/test_compress.py`
  - End-to-end: real command → compressed output
  - Test exit code preservation
  - Test minimum ratio check (raw returned when compression doesn't help)
  - Test stderr merging

- `tests/hook_tests/test_hook.py`
  - Test PreToolUse JSON protocol (valid Bash call → rewrite)
  - Test non-Bash tool → pass through
  - Test excluded commands → pass through
  - Test command escaping in rewrite

### Integration tests

- `tests/server/test_output_integration.py` — extended with new parser hints via MCP
- `tests/hook_tests/test_integration.py` — end-to-end hook → compress → output

### Minimum ratio check tests

- `tests/output_tests/test_ratio_check.py`
  - Short input: returns raw
  - Input where compression adds overhead: returns raw (ANSI-stripped)
  - Normal input: returns compressed

## Benchmarks

Two separate benchmark suites. Both use real agent sessions (Claude Haiku), not estimates.

### Hook Benchmark

**Methodology:**
- Target repo: fastapi/fastapi @ 0.115.6 (same as existing MCP benchmark)
- Two agents per scenario: one with hook active, one without
- Agent given same task prompt both times
- Measure: tokens in Bash tool results (the output the agent sees)

**Scenarios:**

| # | Task | Command(s) | What we measure |
|---|------|-----------|----------------|
| H1 | Check git changes | `git diff` on staged changes | Diff compression |
| H2 | Review git history | `git log --oneline -20` | Log truncation |
| H3 | Check repo status | `git status` in dirty worktree | Status summary |
| H4 | Run Python tests | `pytest tests/ -v` | Test output compression |
| H5 | Lint Python code | `ruff check .` | Lint grouping savings |
| H6 | Type check | `mypy src/` | Type error compression |
| H7 | List dependencies | `pip list` | Package list collapse |
| H8 | Search codebase | `grep -r "router" src/` | Search result compression |
| H9 | Docker status | `docker compose ps` | Container elision |
| H10 | Check k8s pods | `kubectl get pods -A` | Pod elision |

**Metrics reported:**
- Raw tokens (without hook)
- Compressed tokens (with hook)
- Savings percentage
- Tool calls (always 1 for hook, vs 2+ for MCP)

### MCP Benchmark

Existing benchmark methodology (already in README), extended with new scenarios:

| # | Task | Tool | What we measure |
|---|------|------|----------------|
| M1-M6 | Existing scenarios | Existing tools | Unchanged |
| M7 | Compress saved test output | `compact_output(path=...)` | File-based compression |
| M8 | Compress saved lint output | `compact_output(path=..., hint="ruff")` | Lint grouping via MCP |

**Metrics reported:**
- Total tokens (with and without MCP)
- Content tokens (overhead subtracted)
- Savings percentage

### Benchmark reporting in README

```markdown
## Benchmarks

### Hook Model — Automatic Shell Compression

Measured on [repo] with Claude Haiku agents. Hook active vs inactive.

| Task | Raw | Compressed | Savings |
| ... | ... | ... | ... |

### MCP Model — Explicit File Processing

Measured on [repo] with Claude Haiku agents. MCP tools vs Read/Grep/Glob.

| Task | Without Tokkit | With Tokkit | Savings |
| ... | ... | ... | ... |

### Combined Savings

Typical session using both models: X% total token reduction.
```

## Documentation Updates

### README.md

- New section explaining both models with when-to-use guidance
- Hook model benchmark table
- MCP model benchmark table (existing, extended)
- Installation section updated: `tokkit setup` enables both
- Supported commands table for hook model
- Hint values table for MCP model

### skill/SKILL.md

- Add section: "Hook Model (Automatic)" explaining that shell command output is compressed automatically
- Update "When to Use Tokkit" decision table: shell commands are now handled by hook, not MCP
- Remove guidance telling agents to call `compact_output` for live shell output — hook does it
- Keep `compact_output(path=...)` guidance for saved output files

### New hint values documented

All new hints added to both README and SKILL.md tables.

## File Summary

### New files

| File | Purpose |
|------|---------|
| `py/tokkit_hook/__init__.py` | Hook module |
| `py/tokkit_hook/match.py` | Command → hint pattern matching |
| `py/tokkit_hook/compress.py` | `tokkit compress` CLI subcommand |
| `py/tokkit_hook/hook.py` | PreToolUse hook script |
| `py/tokkit_hook/chain.py` | Chained command splitting |
| `py/tokkit_output/parsers/git_diff.py` | Git diff parser |
| `py/tokkit_output/parsers/git_status.py` | Git status parser |
| `py/tokkit_output/parsers/git_log.py` | Git log parser |
| `py/tokkit_output/parsers/git_show.py` | Git show parser |
| `py/tokkit_output/parsers/git_blame.py` | Git blame parser |
| `py/tokkit_output/parsers/git_branch.py` | Git branch parser |
| `py/tokkit_output/parsers/git_stash.py` | Git stash parser |
| `py/tokkit_output/parsers/kubectl.py` | Kubernetes parser |
| `py/tokkit_output/parsers/docker_compose.py` | Docker compose parser |
| `py/tokkit_output/parsers/docker_ps.py` | Docker ps/images parser |
| `py/tokkit_output/parsers/docker_logs.py` | Docker logs parser |
| `py/tokkit_output/parsers/package_list.py` | pip list/freeze, npm ls |
| `py/tokkit_output/parsers/file_listing.py` | ls, tree, find |
| `py/tokkit_output/parsers/search_results.py` | grep, rg, ag |
| `py/tokkit_output/parsers/gh_cli.py` | GitHub CLI |
| `py/tokkit_output/parsers/env_redact.py` | env/printenv with redaction |
| `py/tokkit_output/generic.py` | Generic fallback pipeline |
| `py/tokkit_output/lint_grouper.py` | Lint grouping post-processor |
| `tests/output_tests/fixtures/git_output.py` | Git fixtures |
| `tests/output_tests/fixtures/k8s_output.py` | K8s fixtures |
| `tests/output_tests/fixtures/docker_output.py` | Docker fixtures |
| `tests/output_tests/fixtures/shell_output.py` | Shell tool fixtures |
| `tests/output_tests/fixtures/gh_output.py` | GitHub CLI fixtures |
| `tests/output_tests/test_git_diff_parser.py` | Git diff tests |
| `tests/output_tests/test_git_status_parser.py` | Git status tests |
| `tests/output_tests/test_git_log_parser.py` | Git log tests |
| `tests/output_tests/test_git_show_parser.py` | Git show tests |
| `tests/output_tests/test_git_blame_parser.py` | Git blame tests |
| `tests/output_tests/test_git_branch_parser.py` | Git branch tests |
| `tests/output_tests/test_git_stash_parser.py` | Git stash tests |
| `tests/output_tests/test_kubectl_parser.py` | K8s tests |
| `tests/output_tests/test_docker_compose_parser.py` | Docker compose tests |
| `tests/output_tests/test_docker_ps_parser.py` | Docker ps tests |
| `tests/output_tests/test_docker_logs_parser.py` | Docker logs tests |
| `tests/output_tests/test_package_list_parser.py` | Package list tests |
| `tests/output_tests/test_file_listing_parser.py` | File listing tests |
| `tests/output_tests/test_search_results_parser.py` | Search results tests |
| `tests/output_tests/test_gh_cli_parser.py` | GH CLI tests |
| `tests/output_tests/test_env_redact_parser.py` | Env redact tests |
| `tests/output_tests/test_generic.py` | Generic fallback tests |
| `tests/output_tests/test_lint_grouper.py` | Lint grouper tests |
| `tests/output_tests/test_ratio_check.py` | Ratio check tests |
| `tests/hook_tests/__init__.py` | Hook test module |
| `tests/hook_tests/test_match.py` | Command matching tests |
| `tests/hook_tests/test_compress.py` | Compress CLI tests |
| `tests/hook_tests/test_hook.py` | Hook protocol tests |
| `tests/hook_tests/test_chain.py` | Chain splitting tests |
| `tests/hook_tests/test_integration.py` | Hook integration tests |

### Modified files

| File | Change |
|------|--------|
| `py/tokkit_output/__init__.py` | Add ratio check, lint grouper, generic fallback |
| `py/tokkit_output/parsers/__init__.py` | Register all new parsers |
| `py/tokkit_output/formatter.py` | Support lint grouper output |
| `py/tokkit_cli/main.py` | Add `compress` subcommand |
| `py/tokkit_cli/setup.py` | Write hook config in plugin |
| `py/tokkit_server/protocol.py` | Update tool descriptions, new hints |
| `README.md` | Dual-model docs, benchmarks |
| `skill/SKILL.md` | Hook model docs, updated guidance |
