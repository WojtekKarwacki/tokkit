# Token-Saving HTML Scraper — Design Spec

**Date:** 2026-04-07
**Status:** Approved
**Location:** `core/web/tokkit_scraper`

## Summary

Add a `clean_html` MCP tool that strips irrelevant tags, attributes, and noise from raw HTML, returning token-optimized output. This is a stateless transformation — no session or indexed project required. The caller provides already-fetched HTML (e.g. from WebFetch); the tool returns cleaned content.

## Core Library: `core/web/tokkit_scraper`

### Public API

```python
def clean_html(html: str, mode: str = "markdown") -> str:
    """Strip noise from HTML, return token-optimized text.

    Args:
        html: Raw HTML string.
        mode: Output format.
            - "markdown" (default): semantic structure preserved as markdown.
            - "text": maximum strip, plain text only.
            - "minimal": light clean, keep HTML structure.

    Returns:
        Cleaned string in the requested format.

    Raises:
        ValueError: If mode is not one of the three valid values.
    """
```

### Dependencies

- `selectolax` — Rust-based HTML parser (Modest engine). Fast, minimal, fits tokkit's Rust-native philosophy.
- No other external dependencies.

### Stripping Pipeline (all modes)

Applied in order:

1. **Remove entirely:** `<script>`, `<style>`, `<noscript>`, `<svg>`, `<iframe>`, HTML comments, `<head>`
2. **Remove noise elements:** Elements matching common noise patterns by tag or class/id:
   - Tags: `<nav>`, `<header>`, `<footer>`, `<aside>`
   - Class/id patterns: `cookie`, `consent`, `gdpr`, `sidebar`, `nav`, `menu`, `ad-`, `ads`, `social`, `share`, `popup`, `modal`, `banner`, `promo`
3. **Strip attributes:** Remove all attributes except `href` on `<a>` and `alt` on `<img>` (and `src` on `<img>` for markdown mode)
4. **Collapse whitespace:** Multiple spaces/newlines to single space, remove empty elements

### Mode-Specific Output

#### `"markdown"` (default)

Converts semantic HTML to markdown:

| HTML | Markdown |
|------|----------|
| `<h1>`-`<h6>` | `#`-`######` |
| `<a href="...">text</a>` | `[text](href)` |
| `<ul>/<ol>/<li>` | `- item` / `1. item` |
| `<table>` | Markdown table with `\|` and `---` |
| `<pre>`, `<code>` | Fenced code blocks |
| `<img alt="..." src="...">` | `![alt](src)` |
| `<strong>`, `<b>` | `**bold**` |
| `<em>`, `<i>` | `*italic*` |
| `<blockquote>` | `> quote` |
| Everything else | Plain text content |

#### `"text"`

Extract visible text only. No markdown formatting. Whitespace-normalized plain text with paragraph breaks preserved as double newlines.

#### `"minimal"`

Remove only `<script>`, `<style>`, `<noscript>`, HTML comments, and `<head>`. Preserve all other HTML structure. For cases where the caller wants near-raw HTML with obvious junk removed.

## MCP Tool Definition

### Schema (added to `protocol.py` TOOL_DEFINITIONS)

```python
{
    "name": "clean_html",
    "description": "Strip irrelevant tags, attributes, and noise from HTML. Returns token-optimized text for LLM analysis/research. Does not require an indexed project.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "Raw HTML content to clean."
            },
            "mode": {
                "type": "string",
                "enum": ["markdown", "text", "minimal"],
                "description": "Output mode. 'markdown' (default): semantic structure as markdown. 'text': plain text only. 'minimal': light clean, keep HTML structure."
            }
        },
        "required": ["html"]
    }
}
```

### Dispatch (in `tools.py`)

```python
if tool_name == "clean_html":
    html = args.get("html", "")
    mode = args.get("mode", "markdown")
    if not html:
        return _err("html is required")
    from tokkit_scraper import clean_html
    cleaned = clean_html(html, mode=mode)
    meta = make_meta(tool_name, cleaned, _session_project_path, raw_size=len(html))
    return _ok(cleaned, meta)
```

Key: `clean_html` does **not** require a session or indexed project. It is a stateless transformation.

### Token Stats (in `token_stats.py`)

Add `clean_html` case to `estimate_tokens_avoided`:

```python
if tool_name == "clean_html":
    # Without tokkit: agent consumes the full raw HTML
    # raw_size is passed in from the tool dispatch
    return raw_size // CHARS_PER_TOKEN if raw_size else len(result_text) * 2 // CHARS_PER_TOKEN
```

Adjust `make_meta` signature to accept optional `raw_size: int | None = None` parameter. When provided, use it instead of estimating from `result_text`. All existing callers pass no `raw_size` and behave unchanged.

## Skill Documentation Update

Add to `skill/SKILL.md`:

### Workflow section

```markdown
### 7. Clean Web Content

For HTML pages fetched via WebFetch or other sources:

    clean_html(html="<full page html>") → token-optimized markdown
    clean_html(html="...", mode="text") → plain text only
    clean_html(html="...", mode="minimal") → light cleaning only
```

### Tool selection table entry

```markdown
| Strip HTML noise | `clean_html` | Markdown/text output, strips 60-90% of tokens |
```

## Test Pyramid

### Unit Tests — `core/web/tests/test_clean_html.py`

Tests for the core `clean_html` function:

1. `test_removes_script_tags` — `<script>` and contents stripped in all modes
2. `test_removes_style_tags` — `<style>` and contents stripped
3. `test_removes_head` — `<head>` block stripped
4. `test_removes_nav_footer_aside` — noise elements removed
5. `test_removes_noise_by_class_id` — elements with cookie/consent/sidebar classes removed
6. `test_strips_attributes` — all attributes removed except href on a, alt/src on img
7. `test_collapses_whitespace` — multiple spaces/newlines → single
8. `test_markdown_headings` — h1-h6 → # markers
9. `test_markdown_links` — `<a href>` → `[text](href)`
10. `test_markdown_lists` — ul/ol/li → markdown lists
11. `test_markdown_tables` — `<table>` → markdown table
12. `test_markdown_code_blocks` — pre/code → fenced code blocks
13. `test_markdown_emphasis` — strong/em → bold/italic
14. `test_markdown_blockquotes` — blockquote → > prefix
15. `test_markdown_images` — img with alt → `![alt](src)`
16. `test_text_mode` — plain text output, no formatting
17. `test_minimal_mode` — only scripts/styles/comments removed, HTML preserved
18. `test_empty_input` — empty string returns empty string
19. `test_invalid_mode_raises` — ValueError on unknown mode

### Integration Tests — `server/tests/test_scraper_integration.py`

Tests for tool dispatch and MCP integration:

1. `test_clean_html_tool_dispatch` — `handle_tool_call("clean_html", ...)` routes correctly
2. `test_clean_html_no_session_required` — works without prior `index_repository`
3. `test_clean_html_token_stats_recorded` — `make_meta` tracks savings with raw_size
4. `test_clean_html_error_on_missing_html` — returns MCP error format when html is empty

### E2E Tests — `e2e/test_mcp_scraper.py`

Full MCP JSON-RPC flow:

1. `test_clean_html_via_mcp` — send `tools/call` with `clean_html`, get cleaned result
2. `test_clean_html_in_tools_list` — tool appears in `tools/list` response
3. `test_clean_html_real_page` — clean a realistic HTML fixture, verify output is valid markdown

### Token Savings Benchmark — `e2e/benchmark/test_scraper_benchmark.py`

Following the pattern of the existing code intelligence benchmark:

**3 questions, tokkit vs baseline:**

| # | Question | Baseline | Tokkit |
|---|----------|----------|--------|
| 1 | Extract main content (markdown mode) | Full raw HTML tokens | `clean_html(html, mode="markdown")` tokens |
| 2 | Get plain text (text mode) | Full raw HTML tokens | `clean_html(html, mode="text")` tokens |
| 3 | Light clean (minimal mode) | Full raw HTML tokens | `clean_html(html, mode="minimal")` tokens |

**Fixtures:** 3 real-world HTML pages saved as static files in `e2e/benchmark/fixtures/html/`:
- A documentation page (e.g. Python docs)
- A GitHub-style README page
- A blog post with heavy navigation/ads

**Baselines:** `baseline_raw_html(fixture_path)` returns `len(raw_html) // CHARS_PER_TOKEN`.

**Report:** Generates `SCRAPER_BENCHMARK_RESULTS.md` with savings %, ratio per question, totals.

**Assertion:** Each mode must produce fewer tokens than raw HTML. Markdown mode should achieve at least 50% reduction on typical pages.

## File Changes Summary

| File | Action |
|------|--------|
| `core/web/pyproject.toml` | Add `selectolax` dependency |
| `core/web/tokkit_scraper/__init__.py` | Implement `clean_html` |
| `core/web/tests/test_clean_html.py` | New — 19 unit tests |
| `server/tokkit_server/protocol.py` | Add `clean_html` to TOOL_DEFINITIONS |
| `server/tokkit_server/tools.py` | Add `clean_html` dispatch case |
| `server/tokkit_server/token_stats.py` | Add `clean_html` case + `raw_size` param |
| `server/tests/test_scraper_integration.py` | New — 4 integration tests |
| `e2e/test_mcp_scraper.py` | New — 3 e2e tests |
| `e2e/benchmark/test_scraper_benchmark.py` | New — 3 benchmark questions + report |
| `e2e/benchmark/fixtures/html/` | New — 3 HTML fixture files |
| `e2e/benchmark/baselines.py` | Add `baseline_raw_html` |
| `skill/SKILL.md` | Add clean_html to workflow + tool table |
