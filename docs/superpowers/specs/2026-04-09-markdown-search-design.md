# Markdown Search Tool — Design Spec

## Problem

LLM agents waste tokens reading entire markdown documents when they only need specific sections. A 2000-token README where only one 300-token section is relevant means ~1700 tokens wasted per read. This compounds across sessions with many doc lookups.

## Solution

A new MCP tool `search_markdown` that takes raw markdown + a query, parses the document into a header tree, matches sections by keyword/fuzzy against headers and content, and returns only the relevant sections — ranked by precision.

## Tool Interface

```python
search_markdown(markdown: str, query: str)
```

- `markdown` — raw markdown string (required). Any source: file, `clean_html` output, etc.
- `query` — search keywords (required). Empty string returns header listing only.

Stateless. No file I/O. Follows the `clean_html` / `compact_json` pattern.

## Data Model

The parser converts markdown into a section tree:

```
Document
├── Section(level=1, title="Getting Started", content="...", char_count=120)
│   ├── Section(level=2, title="Installation", content="...", char_count=80)
│   │   └── Section(level=3, title="Authentication", content="...", char_count=200)
│   └── Section(level=2, title="Configuration", content="...", char_count=150)
└── Section(level=1, title="API Reference", content="...", char_count=1800)
    ├── Section(level=2, title="Auth Endpoints", content="...", char_count=600)
    └── Section(level=2, title="User Endpoints", content="...", char_count=900)
```

Each `Section` has:
- `level` (1-6) — header depth
- `title` — header text (without `#` prefix)
- `content` — text between this header and next header at same/higher level, excluding children's content
- `children` — child sections (deeper headers beneath this one)
- `char_count` — total chars including children, used for token estimation

Parser walks markdown line by line, splits on `^#{1,6}\s` pattern, builds tree by tracking level stack.

## Search & Ranking

### Match Tiers

| Tier | Condition | Example | Base Score |
|------|-----------|---------|------------|
| 1 | Header substring (case-insensitive) | "auth" in "Authentication" | 1.0 |
| 2 | Header fuzzy (handles typos/stemming) | "authen" ~ "Authentication" | 0.7 |
| 3 | Content substring (case-insensitive) | "auth" found in section body | 0.3 |

Tier 1 covers both exact and partial substring matches. Tier 2 is for near-misses that aren't substrings — typos, word stems, etc. The tool takes the highest applicable score per section.

### Depth Bonus

Deeper headers = more precise match. Bonus: `+0.05 * level`.

- h1 exact header match: `1.0 + 0.05 = 1.05`
- h3 exact header match: `1.0 + 0.15 = 1.15`

h3 ranks above h1 for the same keyword — a dedicated subsection is more relevant than a broad umbrella.

### Multi-Word Queries

Split query on spaces. Score each word independently against each section. Average the per-word scores. Sections matching all query words rank higher than those matching only some.

### Result Sorting

Descending by final score. Each result includes:
- `title` — header text
- `path` — breadcrumb (e.g., `## Setup > ### Authentication`)
- `score` — numeric rank
- `match_type` — "header" or "content"
- `content` — full section body including children

## Output Format

### Matches Found

```
Matches: 2 | Document: ~2000 tokens | Returned: ~450 tokens | Savings: 77%

### Authentication (score: 1.15, match: header, ~200 tokens)
Path: ## Setup > ### Authentication
---
Content here...

### Auth Endpoints (score: 0.35, match: content, ~250 tokens)
Path: # API Reference > ## Auth Endpoints
---
Content here...
```

### No Matches (Header Fallback)

When no keyword matches are found, return the full header tree with token estimates:

```
No matches for "foobar". Document headers:
# Getting Started (~120 tokens)
  ## Installation (~80 tokens)
    ### Authentication (~200 tokens)
  ## Configuration (~150 tokens)
# API Reference (~1800 tokens)
  ## Auth Endpoints (~600 tokens)
  ## User Endpoints (~900 tokens)
```

This gives the agent a cheap map (~50-100 tokens) to refine its query.

### Empty Query

When `query=""`, return the header tree listing (same as no-match fallback). Useful for agents that just want to understand document structure before querying.

## Module Structure

```
py/tokkit_markdown/
  __init__.py      — exports search_markdown()
  parser.py        — markdown-to-tree parser
  search.py        — matching, scoring, ranking
  formatter.py     — output formatting (results + fallback)
```

## MCP Registration

- Add tool definition to `TOOL_DEFINITIONS` in `py/tokkit_server/protocol.py`
- Add handler in `py/tokkit_server/tools.py` dispatching to `tokkit_markdown.search_markdown()`
- Return result via `_ok(output, meta)` with token savings metadata

## Test Plan

### Unit Tests (`tests/markdown/`)

**Parser tests (`test_parser.py`):**
- Single header document
- Nested headers (h1 > h2 > h3)
- Deeply nested (h1 through h6)
- Skipped levels (h1 > h3, no h2)
- Multiple h1 sections (flat structure)
- Content before first header (preamble)
- Empty sections (header with no content)
- Headers with inline formatting (`## **Bold** Header`)
- Code blocks containing `#` characters (should not be parsed as headers)
- ATX headers only (no setext support needed)
- Large documents with many sections
- Document with no headers (returns single root section)

**Search tests (`test_search.py`):**
- Exact substring match in header
- Case-insensitive matching
- Fuzzy/partial match ("auth" → "Authentication")
- Content match with lower rank
- Depth bonus: h3 match ranks above h1 match for same keyword
- Multi-word query: all words match > partial match
- No matches returns empty results
- Empty query returns no matches (triggers header fallback)
- Multiple sections matching same query, sorted by score
- Section with children: full subtree returned in content

**Formatter tests (`test_formatter.py`):**
- Breadcrumb path generation
- Token estimation (char_count / 4)
- Match output format with metadata line
- Fallback header tree with indentation by level
- Savings percentage calculation
- Empty document handling

### E2E Tests (`tests/e2e/test_mcp_markdown.py`)

- Tool appears in `tools/list`
- Search with matches returns ranked sections
- Search with no matches returns header tree
- Empty query returns header tree
- Token savings metadata present in response

## Skill Documentation

Add to `skill/SKILL.md`:

```
### 9. Search Markdown Content

For finding specific sections in markdown documents:

search_markdown(markdown="<full markdown>", query="authentication setup")
  → ranked matching sections with breadcrumbs and token savings

search_markdown(markdown="...", query="")
  → header tree listing with token estimates (for structural overview)

Single call. If keyword matching finds relevant sections, they're returned
ranked by precision (deeper headers = more precise = higher rank).
If nothing matches, you get the header tree (~50-100 tokens) to refine your query.
```
