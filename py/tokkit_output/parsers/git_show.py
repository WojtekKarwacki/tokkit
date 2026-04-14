"""Git show output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi
from tokkit_output.parsers.git_diff import _parse_unified_diff

_SCHEMA = ["file", "lines_changed", "content"]

_COMMIT_FULL_RE = re.compile(r"^commit ([0-9a-f]{40})$")
_DIFF_START_RE = re.compile(r"^diff --git a/")
_META_RE = re.compile(r"^(Author:|Date:|Merge:)\s+")


class GitShowParser(BaseParser):
    id = "git-show"
    hint_values = ["git-show"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        has_commit = any(_COMMIT_FULL_RE.match(line) for line in lines)
        has_diff = any(_DIFF_START_RE.match(line) for line in lines)

        if has_commit and has_diff:
            return 0.9
        if has_commit or has_diff:
            return 0.4
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Extract commit hash and message
        commit_hash = ""
        message = ""
        in_body = False
        diff_start = len(lines)

        for i, line in enumerate(lines):
            m = _COMMIT_FULL_RE.match(line)
            if m:
                commit_hash = m.group(1)[:8]
                continue

            if _DIFF_START_RE.match(line):
                diff_start = i
                break

            if _META_RE.match(line):
                continue

            if not in_body and line.strip() == "":
                in_body = True
                continue

            if in_body and not message and line.strip():
                message = line.strip()

        # Parse the diff portion
        diff_lines = lines[diff_start:]
        rows_data = _parse_unified_diff(diff_lines)
        rows = [[f, str(c), ct] for f, c, ct in rows_data]

        n_files = len(rows_data)
        total_changes = sum(c for _, c, _ in rows_data)

        if commit_hash and message:
            summary = f"{commit_hash}: {message}"
        elif commit_hash:
            summary = commit_hash
        elif n_files:
            summary = f"{n_files} file{'s' if n_files != 1 else ''}, {total_changes} changes"
        else:
            summary = "no changes"

        if n_files:
            summary += f" — {n_files} file{'s' if n_files != 1 else ''}, {total_changes} changes"

        return ParseResult(
            tool="git-show",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
