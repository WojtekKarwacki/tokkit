# Tokkit — Design Spec

Port of codebase-memory-mcp (C) to a Rust core + Python MCP server for token-optimized code intelligence.

---

## 1. Product Goal

An MCP server that agents (Claude Code, Codex, etc.) connect to for token-efficient codebase understanding. The server combines a Rust code intelligence engine with a Python web scraping engine (built separately). Indexing a repository produces a knowledge graph that answers agent queries with structured results instead of raw source files — targeting 90%+ token reduction on code exploration tasks.

## 2. Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Languages supported | Python, JS, TS (others deferred) | Focus on user's target repos. 3 vs 66 cuts scope dramatically. |
| LSP resolvers | Skipped | 360K LOC of generated code for diminishing returns. Cascade resolution covers 85%+. |
| Storage engine | redb (pure Rust) | No C FFI, ACID, single-file, typed key-value. Replaces SQLite. |
| Query interface | Typed Rust functions | No Cypher interpreter. MCP tools map to fixed query patterns. Faster than interpreted queries. |
| Parser | tree-sitter (Rust crate) | Unified API across languages, trivially extensible, same parser as original. |
| Architecture | Idiomatic Rust library + PyO3 bindings | Smaller codebase, compiler-enforced correctness, independently testable core. |
| Python role | Thin MCP facade | Routes JSON-RPC to Rust engine or Python scraper. No graph logic in Python. |
| Testing e2e | MCP protocol + CLI smoke | Tests the actual agent interface. Both in dedicated e2e/ directory. |

## 3. Project Structure

```
tokkit/
├── core/
│   ├── code/                          # Rust workspace
│   │   ├── Cargo.toml                 # Workspace manifest
│   │   ├── crates/
│   │   │   ├── tokkit-core/           # Library crate — engine logic
│   │   │   │   ├── Cargo.toml
│   │   │   │   └── src/
│   │   │   │       ├── lib.rs         # Public API + central types
│   │   │   │       ├── discover/      # File walking + language detection
│   │   │   │       ├── extract/       # Tree-sitter parsing + symbol extraction
│   │   │   │       ├── resolve/       # Cross-file reference resolution
│   │   │   │       ├── graph/         # In-memory graph buffer
│   │   │   │       ├── store/         # redb persistence + indexes
│   │   │   │       ├── query/         # Typed query functions
│   │   │   │       ├── pipeline/      # Indexing orchestrator
│   │   │   │       └── enrich/        # Post-passes (tests, git, routes, similarity)
│   │   │   └── tokkit-py/            # PyO3 binding crate
│   │   │       ├── Cargo.toml
│   │   │       └── src/lib.rs
│   │   └── tests/                     # Rust integration tests
│   │       └── fixtures/              # Sample Python/JS/TS repos
│   └── scraper/                       # Python scraper (built separately by user)
│       ├── pyproject.toml
│       └── tokkit_scraper/
├── server/                            # Python MCP server
│   ├── pyproject.toml
│   ├── tokkit_server/
│   │   ├── __init__.py
│   │   ├── main.py                    # Entry point, stdio loop, CLI mode
│   │   ├── protocol.py                # JSON-RPC 2.0 parsing/building
│   │   ├── tools.py                   # Tool dispatch to Rust/scraper
│   │   └── watcher.py                 # Background change polling
│   └── tests/                         # Server unit tests
│       └── fixtures/
├── e2e/                               # E2E tests
│   ├── conftest.py
│   ├── fixtures/                      # E2E-specific test repos
│   ├── test_mcp_index.py
│   ├── test_mcp_query.py
│   └── test_cli_smoke.py
└── pyproject.toml                     # Root workspace
```

## 4. Rust Core — Module Design

### 4.1 Central Types (`lib.rs`)

Node labels and edge types are enums, not strings. Compile-time checked, exhaustive matching, zero-cost serialization via serde.

```rust
pub enum NodeLabel {
    Project, Folder, File,
    Function, Method, Class, Interface, Struct, Enum,
    Route, Test,
}

pub enum EdgeType {
    ContainsFile, ContainsFolder,
    Calls, CalledBy,
    Uses, UsedBy,
    Imports, TypeRef,
    Tests, CoChanged, SimilarTo,
    Handles, Configures,
}
```

Node and Edge structs carry typed fields plus a `HashMap<String, String>` for extensible properties.

Confidence is a newtype `Confidence(f64)` with named constructors for each resolution strategy.

### 4.2 discover/

Recursive directory walk with hardcoded skip patterns (node_modules, __pycache__, .git, dist, etc.) and suffix filters (.pyc, .png, .wasm, etc.). Uses the `ignore` crate for .gitignore support. Detects language by file extension — only accepts `.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`. Returns `Vec<FileInfo>`.

### 4.3 extract/

Tree-sitter parsing + AST walking. A `LanguageSpec` trait defines per-language node type tables:

```rust
pub trait LanguageSpec {
    fn language(&self) -> tree_sitter::Language;
    fn function_node_types(&self) -> &[&str];
    fn class_node_types(&self) -> &[&str];
    fn import_node_types(&self) -> &[&str];
    fn call_node_types(&self) -> &[&str];
    // ... additional categories
}
```

Three implementations: `PythonSpec`, `JavaScriptSpec`, `TypeScriptSpec`. The extractor is generic over `LanguageSpec` — adding a language means adding one trait impl.

Per-file extraction uses `bumpalo` arena for all temporary string allocations. Arena resets between files. Thread-local parsers reused across files (just switch language).

Output per file: `FileResult` containing vectors of definitions, calls, imports, usages, type references — all extracted symbols with their locations.

### 4.4 graph/

In-memory graph buffer using `hashbrown::HashMap` keyed by qualified name for O(1) node dedup. Edge dedup via `HashSet<(u64, u64, EdgeType)>`. Supports `merge()` for combining per-worker buffers after parallel extraction (rayon).

Each node gets a unique `u64` ID from an `AtomicU64` counter (safe across worker threads).

### 4.5 resolve/

Four-strategy cascade, each a pure function:

1. **Import map** (confidence 0.95) — resolve via file's import list
2. **Same module** (confidence 0.90) — caller and definition share module prefix
3. **Unique name** (confidence 0.75) — only one candidate project-wide
4. **Suffix match** (confidence 0.55) — multiple candidates, score by common prefix length

Registry: two `HashMap`s — `exact: qualified_name -> NodeLabel` and `by_name: simple_name -> Vec<qualified_name>`.

### 4.6 store/

redb persistence with typed tables:

| Table | Key | Value |
|---|---|---|
| `nodes` | `&str` (qualified_name) | `Node` (bincode serialized) |
| `nodes_by_label` | `(&str, &str)` (label, name) | `u64` (node_id) |
| `nodes_by_file` | `&str` (file_path) | `Vec<u64>` (node_ids) |
| `edges` | `(u64, u64, &str)` (src, tgt, type) | `Edge` (bincode serialized) |
| `edges_by_source` | `u64` (source_id) | `Vec<(u64, EdgeType)>` (targets) |
| `edges_by_target` | `u64` (target_id) | `Vec<(u64, EdgeType)>` (sources) |
| `file_hashes` | `(&str, &str)` (project, path) | `(i64, i64)` (mtime_ns, size) |
| `projects` | `&str` (name) | `ProjectMeta` (serialized) |

Writes use redb transactions. Reads use read transactions (lock-free concurrent reads).

### 4.7 query/

Typed query functions operating on `Store`:

- `search_nodes(filters)` — label, name pattern, file path filter
- `trace_path(from, to, max_depth)` — BFS traversal via edge adjacency tables
- `get_callers(qn)` / `get_callees(qn)` — direct edge lookups
- `get_snippet(qn)` — look up node file_path + line range, read source file
- `get_architecture(project)` — aggregate node/edge stats into structural summary
- `search_code(repo_path, pattern)` — grep (via `grep-searcher` crate) + graph enrichment
- `detect_changes(repo_path)` — compare file mtimes against stored hashes
- `index_status()` — node/edge counts, last index time

### 4.8 pipeline/

Orchestrator. Single-execution lock via `AtomicBool`. Steps:

1. Discover files
2. Check for incremental (compare file_hashes → only re-extract changed files)
3. Build structure (Project/Folder/File nodes + containment edges)
4. Extract symbols (parallel via `rayon::par_iter`, per-worker graph buffers, merge after)
5. Build registry from all definitions
6. Resolve cross-file references (parallel per file)
7. Enrich (test detection, git history, routes, similarity)
8. Persist to redb

### 4.9 enrich/

Independent post-passes, each a standalone function:

- `detect_tests()` — match test files to implementation files, create TESTS edges
- `git_history()` — parse git log via `gix`, create CO_CHANGED edges for frequently co-modified files
- `find_routes()` — detect HTTP endpoints (Flask/Express decorators), create Route nodes + HANDLES edges
- `compute_similarity()` — MinHash + LSH on function bodies, create SIMILAR_TO edges

## 5. PyO3 Binding Surface

12 `#[pyfunction]`s, one per MCP tool. Each takes simple types (strings, optional ints), does all work in Rust, returns a PyO3-compatible struct. The Python server never opens redb or touches the graph.

- `index_repository(path, mode) -> IndexResult`
- `search_nodes(db_path, query, label?, limit?) -> list[NodeResult]`
- `trace_path(db_path, from_qn, to_qn, max_depth?) -> list[PathStep]`
- `get_snippet(db_path, qualified_name, context_lines?) -> str`
- `get_architecture(db_path, project) -> ArchSummary`
- `search_code(db_path, repo_path, pattern, limit?) -> list[CodeMatch]`
- `detect_changes(db_path, repo_path) -> list[ChangedFile]`
- `index_status(db_path) -> StatusResult`
- `delete_project(db_path) -> bool`
- `list_projects(cache_dir) -> list[ProjectInfo]`
- `manage_adr(db_path, action, args) -> str`
- `get_graph_schema(db_path) -> SchemaResult`

## 6. Python MCP Server

Four modules:

- **`main.py`** — entry point. Two modes: MCP server (stdin/stdout JSON-RPC loop) and CLI (`tokkit cli <tool> <json>`). Signal handling for graceful shutdown. Starts watcher thread.
- **`protocol.py`** — JSON-RPC 2.0 implementation. Parses requests, builds responses/errors, handles `initialize`/`tools/list`/`tools/call`. Framework-free, stdlib json module.
- **`tools.py`** — tool registry mapping tool names to handler functions. Each handler validates input args, calls the appropriate `tokkit_py` Rust function or `tokkit_scraper` Python function, formats the result into MCP tool response format.
- **`watcher.py`** — background thread polling for file changes. On detection, calls `tokkit_py.index_repository()` with incremental mode. Configurable poll interval (default 5s).

Dependencies: `tokkit-py` (Rust bindings via maturin), `tokkit-scraper` (path dependency). No third-party Python packages for the server itself.

## 7. Testing Strategy

### Pyramid

```
         /  E2E (~15)  \        MCP protocol + CLI smoke
        /----------------\
       / Integration (~40) \    Full pipeline on fixture repos (Rust)
      /----------------------\
     /   Unit tests (~150+)    \ Per-module (Rust + Python)
    /____________________________\
```

### Rust unit tests

In-module `#[cfg(test)]` blocks:

- `discover/` — skip patterns, language detection, symlinks, empty dirs, gitignore
- `extract/` — per-language on small snippets: "this Python function produces this node with these fields"
- `resolve/` — each strategy in isolation with controlled inputs
- `graph/` — insert, dedup, merge, ID generation
- `store/` — redb round-trip (write → read → verify), index queries
- `query/` — each function against a pre-populated store
- `enrich/` — test detection patterns, route matching, similarity thresholds

### Rust integration tests (`core/code/tests/`)

Full pipeline runs on fixture repos:

- `test_python_repo` — small Python project (~15 files), verify node/edge counts, resolution correctness
- `test_js_repo` — Express.js project, verify route detection, import resolution
- `test_ts_repo` — TypeScript project, verify interface/type extraction, cross-file references
- `test_incremental` — index, modify a file, re-index, verify only changed file re-extracted
- `test_parallel_consistency` — index same repo with 1 worker vs N workers, verify identical results

### Python unit tests (`server/tests/`)

- `test_protocol.py` — JSON-RPC parsing, error responses, edge cases (malformed JSON, missing fields)
- `test_tools.py` — input validation, correct routing (mock PyO3 bindings)
- `test_watcher.py` — change detection logic, poll timing

### E2E tests (`e2e/`)

Spawn the MCP server as a subprocess. Send JSON-RPC over stdin, read stdout.

- `test_mcp_index.py` — initialize → index fixture repo → verify success response with node/edge counts
- `test_mcp_query.py` — index → search_nodes → trace_path → get_snippet → verify content correctness
- `test_cli_smoke.py` — `tokkit cli index_repository '{"path":"..."}' | check exit code + stdout JSON`

All fixtures are small, purpose-built repos. No network access. Deterministic.

## 8. Rust Dependencies

| Crate | Purpose | Replaces |
|---|---|---|
| `tree-sitter` | Parsing framework | tree-sitter C runtime |
| `tree-sitter-python` | Python grammar | vendored grammar |
| `tree-sitter-javascript` | JS grammar | vendored grammar |
| `tree-sitter-typescript` | TS grammar | vendored grammar |
| `redb` | Persistent storage | SQLite + sqlite_writer.c |
| `rayon` | Parallel extraction | worker_pool.c |
| `hashbrown` | Fast hash maps | hash_table.c |
| `bumpalo` | Arena allocator | arena.c |
| `pyo3` | Python bindings | N/A |
| `maturin` | Build Python wheels from Rust | N/A |
| `serde` + `serde_json` | Serialization | manual JSON + yyjson |
| `bincode` | Binary serialization for redb values | N/A |
| `ignore` | .gitignore-aware walking | discover.c gitignore code |
| `gix` | Git history parsing | git subprocess calls |
| `grep-regex` + `grep-searcher` | Code search | grep subprocess |

## 9. Distribution

`pip install tokkit` — maturin builds the Rust core into a platform wheel. The Python server, Rust engine, and scraper all install as one package. No separate Rust binary to manage.

CLI entry point: `tokkit` (via pyproject.toml `[project.scripts]`).

## 10. Future Work (Deferred)

- [ ] Additional languages (Go, Rust, Java, C/C++, Ruby, etc.) — add `LanguageSpec` trait impls
- [ ] LSP-enhanced resolution for specific languages
- [ ] Direct B-tree/page-level redb optimization if bulk loading is slow
- [ ] Cypher query support if ad-hoc queries prove necessary
- [ ] HTTP UI for graph visualization (port React/Three.js frontend)
- [ ] WASM target for browser-based indexing
