# Markdown Search Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `search_markdown` MCP tool that searches markdown documents by header/content matching, returning only relevant sections with ranking metadata — saving 70-85% of tokens compared to reading the full document.

**Architecture:** New `py/tokkit_markdown/` module with three files: parser (markdown-to-tree), search (matching/scoring), formatter (output). Registered as an MCP tool following the `clean_html`/`compact_json` pattern — stateless, single function entry point.

**Tech Stack:** Pure Python, no dependencies. Regex for header parsing, string matching for search.

**Scope note:** Tier 2 fuzzy matching (typos/stemming like "authen" → "Authentication") is deferred. v1 implements substring matching (Tier 1) and content matching (Tier 3) which cover the most valuable cases. Fuzzy can be added later with minimal changes to `_score_section`.

---

### Task 1: Parser — Markdown to Section Tree

**Files:**
- Create: `py/tokkit_markdown/__init__.py`
- Create: `py/tokkit_markdown/parser.py`
- Create: `tests/markdown/test_parser.py`

- [ ] **Step 1: Write the failing tests for the parser**

Create `tests/markdown/__init__.py` (empty) and `tests/markdown/test_parser.py`:

```python
"""Unit tests for the markdown section tree parser."""

from tokkit_markdown.parser import parse_markdown, Section


def test_single_header():
    md = "# Title\n\nSome content here."
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].level == 1
    assert sections[0].title == "Title"
    assert "Some content here." in sections[0].content


def test_nested_headers():
    md = """# Top
Intro text.

## Child One
Child one content.

## Child Two
Child two content.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Top"
    assert "Intro text." in sections[0].content
    assert len(sections[0].children) == 2
    assert sections[0].children[0].title == "Child One"
    assert sections[0].children[1].title == "Child Two"


def test_deeply_nested():
    md = """# H1
## H2
### H3
#### H4
##### H5
###### H6
Deepest content.
"""
    sections = parse_markdown(md)
    assert sections[0].title == "H1"
    node = sections[0]
    for i in range(2, 7):
        assert len(node.children) == 1
        node = node.children[0]
        assert node.level == i
    assert "Deepest content." in node.content


def test_skipped_levels():
    md = """# Top
## Sub
#### Skipped H3
Content under h4.
"""
    sections = parse_markdown(md)
    h1 = sections[0]
    h2 = h1.children[0]
    # h4 becomes child of h2 even though h3 was skipped
    assert len(h2.children) == 1
    assert h2.children[0].level == 4
    assert h2.children[0].title == "Skipped H3"


def test_multiple_top_level():
    md = """# First
Content one.

# Second
Content two.

# Third
Content three.
"""
    sections = parse_markdown(md)
    assert len(sections) == 3
    assert sections[0].title == "First"
    assert sections[1].title == "Second"
    assert sections[2].title == "Third"


def test_content_before_first_header():
    md = """Preamble text here.

# First Header
Content.
"""
    sections = parse_markdown(md)
    # Preamble becomes a level-0 section
    assert sections[0].level == 0
    assert "Preamble text here." in sections[0].content
    assert sections[1].title == "First Header"


def test_empty_sections():
    md = """# Empty One
# Empty Two
# Has Content
Some text.
"""
    sections = parse_markdown(md)
    assert len(sections) == 3
    assert sections[0].content.strip() == ""
    assert sections[1].content.strip() == ""
    assert "Some text." in sections[2].content


def test_header_with_inline_formatting():
    md = """# **Bold** Header
## `Code` in *Heading*
Content.
"""
    sections = parse_markdown(md)
    assert sections[0].title == "**Bold** Header"
    assert sections[0].children[0].title == "`Code` in *Heading*"


def test_hash_in_code_block_not_parsed_as_header():
    md = """# Real Header
Content before code.

```python
# This is a comment, not a header
## Also not a header
def foo():
    pass
```

More content after code.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Real Header"
    assert "# This is a comment" in sections[0].content
    assert "More content after code." in sections[0].content


def test_hash_in_indented_code_block():
    md = """# Real Header

    # indented code line
    ## also indented

After indented block.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert "# indented code line" in sections[0].content


def test_no_headers():
    md = "Just plain text.\nAnother line."
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].level == 0
    assert "Just plain text." in sections[0].content


def test_empty_document():
    sections = parse_markdown("")
    assert sections == []


def test_whitespace_only():
    sections = parse_markdown("   \n\n   ")
    assert sections == []


def test_char_count_includes_children():
    md = """# Parent
Parent text.

## Child
Child text is longer than parent text for testing.
"""
    sections = parse_markdown(md)
    parent = sections[0]
    child = parent.children[0]
    # Parent char_count should include child's content
    assert parent.char_count > child.char_count
    assert parent.char_count >= len("Parent text.") + child.char_count


def test_large_document_many_sections():
    parts = []
    for i in range(50):
        parts.append(f"## Section {i}\nContent for section {i}.\n")
    md = "# Main\n" + "\n".join(parts)
    sections = parse_markdown(md)
    assert sections[0].title == "Main"
    assert len(sections[0].children) == 50


def test_setext_headers_ignored():
    """ATX headers only — setext-style (underline) not treated as headers."""
    md = """# Real Header

Setext Header
==============

Also Setext
-----------

Content.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Real Header"
    assert "Setext Header" in sections[0].content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/markdown/test_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_markdown'`

- [ ] **Step 3: Create the module and implement the parser**

Create `py/tokkit_markdown/__init__.py`:

```python
"""Tokkit Markdown — Token-optimized markdown section search."""

__version__ = "0.1.0"

from tokkit_markdown.search import search_markdown

__all__ = ["search_markdown"]
```

Create `py/tokkit_markdown/parser.py`:

```python
"""Parse markdown into a section tree by headers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


@dataclass
class Section:
    level: int
    title: str
    content: str = ""
    children: list[Section] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        own = len(self.content)
        return own + sum(c.char_count for c in self.children)


def parse_markdown(markdown: str) -> list[Section]:
    """Parse markdown into a tree of Sections keyed by headers.

    Returns a list of top-level sections. Content before the first
    header becomes a level-0 section. Code blocks (fenced and indented)
    are treated as content, not parsed for headers.
    """
    if not markdown or not markdown.strip():
        return []

    lines = markdown.split("\n")
    # Collect (level, title, content_lines) tuples
    raw_sections: list[tuple[int, str, list[str]]] = []
    current_lines: list[str] = []
    current_level = 0
    current_title = ""
    in_fence = False
    fence_marker = ""

    for line in lines:
        # Track fenced code blocks
        if not in_fence:
            fence_match = _FENCE_RE.match(line.strip())
            if fence_match:
                in_fence = True
                fence_marker = fence_match.group(1)[0]  # ` or ~
                current_lines.append(line)
                continue
        else:
            current_lines.append(line)
            stripped = line.strip()
            if stripped.startswith(fence_marker[0] * 3) and stripped.count(fence_marker[0]) >= 3:
                close_chars = stripped.rstrip()
                if all(c == fence_marker[0] for c in close_chars):
                    in_fence = False
            continue

        # Skip indented code blocks (4+ spaces or tab)
        if line.startswith("    ") or line.startswith("\t"):
            current_lines.append(line)
            continue

        header_match = _HEADER_RE.match(line)
        if header_match:
            # Save previous section
            if current_lines or current_title:
                raw_sections.append((current_level, current_title, current_lines))
            current_level = len(header_match.group(1))
            current_title = header_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save final section
    if current_lines or current_title:
        raw_sections.append((current_level, current_title, current_lines))

    # Handle preamble: if first section has no title and level 0, keep it
    # If first section has content but no header, make it level 0
    if raw_sections and raw_sections[0][1] == "" and raw_sections[0][0] == 0:
        content = "\n".join(raw_sections[0][2]).strip()
        if not content:
            raw_sections.pop(0)

    # Build tree
    sections = _build_tree(raw_sections)
    return sections


def _build_tree(raw_sections: list[tuple[int, str, list[str]]]) -> list[Section]:
    """Build a nested Section tree from flat (level, title, lines) list."""
    root_children: list[Section] = []
    # Stack of (section, level) for nesting
    stack: list[Section] = []

    for level, title, content_lines in raw_sections:
        content = "\n".join(content_lines).strip()
        section = Section(level=level, title=title, content=content)

        if level == 0:
            # Preamble — always top level
            root_children.append(section)
            continue

        # Pop stack until we find a parent (lower level)
        while stack and stack[-1].level >= level:
            stack.pop()

        if stack:
            stack[-1].children.append(section)
        else:
            root_children.append(section)

        stack.append(section)

    return root_children
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/markdown/test_parser.py -v`
Expected: All 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_markdown/__init__.py py/tokkit_markdown/parser.py tests/markdown/__init__.py tests/markdown/test_parser.py
git commit -m "feat(markdown): add section tree parser with tests"
```

---

### Task 2: Search Engine — Matching and Scoring

**Files:**
- Create: `py/tokkit_markdown/search.py`
- Create: `tests/markdown/test_search.py`

- [ ] **Step 1: Write the failing tests for the search engine**

Create `tests/markdown/test_search.py`:

```python
"""Unit tests for markdown section search and ranking."""

from tokkit_markdown.search import search_markdown, _score_section
from tokkit_markdown.parser import parse_markdown, Section


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install to get started.

### Authentication
Set up your API key for authentication.

### Database Setup
Configure your database connection string.

## Configuration
Edit the config file.

# API Reference
Full API documentation.

## Auth Endpoints
POST /login to authenticate users.

## User Endpoints
GET /users returns user list.
"""


def test_exact_header_match():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert results[0]["title"] == "Authentication"
    assert results[0]["match_type"] == "header"


def test_case_insensitive_header():
    results = search_markdown(SAMPLE_MD, "authentication")
    assert len(results) > 0
    assert results[0]["title"] == "Authentication"


def test_partial_header_match():
    results = search_markdown(SAMPLE_MD, "auth")
    assert len(results) > 0
    # Should match Authentication and Auth Endpoints
    titles = [r["title"] for r in results]
    assert "Authentication" in titles
    assert "Auth Endpoints" in titles


def test_deeper_header_ranks_higher():
    results = search_markdown(SAMPLE_MD, "auth")
    titles = [r["title"] for r in results]
    # h3 Authentication should rank above h2 Auth Endpoints
    auth_idx = titles.index("Authentication")
    endpoints_idx = titles.index("Auth Endpoints")
    assert auth_idx < endpoints_idx


def test_content_match_lower_rank():
    results = search_markdown(SAMPLE_MD, "authenticate")
    # "authenticate" appears in Auth Endpoints content ("POST /login to authenticate users")
    # and in Authentication header ("Authentication")
    assert len(results) > 0
    header_matches = [r for r in results if r["match_type"] == "header"]
    content_matches = [r for r in results if r["match_type"] == "content"]
    if header_matches and content_matches:
        assert header_matches[0]["score"] > content_matches[0]["score"]


def test_content_match_found():
    results = search_markdown(SAMPLE_MD, "pip install")
    assert len(results) > 0
    assert results[0]["title"] == "Installation"
    assert results[0]["match_type"] == "content"


def test_no_match_returns_empty():
    results = search_markdown(SAMPLE_MD, "xyznonexistent")
    assert results == []


def test_empty_query_returns_empty():
    results = search_markdown(SAMPLE_MD, "")
    assert results == []


def test_multi_word_query():
    results = search_markdown(SAMPLE_MD, "database setup")
    assert len(results) > 0
    assert results[0]["title"] == "Database Setup"


def test_multi_word_partial_match():
    # "API auth" — should match sections containing either word
    results = search_markdown(SAMPLE_MD, "API auth")
    titles = [r["title"] for r in results]
    assert len(results) > 0


def test_result_has_path():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    path = results[0]["path"]
    assert "Getting Started" in path
    assert "Installation" in path
    assert "Authentication" in path


def test_result_has_content():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert "API key" in results[0]["content"]


def test_result_has_score():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert isinstance(results[0]["score"], float)
    assert results[0]["score"] > 0


def test_result_has_token_estimate():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert "tokens" in results[0]
    assert results[0]["tokens"] > 0


def test_section_with_children_includes_subtree():
    results = search_markdown(SAMPLE_MD, "Installation")
    assert len(results) > 0
    content = results[0]["content"]
    # Installation's children (Authentication, Database Setup) should be in content
    assert "Authentication" in content
    assert "Database Setup" in content


def test_results_sorted_by_score():
    results = search_markdown(SAMPLE_MD, "auth")
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_empty_markdown():
    results = search_markdown("", "test")
    assert results == []


def test_no_headers_markdown():
    results = search_markdown("Just plain text with auth keyword.", "auth")
    assert len(results) > 0
    assert results[0]["match_type"] == "content"


def test_depth_bonus_scoring():
    """Verify h3 header match scores higher than h1 header match."""
    md = """# Auth Overview
Overview of auth.

## Details
Some details.

### Auth Config
Specific auth config.
"""
    results = search_markdown(md, "auth")
    titles = [r["title"] for r in results]
    # h3 "Auth Config" should rank above h1 "Auth Overview" due to depth bonus
    config_idx = titles.index("Auth Config")
    overview_idx = titles.index("Auth Overview")
    assert config_idx < overview_idx
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/markdown/test_search.py -v`
Expected: FAIL — `ImportError: cannot import name 'search_markdown' from 'tokkit_markdown.search'`

- [ ] **Step 3: Implement the search engine**

Create `py/tokkit_markdown/search.py`:

```python
"""Search markdown sections by keyword matching with ranked results."""

from __future__ import annotations

from tokkit_markdown.parser import parse_markdown, Section

CHARS_PER_TOKEN = 4


def search_markdown(markdown: str, query: str) -> list[dict]:
    """Search markdown content by query, returning ranked matching sections.

    Returns a list of match dicts sorted by score (highest first):
        {"title", "path", "score", "match_type", "content", "tokens"}

    Empty query returns empty list.
    No matches returns empty list.
    """
    if not markdown or not markdown.strip() or not query or not query.strip():
        return []

    sections = parse_markdown(markdown)
    if not sections:
        return []

    query_words = query.lower().split()
    results: list[dict] = []

    _score_tree(sections, query_words, [], results)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _score_tree(
    sections: list[Section],
    query_words: list[str],
    parent_path: list[str],
    results: list[dict],
) -> None:
    """Recursively score all sections in the tree."""
    for section in sections:
        if section.level == 0:
            path_entry = "(preamble)"
        else:
            prefix = "#" * section.level
            path_entry = f"{prefix} {section.title}"

        current_path = parent_path + [path_entry]

        score, match_type = _score_section(section, query_words)
        if score > 0:
            full_content = _render_section_content(section)
            results.append({
                "title": section.title or "(preamble)",
                "path": " > ".join(current_path),
                "score": round(score, 3),
                "match_type": match_type,
                "content": full_content,
                "tokens": max(1, len(full_content) // CHARS_PER_TOKEN),
            })

        _score_tree(section.children, query_words, current_path, results)


def _score_section(section: Section, query_words: list[str]) -> tuple[float, str]:
    """Score a section against query words.

    Returns (score, match_type). Score 0 means no match.
    """
    if not query_words:
        return 0.0, ""

    title_lower = section.title.lower() if section.title else ""
    content_lower = section.content.lower()

    word_scores: list[float] = []
    best_match_type = "content"

    for word in query_words:
        best_word_score = 0.0

        # Tier 1: Header substring match (base 1.0)
        if word in title_lower:
            best_word_score = 1.0
            best_match_type = "header"

        # Tier 3: Content substring match (base 0.3)
        if best_word_score == 0.0 and word in content_lower:
            best_word_score = 0.3

        word_scores.append(best_word_score)

    # Average across words — sections matching all words rank higher
    avg_score = sum(word_scores) / len(word_scores)

    if avg_score == 0.0:
        return 0.0, ""

    # Depth bonus: deeper = more precise
    depth_bonus = 0.05 * section.level
    final_score = avg_score + depth_bonus

    # Determine overall match type (header if any word matched header)
    has_header_match = any(
        (query_word in title_lower) for query_word in query_words
    )
    match_type = "header" if has_header_match else "content"

    return final_score, match_type


def _render_section_content(section: Section) -> str:
    """Render a section's full content including children."""
    parts = []
    if section.content:
        parts.append(section.content)
    for child in section.children:
        prefix = "#" * child.level
        parts.append(f"{prefix} {child.title}")
        child_content = _render_section_content(child)
        if child_content:
            parts.append(child_content)
    return "\n\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/markdown/test_search.py -v`
Expected: All 19 tests PASS

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_markdown/search.py tests/markdown/test_search.py
git commit -m "feat(markdown): add search engine with scoring and ranking"
```

---

### Task 3: Formatter — Output for MCP Tool

**Files:**
- Create: `py/tokkit_markdown/formatter.py`
- Create: `tests/markdown/test_formatter.py`

- [ ] **Step 1: Write the failing tests for the formatter**

Create `tests/markdown/test_formatter.py`:

```python
"""Unit tests for markdown search output formatting."""

from tokkit_markdown.formatter import format_results, format_header_tree
from tokkit_markdown.parser import parse_markdown


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install.

### Authentication
Set up your API key.

## Configuration
Edit the config.

# API Reference
Full API docs.
"""


def test_format_results_header_line():
    results = [
        {
            "title": "Authentication",
            "path": "# Getting Started > ## Installation > ### Authentication",
            "score": 1.15,
            "match_type": "header",
            "content": "Set up your API key.",
            "tokens": 5,
        }
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "Matches: 1" in output
    assert "Document: ~500 tokens" in output
    assert "Returned: ~5 tokens" in output
    assert "Savings:" in output


def test_format_results_section_block():
    results = [
        {
            "title": "Authentication",
            "path": "# Getting Started > ## Installation > ### Authentication",
            "score": 1.15,
            "match_type": "header",
            "content": "Set up your API key.",
            "tokens": 5,
        }
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "### Authentication" in output
    assert "score: 1.15" in output
    assert "match: header" in output
    assert "~5 tokens" in output
    assert "Path:" in output
    assert "Set up your API key." in output


def test_format_results_multiple():
    results = [
        {
            "title": "First",
            "path": "# First",
            "score": 1.1,
            "match_type": "header",
            "content": "Content one.",
            "tokens": 3,
        },
        {
            "title": "Second",
            "path": "# Second",
            "score": 0.3,
            "match_type": "content",
            "content": "Content two.",
            "tokens": 3,
        },
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "Matches: 2" in output
    first_pos = output.index("First")
    second_pos = output.index("Second")
    assert first_pos < second_pos


def test_format_results_savings_percentage():
    results = [
        {
            "title": "Small",
            "path": "# Small",
            "score": 1.0,
            "match_type": "header",
            "content": "Tiny.",
            "tokens": 50,
        }
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "90%" in output


def test_format_header_tree():
    sections = parse_markdown(SAMPLE_MD)
    output = format_header_tree(sections, query="foobar")
    assert 'No matches for "foobar"' in output
    assert "# Getting Started" in output
    assert "  ## Installation" in output
    assert "    ### Authentication" in output
    assert "  ## Configuration" in output
    assert "# API Reference" in output
    assert "tokens" in output


def test_format_header_tree_indentation():
    sections = parse_markdown(SAMPLE_MD)
    output = format_header_tree(sections, query="xyz")
    lines = output.strip().split("\n")
    # Find the Authentication line — should be indented more than Installation
    install_line = next(l for l in lines if "Installation" in l)
    auth_line = next(l for l in lines if "Authentication" in l)
    assert len(auth_line) - len(auth_line.lstrip()) > len(install_line) - len(install_line.lstrip())


def test_format_header_tree_empty_query():
    sections = parse_markdown(SAMPLE_MD)
    output = format_header_tree(sections, query="")
    assert "Document headers:" in output


def test_format_results_empty():
    output = format_results([], total_doc_tokens=500)
    assert output == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/markdown/test_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_markdown.formatter'`

- [ ] **Step 3: Implement the formatter**

Create `py/tokkit_markdown/formatter.py`:

```python
"""Format search results and header trees for MCP output."""

from __future__ import annotations

from tokkit_markdown.parser import Section

CHARS_PER_TOKEN = 4


def format_results(results: list[dict], total_doc_tokens: int) -> str:
    """Format search results as readable text with metadata.

    Args:
        results: List of match dicts from search_markdown.
        total_doc_tokens: Token estimate of the full document.

    Returns:
        Formatted string with header line and section blocks.
    """
    if not results:
        return ""

    returned_tokens = sum(r["tokens"] for r in results)
    savings = round((1 - returned_tokens / total_doc_tokens) * 100) if total_doc_tokens > 0 else 0
    savings = max(0, savings)

    lines = [
        f"Matches: {len(results)} | Document: ~{total_doc_tokens} tokens | Returned: ~{returned_tokens} tokens | Savings: {savings}%",
        "",
    ]

    for r in results:
        prefix = "#" * _level_from_path(r["path"])
        if not prefix:
            prefix = "#"
        lines.append(f"{prefix} {r['title']} (score: {r['score']}, match: {r['match_type']}, ~{r['tokens']} tokens)")
        lines.append(f"Path: {r['path']}")
        lines.append("---")
        lines.append(r["content"])
        lines.append("")

    return "\n".join(lines).rstrip()


def format_header_tree(sections: list[Section], query: str = "") -> str:
    """Format a header tree listing with token estimates.

    Used when no matches are found or query is empty.
    """
    if query:
        lines = [f'No matches for "{query}". Document headers:']
    else:
        lines = ["Document headers:"]

    _tree_lines(sections, lines, indent=0)
    return "\n".join(lines)


def _tree_lines(sections: list[Section], lines: list[str], indent: int) -> None:
    """Recursively build indented header tree lines."""
    for section in sections:
        if section.level == 0:
            prefix = "(preamble)"
        else:
            prefix = "#" * section.level + " " + section.title
        tokens = max(1, section.char_count // CHARS_PER_TOKEN)
        pad = "  " * indent
        lines.append(f"{pad}{prefix} (~{tokens} tokens)")
        _tree_lines(section.children, lines, indent + 1)


def _level_from_path(path: str) -> int:
    """Extract header level from the last element of a breadcrumb path."""
    parts = path.split(" > ")
    last = parts[-1].strip() if parts else ""
    count = 0
    for ch in last:
        if ch == "#":
            count += 1
        else:
            break
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/markdown/test_formatter.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_markdown/formatter.py tests/markdown/test_formatter.py
git commit -m "feat(markdown): add output formatter for search results and header tree"
```

---

### Task 4: Wire Up Public API

**Files:**
- Modify: `py/tokkit_markdown/__init__.py`
- Create: `tests/markdown/test_search_markdown.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/markdown/test_search_markdown.py`:

```python
"""Integration tests for the search_markdown public API."""

from tokkit_markdown import search_markdown


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install to get started.

### Authentication
Set up your API key for auth.

## Configuration
Edit the config file.

# API Reference
Full API documentation.

## Auth Endpoints
POST /login to authenticate users.
"""


def test_search_with_matches_returns_formatted_string():
    output = search_markdown(SAMPLE_MD, "auth")
    assert "Matches:" in output
    assert "Savings:" in output
    assert "Authentication" in output


def test_search_no_matches_returns_header_tree():
    output = search_markdown(SAMPLE_MD, "xyznonexistent")
    assert "No matches" in output
    assert "# Getting Started" in output
    assert "## Installation" in output


def test_search_empty_query_returns_header_tree():
    output = search_markdown(SAMPLE_MD, "")
    assert "Document headers:" in output
    assert "# Getting Started" in output


def test_search_empty_markdown():
    output = search_markdown("", "test")
    assert output == ""


def test_search_returns_token_savings():
    output = search_markdown(SAMPLE_MD, "Authentication")
    assert "tokens" in output
    assert "Savings:" in output


def test_search_result_ordering():
    output = search_markdown(SAMPLE_MD, "auth")
    # Authentication (h3, header match) should appear before Auth Endpoints (h2, header match)
    auth_pos = output.index("Authentication")
    endpoints_pos = output.index("Auth Endpoints")
    assert auth_pos < endpoints_pos
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/markdown/test_search_markdown.py -v`
Expected: FAIL — `search_markdown` currently imported from `search.py` returns list of dicts, not formatted string

- [ ] **Step 3: Update __init__.py with the public API**

Replace `py/tokkit_markdown/__init__.py`:

```python
"""Tokkit Markdown — Token-optimized markdown section search."""

__version__ = "0.1.0"

from tokkit_markdown.parser import parse_markdown
from tokkit_markdown.search import search_markdown as _search
from tokkit_markdown.formatter import format_results, format_header_tree

CHARS_PER_TOKEN = 4


def search_markdown(markdown: str, query: str) -> str:
    """Search markdown for sections matching query.

    Returns formatted text with matching sections ranked by relevance,
    or a header tree listing if no matches are found / query is empty.
    Returns empty string for empty markdown input.
    """
    if not markdown or not markdown.strip():
        return ""

    sections = parse_markdown(markdown)
    if not sections:
        return ""

    total_doc_tokens = max(1, len(markdown) // CHARS_PER_TOKEN)

    if not query or not query.strip():
        return format_header_tree(sections, query="")

    results = _search(markdown, query)

    if not results:
        return format_header_tree(sections, query=query)

    return format_results(results, total_doc_tokens=total_doc_tokens)


__all__ = ["search_markdown"]
```

- [ ] **Step 4: Run all markdown tests**

Run: `pytest tests/markdown/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_markdown/__init__.py tests/markdown/test_search_markdown.py
git commit -m "feat(markdown): wire up public search_markdown API with formatted output"
```

---

### Task 5: MCP Tool Registration

**Files:**
- Modify: `py/tokkit_server/protocol.py:223` (add to `TOOL_DEFINITIONS`)
- Modify: `py/tokkit_server/tools.py:183` (add handler before `get_token_stats`)
- Modify: `py/tokkit_server/token_stats.py:57` (add savings estimate)

- [ ] **Step 1: Add tool definition to protocol.py**

Add after the `compact_json` entry (after line 222) in `py/tokkit_server/protocol.py`:

```python
    {
        "name": "search_markdown",
        "description": (
            "Search markdown content for relevant sections by keyword. "
            "Returns only matching sections ranked by precision — deeper header matches rank higher. "
            "Typically saves 70-85% of tokens vs reading the full document. "
            "If no matches found, returns a header tree listing (~50-100 tokens) for query refinement. "
            "Empty query returns the header tree. Does NOT require index_repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {
                    "type": "string",
                    "description": "Raw markdown content to search.",
                },
                "query": {
                    "type": "string",
                    "description": "Search keywords. Empty string returns header tree only.",
                },
            },
            "required": ["markdown", "query"],
        },
    },
```

- [ ] **Step 2: Add handler to tools.py**

Add after the `compact_json` handler (after line 182) in `py/tokkit_server/tools.py`:

```python
        if tool_name == "search_markdown":
            markdown = args.get("markdown", "")
            query = args.get("query", "")
            if not markdown:
                return _err("markdown is required")
            from tokkit_markdown import search_markdown
            result = search_markdown(markdown, query)
            meta = make_meta(tool_name, result, _session_project_path, raw_size=len(markdown))
            return _ok(result, meta)
```

- [ ] **Step 3: Add token savings estimate to token_stats.py**

Add after the `compact_json` block (after line 71) in `py/tokkit_server/token_stats.py`:

```python
    if tool_name == "search_markdown":
        if raw_size:
            return raw_size // CHARS_PER_TOKEN
        return len(result_text) * 2 // CHARS_PER_TOKEN
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_server/protocol.py py/tokkit_server/tools.py py/tokkit_server/token_stats.py
git commit -m "feat(markdown): register search_markdown as MCP tool"
```

---

### Task 6: E2E Tests

**Files:**
- Create: `tests/e2e/test_mcp_markdown.py`

- [ ] **Step 1: Write E2E tests**

Create `tests/e2e/test_mcp_markdown.py`:

```python
"""E2E tests for search_markdown MCP tool — full JSON-RPC flow."""

import json


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install to get started.

### Authentication
Set up your API key for authentication.

### Database Setup
Configure your database connection string.

## Configuration
Edit the config file to set your preferences.

# API Reference
Full API documentation below.

## Auth Endpoints
POST /login to authenticate users.

## User Endpoints
GET /users returns the user list.
"""


def test_search_markdown_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "search_markdown" in tool_names


def test_search_markdown_with_matches(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"markdown": SAMPLE_MD, "query": "auth"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "Matches:" in content
    assert "Authentication" in content
    assert "Savings:" in content


def test_search_markdown_no_matches(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"markdown": SAMPLE_MD, "query": "xyznonexistent"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "No matches" in content
    assert "# Getting Started" in content


def test_search_markdown_empty_query(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"markdown": SAMPLE_MD, "query": ""},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "Document headers:" in content


def test_search_markdown_saves_tokens(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(SAMPLE_MD) // 4
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"markdown": SAMPLE_MD, "query": "Authentication"},
    })
    content = resp["result"]["content"][0]["text"]
    # The result should be smaller than the full document
    result_tokens = len(content) // 4
    assert result_tokens < raw_tokens


def test_search_markdown_has_meta(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"markdown": SAMPLE_MD, "query": "auth"},
    })
    assert "_meta" in resp["result"]
    meta = resp["result"]["_meta"]["token_savings"]
    assert meta["tokens_saved"] > 0


def test_search_markdown_missing_markdown(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "search_markdown",
        "arguments": {"markdown": "", "query": "test"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "markdown is required" in content.lower() or content == ""
```

- [ ] **Step 2: Run E2E tests**

Run: `pytest tests/e2e/test_mcp_markdown.py -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: All tests PASS, no regressions

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_mcp_markdown.py
git commit -m "test(markdown): add E2E tests for search_markdown MCP tool"
```

---

### Task 7: Skill Documentation

**Files:**
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Add search_markdown section to SKILL.md**

Add after the "Compact JSON Data" section (section 8) in `skill/SKILL.md`:

```markdown
### 9. Search Markdown Content

For finding specific sections in markdown documents instead of reading the full content:

```
search_markdown(markdown="<full markdown>", query="authentication setup")
  → ranked matching sections with breadcrumbs and token savings

search_markdown(markdown="...", query="")
  → header tree listing with token estimates (for structural overview)
```

Single call covers most cases. Matching sections are ranked by precision:
- **Header match** ranks above content match
- **Deeper headers** (h3 > h2 > h1) rank higher — more specific sections first
- **Multi-word queries** score sections matching all words higher

If no keyword matches are found, the tool returns the document's header tree (~50-100 tokens) so you can refine your query.

**When to use:** Any time you need to find specific information in a markdown document (README, docs, CLAUDE.md, output from `clean_html`). Saves 70-85% tokens vs reading the full document.
```

- [ ] **Step 2: Update the Tool Selection Guide table**

Add a row to the existing table in `skill/SKILL.md`:

```markdown
| Search markdown docs | `search_markdown` | Returns matching sections, not full doc |
```

- [ ] **Step 3: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs: add search_markdown to skill documentation"
```
