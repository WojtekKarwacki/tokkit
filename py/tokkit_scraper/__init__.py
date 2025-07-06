"""Tokkit Scraper — Token-optimized web scraping engine."""

__version__ = "0.1.0"

import re as _re

from selectolax.parser import HTMLParser

from tokkit_scraper.pipeline import strip_noise

_VALID_MODES = {"markdown", "text", "minimal"}

_MINIMAL_REMOVE_TAGS = {"script", "style", "noscript", "svg", "iframe", "head"}

# Lines that are pure noise in markdown output — no information for an LLM
_SKIP_LINE_PATTERNS = [
    _re.compile(r"^\[Skip to content\]"),                   # accessibility nav
    _re.compile(r"^\[]\("),                                  # empty-text links (badges, sponsors, icons)
    _re.compile(r"^!\[]\("),                                 # empty-alt images
]

# Inline markers to strip (lossless — they carry no semantic content)
_STRIP_INLINE = [
    "\u00b6",  # ¶ pilcrow (mkdocs anchor markers)
]


def clean_html(html: str, mode: str = "markdown") -> str:
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")

    if not html or not html.strip():
        return ""

    if mode == "minimal":
        return _clean_minimal(html)

    cleaned_html = strip_noise(html)

    if mode == "text":
        return _extract_text(cleaned_html)

    from tokkit_scraper.markdown import html_to_markdown
    md = html_to_markdown(cleaned_html)
    return _polish_markdown(md)


def _polish_markdown(md: str) -> str:
    """Remove residual noise from markdown output. All removals are lossless."""
    lines = md.splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        # Drop lines matching skip patterns
        if any(p.match(stripped) for p in _SKIP_LINE_PATTERNS):
            continue
        # Strip inline markers
        for marker in _STRIP_INLINE:
            line = line.replace(marker, "")
        out.append(line)
    return "\n".join(out).strip()


def _clean_minimal(html: str) -> str:
    tree = HTMLParser(html)
    for tag in _MINIMAL_REMOVE_TAGS:
        for node in tree.css(tag):
            node.decompose()
    body = tree.css_first("body")
    result = body.html if body else tree.html
    return (result or "").strip()


def _extract_text(html: str) -> str:
    import re
    tree = HTMLParser(html)
    body = tree.css_first("body")
    root = body if body else tree.root
    if root is None:
        return ""
    text = root.text(separator="\n", deep=True) or ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()
