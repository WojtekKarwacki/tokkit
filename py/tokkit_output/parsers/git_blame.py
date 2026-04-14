"""Git blame output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["lines", "hash", "author"]

# e.g.: "^a1b2c3d (Alice Johnson  2025-03-01 10:00:00 +0000  1) import jwt"
_BLAME_RE = re.compile(
    r"^\^?([0-9a-f]{7,8})\s+\((.+?)\s{2,}\d{4}-\d{2}-\d{2}.*?\s+(\d+)\)"
)


class GitBlameParser(BaseParser):
    id = "git-blame"
    hint_values = ["git-blame"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        matches = sum(1 for line in clean.splitlines() if _BLAME_RE.match(line))
        if matches >= 3:
            return 0.9
        if matches >= 1:
            return 0.6
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Parse each blame line into (lineno, hash, author)
        entries: list[tuple[int, str, str]] = []
        for line in lines:
            m = _BLAME_RE.match(line)
            if m:
                commit_hash = m.group(1)
                author = m.group(2).strip()
                lineno = int(m.group(3))
                entries.append((lineno, commit_hash, author))

        if not entries:
            return ParseResult(
                tool="git-blame",
                summary="0 lines",
                schema=_SCHEMA,
                rows=[],
                verbose=verbose,
            )

        # Collapse consecutive same-author+hash lines into ranges
        rows: list[list[str]] = []
        range_start = entries[0][0]
        range_end = entries[0][0]
        current_hash = entries[0][1]
        current_author = entries[0][2]

        def flush_range(start: int, end: int, h: str, a: str) -> None:
            line_range = str(start) if start == end else f"{start}-{end}"
            rows.append([line_range, h, a])

        for lineno, h, a in entries[1:]:
            if h == current_hash and a == current_author:
                range_end = lineno
            else:
                flush_range(range_start, range_end, current_hash, current_author)
                range_start = lineno
                range_end = lineno
                current_hash = h
                current_author = a

        flush_range(range_start, range_end, current_hash, current_author)

        total_lines = len(entries)
        authors = {r[2] for r in rows}
        n_ranges = len(rows)
        summary = f"{total_lines} lines, {len(authors)} author{'s' if len(authors) != 1 else ''}, {n_ranges} range{'s' if n_ranges != 1 else ''}"

        return ParseResult(
            tool="git-blame",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
