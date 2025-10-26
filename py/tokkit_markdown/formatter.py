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
