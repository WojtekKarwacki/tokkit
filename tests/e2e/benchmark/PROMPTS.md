# Benchmark Prompts

Formalized prompts for the 12 benchmark scenarios. Each prompt is designed to
reliably trigger the expected tokkit MCP tool when given to a Claude agent.

See `scenarios.py` for the full definitions including system instructions,
expected tools, and fixture paths.

## System instructions

**Tokkit agent** receives:
> You have access to tokkit MCP tools for code intelligence and content processing.
> These tools process data server-side so raw content never enters your context —
> always prefer them over built-in Read/Grep when the task matches a tokkit tool.
> Available tokkit tools: index_repository, get_architecture, find_dead_code,
> find_routes, trace_fan, clean_html, compact_json, search_markdown, compact_output.

Code graph scenarios (Q1-Q5) also include:
> The repository is at {repo}. Call index_repository first, then use the appropriate graph tool.

**Baseline agent** receives:
> Answer the question using only the built-in tools: Read, Grep, Glob, Bash.
> Do NOT use any MCP tools even if they are available.

## Prompts

### Q1 — Blast radius analysis → `trace_fan`

Which functions are affected if I change `get_openapi`? Show all callers, transitively.

### Q2 — Trace setup call chain → `trace_fan`

Trace the call chain starting from the `setup` function, going 3 levels deep. Show what functions it calls, and what those call in turn.

### Q3 — Dead code detection → `find_dead_code`

Find functions in the fastapi codebase that appear to be dead code — defined but never referenced anywhere.

### Q4 — List route handlers → `find_routes`

List all HTTP route handlers in this project — show the HTTP method, route path, and handler function name.

### Q5 — Architecture overview → `get_architecture`

Give me an architecture overview of this project. What are the main modules, key abstractions, and how is the code organized?

### Q6 — Search README → `search_markdown`

What are the dependencies and requirements for this project? Search the README at {repo}/README.md for the relevant sections.

### Q7 — Clean Python docs (14KB) → `clean_html`

Summarize the Python datetime documentation from the HTML file at {fixtures}/html/python_docs.html

### Q8 — Clean blog post (24KB) → `clean_html`

Summarize the blog post about async/await from the HTML file at {fixtures}/html/blog_post.html

### Q9 — Compact flat records (14KB) → `compact_json`

Summarize the records in the JSON file at {fixtures}/json/flat_records.json

### Q10 — Compact nested data (10KB) → `compact_json`

Summarize the structure of the JSON data at {fixtures}/json/nested_complex.json

### Q11 — Compress pytest (13.7KB) → `compact_output`

Summarize the pytest results in {fixtures}/shell/pytest_output.txt — what passed, what failed, and why.

### Q12 — Compress ruff lint (8.3KB) → `compact_output`

Summarize the ruff lint violations in {fixtures}/shell/ruff_output.txt

## Design principles

1. **File paths in prompts** — Content tools (Q6-Q12) include explicit file paths so
   agents can match the file type to the right MCP tool.

2. **Index reminder for graph tools** — Code graph prompts (Q1-Q5) include a reminder
   to call `index_repository` first.

3. **Same question for both agents** — The natural-language question is identical.
   Only the system instruction differs (prefer MCP vs restrict to builtins).

4. **Tool descriptions do the work** — MCP tool descriptions emphasize "server-side
   reading" and "content never enters agent context" so agents naturally prefer them.
