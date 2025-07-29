# HTML Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `clean_html` MCP tool that strips noise from raw HTML and returns token-optimized text in markdown, text, or minimal mode.

**Architecture:** Pure Python in `core/web/tokkit_scraper` using selectolax (Rust-based parser). Stateless transformation — no session required. Integrated into MCP tool dispatch, token stats, skill docs, and benchmarks.

**Tech Stack:** Python 3.11+, selectolax, pytest

**Spec:** `docs/superpowers/specs/2026-04-07-html-scraper-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `core/web/pyproject.toml` | Modify | Add selectolax dependency |
| `core/web/tokkit_scraper/__init__.py` | Modify | Public `clean_html()` API |
| `core/web/tokkit_scraper/pipeline.py` | Create | Stripping pipeline: remove, strip, collapse |
| `core/web/tokkit_scraper/markdown.py` | Create | HTML→markdown conversion |
| `core/web/tests/__init__.py` | Create | Test package init |
| `core/web/tests/test_clean_html.py` | Create | 19 unit tests for core scraper |
| `server/tokkit_server/protocol.py` | Modify:147 | Add clean_html tool definition |
| `server/tokkit_server/tools.py` | Modify:159 | Add clean_html dispatch |
| `server/tokkit_server/token_stats.py` | Modify:44,202 | Add clean_html estimation + raw_size param |
| `server/tests/test_scraper_integration.py` | Create | 4 integration tests |
| `e2e/test_mcp_scraper.py` | Create | 3 e2e tests |
| `e2e/benchmark/fixtures/html/python_docs.html` | Create | Benchmark fixture: documentation page |
| `e2e/benchmark/fixtures/html/github_readme.html` | Create | Benchmark fixture: GitHub README page |
| `e2e/benchmark/fixtures/html/blog_post.html` | Create | Benchmark fixture: blog with nav/ads |
| `e2e/benchmark/test_scraper_benchmark.py` | Create | 3 benchmark questions + report |
| `skill/SKILL.md` | Modify:95-104 | Add clean_html to workflow + tool table |

---

## Task 1: Add selectolax dependency

**Files:**
- Modify: `core/web/pyproject.toml`

- [ ] **Step 1: Add selectolax to dependencies**

In `core/web/pyproject.toml`, change `dependencies = []` to:

```toml
dependencies = ["selectolax>=0.3.21"]
```

- [ ] **Step 2: Install the dependency**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pip install -e core/web`

Expected: selectolax installs successfully, `tokkit-scraper` is editable-installed.

- [ ] **Step 3: Verify import works**

Run: `/home/edge/code/.venv/bin/python3 -c "from selectolax.parser import HTMLParser; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add core/web/pyproject.toml
git commit -m "feat(scraper): add selectolax dependency"
```

---

## Task 2: Implement stripping pipeline

**Files:**
- Create: `core/web/tokkit_scraper/pipeline.py`
- Create: `core/web/tests/__init__.py`
- Create: `core/web/tests/test_clean_html.py` (partial — pipeline tests only)

- [ ] **Step 1: Write failing tests for the stripping pipeline**

Create `core/web/tests/__init__.py` (empty file).

Create `core/web/tests/test_clean_html.py`:

```python
"""Unit tests for the HTML stripping pipeline."""

from tokkit_scraper.pipeline import strip_noise


def test_removes_script_tags():
    html = "<html><body><p>Hello</p><script>alert('x')</script></body></html>"
    result = strip_noise(html)
    assert "alert" not in result
    assert "Hello" in result


def test_removes_style_tags():
    html = "<html><body><p>Hello</p><style>.x { color: red; }</style></body></html>"
    result = strip_noise(html)
    assert "color" not in result
    assert "Hello" in result


def test_removes_head():
    html = "<html><head><title>Page</title><meta charset='utf-8'></head><body><p>Content</p></body></html>"
    result = strip_noise(html)
    assert "<title>" not in result
    assert "<meta" not in result
    assert "Content" in result


def test_removes_nav_footer_aside():
    html = """<html><body>
        <nav><a href="/">Home</a><a href="/about">About</a></nav>
        <main><p>Article content here</p></main>
        <footer><p>Copyright 2024</p></footer>
        <aside><p>Related links</p></aside>
    </body></html>"""
    result = strip_noise(html)
    assert "Article content here" in result
    assert "Home" not in result
    assert "Copyright" not in result
    assert "Related links" not in result


def test_removes_noise_by_class_id():
    html = """<html><body>
        <div class="cookie-banner">Accept cookies</div>
        <div id="gdpr-consent">GDPR stuff</div>
        <div class="sidebar-nav">Menu</div>
        <div class="ad-container">Buy now</div>
        <p>Real content</p>
    </body></html>"""
    result = strip_noise(html)
    assert "Accept cookies" not in result
    assert "GDPR stuff" not in result
    assert "Menu" not in result
    assert "Buy now" not in result
    assert "Real content" in result


def test_strips_attributes():
    html = '<html><body><p class="intro" data-id="5" style="color:red">Hello</p><a href="/page" class="link" onclick="go()">Click</a></body></html>'
    result = strip_noise(html)
    assert 'class=' not in result
    assert 'data-id' not in result
    assert 'style=' not in result
    assert 'onclick=' not in result
    assert 'href="/page"' in result
    assert "Hello" in result
    assert "Click" in result


def test_collapses_whitespace():
    html = "<html><body><p>Hello    world</p><p>   </p><p>Next</p></body></html>"
    result = strip_noise(html)
    # Multiple spaces collapsed, empty elements removed
    assert "Hello    world" not in result
    assert "Hello" in result
    assert "world" in result
    assert "Next" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/test_clean_html.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_scraper.pipeline'`

- [ ] **Step 3: Implement the stripping pipeline**

Create `core/web/tokkit_scraper/pipeline.py`:

```python
"""HTML stripping pipeline — removes noise, strips attributes, collapses whitespace."""

import re

from selectolax.parser import HTMLParser

# Tags to remove entirely (with all contents)
REMOVE_TAGS = {"script", "style", "noscript", "svg", "iframe", "head"}

# Structural noise tags to remove
NOISE_TAGS = {"nav", "header", "footer", "aside"}

# Class/id substrings that indicate noise elements
NOISE_PATTERNS = (
    "cookie", "consent", "gdpr", "sidebar", "nav", "menu",
    "ad-", "ads", "social", "share", "popup", "modal",
    "banner", "promo",
)

# Attributes to preserve (tag -> set of allowed attrs)
KEEP_ATTRS = {
    "a": {"href"},
    "img": {"href", "alt", "src"},
}

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _is_noise_element(node) -> bool:
    """Check if a node matches noise patterns by class or id."""
    for attr_name in ("class", "id"):
        val = node.attributes.get(attr_name, "")
        if val:
            val_lower = val.lower()
            for pattern in NOISE_PATTERNS:
                if pattern in val_lower:
                    return True
    return False


def _strip_attributes(tree: HTMLParser) -> None:
    """Remove all attributes except those in KEEP_ATTRS."""
    for node in tree.css("*"):
        tag = node.tag
        allowed = KEEP_ATTRS.get(tag, set())
        attrs_to_remove = []
        for attr_name in node.attributes:
            if attr_name not in allowed:
                attrs_to_remove.append(attr_name)
        for attr_name in attrs_to_remove:
            node.attrs.pop(attr_name, None)


def strip_noise(html: str) -> str:
    """Run the full stripping pipeline on raw HTML.

    Returns cleaned HTML string with noise removed, attributes stripped,
    and whitespace collapsed.
    """
    if not html or not html.strip():
        return ""

    tree = HTMLParser(html)

    # 1. Remove tags that should be entirely eliminated
    for tag in REMOVE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    # 2. Remove structural noise tags
    for tag in NOISE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    # 3. Remove elements matching noise class/id patterns
    for node in tree.css("*"):
        if _is_noise_element(node):
            node.decompose()

    # 4. Strip attributes
    _strip_attributes(tree)

    # 5. Get the cleaned HTML
    body = tree.css_first("body")
    if body:
        result = body.html or ""
    else:
        result = tree.html or ""

    # 6. Collapse whitespace
    result = _MULTI_SPACE.sub(" ", result)
    result = _MULTI_NEWLINE.sub("\n\n", result)
    result = result.strip()

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/test_clean_html.py -v`

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/web/tokkit_scraper/pipeline.py core/web/tests/__init__.py core/web/tests/test_clean_html.py
git commit -m "feat(scraper): implement HTML stripping pipeline with tests"
```

---

## Task 3: Implement markdown converter

**Files:**
- Create: `core/web/tokkit_scraper/markdown.py`
- Modify: `core/web/tests/test_clean_html.py` (add markdown tests)

- [ ] **Step 1: Write failing tests for markdown conversion**

Append to `core/web/tests/test_clean_html.py`:

```python
from tokkit_scraper.markdown import html_to_markdown


def test_markdown_headings():
    html = "<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>"
    result = html_to_markdown(html)
    assert "# Title" in result
    assert "## Subtitle" in result
    assert "### Section" in result


def test_markdown_links():
    html = '<p>Visit <a href="https://example.com">Example</a> for more.</p>'
    result = html_to_markdown(html)
    assert "[Example](https://example.com)" in result


def test_markdown_lists():
    html = "<ul><li>One</li><li>Two</li></ul><ol><li>First</li><li>Second</li></ol>"
    result = html_to_markdown(html)
    assert "- One" in result
    assert "- Two" in result
    assert "1. First" in result
    assert "2. Second" in result


def test_markdown_tables():
    html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
    result = html_to_markdown(html)
    assert "| Name | Age |" in result
    assert "| --- | --- |" in result
    assert "| Alice | 30 |" in result


def test_markdown_code_blocks():
    html = "<pre><code>def hello():\n    print('hi')</code></pre>"
    result = html_to_markdown(html)
    assert "```" in result
    assert "def hello():" in result


def test_markdown_emphasis():
    html = "<p><strong>Bold</strong> and <em>italic</em> and <b>also bold</b> and <i>also italic</i></p>"
    result = html_to_markdown(html)
    assert "**Bold**" in result
    assert "*italic*" in result
    assert "**also bold**" in result
    assert "*also italic*" in result


def test_markdown_blockquotes():
    html = "<blockquote><p>A wise quote</p></blockquote>"
    result = html_to_markdown(html)
    assert "> A wise quote" in result


def test_markdown_images():
    html = '<img alt="A cat" src="https://example.com/cat.jpg">'
    result = html_to_markdown(html)
    assert "![A cat](https://example.com/cat.jpg)" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/test_clean_html.py::test_markdown_headings -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_scraper.markdown'`

- [ ] **Step 3: Implement the markdown converter**

Create `core/web/tokkit_scraper/markdown.py`:

```python
"""HTML to Markdown converter — preserves semantic structure."""

import re

from selectolax.parser import HTMLParser


def _get_text(node) -> str:
    """Get text content of a node, stripping leading/trailing whitespace."""
    return (node.text(deep=False) or "").strip()


def _process_node(node, list_counters: dict | None = None) -> str:
    """Recursively convert an HTML node to markdown."""
    if list_counters is None:
        list_counters = {}

    tag = node.tag if hasattr(node, "tag") else ""

    # Skip removed/empty nodes
    if tag in ("-text", "-comment"):
        text = node.text(deep=False) or ""
        return text

    # Headings
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        text = (node.text(deep=True) or "").strip()
        if text:
            return f"\n\n{'#' * level} {text}\n\n"
        return ""

    # Links
    if tag == "a":
        href = node.attributes.get("href", "")
        text = (node.text(deep=True) or "").strip()
        if text and href:
            return f"[{text}]({href})"
        return text

    # Images
    if tag == "img":
        alt = node.attributes.get("alt", "")
        src = node.attributes.get("src", "")
        if alt and src:
            return f"![{alt}]({src})"
        return ""

    # Bold
    if tag in ("strong", "b"):
        text = (node.text(deep=True) or "").strip()
        if text:
            return f"**{text}**"
        return ""

    # Italic
    if tag in ("em", "i"):
        text = (node.text(deep=True) or "").strip()
        if text:
            return f"*{text}*"
        return ""

    # Code blocks
    if tag == "pre":
        code_node = node.css_first("code")
        if code_node:
            code_text = code_node.text(deep=True) or ""
        else:
            code_text = node.text(deep=True) or ""
        return f"\n\n```\n{code_text}\n```\n\n"

    # Inline code
    if tag == "code":
        # If parent is <pre>, skip — handled by pre
        if node.parent and node.parent.tag == "pre":
            return ""
        text = node.text(deep=True) or ""
        return f"`{text}`"

    # Blockquote
    if tag == "blockquote":
        children_md = _process_children(node, list_counters)
        lines = children_md.strip().split("\n")
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"\n\n{quoted}\n\n"

    # Unordered list
    if tag == "ul":
        items = []
        for li in node.css("li"):
            if li.parent == node:  # direct children only
                text = (li.text(deep=True) or "").strip()
                if text:
                    items.append(f"- {text}")
        return "\n\n" + "\n".join(items) + "\n\n" if items else ""

    # Ordered list
    if tag == "ol":
        items = []
        for idx, li in enumerate(node.css("li"), 1):
            if li.parent == node:
                text = (li.text(deep=True) or "").strip()
                if text:
                    items.append(f"{idx}. {text}")
        return "\n\n" + "\n".join(items) + "\n\n" if items else ""

    # List items (handled by ul/ol above, skip standalone)
    if tag == "li":
        return ""

    # Table
    if tag == "table":
        return _convert_table(node)

    # Paragraph / div — add line breaks
    if tag in ("p", "div", "section", "article", "main"):
        children_md = _process_children(node, list_counters)
        text = children_md.strip()
        if text:
            return f"\n\n{text}\n\n"
        return ""

    # Line break
    if tag == "br":
        return "\n"

    # Horizontal rule
    if tag == "hr":
        return "\n\n---\n\n"

    # Default: process children
    return _process_children(node, list_counters)


def _process_children(node, list_counters: dict | None = None) -> str:
    """Process all children of a node and concatenate results."""
    parts = []
    for child in node.iter():
        if child == node:
            continue
        # Only process direct children to avoid double-processing
        if child.parent == node:
            parts.append(_process_node(child, list_counters))
    # Also grab direct text content of this node
    text = node.text(deep=False) or ""
    if text.strip():
        parts.insert(0, text)
    return "".join(parts)


def _convert_table(table_node) -> str:
    """Convert an HTML table to markdown table."""
    rows = []
    for tr in table_node.css("tr"):
        cells = []
        for cell in tr.css("th, td"):
            cells.append((cell.text(deep=True) or "").strip())
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    # Determine column count from widest row
    col_count = max(len(row) for row in rows)

    # Pad rows to same width
    for row in rows:
        while len(row) < col_count:
            row.append("")

    lines = []
    # First row as header
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")
    # Remaining rows
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n\n" + "\n".join(lines) + "\n\n"


_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def html_to_markdown(html: str) -> str:
    """Convert HTML string to markdown.

    Assumes noise has already been stripped by pipeline.strip_noise().
    """
    if not html or not html.strip():
        return ""

    tree = HTMLParser(html)
    body = tree.css_first("body")
    root = body if body else tree.root

    if root is None:
        return ""

    result = _process_node(root)

    # Clean up whitespace
    result = _MULTI_SPACE.sub(" ", result)
    result = _MULTI_NEWLINE.sub("\n\n", result)
    result = result.strip()

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/test_clean_html.py -v`

Expected: All 15 tests PASS (7 pipeline + 8 markdown).

- [ ] **Step 5: Commit**

```bash
git add core/web/tokkit_scraper/markdown.py core/web/tests/test_clean_html.py
git commit -m "feat(scraper): implement HTML to markdown converter with tests"
```

---

## Task 4: Implement `clean_html` public API

**Files:**
- Modify: `core/web/tokkit_scraper/__init__.py`
- Modify: `core/web/tests/test_clean_html.py` (add mode tests)

- [ ] **Step 1: Write failing tests for the public API**

Append to `core/web/tests/test_clean_html.py`:

```python
from tokkit_scraper import clean_html


def test_text_mode():
    html = "<html><body><h1>Title</h1><p>Hello <strong>world</strong></p></body></html>"
    result = clean_html(html, mode="text")
    assert "Title" in result
    assert "Hello" in result
    assert "world" in result
    assert "#" not in result
    assert "**" not in result
    assert "<" not in result


def test_minimal_mode():
    html = """<html><body>
        <script>alert('x')</script>
        <style>.x{}</style>
        <!-- comment -->
        <nav><a href="/">Home</a></nav>
        <p class="intro">Content</p>
    </body></html>"""
    result = clean_html(html, mode="minimal")
    # Scripts, styles, comments removed
    assert "alert" not in result
    assert ".x{}" not in result
    assert "comment" not in result
    # But nav and class preserved in minimal mode
    assert "Home" in result
    assert "Content" in result


def test_empty_input():
    assert clean_html("") == ""
    assert clean_html("   ") == ""


def test_invalid_mode_raises():
    import pytest
    with pytest.raises(ValueError, match="mode"):
        clean_html("<p>Hi</p>", mode="invalid")


def test_markdown_mode_default():
    html = "<html><body><h1>Title</h1><p>Paragraph</p></body></html>"
    result = clean_html(html)
    assert "# Title" in result
    assert "Paragraph" in result


def test_full_pipeline_markdown():
    """Integration: noise stripping + markdown conversion together."""
    html = """<html>
    <head><title>Page</title></head>
    <body>
        <nav><a href="/">Home</a></nav>
        <script>tracking()</script>
        <main>
            <h1>Article</h1>
            <p>Read <a href="/more">more here</a>.</p>
        </main>
        <footer>Copyright</footer>
    </body></html>"""
    result = clean_html(html, mode="markdown")
    assert "# Article" in result
    assert "[more here](/more)" in result
    assert "Home" not in result
    assert "tracking" not in result
    assert "Copyright" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/test_clean_html.py::test_text_mode -v`

Expected: FAIL — `ImportError: cannot import name 'clean_html' from 'tokkit_scraper'`

- [ ] **Step 3: Implement the public API**

Replace `core/web/tokkit_scraper/__init__.py` with:

```python
"""Tokkit Scraper — Token-optimized web scraping engine."""

__version__ = "0.1.0"

from selectolax.parser import HTMLParser

from tokkit_scraper.pipeline import strip_noise, REMOVE_TAGS

_VALID_MODES = {"markdown", "text", "minimal"}


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
        ValueError: If mode is not one of the valid values.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")

    if not html or not html.strip():
        return ""

    if mode == "minimal":
        return _clean_minimal(html)

    # Full noise stripping for markdown and text modes
    cleaned_html = strip_noise(html)

    if mode == "text":
        return _extract_text(cleaned_html)

    # mode == "markdown"
    from tokkit_scraper.markdown import html_to_markdown
    return html_to_markdown(cleaned_html)


def _clean_minimal(html: str) -> str:
    """Minimal mode: remove only scripts, styles, noscript, comments, head."""
    tree = HTMLParser(html)
    for tag in REMOVE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    body = tree.css_first("body")
    result = body.html if body else tree.html
    return (result or "").strip()


def _extract_text(html: str) -> str:
    """Text mode: extract visible text, normalize whitespace."""
    import re
    tree = HTMLParser(html)
    body = tree.css_first("body")
    root = body if body else tree.root
    if root is None:
        return ""
    text = root.text(separator="\n", deep=True) or ""
    # Collapse whitespace but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()
```

- [ ] **Step 4: Run all unit tests to verify they pass**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/test_clean_html.py -v`

Expected: All 21 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/web/tokkit_scraper/__init__.py core/web/tests/test_clean_html.py
git commit -m "feat(scraper): implement clean_html public API with three modes"
```

---

## Task 5: Add MCP tool definition and dispatch

**Files:**
- Modify: `server/tokkit_server/protocol.py:147` (insert before closing `]`)
- Modify: `server/tokkit_server/tools.py:159` (insert before `get_token_stats` case)
- Modify: `server/tokkit_server/token_stats.py:44,202` (add clean_html estimation + raw_size)

- [ ] **Step 1: Write failing integration tests**

Create `server/tests/test_scraper_integration.py`:

```python
"""Integration tests for clean_html MCP tool dispatch."""

import json
from unittest.mock import patch

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_clean_html_tool_dispatch():
    _reset_session()
    html = "<html><body><h1>Title</h1><script>x</script><p>Content</p></body></html>"
    result = handle_tool_call("clean_html", {"html": html, "mode": "markdown"})
    assert not result.get("isError")
    text = result["content"][0]["text"]
    assert "# Title" in text
    assert "Content" in text
    assert "script" not in text.lower()


def test_clean_html_no_session_required():
    _reset_session()
    # No index_repository called — should still work
    html = "<p>Hello</p>"
    result = handle_tool_call("clean_html", {"html": html})
    assert not result.get("isError")
    assert "Hello" in result["content"][0]["text"]


def test_clean_html_token_stats_recorded():
    _reset_session()
    html = "<html><body>" + "<p>Content</p>" * 100 + "</body></html>"
    result = handle_tool_call("clean_html", {"html": html})
    assert not result.get("isError")
    meta = result.get("_meta", {}).get("token_savings", {})
    assert meta.get("tokens_avoided", 0) > 0
    assert meta.get("tokens_used", 0) > 0
    assert meta["tokens_avoided"] >= meta["tokens_used"]


def test_clean_html_error_on_missing_html():
    result = handle_tool_call("clean_html", {})
    assert result.get("isError") is True
    assert "html is required" in result["content"][0]["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest server/tests/test_scraper_integration.py -v`

Expected: FAIL — tool dispatch returns "Unknown tool: clean_html"

- [ ] **Step 3: Add tool definition to protocol.py**

In `server/tokkit_server/protocol.py`, insert before the closing `]` on line 148 (after the `get_token_stats` definition):

```python
    {
        "name": "clean_html",
        "description": "Strip irrelevant tags, attributes, and noise from HTML. Returns token-optimized text for LLM analysis/research. Does not require an indexed project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "Raw HTML content to clean.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["markdown", "text", "minimal"],
                    "description": "Output mode. 'markdown' (default): semantic structure as markdown. 'text': plain text only. 'minimal': light clean, keep HTML structure.",
                },
            },
            "required": ["html"],
        },
    },
```

- [ ] **Step 4: Add dispatch case to tools.py**

In `server/tokkit_server/tools.py`, insert before line 159 (`if tool_name == "get_token_stats":`):

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

- [ ] **Step 5: Update token_stats.py — add raw_size param to make_meta**

In `server/tokkit_server/token_stats.py`, replace the `make_meta` function (lines 202-218) with:

```python
def make_meta(tool_name: str, result_text: str, session_project_path: str | None, raw_size: int | None = None) -> dict:
    """Build the _meta field for a tool response.

    Also records the query to persistent stats.
    Returns a dict to be added to the tool result.
    """
    tokens_used = len(result_text) // CHARS_PER_TOKEN
    tokens_avoided = estimate_tokens_avoided(tool_name, {}, result_text, session_project_path, raw_size=raw_size)
    tokens_saved = max(0, tokens_avoided - tokens_used)

    record_query(tool_name, tokens_used, tokens_avoided)

    return {
        "tokens_used": tokens_used,
        "tokens_avoided": tokens_avoided,
        "tokens_saved": tokens_saved,
    }
```

- [ ] **Step 6: Update token_stats.py — add clean_html case to estimate_tokens_avoided**

In `server/tokkit_server/token_stats.py`, update the `estimate_tokens_avoided` function signature (line 44) to accept `raw_size`:

```python
def estimate_tokens_avoided(tool_name: str, args: dict, result_text: str, session_project_path: str | None, raw_size: int | None = None) -> int:
```

Then insert before the `return 0` at line 115:

```python
    if tool_name == "clean_html":
        # Without tokkit: agent consumes the full raw HTML
        if raw_size:
            return raw_size // CHARS_PER_TOKEN
        # Fallback: assume cleaned output is ~40% of original
        return len(result_text) * 2 // CHARS_PER_TOKEN
```

- [ ] **Step 7: Run integration tests to verify they pass**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest server/tests/test_scraper_integration.py -v`

Expected: All 4 tests PASS.

- [ ] **Step 8: Run ALL existing tests to check for regressions**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest server/tests/ core/web/tests/ -v`

Expected: All tests PASS (existing + new).

- [ ] **Step 9: Commit**

```bash
git add server/tokkit_server/protocol.py server/tokkit_server/tools.py server/tokkit_server/token_stats.py server/tests/test_scraper_integration.py
git commit -m "feat(scraper): add clean_html MCP tool with dispatch and token stats"
```

---

## Task 6: Add E2E tests

**Files:**
- Create: `e2e/test_mcp_scraper.py`

- [ ] **Step 1: Write the E2E tests**

Create `e2e/test_mcp_scraper.py`:

```python
"""E2E tests for clean_html MCP tool — full JSON-RPC flow."""

import json


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Page</title><style>.x{}</style></head>
<body>
    <nav><a href="/">Home</a><a href="/about">About</a></nav>
    <script>analytics.track('page_view');</script>
    <main>
        <h1>Welcome to Testing</h1>
        <p>This is a <strong>test page</strong> with some content.</p>
        <ul>
            <li>Item one</li>
            <li>Item two</li>
        </ul>
        <table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>Key</td><td>123</td></tr>
        </table>
    </main>
    <footer><p>Copyright 2024</p></footer>
</body>
</html>"""


def test_clean_html_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "clean_html" in tool_names


def test_clean_html_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "clean_html",
        "arguments": {"html": SAMPLE_HTML, "mode": "markdown"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    # Verify noise stripped and markdown generated
    assert "# Welcome to Testing" in content
    assert "**test page**" in content
    assert "- Item one" in content
    assert "| Name | Value |" in content
    # Verify noise removed
    assert "analytics" not in content
    assert "Home" not in content  # nav stripped
    assert "Copyright" not in content  # footer stripped


def test_clean_html_real_page(mcp_server):
    """Verify token reduction on a realistic HTML page."""
    mcp_server.send("initialize", {})
    raw_tokens = len(SAMPLE_HTML) // 4
    resp = mcp_server.send("tools/call", {
        "name": "clean_html",
        "arguments": {"html": SAMPLE_HTML, "mode": "markdown"},
    })
    content = resp["result"]["content"][0]["text"]
    cleaned_tokens = len(content) // 4
    # Cleaned should be significantly smaller
    assert cleaned_tokens < raw_tokens
    # At least 40% reduction on this sample
    savings_pct = (1 - cleaned_tokens / raw_tokens) * 100
    assert savings_pct > 40, f"Only {savings_pct:.1f}% savings, expected >40%"
```

- [ ] **Step 2: Run E2E tests**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/test_mcp_scraper.py -v`

Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add e2e/test_mcp_scraper.py
git commit -m "test(scraper): add E2E tests for clean_html MCP tool"
```

---

## Task 7: Add benchmark fixtures and benchmark tests

**Files:**
- Create: `e2e/benchmark/fixtures/html/python_docs.html`
- Create: `e2e/benchmark/fixtures/html/github_readme.html`
- Create: `e2e/benchmark/fixtures/html/blog_post.html`
- Create: `e2e/benchmark/test_scraper_benchmark.py`

- [ ] **Step 1: Create HTML fixture directory**

Run: `mkdir -p /home/edge/code/research/tokkit/e2e/benchmark/fixtures/html`

- [ ] **Step 2: Create benchmark HTML fixtures**

Create `e2e/benchmark/fixtures/html/python_docs.html` — a realistic Python documentation page. Use a simplified but representative structure (~5KB of HTML that includes nav, sidebar, content, footer, scripts):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>json — JSON encoder and decoder — Python 3.12 documentation</title>
    <style>
        body { font-family: sans-serif; }
        .sidebar { width: 250px; float: left; }
        .content { margin-left: 270px; }
        .footer { clear: both; padding: 20px; }
        .nav { background: #333; color: white; padding: 10px; }
        .breadcrumb { padding: 5px; }
        .related { margin: 10px 0; }
        .sphinxsidebar { background: #f0f0f0; }
        pre { background: #f5f5f5; padding: 10px; }
        code { background: #f0f0f0; padding: 2px 4px; }
        .admonition { border: 1px solid #ddd; padding: 10px; }
        .deprecated { background: #fff3cd; }
        .versionadded { background: #d4edda; }
    </style>
    <script>
        var DOCUMENTATION_OPTIONS = { URL_ROOT: '../', VERSION: '3.12.0', COLLAPSE_INDEX: false };
    </script>
    <script src="_static/jquery.js"></script>
    <script src="_static/underscore.js"></script>
    <script src="_static/doctools.js"></script>
    <script src="_static/searchtools.js"></script>
</head>
<body>
    <nav class="nav">
        <a href="../index.html">Python</a> |
        <a href="../genindex.html">Index</a> |
        <a href="../py-modindex.html">Modules</a> |
        <a href="../search.html">Search</a>
    </nav>

    <div class="breadcrumb">
        <a href="../index.html">Python 3.12 Docs</a> &raquo;
        <a href="index.html">Library Reference</a> &raquo;
        json — JSON encoder and decoder
    </div>

    <div class="related">
        <span>Previous: <a href="csv.html">csv</a></span>
        <span>Next: <a href="xml.html">xml</a></span>
    </div>

    <aside class="sphinxsidebar">
        <h3>Table of Contents</h3>
        <ul>
            <li><a href="#module-json">json — JSON encoder and decoder</a></li>
            <li><a href="#json.dumps">json.dumps</a></li>
            <li><a href="#json.loads">json.loads</a></li>
            <li><a href="#json.dump">json.dump</a></li>
            <li><a href="#json.load">json.load</a></li>
            <li><a href="#json.JSONEncoder">JSONEncoder</a></li>
            <li><a href="#json.JSONDecoder">JSONDecoder</a></li>
        </ul>
        <h3>Quick Search</h3>
        <form action="../search.html"><input type="text" name="q" placeholder="Search docs"></form>
    </aside>

    <main class="content">
        <h1 id="module-json">json — JSON encoder and decoder</h1>

        <p><strong>Source code:</strong> <a href="https://github.com/python/cpython/blob/3.12/Lib/json/__init__.py">Lib/json/__init__.py</a></p>

        <p>JSON (JavaScript Object Notation), specified by <a href="https://tools.ietf.org/html/rfc7159">RFC 7159</a> and by <a href="https://ecma-international.org/publications-and-standards/standards/ecma-404/">ECMA-404</a>, is a lightweight data interchange format inspired by JavaScript object literal syntax.</p>

        <div class="admonition warning">
            <p><strong>Warning:</strong> Be cautious when parsing JSON data from untrusted sources. A malicious JSON string may cause the decoder to consume considerable CPU and memory resources.</p>
        </div>

        <h2 id="json.dumps">json.dumps</h2>

        <p><code>json.dumps(obj, *, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=None, separators=None, default=None, sort_keys=False, **kw)</code></p>

        <p>Serialize <em>obj</em> to a JSON formatted <code>str</code> using this conversion table. The arguments have the same meaning as in <code>dump()</code>.</p>

        <div class="versionadded">
            <p><strong>New in version 3.2:</strong> Allow <em>indent</em> to be a string.</p>
        </div>

        <pre><code>>>> import json
>>> json.dumps(['foo', {'bar': ('baz', None, 1.0, 2)}])
'["foo", {"bar": ["baz", null, 1.0, 2]}]'
>>> json.dumps({"c": 0, "b": 0, "a": 0}, sort_keys=True)
'{"a": 0, "b": 0, "c": 0}'</code></pre>

        <h2 id="json.loads">json.loads</h2>

        <p><code>json.loads(s, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw)</code></p>

        <p>Deserialize <em>s</em> (a <code>str</code>, <code>bytes</code> or <code>bytearray</code> instance containing a JSON document) to a Python object using this conversion table.</p>

        <pre><code>>>> import json
>>> json.loads('["foo", {"bar":["baz", null, 1.0, 2]}]')
['foo', {'bar': ['baz', None, 1.0, 2]}]</code></pre>

        <h2 id="json.dump">json.dump</h2>

        <p><code>json.dump(obj, fp, *, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=None, separators=None, default=None, sort_keys=False, **kw)</code></p>

        <p>Serialize <em>obj</em> as a JSON formatted stream to <em>fp</em> (a <code>.write()</code>-supporting file-like object) using this conversion table.</p>

        <h2 id="json.load">json.load</h2>

        <p><code>json.load(fp, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw)</code></p>

        <p>Deserialize <em>fp</em> (a <code>.read()</code>-supporting file-like object containing a JSON document) to a Python object using this conversion table.</p>

        <h2 id="json.JSONEncoder">class json.JSONEncoder</h2>

        <p>Extensible JSON encoder for Python data structures. Supports the following objects and types by default:</p>

        <table>
            <tr><th>Python</th><th>JSON</th></tr>
            <tr><td>dict</td><td>object</td></tr>
            <tr><td>list, tuple</td><td>array</td></tr>
            <tr><td>str</td><td>string</td></tr>
            <tr><td>int, float</td><td>number</td></tr>
            <tr><td>True</td><td>true</td></tr>
            <tr><td>False</td><td>false</td></tr>
            <tr><td>None</td><td>null</td></tr>
        </table>

        <h2 id="json.JSONDecoder">class json.JSONDecoder</h2>

        <p>Simple JSON decoder. Performs the following translations in decoding by default:</p>

        <table>
            <tr><th>JSON</th><th>Python</th></tr>
            <tr><td>object</td><td>dict</td></tr>
            <tr><td>array</td><td>list</td></tr>
            <tr><td>string</td><td>str</td></tr>
            <tr><td>number (int)</td><td>int</td></tr>
            <tr><td>number (real)</td><td>float</td></tr>
            <tr><td>true</td><td>True</td></tr>
            <tr><td>false</td><td>False</td></tr>
            <tr><td>null</td><td>None</td></tr>
        </table>
    </main>

    <footer class="footer">
        <p>&copy; 2001-2024, Python Software Foundation. Licensed under the Python Software Foundation License.</p>
        <p>The Python Software Foundation is a non-profit corporation. <a href="https://www.python.org/psf/donations/">Please donate.</a></p>
        <p>Last updated on Oct 02, 2024. Found a bug? <a href="https://docs.python.org/3/bugs.html">Report it here.</a></p>
    </footer>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var sidebar = document.querySelector('.sphinxsidebar');
            window.addEventListener('scroll', function() {
                sidebar.style.top = Math.max(0, 50 - window.scrollY) + 'px';
            });
        });
    </script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=UA-XXXXX"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'UA-XXXXX');
    </script>
</body>
</html>
```

Create `e2e/benchmark/fixtures/html/github_readme.html` — a realistic GitHub repository page:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>fastapi/fastapi: FastAPI framework — GitHub</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
        .header { background: #24292e; color: white; padding: 16px; }
        .header-nav a { color: white; margin: 0 8px; }
        .repohead { padding: 16px; border-bottom: 1px solid #e1e4e8; }
        .pagehead-actions { float: right; }
        .btn { padding: 6px 12px; border: 1px solid #ccc; border-radius: 4px; }
        .social-count { font-size: 12px; }
        .repository-content { max-width: 1012px; margin: 0 auto; }
        .file-navigation { padding: 16px 0; }
        .Box-row { padding: 8px 16px; border-bottom: 1px solid #eee; }
        .sidebar { float: right; width: 296px; }
        .topic-tag { background: #ddf4ff; color: #0969da; padding: 2px 8px; border-radius: 12px; }
        .flash { padding: 16px; background: #fff8c5; border: 1px solid #d4a72c; margin-bottom: 16px; }
        .footer { padding: 40px 0; border-top: 1px solid #e1e4e8; color: #6a737d; font-size: 12px; }
        .footer-nav a { color: #0366d6; margin: 0 8px; }
        pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; }
        .markdown-body h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
        .markdown-body h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
    </style>
    <script src="/assets/vendor.js"></script>
    <script src="/assets/github.js"></script>
    <script>
        document.addEventListener('pjax:click', function() { /* analytics */ });
        window._octo = window._octo || [];
        _octo.push(['recordPageView']);
    </script>
</head>
<body>
    <header class="header">
        <nav class="header-nav">
            <a href="https://github.com">
                <svg height="32" viewBox="0 0 16 16" width="32"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49"></path></svg>
            </a>
            <a href="/explore">Explore</a>
            <a href="/marketplace">Marketplace</a>
            <a href="/pulls">Pull requests</a>
            <a href="/issues">Issues</a>
            <a href="/codespaces">Codespaces</a>
        </nav>
        <div class="header-search">
            <form action="/search"><input type="text" placeholder="Search or jump to..."></form>
        </div>
    </header>

    <div class="repohead">
        <h1><a href="/fastapi">fastapi</a> / <strong><a href="/fastapi/fastapi">fastapi</a></strong></h1>
        <div class="pagehead-actions">
            <form action="/notifications/subscribe"><button class="btn">Watch</button></form>
            <a class="btn" href="/fastapi/fastapi/fork">Fork <span class="social-count">5.8k</span></a>
            <a class="btn" href="/fastapi/fastapi/stargazers">Star <span class="social-count">78.5k</span></a>
        </div>
    </div>

    <div class="repository-content">
        <div class="flash">
            <strong>Sponsor</strong> this project — <a href="https://github.com/sponsors/tiangolo">github.com/sponsors/tiangolo</a>
        </div>

        <nav class="file-navigation">
            <a href="/fastapi/fastapi">Code</a>
            <a href="/fastapi/fastapi/issues">Issues <span>350</span></a>
            <a href="/fastapi/fastapi/pulls">Pull requests <span>42</span></a>
            <a href="/fastapi/fastapi/actions">Actions</a>
            <a href="/fastapi/fastapi/security">Security</a>
        </nav>

        <aside class="sidebar">
            <h3>About</h3>
            <p>FastAPI framework, high performance, easy to learn, fast to code, ready for production</p>
            <div>
                <span class="topic-tag">python</span>
                <span class="topic-tag">api</span>
                <span class="topic-tag">rest</span>
                <span class="topic-tag">fastapi</span>
                <span class="topic-tag">async</span>
                <span class="topic-tag">pydantic</span>
            </div>
            <h3>Releases</h3>
            <a href="/fastapi/fastapi/releases">143 releases</a>
            <h3>Contributors</h3>
            <p>684 contributors</p>
            <h3>Languages</h3>
            <p>Python 99.9%</p>
        </aside>

        <article class="markdown-body">
            <h1>FastAPI</h1>

            <p><em>FastAPI framework, high performance, easy to learn, fast to code, ready for production</em></p>

            <p><a href="https://fastapi.tiangolo.com">Documentation</a> | <a href="https://github.com/fastapi/fastapi">Source Code</a></p>

            <p>FastAPI is a modern, fast (high-performance), web framework for building APIs with Python based on standard Python type hints.</p>

            <h2>Key Features</h2>

            <ul>
                <li><strong>Fast</strong>: Very high performance, on par with NodeJS and Go (thanks to Starlette and Pydantic).</li>
                <li><strong>Fast to code</strong>: Increase the speed to develop features by about 200% to 300%.</li>
                <li><strong>Fewer bugs</strong>: Reduce about 40% of human (developer) induced errors.</li>
                <li><strong>Intuitive</strong>: Great editor support. Completion everywhere. Less time debugging.</li>
                <li><strong>Easy</strong>: Designed to be easy to use and learn. Less time reading docs.</li>
                <li><strong>Short</strong>: Minimize code duplication. Multiple features from each parameter declaration.</li>
                <li><strong>Robust</strong>: Get production-ready code. With automatic interactive documentation.</li>
                <li><strong>Standards-based</strong>: Based on the open standards for APIs: OpenAPI and JSON Schema.</li>
            </ul>

            <h2>Installation</h2>

            <pre><code>pip install fastapi</code></pre>

            <p>You will also need an ASGI server, for production such as <a href="https://www.uvicorn.org">Uvicorn</a> or <a href="https://github.com/pgjones/hypercorn">Hypercorn</a>.</p>

            <pre><code>pip install "uvicorn[standard]"</code></pre>

            <h2>Example</h2>

            <h3>Create it</h3>

            <p>Create a file <code>main.py</code> with:</p>

            <pre><code>from typing import Union
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}</code></pre>

            <h3>Run it</h3>

            <pre><code>uvicorn main:app --reload</code></pre>

            <h3>Check it</h3>

            <p>Open your browser at <a href="http://127.0.0.1:8000/items/5?q=somequery">http://127.0.0.1:8000/items/5?q=somequery</a>.</p>

            <p>You will see the JSON response as:</p>

            <pre><code>{"item_id": 5, "q": "somequery"}</code></pre>

            <h2>License</h2>

            <p>This project is licensed under the terms of the <a href="https://github.com/fastapi/fastapi/blob/master/LICENSE">MIT license</a>.</p>
        </article>
    </div>

    <footer class="footer">
        <nav class="footer-nav">
            <a href="https://docs.github.com/en/github/site-policy/github-terms-of-service">Terms</a>
            <a href="https://docs.github.com/en/github/site-policy/github-privacy-statement">Privacy</a>
            <a href="https://github.com/security">Security</a>
            <a href="https://www.githubstatus.com/">Status</a>
            <a href="https://docs.github.com">Docs</a>
            <a href="https://github.com/contact">Contact</a>
            <a href="https://github.com/pricing">Pricing</a>
            <a href="https://docs.github.com/en/developers">API</a>
            <a href="https://training.github.com">Training</a>
            <a href="https://github.blog">Blog</a>
            <a href="https://github.com/about">About</a>
        </nav>
        <p>&copy; 2024 GitHub, Inc.</p>
    </footer>

    <script>
        (function() {
            var ga = document.createElement('script');
            ga.type = 'text/javascript'; ga.async = true;
            ga.src = 'https://ssl.google-analytics.com/ga.js';
            document.getElementsByTagName('head')[0].appendChild(ga);
        })();
    </script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Lazy load images, setup copy buttons, handle keyboard nav
            document.querySelectorAll('.js-navigation-item').forEach(function(el) {
                el.addEventListener('keydown', function(e) { /* keyboard nav */ });
            });
        });
    </script>
</body>
</html>
```

Create `e2e/benchmark/fixtures/html/blog_post.html` — a blog post with heavy ads/nav:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Understanding Async Python: A Deep Dive — TechBlog</title>
    <meta name="description" content="A comprehensive guide to async programming in Python">
    <meta name="keywords" content="python, async, asyncio, tutorial">
    <meta property="og:title" content="Understanding Async Python">
    <meta property="og:type" content="article">
    <style>
        body { font-family: Georgia, serif; line-height: 1.6; }
        .site-header { background: #1a1a2e; color: white; padding: 20px; }
        .site-nav a { color: #e0e0e0; margin: 0 12px; text-decoration: none; }
        .breadcrumb { padding: 8px 0; font-size: 14px; color: #666; }
        .article-meta { color: #666; font-size: 14px; margin-bottom: 20px; }
        .article-content { max-width: 720px; margin: 0 auto; }
        .sidebar { float: right; width: 300px; padding: 20px; }
        .ad-container { background: #f5f5f5; border: 1px solid #ddd; padding: 20px; margin: 20px 0; text-align: center; }
        .ad-label { font-size: 10px; color: #999; }
        .social-share { padding: 20px 0; border-top: 1px solid #eee; }
        .social-share a { margin: 0 8px; }
        .newsletter-popup { display: none; position: fixed; background: white; border: 2px solid #333; padding: 30px; }
        .cookie-banner { position: fixed; bottom: 0; background: #333; color: white; padding: 15px; width: 100%; }
        .related-posts { padding: 20px 0; }
        .comments-section { padding: 20px 0; border-top: 1px solid #eee; }
        .site-footer { background: #1a1a2e; color: #ccc; padding: 40px 20px; }
        .footer-links a { color: #aaa; margin: 0 8px; }
        pre { background: #282c34; color: #abb2bf; padding: 20px; border-radius: 8px; overflow-x: auto; }
        code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
        blockquote { border-left: 4px solid #e0e0e0; padding-left: 16px; color: #555; }
    </style>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXX"></script>
    <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-XXXXX');</script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
    <script src="/assets/app.bundle.js"></script>
    <script>
        // Cookie consent management
        (function() {
            var consent = localStorage.getItem('cookie_consent');
            if (!consent) {
                document.addEventListener('DOMContentLoaded', function() {
                    document.querySelector('.cookie-banner').style.display = 'block';
                });
            }
        })();
    </script>
</head>
<body>
    <header class="site-header">
        <div class="site-logo"><a href="/">TechBlog</a></div>
        <nav class="site-nav">
            <a href="/">Home</a>
            <a href="/python">Python</a>
            <a href="/javascript">JavaScript</a>
            <a href="/devops">DevOps</a>
            <a href="/ai-ml">AI/ML</a>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
            <a href="/newsletter">Newsletter</a>
        </nav>
    </header>

    <div class="breadcrumb">
        <a href="/">Home</a> &gt; <a href="/python">Python</a> &gt; Understanding Async Python
    </div>

    <div class="ad-container">
        <div class="ad-label">ADVERTISEMENT</div>
        <p>Master Python in 30 Days — Online Course — 50% OFF!</p>
        <a href="https://ads.example.com/python-course">Learn More</a>
    </div>

    <aside class="sidebar">
        <div class="ad-container">
            <div class="ad-label">SPONSORED</div>
            <p>Cloud Hosting from $5/mo</p>
        </div>
        <h3>Popular Posts</h3>
        <ul>
            <li><a href="/post/1">10 Python Tips</a></li>
            <li><a href="/post/2">Django vs Flask</a></li>
            <li><a href="/post/3">Getting Started with ML</a></li>
        </ul>
        <h3>Categories</h3>
        <ul>
            <li><a href="/python">Python (45)</a></li>
            <li><a href="/javascript">JavaScript (32)</a></li>
            <li><a href="/devops">DevOps (18)</a></li>
        </ul>
        <div class="ad-container">
            <div class="ad-label">ADVERTISEMENT</div>
            <p>Free eBook: Python Best Practices</p>
        </div>
    </aside>

    <article class="article-content">
        <h1>Understanding Async Python: A Deep Dive</h1>

        <div class="article-meta">
            <span>By <a href="/author/jane">Jane Smith</a></span> |
            <span>Published: March 15, 2024</span> |
            <span>Updated: March 20, 2024</span> |
            <span>12 min read</span>
        </div>

        <p>Asynchronous programming has become an essential skill for Python developers. Whether you're building web APIs, processing data pipelines, or creating real-time applications, understanding <code>asyncio</code> and its ecosystem is crucial.</p>

        <blockquote>
            <p>"Concurrency is not parallelism." — Rob Pike</p>
        </blockquote>

        <h2>What is Async Programming?</h2>

        <p>At its core, async programming allows your program to handle multiple operations without waiting for each one to complete before starting the next. This is particularly useful for <strong>I/O-bound</strong> operations like:</p>

        <ul>
            <li>Network requests (HTTP calls, database queries)</li>
            <li>File operations (reading/writing large files)</li>
            <li>User input handling</li>
            <li>WebSocket connections</li>
        </ul>

        <h2>The Event Loop</h2>

        <p>The event loop is the heart of async Python. It manages and distributes the execution of different tasks. Think of it as a <em>task scheduler</em> that decides which coroutine runs next.</p>

        <pre><code>import asyncio

async def fetch_data(url: str) -> dict:
    """Fetch data from a URL asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def main():
    urls = [
        "https://api.example.com/users",
        "https://api.example.com/posts",
        "https://api.example.com/comments",
    ]
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    for result in results:
        print(result)

asyncio.run(main())</code></pre>

        <h2>Coroutines vs Threads</h2>

        <p>A common question is: when should I use coroutines vs threads?</p>

        <table>
            <tr>
                <th>Feature</th>
                <th>Coroutines (asyncio)</th>
                <th>Threads</th>
            </tr>
            <tr>
                <td>Best for</td>
                <td>I/O-bound tasks</td>
                <td>CPU-bound tasks (with GIL caveats)</td>
            </tr>
            <tr>
                <td>Memory overhead</td>
                <td>Low (~1KB per coroutine)</td>
                <td>High (~8MB per thread stack)</td>
            </tr>
            <tr>
                <td>Context switching</td>
                <td>Cooperative (explicit await)</td>
                <td>Preemptive (OS-managed)</td>
            </tr>
            <tr>
                <td>Race conditions</td>
                <td>Rare (single-threaded)</td>
                <td>Common (shared state)</td>
            </tr>
            <tr>
                <td>Debugging</td>
                <td>Easier (deterministic)</td>
                <td>Harder (non-deterministic)</td>
            </tr>
        </table>

        <h2>Practical Patterns</h2>

        <h3>Pattern 1: Concurrent API Calls</h3>

        <pre><code>async def fetch_all_users(user_ids: list[int]) -> list[User]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_user(session, uid)
            for uid in user_ids
        ]
        return await asyncio.gather(*tasks)</code></pre>

        <h3>Pattern 2: Producer-Consumer</h3>

        <pre><code>async def producer(queue: asyncio.Queue):
    for i in range(100):
        await queue.put(f"item-{i}")
    await queue.put(None)  # sentinel

async def consumer(queue: asyncio.Queue):
    while True:
        item = await queue.get()
        if item is None:
            break
        await process(item)</code></pre>

        <h3>Pattern 3: Timeout and Retry</h3>

        <pre><code>async def fetch_with_retry(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            async with asyncio.timeout(10):
                return await fetch_data(url)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)</code></pre>

        <h2>Common Pitfalls</h2>

        <ol>
            <li><strong>Blocking the event loop</strong> — Never call synchronous I/O functions inside async code.</li>
            <li><strong>Forgetting to await</strong> — A coroutine that isn't awaited will never execute.</li>
            <li><strong>Resource leaks</strong> — Always use async context managers for cleanup.</li>
            <li><strong>Mixing sync and async</strong> — Use <code>asyncio.to_thread()</code> for sync code in async contexts.</li>
        </ol>

        <h2>Conclusion</h2>

        <p>Async Python is a powerful tool when used correctly. Start with simple patterns, measure performance, and gradually adopt more complex patterns as needed. The key is understanding <em>when</em> async helps — primarily I/O-bound workloads — and when it adds unnecessary complexity.</p>

        <div class="social-share">
            <strong>Share this article:</strong>
            <a href="https://twitter.com/share?url=...">Twitter</a>
            <a href="https://facebook.com/sharer?url=...">Facebook</a>
            <a href="https://linkedin.com/share?url=...">LinkedIn</a>
            <a href="https://reddit.com/submit?url=...">Reddit</a>
            <a href="mailto:?subject=...&body=...">Email</a>
        </div>
    </article>

    <section class="related-posts">
        <h3>Related Articles</h3>
        <ul>
            <li><a href="/post/async-fastapi">Building Async APIs with FastAPI</a></li>
            <li><a href="/post/python-threading">Python Threading: A Complete Guide</a></li>
            <li><a href="/post/asyncio-patterns">Advanced asyncio Patterns</a></li>
        </ul>
    </section>

    <section class="comments-section">
        <h3>Comments (23)</h3>
        <div class="comment">
            <strong>user123</strong> <span>March 16, 2024</span>
            <p>Great article! The comparison table was really helpful.</p>
        </div>
        <div class="comment">
            <strong>pythonista</strong> <span>March 17, 2024</span>
            <p>You should mention uvloop for even better performance.</p>
        </div>
        <form class="comment-form">
            <textarea placeholder="Leave a comment..."></textarea>
            <button type="submit">Post Comment</button>
        </form>
    </section>

    <div class="newsletter-popup" id="newsletter-popup">
        <h2>Subscribe to our Newsletter!</h2>
        <p>Get weekly Python tips and tutorials.</p>
        <form action="/subscribe"><input type="email" placeholder="your@email.com"><button>Subscribe</button></form>
        <button onclick="closePopup()">No thanks</button>
    </div>

    <div class="cookie-banner" id="cookie-banner">
        <p>We use cookies to improve your experience. By using our site, you agree to our <a href="/privacy">privacy policy</a>.</p>
        <button onclick="acceptCookies()">Accept</button>
        <button onclick="rejectCookies()">Reject</button>
    </div>

    <footer class="site-footer">
        <div class="footer-links">
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
            <a href="/sitemap">Sitemap</a>
            <a href="/rss">RSS Feed</a>
        </div>
        <p>&copy; 2024 TechBlog. All rights reserved.</p>
        <p>Built with love and caffeine.</p>
    </footer>

    <script>
        // Newsletter popup - show after 30 seconds
        setTimeout(function() {
            document.getElementById('newsletter-popup').style.display = 'block';
        }, 30000);
        function closePopup() { document.getElementById('newsletter-popup').style.display = 'none'; }
        function acceptCookies() { localStorage.setItem('cookie_consent', 'true'); document.getElementById('cookie-banner').style.display = 'none'; }
        function rejectCookies() { localStorage.setItem('cookie_consent', 'false'); document.getElementById('cookie-banner').style.display = 'none'; }
    </script>
    <script>
        // Page view tracking
        fetch('/api/analytics', {
            method: 'POST',
            body: JSON.stringify({ page: window.location.pathname, referrer: document.referrer, timestamp: Date.now() })
        });
    </script>
</body>
</html>
```

- [ ] **Step 3: Write the benchmark tests**

Create `e2e/benchmark/test_scraper_benchmark.py`:

```python
"""Token savings benchmark: clean_html modes vs raw HTML baseline."""

import os
from datetime import date

import pytest

from e2e.benchmark.config import CHARS_PER_TOKEN

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "html")

FIXTURE_FILES = [
    "python_docs.html",
    "github_readme.html",
    "blog_post.html",
]

QUESTIONS = [
    "Extract main content (markdown mode)",
    "Get plain text (text mode)",
    "Light clean (minimal mode)",
]

MODES = ["markdown", "text", "minimal"]

# Module-level list to collect results
_results: list[dict] = []


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path) as f:
        return f.read()


def _baseline_raw_html(html: str) -> int:
    """Baseline: agent consumes the full raw HTML."""
    return len(html) // CHARS_PER_TOKEN


@pytest.mark.benchmark
class TestScraperBenchmark:

    def test_q1_markdown_mode(self, benchmark_mcp_scraper):
        """Benchmark: markdown mode across all fixtures."""
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            html = _load_fixture(fixture_file)
            total_baseline += _baseline_raw_html(html)
            response = benchmark_mcp_scraper.call_tool("clean_html", {
                "html": html,
                "mode": "markdown",
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": QUESTIONS[0],
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q2_text_mode(self, benchmark_mcp_scraper):
        """Benchmark: text mode across all fixtures."""
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            html = _load_fixture(fixture_file)
            total_baseline += _baseline_raw_html(html)
            response = benchmark_mcp_scraper.call_tool("clean_html", {
                "html": html,
                "mode": "text",
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": QUESTIONS[1],
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_q3_minimal_mode(self, benchmark_mcp_scraper):
        """Benchmark: minimal mode across all fixtures."""
        total_baseline = 0
        total_tokkit = 0
        for fixture_file in FIXTURE_FILES:
            html = _load_fixture(fixture_file)
            total_baseline += _baseline_raw_html(html)
            response = benchmark_mcp_scraper.call_tool("clean_html", {
                "html": html,
                "mode": "minimal",
            })
            total_tokkit += len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": QUESTIONS[2],
            "tokkit": total_tokkit,
            "baseline": total_baseline,
        })
        assert total_tokkit < total_baseline

    def test_z_generate_report(self):
        """Run last (alphabetically). Writes SCRAPER_BENCHMARK_RESULTS.md."""
        if len(_results) < 3:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in _results)
        total_baseline = sum(r["baseline"] for r in _results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        lines = [
            "# Tokkit Scraper Token Savings Benchmark",
            "",
            f"**Fixtures:** {len(FIXTURE_FILES)} HTML pages (python docs, GitHub README, blog post)",
            f"**Date:** {date.today().isoformat()}",
            "",
            "| # | Mode | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
            "|---|------|----------------:|------------------:|----------:|------:|",
        ]

        for i, r in enumerate(_results, 1):
            savings = (1 - r["tokkit"] / r["baseline"]) * 100 if r["baseline"] > 0 else 0
            ratio = r["baseline"] / r["tokkit"] if r["tokkit"] > 0 else 0
            lines.append(
                f"| {i} | {r['question']} | {r['tokkit']:,} | {r['baseline']:,} | {savings:.1f}% | {ratio:.1f}x |"
            )

        lines.append(
            f"| | **Total** | **{total_tokkit:,}** | **{total_baseline:,}** | **{total_savings:.1f}%** | **{total_ratio:.1f}x** |"
        )
        lines.extend([
            "",
            f"*Token estimate: len(bytes) / {CHARS_PER_TOKEN}. Both paths use the same constant.*",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "SCRAPER_BENCHMARK_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
        assert total_tokkit < total_baseline
```

- [ ] **Step 4: Add benchmark fixture for scraper to benchmark conftest**

Add to `e2e/benchmark/conftest.py` — append a new fixture after the existing `benchmark_mcp` fixture:

```python
@pytest.fixture(scope="session")
def benchmark_mcp_scraper():
    """Start MCP server for scraper benchmarks (no repo indexing needed)."""
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

    # Initialize only — no indexing needed for clean_html
    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()  # consume response

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()
```

- [ ] **Step 5: Run benchmark tests**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/benchmark/test_scraper_benchmark.py -v -m benchmark`

Expected: All 4 tests PASS. `SCRAPER_BENCHMARK_RESULTS.md` generated with savings data. Markdown mode should show >50% savings.

- [ ] **Step 6: Commit**

```bash
git add e2e/benchmark/fixtures/html/ e2e/benchmark/test_scraper_benchmark.py e2e/benchmark/conftest.py
git commit -m "test(scraper): add token savings benchmark with 3 HTML fixtures"
```

---

## Task 8: Update skill documentation

**Files:**
- Modify: `skill/SKILL.md:95-104` (tool selection table)
- Modify: `skill/SKILL.md:76` (after section 6, add section 7)

- [ ] **Step 1: Add workflow section 7 to SKILL.md**

In `skill/SKILL.md`, after the "### 6. Check Savings" section (after line 78), insert:

```markdown
### 7. Clean Web Content

For HTML pages fetched via WebFetch or other sources:

```
clean_html(html="<full page html>") → token-optimized markdown
clean_html(html="...", mode="text") → plain text only
clean_html(html="...", mode="minimal") → light cleaning only
```

Does not require an indexed project. Works standalone as a stateless transformation.
```

- [ ] **Step 2: Add clean_html to the tool selection table**

In `skill/SKILL.md`, in the Tool Selection Guide table (around line 104), add a new row:

```markdown
| Strip HTML noise | `clean_html` | Markdown/text output, strips 60-90% of tokens |
```

- [ ] **Step 3: Verify skill doc renders correctly**

Run: `cd /home/edge/code/research/tokkit && head -120 skill/SKILL.md`

Expected: New section 7 and table row visible, formatting correct.

- [ ] **Step 4: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs(skill): add clean_html to workflow and tool selection guide"
```

---

## Task 9: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run all unit tests**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest core/web/tests/ server/tests/ -v`

Expected: All unit + integration tests PASS.

- [ ] **Step 2: Run all E2E tests**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/test_mcp_scraper.py e2e/test_mcp_index.py e2e/test_mcp_query.py -v`

Expected: All E2E tests PASS (new + existing).

- [ ] **Step 3: Run scraper benchmark**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest e2e/benchmark/test_scraper_benchmark.py -v -m benchmark`

Expected: All PASS, report generated.

- [ ] **Step 4: Verify no regressions in existing tests**

Run: `cd /home/edge/code/research/tokkit && /home/edge/code/.venv/bin/pytest server/tests/ e2e/ -v --ignore=e2e/benchmark/test_benchmark.py`

Expected: All existing tests still PASS.

- [ ] **Step 5: Final commit (if any fixes needed)**

Only if previous steps revealed issues that required fixes.
