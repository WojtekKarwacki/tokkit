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
