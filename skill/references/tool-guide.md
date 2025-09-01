# Tokkit Tool Reference

Detailed parameter reference, response formats, and query patterns for all tokkit MCP tools.

## Tool Reference

### index_repository

Index a Python/JS/TS repository into a knowledge graph.

**Parameters:**
- `path` (string, required) — absolute path to the repository root
- `mode` (string, optional) — `"full"` (default) or `"fast"`

**Response:** JSON string
```json
{"project_name": "myapp", "node_count": 245, "edge_count": 512, "elapsed_ms": 1200}
```

**Notes:**
- Full mode: deep AST extraction + all enrichment passes (tests, routes, similarity, git history)
- Fast mode: basic structure only, skips enrichment. Use for very large repos
- Graph persists to `/tmp/tokkit/{project_name}.redb`
- Only one index can run at a time (pipeline lock)

---

### search_graph

Search the knowledge graph for nodes by name pattern and/or label.

**Parameters:**
- `query` (string, required) — substring match on node name or qualified_name (case-insensitive)
- `label` (string, optional) — filter by node label: `Project`, `Folder`, `File`, `Function`, `Method`, `Class`, `Interface`, `Enum`, `Variable`, `Route`, `Test`
- `limit` (integer, optional) — max results (default 50)

**Response:** JSON array of nodes
```json
[
  {
    "id": 42,
    "label": "Function",
    "name": "authenticate",
    "qualified_name": "myapp::src/auth.py::authenticate",
    "file_path": "src/auth.py",
    "line_start": 15,
    "line_end": 28,
    "properties": {}
  }
]
```

---

### trace_path

Find the shortest path between two nodes via BFS over edges.

**Parameters:**
- `from` (string, required) — source node qualified_name
- `to` (string, required) — target node qualified_name
- `max_depth` (integer, optional) — max BFS depth (default 5)

**Response:** JSON array of path steps (empty if no path found)
```json
[
  {"node": {"name": "main", "qualified_name": "...", ...}, "edge": null, "depth": 0},
  {"node": {"name": "authenticate", ...}, "edge": {"edge_type": "CALLS", "confidence": 0.95, ...}, "depth": 1}
]
```

**Tips:**
- Increase `max_depth` to 8-10 for deeply nested codebases
- Empty result means no path exists within the depth limit — try reversing direction or using search_graph to find intermediate nodes
- Each step's `edge.confidence` tells how reliable that link is

---

### get_code_snippet

Retrieve the source code for a specific symbol.

**Parameters:**
- `qualified_name` (string, required) — exact qualified name from search_graph results
- `context_lines` (integer, optional) — lines of context above/below (default 3)

**Response:** JSON object (or null if not found)
```json
{
  "qualified_name": "myapp::src/auth.py::authenticate",
  "file_path": "src/auth.py",
  "line_start": 12,
  "line_end": 31,
  "content": "def authenticate(username, password):\n    ...",
  "language": "py"
}
```

**Key advantage:** Returns only the function/class body. Reading the full file would cost 5-50x more tokens.

---

### get_architecture

Get a structural overview of an indexed project.

**Parameters:**
- `project` (string, required) — project name (same as directory name)

**Response:** JSON object
```json
{
  "project_name": "myapp",
  "languages": ["py", "js"],
  "top_files": ["main.py", "auth.py", "utils.py"],
  "entry_points": [],
  "packages": ["src", "tests", "config"],
  "summary": "245 nodes, 512 edges"
}
```

---

### detect_changes

Find files changed since last index.

**Parameters:** none required (uses session state)

**Response:** JSON array
```json
[
  {"path": "src/auth.py", "change_type": "modified"},
  {"path": "src/new_file.py", "change_type": "added"}
]
```

---

### index_status

Check if a project is indexed.

**Parameters:** none

**Response:** JSON object
```json
{"indexed": true, "project_name": "myapp", "node_count": 245, "edge_count": 512}
```

---

### get_graph_schema

Get available node labels and edge types in the current graph.

**Parameters:** none

**Response:** JSON object
```json
{
  "node_labels": ["Project", "Folder", "File", "Function", "Method", "Class"],
  "edge_types": ["CONTAINS_FILE", "CONTAINS_FOLDER", "CALLS", "TESTS_FILE"],
  "node_count": 245,
  "edge_count": 512
}
```

---

### get_token_stats

Get aggregate token savings statistics. Stats persist across sessions at `~/.local/share/tokkit/stats.json`.

**Parameters:** none

**Response:** JSON object
```json
{
  "total_queries": 47,
  "total_tokens_used": 3200,
  "total_tokens_avoided": 185000,
  "total_tokens_saved": 181800,
  "savings_pct": 98.3,
  "efficiency_ratio": 57.8,
  "by_tool": {
    "search_graph": {"queries": 30, "tokens_used": 1500, "tokens_avoided": 120000, "tokens_saved": 118500},
    "get_code_snippet": {"queries": 12, "tokens_used": 800, "tokens_avoided": 48000, "tokens_saved": 47200}
  }
}
```

---

### list_projects

List all indexed projects.

**Parameters:** none

**Response:** JSON array of projects with their stats.

---

### delete_project

Delete an indexed project's database.

**Parameters:**
- `project` (string, required) — project name

---

## Common Query Patterns

### Pattern 1: Understand a feature end-to-end

```
1. search_graph(query="feature_keyword") → find entry points
2. For each result, trace_path(from=entry_point, to=...) → map the call chain
3. get_code_snippet on key functions → read implementation details
```

### Pattern 2: Find all callers of a function

```
1. search_graph(query="function_name", label="Function") → get the QN
2. search_graph(query="function_name") → broader search catches callers that import it
3. trace_path from suspected callers to the target
```

### Pattern 3: Identify untested code

```
1. get_graph_schema → confirm TESTS_FILE edges exist
2. search_graph(label="File") → all source files
3. Files without incoming TESTS_FILE edges are untested
```

### Pattern 4: Find files that change together

```
1. search_graph(label="File") → all files
2. Edges of type CO_CHANGED connect coupled files
3. High coupling_score (>0.7) = strong co-change signal
```

### Pattern 5: Find duplicate code

```
1. Edges of type SIMILAR_TO connect functions with matching names in different files
2. get_code_snippet on both sides to compare implementations
```

### Pattern 6: Map HTTP endpoints

```
1. search_graph(label="Route") → all detected routes
2. HANDLES edges connect routes to their handler functions
3. get_code_snippet on handlers to see implementation
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TOKKIT_CACHE_DIR` | `/tmp/tokkit` | Directory for index databases (`.redb` files) |
| `TOKKIT_SHOW_SAVINGS` | unset | Set to `1` to append a token savings summary line to every tool response |
| `XDG_DATA_HOME` | `~/.local/share` | Base directory for persistent data (stats file) |

### Inline Savings Display

By default, token savings metadata is only included in the `_meta` field of tool responses (invisible to most agents). To make savings visible in every tool response, set `TOKKIT_SHOW_SAVINGS=1` in your MCP config:

```json
{
  "mcpServers": {
    "tokkit": {
      "command": "uvx",
      "args": ["tokkit", "serve"],
      "env": {"TOKKIT_SHOW_SAVINGS": "1"}
    }
  }
}
```

When enabled, each tool response will include a line like:

```
[tokkit: saved ~4,858 tokens (97.2%) | session total: 12,340 tokens saved]
```

### Data Locations

| Path | Contents |
|------|----------|
| `~/.local/share/tokkit/stats.json` | Persistent token savings statistics (survives reboots) |
| `$TOKKIT_CACHE_DIR/{project}.redb` | Index databases (default: `/tmp/tokkit/`) |
| `~/.local/share/tokkit/SKILL.md` | Installed skill documentation |
