"""Git status output parser."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "status", "staged"]

_LONG_MOD_RE = re.compile(
    r"^\t(modified|new file|deleted|renamed|copied|unmerged):\s+(.+)$"
)
_SHORT_LINE_RE = re.compile(r"^([MADRCU?! ]{2})\s+(.+)$")

_STATUS_LABELS = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "U": "unmerged",
    "?": "untracked",
    " ": "unstaged",
    "!": "ignored",
}

_DIR_THRESHOLD = 8


def _short_status_label(ch: str) -> str:
    return _STATUS_LABELS.get(ch, ch)


class GitStatusParser(BaseParser):
    id = "git-status"
    hint_values = ["git-status"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        lines = clean.splitlines()

        if any("On branch" in line for line in lines):
            score += 0.5
        if any("nothing to commit" in line for line in lines):
            score += 0.3

        long_mod = sum(1 for line in lines if _LONG_MOD_RE.match(line))
        if long_mod >= 1:
            score += 0.4

        short_mod = sum(1 for line in lines if _SHORT_LINE_RE.match(line))
        if short_mod >= 2:
            score += 0.5

        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Detect format
        has_long = any(_LONG_MOD_RE.match(line) for line in lines)
        has_short = any(_SHORT_LINE_RE.match(line) for line in lines)

        # Clean repo check
        if not has_long and not has_short:
            if any("nothing to commit" in line for line in lines):
                return ParseResult(
                    tool="git-status",
                    summary="Working tree clean",
                    schema=_SCHEMA,
                    rows=[],
                    verbose=verbose,
                )

        rows: list[list[str]] = []

        if has_short:
            rows = _parse_short(lines)
        elif has_long:
            rows = _parse_long(lines)

        summary = _build_summary(rows)
        rows = _maybe_group_dirs(rows)

        return ParseResult(
            tool="git-status",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )


def _parse_long(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    in_staged = False
    in_unstaged = False
    in_untracked = False

    for line in lines:
        if line.startswith("Changes to be committed"):
            in_staged = True
            in_unstaged = False
            in_untracked = False
            continue
        if line.startswith("Changes not staged"):
            in_staged = False
            in_unstaged = True
            in_untracked = False
            continue
        if line.startswith("Untracked files"):
            in_staged = False
            in_unstaged = False
            in_untracked = True
            continue

        # Skip hint lines
        if line.strip().startswith('(use "git'):
            continue

        if in_untracked:
            stripped = line.strip()
            if stripped and not stripped.startswith("("):
                rows.append([stripped, "untracked", "false"])
            continue

        m = _LONG_MOD_RE.match(line)
        if m:
            status = m.group(1)
            filepath = m.group(2).strip()
            staged = "true" if in_staged else "false"
            rows.append([filepath, status, staged])

    return rows


def _parse_short(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        m = _SHORT_LINE_RE.match(line)
        if not m:
            continue
        xy = m.group(1)
        filepath = m.group(2).strip()
        x = xy[0]  # index/staged
        y = xy[1]  # worktree/unstaged

        if x == "?" and y == "?":
            rows.append([filepath, "untracked", "false"])
            continue

        if x not in (" ", "?", "!") and x.strip():
            status = _short_status_label(x)
            rows.append([filepath, status, "true"])
        elif y not in (" ", "?", "!") and y.strip():
            status = _short_status_label(y)
            rows.append([filepath, status, "false"])
    return rows


def _build_summary(rows: list[list[str]]) -> str:
    if not rows:
        return "Working tree clean"
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        status = row[1]
        first = status[0].upper()
        if first == "M":
            counts["M"] += 1
        elif first == "A" or status == "added":
            counts["A"] += 1
        elif first == "D":
            counts["D"] += 1
        elif status == "untracked":
            counts["?"] += 1
        else:
            counts["O"] += 1

    total = len(rows)
    parts = []
    for key in ("M", "A", "D", "?"):
        if counts[key]:
            parts.append(f"{key}:{counts[key]}")
    if counts["O"]:
        parts.append(f"O:{counts['O']}")

    if parts:
        return f"Files: {total} ({', '.join(parts)})"
    return f"Files: {total}"


def _maybe_group_dirs(rows: list[list[str]]) -> list[list[str]]:
    dir_files: dict[str, list[list[str]]] = defaultdict(list)
    no_dir: list[list[str]] = []

    for row in rows:
        filepath = row[0]
        if "/" in filepath:
            dirname = filepath.split("/")[0]
            dir_files[dirname].append(row)
        else:
            no_dir.append(row)

    result: list[list[str]] = list(no_dir)
    for dirname, file_rows in sorted(dir_files.items()):
        if len(file_rows) > _DIR_THRESHOLD:
            counts: dict[str, int] = defaultdict(int)
            for r in file_rows:
                status = r[1]
                first = status[0].upper()
                if first == "M":
                    counts["M"] += 1
                elif first == "A" or status == "added":
                    counts["A"] += 1
                elif first == "D":
                    counts["D"] += 1
                elif status == "untracked":
                    counts["?"] += 1
                else:
                    counts["O"] += 1

            parts = []
            for key in ("M", "A", "D", "?"):
                if counts[key]:
                    parts.append(f"{key}:{counts[key]}")
            summary = ", ".join(parts)
            result.append([f"{dirname}/", f"({len(file_rows)} files: {summary})", ""])
        else:
            result.extend(file_rows)

    return result
