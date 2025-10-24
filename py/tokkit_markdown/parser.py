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
            if current_lines or current_title:
                raw_sections.append((current_level, current_title, current_lines))
            current_level = len(header_match.group(1))
            current_title = header_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines or current_title:
        raw_sections.append((current_level, current_title, current_lines))

    if raw_sections and raw_sections[0][1] == "" and raw_sections[0][0] == 0:
        content = "\n".join(raw_sections[0][2]).strip()
        if not content:
            raw_sections.pop(0)

    sections = _build_tree(raw_sections)
    return sections


def _build_tree(raw_sections: list[tuple[int, str, list[str]]]) -> list[Section]:
    """Build a nested Section tree from flat (level, title, lines) list."""
    root_children: list[Section] = []
    stack: list[Section] = []

    for level, title, content_lines in raw_sections:
        content = "\n".join(content_lines).strip()
        section = Section(level=level, title=title, content=content)

        if level == 0:
            root_children.append(section)
            continue

        while stack and stack[-1].level >= level:
            stack.pop()

        if stack:
            stack[-1].children.append(section)
        else:
            root_children.append(section)

        stack.append(section)

    return root_children
