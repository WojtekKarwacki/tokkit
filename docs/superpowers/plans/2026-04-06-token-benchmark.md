# Token Savings Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproducible benchmark proving tokkit saves tokens vs file-by-file exploration, running 5 structural questions against fastapi/fastapi.

**Architecture:** Each question has two implementations - a baseline (simulated agent doing grep+read) and a tokkit path (MCP tool call). Both measure actual bytes consumed. A pytest harness runs both, compares, and writes a Markdown report.

**Tech Stack:** Rust (tokkit-core), PyO3 (tokkit-py), Python (MCP server + pytest benchmark)

**Spec:** `docs/superpowers/specs/2026-04-06-token-benchmark-design.md`

---

### Task 1: Add `name_pattern` filter to `search_graph`

**Files:**
- Modify: `core/code/crates/tokkit-core/src/types.rs:284-289` (SearchFilters struct)
- Modify: `core/code/crates/tokkit-core/src/query/mod.rs:9-43` (search_nodes fn)
- Test: `core/code/crates/tokkit-core/src/query/mod.rs` (inline tests)

- [ ] **Step 1: Add `name_pattern` field to `SearchFilters`**

In `core/code/crates/tokkit-core/src/types.rs`, change:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchFilters {
    pub query: Option<String>,
    pub label: Option<NodeLabel>,
    pub file_path: Option<String>,
    pub limit: Option<u32>,
}
```

to:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchFilters {
    pub query: Option<String>,
    pub label: Option<NodeLabel>,
    pub file_path: Option<String>,
    pub limit: Option<u32>,
    pub name_pattern: Option<String>,
}
```

- [ ] **Step 2: Fix all existing SearchFilters constructions**

Add `name_pattern: None` to every existing `SearchFilters { ... }` literal. These are in:
- `core/code/crates/tokkit-core/src/query/mod.rs` tests (~line 338, 350)
- `core/code/crates/tokkit-py/src/lib.rs` (~line 73)

- [ ] **Step 3: Add regex filtering to `search_nodes`**

In `core/code/crates/tokkit-core/src/query/mod.rs`, add `use regex::Regex;` at the top, and inside the `.filter(|n| { ... })` closure, after the `label` check, add:

```rust
if let Some(pat) = &filters.name_pattern {
    if let Ok(re) = Regex::new(pat) {
        if !re.is_match(&n.name) {
            return false;
        }
    }
}
```

- [ ] **Step 4: Add `regex` dependency to Cargo.toml**

In `core/code/crates/tokkit-core/Cargo.toml`, add under `[dependencies]`:

```toml
regex = "1"
```

- [ ] **Step 5: Write test for name_pattern**

Add to the `mod tests` block in `core/code/crates/tokkit-core/src/query/mod.rs`:

```rust
#[test]
fn search_by_name_pattern() {
    let store = make_test_store();
    let filters = SearchFilters {
        query: None,
        label: None,
        file_path: None,
        limit: None,
        name_pattern: Some("auth.*".to_string()),
    };
    let results = search_nodes(&store, &filters).unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].name, "authenticate");
}

#[test]
fn search_name_pattern_no_match() {
    let store = make_test_store();
    let filters = SearchFilters {
        query: None,
        label: None,
        file_path: None,
        limit: None,
        name_pattern: Some("^zzz.*".to_string()),
    };
    let results = search_nodes(&store, &filters).unwrap();
    assert!(results.is_empty());
}
```

- [ ] **Step 6: Run tests**

Run: `cd /home/edge/code/research/tokkit/core/code && cargo test --workspace`
Expected: All tests pass including the two new ones.

- [ ] **Step 7: Commit**

```
git add -A && git commit -m "feat: add name_pattern regex filter to search_graph"
```

---

### Task 2: Add `max_degree` and `exclude_entry_points` filters to `search_graph`

**Files:**
- Modify: `core/code/crates/tokkit-core/src/types.rs:284-290` (SearchFilters)
- Modify: `core/code/crates/tokkit-core/src/query/mod.rs:9-43` (search_nodes)
- Test: `core/code/crates/tokkit-core/src/query/mod.rs` (inline tests)

- [ ] **Step 1: Add fields to SearchFilters**

Add two more fields to `SearchFilters`:

```rust
pub max_degree: Option<u32>,
pub exclude_entry_points: Option<bool>,
```

- [ ] **Step 2: Fix all existing SearchFilters constructions**

Add `max_degree: None, exclude_entry_points: None` to every `SearchFilters { ... }` literal (same files as Task 1 step 2, plus the tests added in Task 1).

- [ ] **Step 3: Implement degree filtering in search_nodes**

The current `search_nodes` loads all nodes and filters. After the existing filter loop, add a post-filter step that computes degree. Replace the current function body with:

```rust
pub fn search_nodes(store: &Store, filters: &SearchFilters) -> Result<Vec<Node>> {
    let limit = filters.limit.unwrap_or(50) as usize;
    let all = store.all_nodes()?;
    let mut results: Vec<Node> = all
        .into_iter()
        .filter(|n| {
            if let Some(q) = &filters.query {
                let q_lower = q.to_lowercase();
                let name_match = n.name.to_lowercase().contains(&q_lower);
                let qn_match = n.qualified_name.to_lowercase().contains(&q_lower);
                if !name_match && !qn_match {
                    return false;
                }
            }
            if let Some(label) = &filters.label
                && n.label != *label
            {
                return false;
            }
            if let Some(fp) = &filters.file_path {
                match &n.file_path {
                    Some(nfp) => {
                        if !nfp.contains(fp.as_str()) {
                            return false;
                        }
                    }
                    None => return false,
                }
            }
            if let Some(pat) = &filters.name_pattern {
                if let Ok(re) = Regex::new(pat) {
                    if !re.is_match(&n.name) {
                        return false;
                    }
                }
            }
            if filters.exclude_entry_points == Some(true) {
                let dominated_names = ["main", "__main__", "__init__"];
                if dominated_names.iter().any(|&ep| n.name == ep) {
                    return false;
                }
                if n.name.starts_with("test_") || n.name.starts_with("Test") {
                    return false;
                }
                if n.label == NodeLabel::Route {
                    return false;
                }
            }
            true
        })
        .collect();

    // Post-filter: max_degree (requires edge lookups)
    if let Some(max_deg) = filters.max_degree {
        results.retain(|n| {
            let out_edges = store.get_edges_from(n.id).unwrap_or_default();
            let in_edges = store.get_edges_to(n.id).unwrap_or_default();
            let total_degree = out_edges.len() + in_edges.len();
            total_degree <= max_deg as usize
        });
    }

    results.truncate(limit);
    Ok(results)
}
```

- [ ] **Step 4: Write tests**

Add to the test module in `query/mod.rs`. The test store from `make_test_store()` has: `authenticate` (1 outbound CALLS edge), `get_user` (1 inbound CALLS edge), `UserService` (0 edges).

```rust
#[test]
fn search_max_degree_zero_finds_isolated() {
    let store = make_test_store();
    let filters = SearchFilters {
        query: None,
        label: None,
        file_path: None,
        limit: None,
        name_pattern: None,
        max_degree: Some(0),
        exclude_entry_points: None,
    };
    let results = search_nodes(&store, &filters).unwrap();
    // Only UserService has 0 edges
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].name, "UserService");
}

#[test]
fn search_exclude_entry_points() {
    let store = Store::open_memory().expect("open_memory");
    let mut buf = GraphBuffer::new("proj", "/root");
    buf.add_node(NodeLabel::Function, "main", "proj::main", Some("main.py".to_string()), 1, 5);
    buf.add_node(NodeLabel::Function, "test_foo", "proj::test_foo", Some("test.py".to_string()), 1, 5);
    buf.add_node(NodeLabel::Function, "helper", "proj::helper", Some("lib.py".to_string()), 1, 5);
    store.write_graph(&buf).unwrap();

    let filters = SearchFilters {
        query: None,
        label: None,
        file_path: None,
        limit: None,
        name_pattern: None,
        max_degree: None,
        exclude_entry_points: Some(true),
    };
    let results = search_nodes(&store, &filters).unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].name, "helper");
}
```

- [ ] **Step 5: Run tests**

Run: `cd /home/edge/code/research/tokkit/core/code && cargo test --workspace`
Expected: All pass.

- [ ] **Step 6: Commit**

```
git add -A && git commit -m "feat: add max_degree and exclude_entry_points to search_graph"
```

---

### Task 3: Add `relationship` filter to `search_graph`

**Files:**
- Modify: `core/code/crates/tokkit-core/src/types.rs` (SearchFilters)
- Modify: `core/code/crates/tokkit-core/src/query/mod.rs` (search_nodes)
- Test: `core/code/crates/tokkit-core/src/query/mod.rs` (inline tests)

- [ ] **Step 1: Add `relationship` field to SearchFilters**

```rust
pub relationship: Option<String>,
```

- [ ] **Step 2: Fix all SearchFilters constructions**

Add `relationship: None` everywhere.

- [ ] **Step 3: Implement relationship filtering**

Add to the post-filter section of `search_nodes`, after the `max_degree` block:

```rust
if let Some(ref rel) = filters.relationship {
    results.retain(|n| {
        let out_edges = store.get_edges_from(n.id).unwrap_or_default();
        let in_edges = store.get_edges_to(n.id).unwrap_or_default();
        out_edges.iter().any(|e| e.edge_type.as_str() == rel)
            || in_edges.iter().any(|e| e.edge_type.as_str() == rel)
    });
}
```

- [ ] **Step 4: Write test**

```rust
#[test]
fn search_by_relationship() {
    let store = make_test_store();
    let filters = SearchFilters {
        query: None,
        label: None,
        file_path: None,
        limit: None,
        name_pattern: None,
        max_degree: None,
        exclude_entry_points: None,
        relationship: Some("CALLS".to_string()),
    };
    let results = search_nodes(&store, &filters).unwrap();
    // authenticate has outbound CALLS, get_user has inbound CALLS
    assert_eq!(results.len(), 2);
    let names: Vec<&str> = results.iter().map(|n| n.name.as_str()).collect();
    assert!(names.contains(&"authenticate"));
    assert!(names.contains(&"get_user"));
}
```

- [ ] **Step 5: Run tests**

Run: `cd /home/edge/code/research/tokkit/core/code && cargo test --workspace`
Expected: All pass.

- [ ] **Step 6: Commit**

```
git add -A && git commit -m "feat: add relationship edge-type filter to search_graph"
```

---

### Task 4: Add fan-out `trace_path` mode

**Files:**
- Modify: `core/code/crates/tokkit-core/src/query/mod.rs:45-113` (trace_path fn)
- Modify: `core/code/crates/tokkit-core/src/query/mod.rs` (add trace_fan fn)
- Test: `core/code/crates/tokkit-core/src/query/mod.rs` (inline tests)

The existing `trace_path(from, to, max_depth)` does point-to-point BFS. We need a new function `trace_fan` that does fan-out/fan-in from a single starting node. Keep the existing `trace_path` for backward compatibility.

- [ ] **Step 1: Write the `trace_fan` function**

Add to `core/code/crates/tokkit-core/src/query/mod.rs`:

```rust
pub fn trace_fan(
    store: &Store,
    start_qn: &str,
    direction: &str, // "inbound", "outbound", "both"
    max_depth: u32,
) -> Result<Vec<PathStep>> {
    let start_node = match store.get_node(start_qn)? {
        Some(n) => n,
        None => return Ok(vec![]),
    };

    let mut results: Vec<PathStep> = Vec::new();
    let mut queue: VecDeque<(u64, u32)> = VecDeque::new();
    let mut visited: HashSet<u64> = HashSet::new();

    results.push(PathStep {
        node: start_node.clone(),
        edge: None,
        depth: 0,
    });
    visited.insert(start_node.id);
    queue.push_back((start_node.id, 0));

    while let Some((current_id, depth)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }

        let mut edges: Vec<Edge> = Vec::new();
        if direction == "outbound" || direction == "both" {
            edges.extend(store.get_edges_from(current_id)?);
        }
        if direction == "inbound" || direction == "both" {
            edges.extend(store.get_edges_to(current_id)?);
        }

        for edge in edges {
            let next_id = if edge.source_id == current_id {
                edge.target_id
            } else {
                edge.source_id
            };

            if visited.contains(&next_id) {
                continue;
            }
            visited.insert(next_id);

            if let Some(next_node) = store.get_node_by_id(next_id)? {
                results.push(PathStep {
                    node: next_node,
                    edge: Some(edge),
                    depth: depth + 1,
                });
                queue.push_back((next_id, depth + 1));
            }
        }
    }

    Ok(results)
}
```

- [ ] **Step 2: Write tests**

```rust
#[test]
fn trace_fan_outbound() {
    let store = make_test_store();
    let path = trace_fan(&store, "proj::authenticate", "outbound", 3).unwrap();
    // authenticate -> get_user
    assert_eq!(path.len(), 2);
    assert_eq!(path[0].node.name, "authenticate");
    assert_eq!(path[0].depth, 0);
    assert_eq!(path[1].node.name, "get_user");
    assert_eq!(path[1].depth, 1);
}

#[test]
fn trace_fan_inbound() {
    let store = make_test_store();
    let path = trace_fan(&store, "proj::get_user", "inbound", 3).unwrap();
    assert_eq!(path.len(), 2);
    assert_eq!(path[0].node.name, "get_user");
    assert_eq!(path[1].node.name, "authenticate");
}

#[test]
fn trace_fan_depth_zero() {
    let store = make_test_store();
    let path = trace_fan(&store, "proj::authenticate", "outbound", 0).unwrap();
    // Only the start node
    assert_eq!(path.len(), 1);
    assert_eq!(path[0].node.name, "authenticate");
}
```

- [ ] **Step 3: Run tests**

Run: `cd /home/edge/code/research/tokkit/core/code && cargo test --workspace`
Expected: All pass.

- [ ] **Step 4: Commit**

```
git add -A && git commit -m "feat: add trace_fan for directional fan-out/fan-in tracing"
```

---

### Task 5: Expose new features through PyO3 bindings

**Files:**
- Modify: `core/code/crates/tokkit-py/src/lib.rs:64-81` (search_nodes fn)
- Modify: `core/code/crates/tokkit-py/src/lib.rs:83-95` (trace_path fn + add trace_fan)
- Modify: `core/code/crates/tokkit-py/src/lib.rs:279-294` (module registration)

- [ ] **Step 1: Update `search_nodes` to accept new params**

Replace the `search_nodes` function in `lib.rs`:

```rust
#[pyfunction]
#[pyo3(signature = (db_path, query, label = None, limit = None, name_pattern = None, max_degree = None, exclude_entry_points = None, relationship = None))]
fn search_nodes(
    db_path: &str,
    query: &str,
    label: Option<&str>,
    limit: Option<u32>,
    name_pattern: Option<String>,
    max_degree: Option<u32>,
    exclude_entry_points: Option<bool>,
    relationship: Option<String>,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let filters = SearchFilters {
        query: Some(query.to_string()),
        label: label.and_then(parse_label),
        file_path: None,
        limit,
        name_pattern,
        max_degree,
        exclude_entry_points,
        relationship,
    };
    let nodes = query::search_nodes(&store, &filters).map_err(to_py_err)?;
    to_json(&nodes)
}
```

- [ ] **Step 2: Add `trace_fan` binding**

Add a new function after the existing `trace_path`:

```rust
#[pyfunction]
#[pyo3(signature = (db_path, function_name, direction = "both", depth = 3))]
fn trace_fan(
    db_path: &str,
    function_name: &str,
    direction: &str,
    depth: u32,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let path = query::trace_fan(&store, function_name, direction, depth).map_err(to_py_err)?;
    to_json(&path)
}
```

- [ ] **Step 3: Register `trace_fan` in the module**

Add to the `tokkit_py` module function:

```rust
m.add_function(wrap_pyfunction!(trace_fan, m)?)?;
```

- [ ] **Step 4: Run Rust tests**

Run: `cd /home/edge/code/research/tokkit/core/code && cargo test --workspace`
Expected: All pass.

- [ ] **Step 5: Build the Python wheel**

Run: `cd /home/edge/code/research/tokkit/core/code/crates/tokkit-py && maturin develop --release`
Expected: Builds successfully, `tokkit_py` importable from Python.

- [ ] **Step 6: Commit**

```
git add -A && git commit -m "feat: expose search_graph filters and trace_fan via PyO3"
```

---

### Task 6: Wire new features through MCP server

**Files:**
- Modify: `server/tokkit_server/tools.py:57-66` (search_graph handler)
- Modify: `server/tokkit_server/tools.py` (add trace_fan handler)
- Modify: `server/tokkit_server/protocol.py` (add trace_fan to tool definitions)

- [ ] **Step 1: Update search_graph handler in tools.py**

Replace the `search_graph` block in `handle_tool_call`:

```python
if tool_name == "search_graph":
    if not _session_db_path:
        return _err("No project indexed in this session. Call index_repository first.")
    query = args.get("query", "")
    label = args.get("label")
    limit = args.get("limit")
    name_pattern = args.get("name_pattern")
    max_degree = args.get("max_degree")
    exclude_entry_points = args.get("exclude_entry_points")
    relationship = args.get("relationship")
    result = _call_rust(
        "search_nodes", _session_db_path, query,
        label=label, limit=limit, name_pattern=name_pattern,
        max_degree=max_degree, exclude_entry_points=exclude_entry_points,
        relationship=relationship,
    )
    meta = make_meta(tool_name, result, _session_project_path)
    return _ok(result, meta)
```

- [ ] **Step 2: Add trace_fan handler**

Add after the existing `trace_path` block:

```python
if tool_name == "trace_fan":
    if not _session_db_path:
        return _err("No project indexed in this session. Call index_repository first.")
    function_name = args.get("function_name", "")
    direction = args.get("direction", "both")
    depth = args.get("depth", 3)
    result = _call_rust("trace_fan", _session_db_path, function_name, direction=direction, depth=depth)
    meta = make_meta(tool_name, result, _session_project_path)
    return _ok(result, meta)
```

- [ ] **Step 3: Add trace_fan to protocol.py tool definitions**

Find the tools list in `protocol.py` and add the `trace_fan` tool definition. Read the file first to find the exact location.

- [ ] **Step 4: Run existing e2e tests**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/ -v`
Expected: All existing tests pass.

- [ ] **Step 5: Commit**

```
git add -A && git commit -m "feat: wire search_graph filters and trace_fan through MCP server"
```

---

### Task 7: Write benchmark config and fixtures

**Files:**
- Create: `e2e/benchmark/__init__.py`
- Create: `e2e/benchmark/config.py`
- Create: `e2e/benchmark/conftest.py`

- [ ] **Step 1: Create config.py**

```python
"""Benchmark configuration - pinned repo and constants."""

REPO_URL = "https://github.com/fastapi/fastapi.git"
# Pin to a specific commit for deterministic results.
# Update this SHA manually when you want to re-baseline.
REPO_SHA = "0.115.6"  # tag-based pin; replace with SHA after first clone
REPO_DIR_NAME = "fastapi"
CHARS_PER_TOKEN = 4

# Questions map to the original codebase-memory-mcp benchmark
QUESTIONS = [
    "Find function by pattern",
    "Trace call chain (depth 3)",
    "Dead code detection",
    "List all routes",
    "Architecture overview",
]
```

- [ ] **Step 2: Create conftest.py**

```python
"""Benchmark fixtures: clone repo, start MCP server."""

import json
import os
import subprocess
import sys

import pytest

from e2e.benchmark.config import REPO_URL, REPO_SHA, REPO_DIR_NAME

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
PYTHON = "/home/edge/code/.venv/bin/python3"


@pytest.fixture(scope="session")
def benchmark_repo():
    """Clone fastapi at pinned version, return path."""
    repo_path = os.path.join(CACHE_DIR, REPO_DIR_NAME)
    if not os.path.isdir(repo_path):
        os.makedirs(CACHE_DIR, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", REPO_SHA, REPO_URL, repo_path],
            check=True,
            capture_output=True,
        )
    return repo_path


@pytest.fixture(scope="session")
def benchmark_mcp(benchmark_repo):
    """Start MCP server and index the benchmark repo."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def call_tool(self, name, arguments=None):
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection")
            resp = json.loads(line)
            content = resp["result"]["content"][0]["text"]
            return content

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)

    client = McpClient(proc)

    # Initialize
    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()  # consume response

    # Index the benchmark repo
    client.call_tool("index_repository", {"path": benchmark_repo})

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()
```

- [ ] **Step 3: Create `__init__.py`**

Create empty `e2e/benchmark/__init__.py`.

- [ ] **Step 4: Verify fixtures work**

Create a minimal test in `e2e/benchmark/test_smoke.py`:

```python
def test_benchmark_repo_exists(benchmark_repo):
    import os
    assert os.path.isdir(benchmark_repo)
    assert os.path.isfile(os.path.join(benchmark_repo, "pyproject.toml"))


def test_benchmark_mcp_indexed(benchmark_mcp):
    import json
    result = benchmark_mcp.call_tool("index_status")
    status = json.loads(result)
    assert status["indexed"] is True
    assert status["node_count"] > 100
```

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/benchmark/test_smoke.py -v`
Expected: Both tests pass. The fastapi repo is cloned and indexed.

- [ ] **Step 5: Add `.cache` to .gitignore**

Append to `e2e/benchmark/.gitignore`:

```
.cache/
```

- [ ] **Step 6: Commit**

```
git add -A && git commit -m "feat: add benchmark fixtures - clone fastapi, start MCP server"
```

---

### Task 8: Write baseline measurement functions

**Files:**
- Create: `e2e/benchmark/baselines.py`

- [ ] **Step 1: Write baselines.py**

```python
"""Baseline measurements: simulate what an agent without tokkit would read."""

import os
import re
import subprocess
from pathlib import Path

from e2e.benchmark.config import CHARS_PER_TOKEN


def _count_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _py_files(repo_path: str) -> list[str]:
    """All .py files in the repo, excluding tests and __pycache__."""
    result = []
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", ".tox", ".mypy_cache"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
    return result


def baseline_find_function(repo_path: str, pattern: str = "Depends") -> int:
    """Q1: Find function by pattern.

    Agent would: grep for 'def <pattern>' -> read each matching file.
    """
    total_bytes = 0

    # Step 1: grep for the pattern
    grep_result = subprocess.run(
        ["grep", "-rl", f"def {pattern}", repo_path, "--include=*.py"],
        capture_output=True, text=True,
    )
    total_bytes += len(grep_result.stdout)

    # Step 2: read each matching file
    for line in grep_result.stdout.strip().splitlines():
        filepath = line.strip()
        if filepath and os.path.isfile(filepath):
            total_bytes += os.path.getsize(filepath)

    return total_bytes // CHARS_PER_TOKEN


def baseline_trace_calls(repo_path: str, start_func: str = "FastAPI.__init__", max_depth: int = 3) -> int:
    """Q2: Trace call chain depth 3.

    Agent would: find function file, read it, extract calls, grep for each, recurse.
    """
    total_bytes = 0
    visited_files: set[str] = set()
    visited_funcs: set[str] = set()

    def _trace(func_name: str, depth: int):
        nonlocal total_bytes
        if depth > max_depth or func_name in visited_funcs:
            return
        visited_funcs.add(func_name)

        # Grep for definition
        short_name = func_name.split(".")[-1]
        grep_result = subprocess.run(
            ["grep", "-rl", f"def {short_name}", repo_path, "--include=*.py"],
            capture_output=True, text=True,
        )
        total_bytes += len(grep_result.stdout)

        for line in grep_result.stdout.strip().splitlines():
            filepath = line.strip()
            if filepath and os.path.isfile(filepath) and filepath not in visited_files:
                visited_files.add(filepath)
                content = Path(filepath).read_text(errors="replace")
                total_bytes += len(content)

                # Extract call targets from the function body
                for match in re.findall(r"\b([a-zA-Z_]\w*)\s*\(", content):
                    if match not in {"if", "for", "while", "with", "return", "print", "len", "str", "int", "list", "dict", "set", "tuple", "isinstance", "type", "super", "range", "enumerate", "zip", "map", "filter"}:
                        _trace(match, depth + 1)

    _trace(start_func, 0)
    return total_bytes // CHARS_PER_TOKEN


def baseline_dead_code(repo_path: str) -> int:
    """Q3: Dead code detection.

    Agent would: read all .py files to find defs, then grep each name across repo.
    """
    total_bytes = 0
    all_files = _py_files(repo_path)
    func_names: list[str] = []

    # Step 1: read all files, collect function names
    for filepath in all_files:
        content = Path(filepath).read_text(errors="replace")
        total_bytes += len(content)
        for match in re.findall(r"^\s*def\s+(\w+)", content, re.MULTILINE):
            func_names.append(match)

    # Step 2: grep each function name across the repo
    for name in func_names:
        grep_result = subprocess.run(
            ["grep", "-r", name, repo_path, "--include=*.py", "-l"],
            capture_output=True, text=True,
        )
        total_bytes += len(grep_result.stdout)

    return total_bytes // CHARS_PER_TOKEN


def baseline_list_routes(repo_path: str) -> int:
    """Q4: List all routes.

    Agent would: grep for route decorators, read each matching file.
    """
    total_bytes = 0

    grep_result = subprocess.run(
        ["grep", "-rn", "-E", r"@(app|router)\.(get|post|put|delete|patch|options|head)", repo_path, "--include=*.py"],
        capture_output=True, text=True,
    )
    total_bytes += len(grep_result.stdout)

    # Read each unique matching file
    seen: set[str] = set()
    for line in grep_result.stdout.strip().splitlines():
        filepath = line.split(":")[0].strip()
        if filepath and os.path.isfile(filepath) and filepath not in seen:
            seen.add(filepath)
            total_bytes += os.path.getsize(filepath)

    return total_bytes // CHARS_PER_TOKEN


def baseline_architecture(repo_path: str) -> int:
    """Q5: Architecture overview.

    Agent would: glob the tree, read __init__.py files, read top-level modules.
    """
    total_bytes = 0

    # Step 1: file listing
    all_files = _py_files(repo_path)
    file_listing = "\n".join(all_files)
    total_bytes += len(file_listing)

    # Step 2: read all __init__.py
    for filepath in all_files:
        if filepath.endswith("__init__.py"):
            total_bytes += os.path.getsize(filepath)

    # Step 3: read top-level modules (files directly under fastapi/)
    fastapi_dir = os.path.join(repo_path, "fastapi")
    if os.path.isdir(fastapi_dir):
        for f in os.listdir(fastapi_dir):
            fp = os.path.join(fastapi_dir, f)
            if f.endswith(".py") and os.path.isfile(fp):
                total_bytes += os.path.getsize(fp)

    return total_bytes // CHARS_PER_TOKEN
```

- [ ] **Step 2: Verify baselines produce non-zero numbers**

Create `e2e/benchmark/test_baselines.py`:

```python
from e2e.benchmark.baselines import (
    baseline_find_function,
    baseline_trace_calls,
    baseline_dead_code,
    baseline_list_routes,
    baseline_architecture,
)


def test_baselines_nonzero(benchmark_repo):
    assert baseline_find_function(benchmark_repo) > 0
    assert baseline_trace_calls(benchmark_repo) > 0
    assert baseline_dead_code(benchmark_repo) > 0
    assert baseline_list_routes(benchmark_repo) > 0
    assert baseline_architecture(benchmark_repo) > 0
```

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/benchmark/test_baselines.py -v`
Expected: All pass.

- [ ] **Step 3: Commit**

```
git add -A && git commit -m "feat: add baseline measurement functions for 5 benchmark questions"
```

---

### Task 9: Write tokkit measurements and report generator

**Files:**
- Create: `e2e/benchmark/test_benchmark.py`

- [ ] **Step 1: Write the benchmark test**

```python
"""Token savings benchmark: 5 questions, tokkit vs baseline."""

import json
import os
from datetime import date

import pytest

from e2e.benchmark.baselines import (
    baseline_find_function,
    baseline_trace_calls,
    baseline_dead_code,
    baseline_list_routes,
    baseline_architecture,
)
from e2e.benchmark.config import CHARS_PER_TOKEN, QUESTIONS, REPO_SHA


def _tokkit_tokens(response_text: str) -> int:
    return len(response_text) // CHARS_PER_TOKEN


@pytest.mark.benchmark
class TestTokenBenchmark:
    """Run all 5 benchmark questions and generate report."""

    results: list[dict] = []

    def test_q1_find_function(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_find_function(benchmark_repo)
        response = benchmark_mcp.call_tool("search_graph", {
            "query": "",
            "name_pattern": "Depends.*",
        })
        tokkit = _tokkit_tokens(response)
        self.__class__.results.append({
            "question": QUESTIONS[0],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_q2_trace_calls(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_trace_calls(benchmark_repo)

        # First find a good starting function
        search_resp = benchmark_mcp.call_tool("search_graph", {
            "query": "FastAPI",
            "label": "Class",
        })
        nodes = json.loads(search_resp)
        assert len(nodes) > 0, "No FastAPI class found"
        start_qn = nodes[0]["qualified_name"]

        response = benchmark_mcp.call_tool("trace_fan", {
            "function_name": start_qn,
            "direction": "outbound",
            "depth": 3,
        })
        tokkit = _tokkit_tokens(response)
        self.__class__.results.append({
            "question": QUESTIONS[1],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_q3_dead_code(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_dead_code(benchmark_repo)
        response = benchmark_mcp.call_tool("search_graph", {
            "query": "",
            "max_degree": 0,
            "exclude_entry_points": True,
            "limit": 200,
        })
        tokkit = _tokkit_tokens(response)
        self.__class__.results.append({
            "question": QUESTIONS[2],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_q4_list_routes(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_list_routes(benchmark_repo)
        response = benchmark_mcp.call_tool("search_graph", {
            "query": "",
            "relationship": "HANDLES",
            "limit": 200,
        })
        tokkit = _tokkit_tokens(response)
        self.__class__.results.append({
            "question": QUESTIONS[3],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_q5_architecture(self, benchmark_repo, benchmark_mcp):
        baseline = baseline_architecture(benchmark_repo)
        response = benchmark_mcp.call_tool("get_architecture", {})
        tokkit = _tokkit_tokens(response)
        self.__class__.results.append({
            "question": QUESTIONS[4],
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_z_generate_report(self, benchmark_repo):
        """Run last (alphabetically). Writes BENCHMARK_RESULTS.md."""
        results = self.__class__.results
        if len(results) < 5:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in results)
        total_baseline = sum(r["baseline"] for r in results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        lines = [
            "# Tokkit Token Savings Benchmark",
            "",
            f"**Repo:** fastapi/fastapi @ `{REPO_SHA}`",
            f"**Date:** {date.today().isoformat()}",
            "",
            "| # | Question | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
            "|---|----------|----------------:|------------------:|----------:|------:|",
        ]

        for i, r in enumerate(results, 1):
            savings = (1 - r["tokkit"] / r["baseline"]) * 100 if r["baseline"] > 0 else 0
            ratio = r["baseline"] / r["tokkit"] if r["tokkit"] > 0 else 0
            lines.append(
                f"| {i} | {r['question']} | {r['tokkit']:,} | {r['baseline']:,} | {savings:.1f}% | {ratio:.0f}x |"
            )

        lines.append(
            f"| | **Total** | **{total_tokkit:,}** | **{total_baseline:,}** | **{total_savings:.1f}%** | **{total_ratio:.0f}x** |"
        )
        lines.extend([
            "",
            f"*Token estimate: len(bytes) / {CHARS_PER_TOKEN}. Both paths use the same constant.*",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "BENCHMARK_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
```

- [ ] **Step 2: Run the full benchmark**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/benchmark/test_benchmark.py -v -s`
Expected: All 5 questions pass (tokkit < baseline), report printed and written.

- [ ] **Step 3: Review the generated BENCHMARK_RESULTS.md**

Read the file and verify all numbers are non-zero and ratios make sense.

- [ ] **Step 4: Commit**

```
git add -A && git commit -m "feat: add token savings benchmark with 5 questions and report generator"
```

---

### Task 10: Clean up and final verification

**Files:**
- Modify: `e2e/benchmark/test_smoke.py` (delete - was temporary)
- Modify: `e2e/benchmark/test_baselines.py` (delete - was temporary)

- [ ] **Step 1: Remove temporary test files**

Delete `e2e/benchmark/test_smoke.py` and `e2e/benchmark/test_baselines.py`. Their assertions are covered by the main benchmark test.

- [ ] **Step 2: Run the complete test suite**

Run: `cd /home/edge/code/research/tokkit/core/code && cargo test --workspace`
Expected: All Rust tests pass.

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/ -v`
Expected: All tests pass (existing e2e + benchmark).

- [ ] **Step 3: Verify BENCHMARK_RESULTS.md looks correct**

Read the file. Verify:
- All 5 questions have non-zero tokkit and baseline numbers
- Savings > 0% for every question
- Ratios are realistic (expect 10x-200x range)
- Report date is correct

- [ ] **Step 4: Commit**

```
git add -A && git commit -m "chore: clean up temporary benchmark test files"
```
