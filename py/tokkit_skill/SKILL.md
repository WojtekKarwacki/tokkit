---
name: tokkit-code-intelligence
description: >
  Use for ANY codebase exploration, analysis, or understanding task on
  Python, JavaScript, or TypeScript repositories. Triggers: "explore the
  codebase", "find where X is defined", "how does Y work", "what calls
  this function", "show me the architecture", "trace the call chain",
  "what files are related", "find similar code", "what tests cover this",
  "find dead code", "unused code", "check dependencies", "analyze code",
  "code structure", "what imports this", "who uses this", "find all
  classes/functions", "code quality", "codebase overview". Uses tokkit
  knowledge graph tools instead of reading raw source files — 90%+ token
  savings.
---

# Tokkit Code Intelligence

Use the tokkit MCP tools to answer codebase questions with 90%+ fewer tokens than reading raw files. The tools query a pre-built knowledge graph of symbols, calls, imports, and relationships.

## Workflow

Follow this sequence for any codebase exploration task:

### 1. Index First

Before any query, ensure the repository is indexed:

```
index_status → check if already indexed
index_repository(path="/absolute/path/to/repo") → build the graph
```

Indexing takes 1-5 seconds for typical repos. Only needed once per session — the graph persists to disk.

### 2. Orient with Architecture

For broad questions ("how does this project work?", "what's the structure?"):

```
get_architecture(project="repo-name") → languages, packages, key files
get_graph_schema → available node labels and edge types
```

### 3. Search the Graph

For specific questions ("where is authenticate defined?", "find all controllers"):

```
search_graph(query="authenticate") → nodes matching by name
search_graph(query="", label="Class") → all classes
search_graph(query="auth", label="Function", limit=20) → filtered search
```

Results include `qualified_name` — use this for subsequent calls.

### 4. Trace Connections

For relationship questions ("what calls this?", "how does data flow?"):

```
trace_path(from="proj::src/main.py::main", to="proj::src/db.py::connect", max_depth=5)
```

Returns each step with the connecting edge type and confidence score.

### 5. Read Only What's Needed

For code details, use `get_code_snippet` — returns just the function/class body, not the whole file:

```
get_code_snippet(qualified_name="proj::src/auth.py::AuthService.login", context_lines=3)
```

Fall back to `Read` tool only for non-code files (README, configs) or when the graph doesn't have the answer.

### 6. Check Savings

After exploration, report token efficiency:

```
get_token_stats → total queries, tokens saved, savings percentage
```

### 7. Clean Web Content

For HTML pages fetched via WebFetch or other sources:

```
clean_html(html="<full page html>") → token-optimized markdown
clean_html(html="...", mode="text") → plain text only
clean_html(html="...", mode="minimal") → light cleaning only
```

Does not require an indexed project. Works standalone as a stateless transformation.

### 8. Compact JSON Data

For JSON payloads about to be sent to an LLM:

```
compact_json(json="<raw json string>") → token-optimized CSV or YAML
```

Auto-detects the best format:
- **CSV** (semicolon-delimited) for flat/flattenable data — saves 50-70%
- **YAML** for data with nested lists of objects — saves 20-30%

Does not require an indexed project. Works standalone as a stateless transformation.

## Qualified Name Format

All tools that accept `qualified_name` use this format:

```
{project_name}::{file_path}::{scope.entity_name}
```

Examples:
- `myapp::src/auth.py::authenticate` — top-level function
- `myapp::src/auth.py::AuthService.login` — method in class
- `myapp::src/routes/users.js::listUsers` — JS function

Always use `search_graph` first to discover exact qualified names. Do not guess them.

## Tool Selection Guide

| Task | Tool | Why |
|------|------|-----|
| Find a symbol by name | `search_graph` | O(1) graph lookup vs grep |
| Get function source code | `get_code_snippet` | Returns function only, not whole file |
| Trace call chain | `trace_path` | BFS across the graph |
| Project overview | `get_architecture` | Summary vs reading everything |
| Find what changed | `detect_changes` | Compares mtimes vs stored hashes |
| Strip HTML noise | `clean_html` | Markdown/text output, strips 60-90% of tokens |
| Compact JSON for LLM | `compact_json` | CSV/YAML output, saves 30-60% tokens |
| Raw text search | `Read`/`Grep` tools | `search_code` is not yet implemented |

## Interpreting Confidence Scores

Edges from call resolution carry confidence scores:

| Score | Strategy | Reliability |
|-------|----------|-------------|
| 0.95 | Import map — resolved via explicit import | Trust fully |
| 0.90 | Same module — caller and target in same file | Trust fully |
| 0.75 | Unique name — only one candidate project-wide | Reliable, verify if critical |
| 0.55 | Suffix match — best guess among multiple candidates | Verify before acting on it |

When an edge has 0.55 confidence, confirm the connection by reading the actual call site with `get_code_snippet`.

## Special Edge Types

The graph contains more than just CALLS edges:

- **TESTS / TESTS_FILE** — test file → implementation file. Found via naming conventions (`test_auth.py` → `auth.py`, `auth.spec.ts` → `auth.ts`)
- **CO_CHANGED** — files that frequently change together in git history. Properties: `co_changes` (count), `coupling_score` (0.0-1.0). Only created when coupling >= 0.3 with 3+ co-changes
- **SIMILAR_TO** — functions with matching names in different files. Indicates potential duplication
- **HANDLES** — function → Route node. Detected from naming conventions (`get_users`, `post_items` in route/controller files)

Use `get_graph_schema` to see which edge types exist in the current graph.

## Known Limitations

- **search_code is stubbed** — returns empty results. Use `Grep` tool for raw text search
- **trace_path default depth is 5** — increase `max_depth` for deep call chains
- **Route detection is heuristic** — requires function naming conventions (`get_*`, `post_*`) in route files
- **Languages supported:** Python, JavaScript, TypeScript only. Other languages are skipped during indexing
- **Incremental indexing** — not yet implemented. Re-indexing rebuilds the full graph

## Anti-Patterns

**Do NOT read entire source files when the graph can answer the question.** Each unnecessary file read wastes thousands of tokens.

**Do NOT guess qualified names.** Always search first, then use the exact QN from results.

**Do NOT skip indexing.** Without `index_repository`, all query tools return errors.

## Additional Resources

Consult `references/tool-guide.md` for detailed parameter reference, response formats, and common query patterns.
