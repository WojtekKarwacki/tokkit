"""Git stash output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["index", "branch", "message"]

# e.g.: "stash@{0}: WIP on feat/auth-improvements: a1b2c3d feat: ..."
#   or: "stash@{1}: On main: fix cors before switching branches"
_STASH_RE = re.compile(r"^stash@\{(\d+)\}:\s+((?:WIP on|On)\s+(\S+?)):\s+(.+)$")

_DEFAULT_LIMIT = 10
_HEAD_ENTRIES = 5
_TAIL_ENTRIES = 2


class GitStashParser(BaseParser):
    id = "git-stash"
    hint_values = ["git-stash"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        matches = sum(1 for line in clean.splitlines() if _STASH_RE.match(line))
        if matches >= 2:
            return 0.9
        if matches == 1:
            return 0.6
        return 0.0

    def parse(self, text: str, verbose: bool = False, limit: int = _DEFAULT_LIMIT) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        all_entries: list[list[str]] = []
        for line in lines:
            m = _STASH_RE.match(line.strip())
            if m:
                idx = m.group(1)
                branch = m.group(3)
                message = m.group(4).strip()
                all_entries.append([idx, branch, message])

        total = len(all_entries)

        if total <= limit:
            rows = all_entries
        else:
            head = all_entries[:_HEAD_ENTRIES]
            tail = all_entries[-_TAIL_ENTRIES:]
            gap = total - _HEAD_ENTRIES - _TAIL_ENTRIES
            rows = head + [[f"... ({gap} more)", "", ""]] + tail

        if total == 0:
            summary = "No stashes"
        else:
            summary = f"{total} stash{'es' if total != 1 else ''}"

        return ParseResult(
            tool="git-stash",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
