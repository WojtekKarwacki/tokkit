"""Git log output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["hash", "message"]

_COMMIT_FULL_RE = re.compile(r"^commit ([0-9a-f]{40})$")
_ONELINE_RE = re.compile(r"^([0-9a-f]{7,40})\s+(.+)$")
_META_RE = re.compile(r"^(Author:|Date:|Merge:)\s+")

_DEFAULT_LIMIT = 10


class GitLogParser(BaseParser):
    id = "git-log"
    hint_values = ["git-log"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()
        score = 0.0

        if any(_COMMIT_FULL_RE.match(line) for line in lines):
            score += 0.6
        if any(_META_RE.match(line) for line in lines):
            score += 0.3

        oneline_count = sum(1 for line in lines if _ONELINE_RE.match(line))
        if oneline_count >= 2 and score == 0.0:
            score += 0.5

        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False, limit: int = _DEFAULT_LIMIT) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        has_verbose = any(_COMMIT_FULL_RE.match(line) for line in lines)

        if has_verbose:
            all_rows = _parse_verbose(lines)
        else:
            all_rows = _parse_oneline(lines)

        total = len(all_rows)
        rows = all_rows[:limit]

        if total == 0:
            summary = "0 entries"
        elif total <= limit:
            summary = f"{total} {'entry' if total == 1 else 'entries'}"
        else:
            summary = f"{len(rows)} entries (showing {len(rows)} of {total})"

        return ParseResult(
            tool="git-log",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )


def _parse_oneline(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        m = _ONELINE_RE.match(line.strip())
        if m:
            rows.append([m.group(1)[:8], m.group(2).strip()])
    return rows


def _parse_verbose(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    current_hash: str | None = None
    message_lines: list[str] = []
    in_body = False

    def flush():
        nonlocal current_hash, message_lines, in_body
        if current_hash is not None:
            msg = next((l for l in message_lines if l.strip()), "")
            rows.append([current_hash, msg.strip()])
        current_hash = None
        message_lines = []
        in_body = False

    for line in lines:
        m = _COMMIT_FULL_RE.match(line)
        if m:
            flush()
            current_hash = m.group(1)[:8]
            in_body = False
            continue

        if current_hash is None:
            continue

        if _META_RE.match(line):
            continue

        # Blank line separates header from body
        if not in_body and line.strip() == "":
            in_body = True
            continue

        if in_body:
            message_lines.append(line.strip())

    flush()
    return rows
