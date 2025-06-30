# Tokkit Python Server + PyO3 Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build PyO3 bindings for tokkit-core and a Python MCP server that agents connect to for token-efficient code intelligence.

**Architecture:** Thin Python MCP facade routing JSON-RPC requests to Rust engine via PyO3. Server is stdlib-only (no frameworks). E2E tests verify the full stack.

**Tech Stack:** Python 3.11+, PyO3, maturin, pytest

**Spec:** `docs/superpowers/specs/2026-04-04-tokkit-port-design.md`

**Depends on:** Plan 1 (Rust Core) — complete.

---

## File Map

```
tokkit/
├── core/
│   ├── code/
│   │   └── crates/
│   │       └── tokkit-py/
│   │           ├── Cargo.toml          # Already exists, update deps
│   │           └── src/lib.rs          # PyO3 bindings (rewrite)
│   └── scraper/                        # Stub only — user builds this
│       ├── pyproject.toml
│       └── tokkit_scraper/__init__.py
├── server/
│   ├── pyproject.toml
│   └── tokkit_server/
│       ├── __init__.py
│       ├── main.py                     # Entry point: stdio MCP + CLI mode
│       ├── protocol.py                 # JSON-RPC 2.0 parsing/building
│       ├── tools.py                    # Tool dispatch to Rust/scraper
│       └── watcher.py                  # Background file change polling
│   └── tests/
│       ├── __init__.py
│       ├── test_protocol.py
│       ├── test_tools.py
│       └── fixtures/
├── e2e/
│   ├── conftest.py
│   ├── fixtures/                       # Small test repos
│   │   └── sample_project/
│   ├── test_mcp_index.py
│   ├── test_mcp_query.py
│   └── test_cli_smoke.py
└── pyproject.toml                      # Root workspace
```

---

## Task 1: PyO3 Bindings

**Files:**
- Modify: `tokkit/core/code/crates/tokkit-py/Cargo.toml`
- Rewrite: `tokkit/core/code/crates/tokkit-py/src/lib.rs`

- [ ] **Step 1: Update tokkit-py Cargo.toml**

Add serde_json dependency for result serialization:

```toml
[package]
name = "tokkit-py"
version.workspace = true
edition.workspace = true

[lib]
name = "tokkit_py"
crate-type = ["cdylib"]

[dependencies]
tokkit-core.workspace = true
pyo3 = { version = "0.23", features = ["extension-module"] }
serde_json = "1"
```

- [ ] **Step 2: Write PyO3 bindings**

Rewrite `src/lib.rs` with 12 `#[pyfunction]`s. Each function:
- Takes simple Python types (str, Optional[int])
- Calls tokkit-core functions
- Returns Python dicts/lists via serde_json serialization

```rust
use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use tokkit_core::types::*;
use tokkit_core::{pipeline, store, query};

fn to_py_err(e: tokkit_core::TokkitError) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

fn to_json_string<T: serde::Serialize>(val: &T) -> PyResult<String> {
    serde_json::to_string(val).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (path, mode = "full"))]
fn index_repository(path: &str, mode: &str) -> PyResult<String> {
    let idx_mode = match mode {
        "fast" => IndexMode::Fast,
        _ => IndexMode::Full,
    };

    // Derive db_path from project name
    let project = std::path::Path::new(path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown");
    let cache_dir = dirs::cache_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("/tmp"))
        .join("tokkit");
    std::fs::create_dir_all(&cache_dir).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let db_path = cache_dir.join(format!("{project}.redb"));

    if !pipeline::try_lock() {
        return Err(PyRuntimeError::new_err("Pipeline busy — another index is running"));
    }
    let result = pipeline::run(path, db_path.to_str().unwrap(), idx_mode)
        .map_err(to_py_err);
    pipeline::unlock();

    to_json_string(&result?)
}

#[pyfunction]
#[pyo3(signature = (db_path, query, label = None, limit = None))]
fn search_nodes(db_path: &str, query: &str, label: Option<&str>, limit: Option<u32>) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    let label_enum = label.and_then(|l| parse_label(l));
    let filters = SearchFilters {
        query: Some(query.to_string()),
        label: label_enum,
        file_path: None,
        limit,
    };
    let results = query::search_nodes(&s, filters).map_err(to_py_err)?;
    to_json_string(&results)
}

#[pyfunction]
#[pyo3(signature = (db_path, from_qn, to_qn, max_depth = None))]
fn trace_path(db_path: &str, from_qn: &str, to_qn: &str, max_depth: Option<u32>) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    let path = query::trace_path(&s, from_qn, to_qn, max_depth.unwrap_or(5)).map_err(to_py_err)?;
    to_json_string(&path)
}

#[pyfunction]
#[pyo3(signature = (db_path, qualified_name, repo_path, context_lines = None))]
fn get_snippet(db_path: &str, qualified_name: &str, repo_path: &str, context_lines: Option<u32>) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    let snippet = query::get_snippet(&s, qualified_name, repo_path, context_lines.unwrap_or(3)).map_err(to_py_err)?;
    to_json_string(&snippet)
}

#[pyfunction]
fn get_architecture(db_path: &str, project: &str) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    // Build basic architecture summary from graph data
    let nodes = s.all_nodes().map_err(to_py_err)?;
    let edges = s.all_edges().map_err(to_py_err)?;

    let mut languages = std::collections::HashSet::new();
    let mut top_files = Vec::new();
    let mut packages = Vec::new();

    for n in &nodes {
        if let Some(ref fp) = n.file_path {
            if let Some(ext) = fp.rsplit('.').next() {
                languages.insert(ext.to_string());
            }
        }
        if n.label == NodeLabel::File {
            top_files.push(n.name.clone());
        }
        if n.label == NodeLabel::Folder {
            packages.push(n.name.clone());
        }
    }

    top_files.truncate(20);
    packages.truncate(20);

    let summary = ArchSummary {
        project_name: project.to_string(),
        languages: languages.into_iter().collect(),
        top_files,
        entry_points: Vec::new(),
        packages,
        summary: format!("{} nodes, {} edges", nodes.len(), edges.len()),
    };
    to_json_string(&summary)
}

#[pyfunction]
#[pyo3(signature = (db_path, repo_path, pattern, limit = None))]
fn search_code(db_path: &str, repo_path: &str, pattern: &str, limit: Option<u32>) -> PyResult<String> {
    // Basic grep-based search — full implementation in future
    let _ = (db_path, repo_path, pattern, limit);
    to_json_string(&Vec::<CodeMatch>::new())
}

#[pyfunction]
fn detect_changes(db_path: &str, repo_path: &str) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    let mode = IndexMode::Full;
    let files = tokkit_core::discover::discover(repo_path, mode).map_err(to_py_err)?;
    let project = std::path::Path::new(repo_path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown");
    let changes = query::detect_changes(&s, project, repo_path, &files).map_err(to_py_err)?;
    to_json_string(&changes)
}

#[pyfunction]
fn index_status(db_path: &str) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    let status = query::index_status(&s).map_err(to_py_err)?;
    to_json_string(&status)
}

#[pyfunction]
fn delete_project(db_path: &str) -> PyResult<bool> {
    if std::path::Path::new(db_path).exists() {
        std::fs::remove_file(db_path).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(true)
    } else {
        Ok(false)
    }
}

#[pyfunction]
fn list_projects(cache_dir: &str) -> PyResult<String> {
    let mut projects = Vec::new();
    let path = std::path::Path::new(cache_dir);
    if path.is_dir() {
        if let Ok(entries) = std::fs::read_dir(path) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.extension().is_some_and(|e| e == "redb") {
                    let name = p.file_stem()
                        .and_then(|n| n.to_str())
                        .unwrap_or("unknown")
                        .to_string();
                    if let Ok(s) = store::Store::open(p.to_str().unwrap_or("")) {
                        let nc = s.node_count().unwrap_or(0);
                        let ec = s.edge_count().unwrap_or(0);
                        projects.push(ProjectInfo {
                            name,
                            db_path: p.to_string_lossy().to_string(),
                            node_count: nc,
                            edge_count: ec,
                        });
                    }
                }
            }
        }
    }
    to_json_string(&projects)
}

#[pyfunction]
fn get_graph_schema(db_path: &str) -> PyResult<String> {
    let s = store::Store::open(db_path).map_err(to_py_err)?;
    let schema = query::get_graph_schema(&s).map_err(to_py_err)?;
    to_json_string(&schema)
}

#[pyfunction]
fn manage_adr(_db_path: &str, _action: &str, _args: &str) -> PyResult<String> {
    // Stub — ADR management is a future feature
    Ok("{}".to_string())
}

fn parse_label(s: &str) -> Option<NodeLabel> {
    match s {
        "Project" => Some(NodeLabel::Project),
        "Folder" => Some(NodeLabel::Folder),
        "File" => Some(NodeLabel::File),
        "Function" => Some(NodeLabel::Function),
        "Method" => Some(NodeLabel::Method),
        "Class" => Some(NodeLabel::Class),
        "Interface" => Some(NodeLabel::Interface),
        "Struct" => Some(NodeLabel::Struct),
        "Enum" => Some(NodeLabel::Enum),
        "Variable" => Some(NodeLabel::Variable),
        "Route" => Some(NodeLabel::Route),
        "Test" => Some(NodeLabel::Test),
        _ => None,
    }
}

#[pymodule]
fn tokkit_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(index_repository, m)?)?;
    m.add_function(wrap_pyfunction!(search_nodes, m)?)?;
    m.add_function(wrap_pyfunction!(trace_path, m)?)?;
    m.add_function(wrap_pyfunction!(get_snippet, m)?)?;
    m.add_function(wrap_pyfunction!(get_architecture, m)?)?;
    m.add_function(wrap_pyfunction!(search_code, m)?)?;
    m.add_function(wrap_pyfunction!(detect_changes, m)?)?;
    m.add_function(wrap_pyfunction!(index_status, m)?)?;
    m.add_function(wrap_pyfunction!(delete_project, m)?)?;
    m.add_function(wrap_pyfunction!(list_projects, m)?)?;
    m.add_function(wrap_pyfunction!(get_graph_schema, m)?)?;
    m.add_function(wrap_pyfunction!(manage_adr, m)?)?;
    Ok(())
}
```

Note: Add `dirs = "6"` to tokkit-py Cargo.toml dependencies for cache_dir resolution.

- [ ] **Step 3: Verify Rust compilation**

Run: `cd tokkit/core/code && cargo check --workspace`
Expected: Compiles without errors.

- [ ] **Step 4: Build the Python wheel**

Run: `cd tokkit/core/code/crates/tokkit-py && pip install maturin && maturin develop`
Expected: tokkit_py importable in Python.

- [ ] **Step 5: Quick Python smoke test**

```python
python3 -c "import tokkit_py; print(tokkit_py.__version__)"
```

- [ ] **Step 6: Commit**

```bash
git add tokkit/core/code/crates/tokkit-py/
git commit -m "feat(py): add PyO3 bindings for tokkit-core (12 functions)"
```

---

## Task 2: Scraper Stub

**Files:**
- Create: `tokkit/core/scraper/pyproject.toml`
- Create: `tokkit/core/scraper/tokkit_scraper/__init__.py`

- [ ] **Step 1: Create scraper stub**

```toml
# tokkit/core/scraper/pyproject.toml
[project]
name = "tokkit-scraper"
version = "0.1.0"
description = "Token-optimized web scraping engine"
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"
```

```python
# tokkit/core/scraper/tokkit_scraper/__init__.py
"""Tokkit Scraper — Token-optimized web scraping engine.

This module is a placeholder. Implement your scraping logic here.
"""

__version__ = "0.1.0"


def fetch_clean(url: str) -> str:
    """Fetch a URL and return token-optimized clean text.

    Placeholder — implement with trafilatura or similar.
    """
    raise NotImplementedError("Scraper not yet implemented")
```

- [ ] **Step 2: Commit**

```bash
git add tokkit/core/scraper/
git commit -m "feat(scraper): add scraper stub package"
```

---

## Task 3: Python MCP Server — Protocol Layer

**Files:**
- Create: `tokkit/server/pyproject.toml`
- Create: `tokkit/server/tokkit_server/__init__.py`
- Create: `tokkit/server/tokkit_server/protocol.py`
- Create: `tokkit/server/tests/__init__.py`
- Create: `tokkit/server/tests/test_protocol.py`

- [ ] **Step 1: Create server pyproject.toml**

```toml
# tokkit/server/pyproject.toml
[project]
name = "tokkit-server"
version = "0.1.0"
description = "MCP server for token-optimized code intelligence"
requires-python = ">=3.11"
dependencies = [
    "tokkit-scraper",
]

[project.scripts]
tokkit = "tokkit_server.main:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create __init__.py**

```python
# tokkit/server/tokkit_server/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 3: Write protocol.py — JSON-RPC 2.0**

```python
# tokkit/server/tokkit_server/protocol.py
"""JSON-RPC 2.0 protocol implementation for MCP."""

import json
from typing import Any


def parse_request(line: str) -> dict[str, Any]:
    """Parse a JSON-RPC 2.0 request from a line of text.

    Returns dict with keys: id, method, params.
    Raises ValueError on invalid JSON or missing fields.
    """
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Request must be a JSON object")

    return {
        "id": data.get("id"),
        "method": data.get("method", ""),
        "params": data.get("params", {}),
    }


def build_response(request_id: Any, result: Any) -> str:
    """Build a JSON-RPC 2.0 success response."""
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    })


def build_error(request_id: Any, code: int, message: str, data: Any = None) -> str:
    """Build a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error,
    })


# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603


# MCP tool definitions for tools/list
TOOL_DEFINITIONS = [
    {
        "name": "index_repository",
        "description": "Index a code repository into a knowledge graph for token-efficient querying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the repository root"},
                "mode": {"type": "string", "enum": ["full", "fast"], "default": "full"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_graph",
        "description": "Search the knowledge graph for nodes by name, label, or file path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (name substring match)"},
                "label": {"type": "string", "description": "Node label filter (Function, Class, etc.)"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "trace_path",
        "description": "Find the shortest path between two nodes in the knowledge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "Source node qualified name"},
                "to": {"type": "string", "description": "Target node qualified name"},
                "max_depth": {"type": "integer", "default": 5},
            },
            "required": ["from", "to"],
        },
    },
    {
        "name": "get_code_snippet",
        "description": "Get the source code for a specific symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "qualified_name": {"type": "string"},
                "context_lines": {"type": "integer", "default": 3},
            },
            "required": ["qualified_name"],
        },
    },
    {
        "name": "get_architecture",
        "description": "Get a structural overview of an indexed project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
            },
            "required": ["project"],
        },
    },
    {
        "name": "search_code",
        "description": "Search source code with grep and enrich results with graph context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "detect_changes",
        "description": "Detect files changed since last index.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "index_status",
        "description": "Check indexing status for the current project.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_projects",
        "description": "List all indexed projects.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "delete_project",
        "description": "Delete an indexed project's database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
            },
            "required": ["project"],
        },
    },
    {
        "name": "get_graph_schema",
        "description": "Get available node labels and edge types in the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def build_initialize_response(request_id: Any) -> str:
    """Build MCP initialize response with server capabilities."""
    return build_response(request_id, {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "tokkit", "version": "0.1.0"},
    })


def build_tools_list_response(request_id: Any) -> str:
    """Build MCP tools/list response."""
    return build_response(request_id, {"tools": TOOL_DEFINITIONS})
```

- [ ] **Step 4: Write test_protocol.py**

```python
# tokkit/server/tests/test_protocol.py
import json
import pytest
from tokkit_server.protocol import (
    parse_request,
    build_response,
    build_error,
    build_initialize_response,
    build_tools_list_response,
    PARSE_ERROR,
    METHOD_NOT_FOUND,
)


class TestParseRequest:
    def test_parses_valid_request(self):
        line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        req = parse_request(line)
        assert req["id"] == 1
        assert req["method"] == "initialize"
        assert req["params"] == {}

    def test_parses_request_without_params(self):
        line = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        req = parse_request(line)
        assert req["params"] == {}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_request("not json{{{")

    def test_raises_on_non_object(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_request('"just a string"')


class TestBuildResponse:
    def test_success_response(self):
        resp = build_response(1, {"status": "ok"})
        data = json.loads(resp)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["result"]["status"] == "ok"

    def test_error_response(self):
        resp = build_error(1, PARSE_ERROR, "bad input")
        data = json.loads(resp)
        assert data["error"]["code"] == PARSE_ERROR
        assert data["error"]["message"] == "bad input"

    def test_error_with_data(self):
        resp = build_error(1, METHOD_NOT_FOUND, "no such method", {"method": "foo"})
        data = json.loads(resp)
        assert data["error"]["data"]["method"] == "foo"


class TestMcpResponses:
    def test_initialize_response(self):
        resp = build_initialize_response(1)
        data = json.loads(resp)
        result = data["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "tokkit"

    def test_tools_list_response(self):
        resp = build_tools_list_response(1)
        data = json.loads(resp)
        tools = data["result"]["tools"]
        assert len(tools) >= 10
        tool_names = [t["name"] for t in tools]
        assert "index_repository" in tool_names
        assert "search_graph" in tool_names
        assert "trace_path" in tool_names
```

- [ ] **Step 5: Run protocol tests**

Run: `cd tokkit/server && pip install -e . && pytest tests/test_protocol.py -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add tokkit/server/ tokkit/core/scraper/
git commit -m "feat(server): add JSON-RPC protocol layer with MCP tool definitions"
```

---

## Task 4: Python MCP Server — Tool Dispatch + Main

**Files:**
- Create: `tokkit/server/tokkit_server/tools.py`
- Create: `tokkit/server/tokkit_server/main.py`
- Create: `tokkit/server/tokkit_server/watcher.py`
- Create: `tokkit/server/tests/test_tools.py`

- [ ] **Step 1: Write tools.py**

```python
# tokkit/server/tokkit_server/tools.py
"""Tool dispatch — routes MCP tool calls to Rust engine or Python scraper."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Track the current session's project for tools that need implicit context
_session_project_path: str | None = None
_session_db_path: str | None = None


def _cache_dir() -> str:
    """Get the tokkit cache directory."""
    base = os.environ.get("TOKKIT_CACHE_DIR")
    if base:
        return base
    xdg = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(xdg, "tokkit")


def _db_path_for_project(project_name: str) -> str:
    """Get the database path for a project."""
    return os.path.join(_cache_dir(), f"{project_name}.redb")


def _project_name(path: str) -> str:
    """Extract project name from path."""
    return os.path.basename(os.path.abspath(path))


def handle_tool_call(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Route a tool call to the appropriate handler.

    Returns MCP tool result content (list of content blocks).
    """
    try:
        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return _error_result(f"Unknown tool: {tool_name}")
        result = handler(args)
        return _text_result(result)
    except Exception as e:
        logger.exception("Tool call failed: %s", tool_name)
        return _error_result(str(e))


def _text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _error_result(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Error: {message}"}], "isError": True}


def _call_rust(fn_name: str, *args, **kwargs) -> str:
    """Call a tokkit_py Rust function. Lazy import to allow testing without Rust."""
    import tokkit_py
    fn = getattr(tokkit_py, fn_name)
    return fn(*args, **kwargs)


# --- Tool handlers ---

def _handle_index_repository(args: dict) -> str:
    global _session_project_path, _session_db_path
    path = args.get("path", "")
    mode = args.get("mode", "full")
    if not path:
        raise ValueError("path is required")
    _session_project_path = path
    _session_db_path = _db_path_for_project(_project_name(path))
    return _call_rust("index_repository", path, mode)


def _handle_search_graph(args: dict) -> str:
    db_path = _session_db_path
    if not db_path:
        raise ValueError("No project indexed in this session. Call index_repository first.")
    query = args.get("query", "")
    label = args.get("label")
    limit = args.get("limit")
    return _call_rust("search_nodes", db_path, query, label, limit)


def _handle_trace_path(args: dict) -> str:
    db_path = _session_db_path
    if not db_path:
        raise ValueError("No project indexed. Call index_repository first.")
    return _call_rust("trace_path", db_path, args["from"], args["to"], args.get("max_depth"))


def _handle_get_code_snippet(args: dict) -> str:
    db_path = _session_db_path
    repo_path = _session_project_path
    if not db_path or not repo_path:
        raise ValueError("No project indexed. Call index_repository first.")
    return _call_rust("get_snippet", db_path, args["qualified_name"], repo_path, args.get("context_lines"))


def _handle_get_architecture(args: dict) -> str:
    db_path = _session_db_path
    if not db_path:
        raise ValueError("No project indexed. Call index_repository first.")
    project = args.get("project", "")
    return _call_rust("get_architecture", db_path, project)


def _handle_search_code(args: dict) -> str:
    db_path = _session_db_path
    repo_path = _session_project_path
    if not db_path or not repo_path:
        raise ValueError("No project indexed. Call index_repository first.")
    return _call_rust("search_code", db_path, repo_path, args["pattern"], args.get("limit"))


def _handle_detect_changes(args: dict) -> str:
    db_path = _session_db_path
    repo_path = _session_project_path
    if not db_path or not repo_path:
        raise ValueError("No project indexed. Call index_repository first.")
    return _call_rust("detect_changes", db_path, repo_path)


def _handle_index_status(args: dict) -> str:
    db_path = _session_db_path
    if not db_path:
        return json.dumps({"indexed": False, "node_count": 0, "edge_count": 0})
    return _call_rust("index_status", db_path)


def _handle_list_projects(args: dict) -> str:
    return _call_rust("list_projects", _cache_dir())


def _handle_delete_project(args: dict) -> str:
    project = args.get("project", "")
    db_path = _db_path_for_project(project)
    import tokkit_py
    deleted = tokkit_py.delete_project(db_path)
    return json.dumps({"deleted": deleted})


def _handle_get_graph_schema(args: dict) -> str:
    db_path = _session_db_path
    if not db_path:
        raise ValueError("No project indexed. Call index_repository first.")
    return _call_rust("get_graph_schema", db_path)


TOOL_HANDLERS = {
    "index_repository": _handle_index_repository,
    "search_graph": _handle_search_graph,
    "trace_path": _handle_trace_path,
    "get_code_snippet": _handle_get_code_snippet,
    "get_architecture": _handle_get_architecture,
    "search_code": _handle_search_code,
    "detect_changes": _handle_detect_changes,
    "index_status": _handle_index_status,
    "list_projects": _handle_list_projects,
    "delete_project": _handle_delete_project,
    "get_graph_schema": _handle_get_graph_schema,
}
```

- [ ] **Step 2: Write watcher.py**

```python
# tokkit/server/tokkit_server/watcher.py
"""Background file change watcher."""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class Watcher:
    """Polls for file changes and triggers re-indexing."""

    def __init__(self, poll_interval: float = 5.0):
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._project_path: str | None = None

    def set_project(self, path: str) -> None:
        self._project_path = path

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self.poll_interval)
            if self._stop_event.is_set():
                break
            if self._project_path:
                self._check_and_reindex()

    def _check_and_reindex(self) -> None:
        try:
            from tokkit_server.tools import handle_tool_call
            result = handle_tool_call("detect_changes", {})
            # If changes detected, trigger incremental re-index
            content = result.get("content", [{}])
            if content and not result.get("isError"):
                text = content[0].get("text", "[]")
                import json
                changes = json.loads(text)
                if changes:
                    logger.info("Watcher detected %d changes, re-indexing", len(changes))
                    handle_tool_call("index_repository", {
                        "path": self._project_path,
                        "mode": "full",
                    })
        except Exception:
            logger.debug("Watcher check failed", exc_info=True)
```

- [ ] **Step 3: Write main.py**

```python
# tokkit/server/tokkit_server/main.py
"""Tokkit MCP server entry point."""

import json
import logging
import signal
import sys
from typing import TextIO

from tokkit_server.protocol import (
    parse_request,
    build_response,
    build_error,
    build_initialize_response,
    build_tools_list_response,
    PARSE_ERROR,
    METHOD_NOT_FOUND,
    INTERNAL_ERROR,
)
from tokkit_server.tools import handle_tool_call
from tokkit_server.watcher import Watcher

logger = logging.getLogger(__name__)

_shutdown = False


def _signal_handler(sig, frame):
    global _shutdown
    _shutdown = True


def serve_stdio(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Run the MCP server on stdin/stdout."""
    global _shutdown

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    watcher = Watcher()
    initialized = False

    while not _shutdown:
        try:
            line = stdin.readline()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            break

        line = line.strip()
        if not line:
            continue

        # Handle Content-Length framing
        if line.startswith("Content-Length:"):
            length = int(line.split(":")[1].strip())
            stdin.readline()  # empty line
            line = stdin.read(length)

        try:
            req = parse_request(line)
        except ValueError:
            stdout.write(build_error(None, PARSE_ERROR, "Parse error") + "\n")
            stdout.flush()
            continue

        request_id = req["id"]
        method = req["method"]
        params = req["params"]

        response = dispatch(method, params, request_id, watcher)

        if method == "initialize":
            initialized = True

        if response:
            stdout.write(response + "\n")
            stdout.flush()

    watcher.stop()
    return 0


def dispatch(method: str, params: dict, request_id, watcher: Watcher) -> str | None:
    """Dispatch a JSON-RPC method to the appropriate handler."""
    if method == "initialize":
        return build_initialize_response(request_id)

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return build_tools_list_response(request_id)

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = handle_tool_call(tool_name, tool_args)

        # If index_repository was called, update watcher
        if tool_name == "index_repository" and not result.get("isError"):
            path = tool_args.get("path", "")
            if path:
                watcher.set_project(path)
                watcher.start()

        return build_response(request_id, result)

    return build_error(request_id, METHOD_NOT_FOUND, f"Unknown method: {method}")


def run_cli(args: list[str]) -> int:
    """Run a single tool call from CLI."""
    if len(args) < 1:
        print("Usage: tokkit cli <tool_name> [json_args]", file=sys.stderr)
        return 1

    tool_name = args[0]
    tool_args_str = args[1] if len(args) > 1 else "{}"

    try:
        tool_args = json.loads(tool_args_str)
    except json.JSONDecodeError:
        print(f"Invalid JSON args: {tool_args_str}", file=sys.stderr)
        return 1

    result = handle_tool_call(tool_name, tool_args)
    content = result.get("content", [])
    for block in content:
        if block.get("type") == "text":
            print(block["text"])

    return 1 if result.get("isError") else 0


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    args = sys.argv[1:]

    if not args:
        sys.exit(serve_stdio())
    elif args[0] == "cli":
        sys.exit(run_cli(args[1:]))
    elif args[0] in ("--version", "-v"):
        print("tokkit 0.1.0")
    elif args[0] in ("--help", "-h"):
        print("Usage:")
        print("  tokkit              Run MCP server on stdio")
        print("  tokkit cli <tool> [json]  Run a single tool")
        print("  tokkit --version    Print version")
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write test_tools.py (mock Rust bindings)**

```python
# tokkit/server/tests/test_tools.py
import json
import pytest
from unittest.mock import patch, MagicMock
from tokkit_server.tools import handle_tool_call, _text_result, _error_result


class TestToolDispatch:
    def test_unknown_tool_returns_error(self):
        result = handle_tool_call("nonexistent_tool", {})
        assert result.get("isError") is True
        assert "Unknown tool" in result["content"][0]["text"]

    @patch("tokkit_server.tools._call_rust")
    def test_index_repository_calls_rust(self, mock_rust):
        mock_rust.return_value = json.dumps({"project_name": "test", "node_count": 10, "edge_count": 5})
        result = handle_tool_call("index_repository", {"path": "/tmp/test"})
        assert result.get("isError") is None or result["isError"] is False
        mock_rust.assert_called_once_with("index_repository", "/tmp/test", "full")

    @patch("tokkit_server.tools._call_rust")
    def test_search_graph_requires_indexed_project(self, mock_rust):
        # Reset session state
        import tokkit_server.tools as tools_mod
        tools_mod._session_db_path = None
        result = handle_tool_call("search_graph", {"query": "test"})
        assert result.get("isError") is True
        assert "No project indexed" in result["content"][0]["text"]

    def test_text_result_format(self):
        result = _text_result("hello")
        assert result == {"content": [{"type": "text", "text": "hello"}]}

    def test_error_result_format(self):
        result = _error_result("bad thing")
        assert result["isError"] is True
        assert "bad thing" in result["content"][0]["text"]

    def test_index_status_without_session(self):
        import tokkit_server.tools as tools_mod
        tools_mod._session_db_path = None
        result = handle_tool_call("index_status", {})
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["indexed"] is False
```

- [ ] **Step 5: Run server tests**

Run: `cd tokkit/server && pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add tokkit/server/
git commit -m "feat(server): add MCP server with tool dispatch, CLI mode, and watcher"
```

---

## Task 5: E2E Tests

**Files:**
- Create: `tokkit/e2e/conftest.py`
- Create: `tokkit/e2e/fixtures/sample_project/` (small Python repo)
- Create: `tokkit/e2e/test_mcp_index.py`
- Create: `tokkit/e2e/test_mcp_query.py`
- Create: `tokkit/e2e/test_cli_smoke.py`
- Create: `tokkit/pyproject.toml` (root config)

- [ ] **Step 1: Create root pyproject.toml**

```toml
# tokkit/pyproject.toml
[project]
name = "tokkit"
version = "0.1.0"
description = "Token-optimized code intelligence for LLM agents"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["e2e", "server/tests"]
```

- [ ] **Step 2: Create e2e fixture**

`e2e/fixtures/sample_project/main.py`:
```python
from utils import helper

def main():
    result = helper()
    return result
```

`e2e/fixtures/sample_project/utils.py`:
```python
def helper():
    return 42

def unused():
    pass
```

- [ ] **Step 3: Write conftest.py**

```python
# tokkit/e2e/conftest.py
import json
import os
import subprocess
import sys
import tempfile
import pytest


@pytest.fixture
def sample_project_path():
    """Path to the sample Python fixture project."""
    return os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


@pytest.fixture
def mcp_server():
    """Start the MCP server as a subprocess and provide send/receive helpers."""
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

        def send(self, method: str, params: dict = None) -> dict:
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": method,
                "params": params or {},
            }
            line = json.dumps(request) + "\n"
            self.proc.stdin.write(line)
            self.proc.stdin.flush()

            # Read response
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

- [ ] **Step 4: Write test_mcp_index.py**

```python
# tokkit/e2e/test_mcp_index.py
import json
import pytest


def test_initialize_handshake(mcp_server):
    """MCP server responds to initialize with correct protocol version."""
    resp = mcp_server.send("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    })
    assert "result" in resp
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "tokkit"


def test_tools_list(mcp_server):
    """MCP server returns tool definitions."""
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "index_repository" in tool_names
    assert "search_graph" in tool_names
    assert len(tools) >= 10


def test_index_and_search(mcp_server, sample_project_path):
    """Full flow: initialize → index → search → verify results."""
    mcp_server.send("initialize", {})

    # Index
    resp = mcp_server.send("tools/call", {
        "name": "index_repository",
        "arguments": {"path": sample_project_path},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    result = json.loads(content)
    assert result["node_count"] > 0

    # Search
    resp = mcp_server.send("tools/call", {
        "name": "search_graph",
        "arguments": {"query": "helper"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    nodes = json.loads(content)
    assert len(nodes) > 0
```

- [ ] **Step 5: Write test_mcp_query.py**

```python
# tokkit/e2e/test_mcp_query.py
import json
import pytest


def test_index_status_before_indexing(mcp_server):
    """Index status returns not-indexed before any indexing."""
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "index_status",
        "arguments": {},
    })
    content = resp["result"]["content"][0]["text"]
    status = json.loads(content)
    assert status["indexed"] is False


def test_get_graph_schema(mcp_server, sample_project_path):
    """Graph schema returns labels and edge types after indexing."""
    mcp_server.send("initialize", {})
    mcp_server.send("tools/call", {
        "name": "index_repository",
        "arguments": {"path": sample_project_path},
    })
    resp = mcp_server.send("tools/call", {
        "name": "get_graph_schema",
        "arguments": {},
    })
    content = resp["result"]["content"][0]["text"]
    schema = json.loads(content)
    assert len(schema["node_labels"]) > 0
    assert schema["node_count"] > 0
```

- [ ] **Step 6: Write test_cli_smoke.py**

```python
# tokkit/e2e/test_cli_smoke.py
import json
import os
import subprocess
import sys
import pytest


def test_cli_version():
    """CLI --version prints version string."""
    result = subprocess.run(
        [sys.executable, "-m", "tokkit_server.main", "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_cli_help():
    """CLI --help prints usage."""
    result = subprocess.run(
        [sys.executable, "-m", "tokkit_server.main", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "tokkit" in result.stdout.lower()


def test_cli_index_and_status(sample_project_path):
    """CLI can index a repo and check status."""
    # Index
    result = subprocess.run(
        [sys.executable, "-m", "tokkit_server.main", "cli", "index_repository",
         json.dumps({"path": sample_project_path})],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["node_count"] > 0

    # Status
    result = subprocess.run(
        [sys.executable, "-m", "tokkit_server.main", "cli", "index_status", "{}"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
```

- [ ] **Step 7: Run all tests**

Run: `cd tokkit && pytest e2e/ server/tests/ -v`
Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add tokkit/e2e/ tokkit/pyproject.toml
git commit -m "test(e2e): add MCP protocol, query, and CLI smoke tests"
```

---

## Task 6: Final Verification

- [ ] **Step 1: Run full Rust test suite**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: 70 tests pass.

- [ ] **Step 2: Run full Python test suite**

Run: `cd tokkit && pytest e2e/ server/tests/ -v`
Expected: All tests pass.

- [ ] **Step 3: Verify CLI works end to end**

```bash
cd tokkit && python -m tokkit_server.main --version
python -m tokkit_server.main cli index_repository '{"path": "/home/edge/code/research/tokkit/core/code/crates/tokkit-core/tests/fixtures/python_project"}'
```

- [ ] **Step 4: Final commit**

```bash
git add -A tokkit/
git commit -m "chore: Plan 2 complete — PyO3 bindings, MCP server, e2e tests"
```
