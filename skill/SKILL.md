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

ALWAYS prefer tokkit MCP tools over built-in Read/Grep when the task matches. These tools process data server-side — raw content never enters your context.

## When to Use Tokkit (decision table)

Check this table BEFORE reaching for Read, Grep, or Glob:

| You're about to... | Use this instead | Why |
|---------------------|-----------------|-----|
| Read an `.html` file | `clean_html(path=...)` | Server-side read, 60-90% fewer tokens |
| Read a `.json` file | `compact_json(path=...)` | Server-side read, 30-70% fewer tokens |
| Read a `.md` file for specific info | `search_markdown(path=..., query=...)` | Returns matching sections only, 70-85% fewer tokens |
| Read test/lint/build output | `compact_output(path=..., hint=...)` | Strips noise, keeps failures, 70-85% fewer tokens |
| Grep for function definitions + references | `find_dead_code()` | One call vs O(N^2) greps |
| Grep for route decorators | `find_routes()` | One call, detects all frameworks |
| Recursive grep+read to trace call chains | `trace_fan(function_name=...)` | One call replaces 10-20 grep+read |
| Glob + Read to understand a project | `get_architecture()` | Complete overview in one call |

**The `path=` parameter is critical.** Content tools (`clean_html`, `compact_json`, `search_markdown`, `compact_output`) read files server-side when you pass `path=`. The raw content never enters your context. If you use `Read` first and then pass the content, you've already paid the token cost.

## MCP Tools (9 available)

| Tool | Use instead of | Saves |
|------|---------------|-------|
| `index_repository` | *(prerequisite for graph tools)* | — |
| `get_architecture` | Glob + Read README + Read source files | 80%+ |
| `find_dead_code` | Grep all defs + grep all references | 90%+ |
| `find_routes` | Grep for route decorators | 80%+ |
| `trace_fan` | Recursive grep → read → grep cycles | 80%+ |
| `clean_html` | Read .html file | 60-90% |
| `compact_json` | Read .json file | 30-70% |
| `search_markdown` | Read .md file | 70-85% |
| `compact_output` | Read test/lint output | 70-85% |

## Workflow

### 1. Index First (graph tools only)

Before using `get_architecture`, `find_dead_code`, `find_routes`, or `trace_fan`:

```
index_repository(path="/absolute/path/to/repo")
```

Takes 1-5 seconds. Only needed once per session.

### 2. Graph Tools (code analysis)

```
get_architecture()                                          → project overview
find_dead_code(limit=200)                                   → unreferenced functions
find_routes(limit=200)                                      → HTTP handlers with method + path
trace_fan(function_name="authenticate", direction="outbound", depth=3)  → call fan-out
trace_fan(function_name="authenticate", direction="inbound")            → who calls this
```

`trace_fan` accepts plain function names — no qualified name lookup needed.

### 3. Content Tools (no indexing required)

All content tools accept `path=` for server-side file reading. Always prefer `path=` over passing raw content.

```
clean_html(path="/path/to/page.html")                       → clean markdown
clean_html(path="...", mode="text")                          → plain text only

compact_json(path="/path/to/data.json")                      → CSV or YAML

search_markdown(path="/path/to/README.md", query="auth setup") → matching sections
search_markdown(path="...", query="")                          → header tree overview

compact_output(path="/path/to/test-results.txt", hint="pytest") → failures only
compact_output(path="...", hint="ruff")                         → violations summary
```

### 4. Fall Back to Read/Grep

Use built-in tools only when tokkit doesn't cover the case:
- Reading a specific function body → `Grep` to find line, then `Read(offset=, limit=)`
- Raw text search across files → `Grep`
- Non-code files (configs, lock files) → `Read`
- Languages other than Python/JS/TS → `Read` + `Grep`

## compact_output: Supported Parsers

| Category | Tools | Hint values |
|----------|-------|-------------|
| Python test | pytest, unittest | `pytest`, `unittest` |
| Python lint/type | ruff, mypy, pyright | `ruff`, `mypy`, `pyright` |
| Python other | pip, tracebacks | `pip`, `traceback` |
| JS/TS test | jest, vitest, mocha | `jest`, `vitest`, `mocha` |
| JS/TS lint/type | tsc, eslint | `tsc`, `eslint` |
| JS/TS build | webpack, vite | `webpack`, `vite` |
| JS/TS package | npm | `npm` |
| Rust | cargo test/build/clippy | `cargo-test`, `cargo-build`, `cargo-clippy` |
| Container | docker build | `docker` |

Auto-detects when hint is omitted. Best results with explicit hint.

## Known Limitations

- **Route detection** covers decorator-based frameworks (FastAPI, Flask, Starlette, NestJS) and call-expression frameworks (Express, Koa, Hono, Fastify), plus file-based routing (Next.js, SvelteKit). Django urlpatterns and Tornado class-based handlers are not yet detected.
- **Languages supported:** Python, JavaScript, TypeScript only. Other languages are skipped during indexing.
- **Incremental indexing** — not yet implemented. Re-indexing rebuilds the full graph.

## Anti-Patterns

**Do NOT Read an .html/.json/.md file when a tokkit tool can process it server-side.** You pay the full token cost of the raw content for no reason.

**Do NOT grep for function definitions to find dead code.** `find_dead_code` does it in one call.

<!-- rev-32 -->
**Do NOT skip indexing.** Without `index_repository`, all graph tools return errors.
