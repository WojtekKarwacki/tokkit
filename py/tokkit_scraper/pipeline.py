"""HTML stripping pipeline for token-optimized web scraping."""

import re

from selectolax.parser import HTMLParser

REMOVE_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "head",
    "nav",
    "header",
    "footer",
    "aside",
}

_NOISE_PATTERNS = re.compile(
    r"cookie|consent|gdpr|sidebar|nav|menu|ad-|ads|social|share|popup|modal|banner|promo",
    re.IGNORECASE,
)

_KEEP_ATTRS = {
    "a": {"href"},
    "img": {"alt", "src"},
}

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _is_noise_element(node) -> bool:
    cls = node.attributes.get("class") or ""
    eid = node.attributes.get("id") or ""
    return bool(_NOISE_PATTERNS.search(cls) or _NOISE_PATTERNS.search(eid))


def _strip_attributes(node) -> None:
    tag = node.tag
    keep = _KEEP_ATTRS.get(tag, set())
    attrs = list(node.attributes.keys())
    for attr in attrs:
        if attr not in keep:
            del node.attrs[attr]


def strip_noise(html: str) -> str:
    if not html:
        return ""

    tree = HTMLParser(html)

    for tag in REMOVE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    for node in tree.css("*"):
        if node.tag not in ("#text", "#comment", "html", "body", "-undef") and _is_noise_element(node):
            node.decompose()

    for comment in tree.css("*"):
        pass

    tree.strip_tags(["!--"])

    for node in tree.css("*"):
        if node.tag in ("#text", "#comment", "html", "body", "-undef"):
            continue
        _strip_attributes(node)

    result = tree.html or ""

    result = _MULTI_SPACE.sub(" ", result)
    result = _MULTI_NEWLINE.sub("\n\n", result)
    result = result.strip()

    return result
