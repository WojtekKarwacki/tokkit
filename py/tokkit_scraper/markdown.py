"""HTML-to-markdown converter using selectolax."""

from selectolax.parser import HTMLParser, Node


def html_to_markdown(html: str) -> str:
    """Convert cleaned HTML to markdown text."""
    if not html or not html.strip():
        return ""

    parser = HTMLParser(html)
    parts: list[str] = []
    _convert_node(parser.root, parts, list_context=None, list_counters=None)
    return "\n".join(parts).strip()


def _get_text(node: Node) -> str:
    return (node.text(deep=True) or "").strip()


def _convert_node(
    node: Node,
    parts: list[str],
    list_context: str | None,
    list_counters: list[int] | None,
) -> None:
    tag = node.tag if node.tag else ""

    if tag == "-text":
        text = (node.text_content or "").strip()
        if text:
            parts.append(text)

    elif tag in ("-document", "html", "body", "div", "span", "p", "section", "article", "main"):
        _process_children(node, parts, list_context, list_counters)

    elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        text = _get_text(node)
        if text:
            parts.append(f"{'#' * level} {text}")

    elif tag == "a":
        href = node.attributes.get("href", "") or ""
        text = _get_text(node)
        if text:
            parts.append(f"[{text}]({href})")

    elif tag == "img":
        alt = node.attributes.get("alt", "") or ""
        src = node.attributes.get("src", "") or ""
        parts.append(f"![{alt}]({src})")

    elif tag in ("strong", "b"):
        text = _get_text(node)
        if text:
            parts.append(f"**{text}**")

    elif tag in ("em", "i"):
        text = _get_text(node)
        if text:
            parts.append(f"*{text}*")

    elif tag == "blockquote":
        inner_parts: list[str] = []
        _process_children(node, inner_parts, list_context, list_counters)
        combined = " ".join(inner_parts).strip()
        if combined:
            parts.append(f"> {combined}")

    elif tag in ("pre", "code"):
        text = _get_text(node)
        if text:
            parts.append(f"```\n{text}\n```")

    elif tag == "ul":
        _process_list(node, parts, ordered=False)

    elif tag == "ol":
        _process_list(node, parts, ordered=True)

    elif tag == "li":
        # Handled inside _process_list; direct li outside list → plain text
        text = _get_text(node)
        if text:
            parts.append(f"- {text}")

    elif tag == "table":
        _convert_table(node, parts)

    elif tag in ("script", "style", "head"):
        return

    else:
        _process_children(node, parts, list_context, list_counters)


def _process_children(
    node: Node,
    parts: list[str],
    list_context: str | None,
    list_counters: list[int] | None,
) -> None:
    child = node.child
    while child:
        _convert_node(child, parts, list_context, list_counters)
        child = child.next


def _process_list(node: Node, parts: list[str], ordered: bool) -> None:
    counter = 0
    child = node.child
    while child:
        if child.tag == "li":
            text = _get_text(child)
            if text:
                if ordered:
                    counter += 1
                    parts.append(f"{counter}. {text}")
                else:
                    parts.append(f"- {text}")
        child = child.next


def _convert_table(node: Node, parts: list[str]) -> None:
    rows: list[list[str]] = []
    header_row_index: int | None = None

    for tr in node.css("tr"):
        cells: list[str] = []
        for cell in tr.css("th, td"):
            cells.append((cell.text(deep=True) or "").strip())
        if cells:
            if tr.css("th") and header_row_index is None:
                header_row_index = len(rows)
            rows.append(cells)

    if not rows:
        return

    if header_row_index is None:
        header_row_index = 0

    for i, row in enumerate(rows):
        parts.append("| " + " | ".join(row) + " |")
        if i == header_row_index:
            parts.append("| " + " | ".join("---" for _ in row) + " |")
