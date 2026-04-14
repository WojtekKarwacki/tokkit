"""Git diff output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "lines_changed", "content"]

_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_HUNK_HEADER_RE = re.compile(r"^@@ .+ @@")
_STAT_LINE_RE = re.compile(r"^\s*(\S.*?)\s*\|\s*(\d+)\s*[+\-]*\s*$")
_STAT_SUMMARY_RE = re.compile(r"^\s*\d+ files? changed")

_LOCK_FILES = frozenset(
    [
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "poetry.lock",
        "uv.lock",
        "go.sum",
        "Gemfile.lock",
        "composer.lock",
        "Pipfile.lock",
    ]
)

_CONTEXT_WINDOW = 3
_HUNK_CHANGE_LIMIT = 50


def _is_lock_file(path: str) -> bool:
    return path.split("/")[-1] in _LOCK_FILES


def _parse_unified_diff(lines: list[str]) -> list[tuple[str, int, str]]:
    """Parse unified diff lines into (file, lines_changed, content) tuples."""
    rows: list[tuple[str, int, str]] = []

    current_file: str | None = None
    is_lock = False
    lock_line_count = 0

    content_lines: list[str] = []
    change_count = 0
    hunk_change_count = 0
    truncated = False

    leading_context: list[str] = []
    trailing_count = 0
    in_hunk = False

    def flush_file() -> None:
        nonlocal current_file, content_lines, change_count, hunk_change_count
        nonlocal truncated, leading_context, trailing_count, in_hunk
        nonlocal is_lock, lock_line_count

        if current_file is None:
            return

        if is_lock:
            rows.append((current_file, lock_line_count, f"(lockfile changed, {lock_line_count} lines)"))
        else:
            content = "\n".join(content_lines)
            rows.append((current_file, change_count, content))

        current_file = None
        content_lines = []
        change_count = 0
        hunk_change_count = 0
        truncated = False
        leading_context = []
        trailing_count = 0
        in_hunk = False
        is_lock = False
        lock_line_count = 0

    for line in lines:
        # New file header
        m = _DIFF_HEADER_RE.match(line)
        if m:
            flush_file()
            current_file = m.group(2)
            is_lock = _is_lock_file(current_file)
            in_hunk = False
            continue

        if current_file is None:
            continue

        if is_lock:
            if line.startswith("+") and not line.startswith("+++"):
                lock_line_count += 1
            continue

        # Strip index/meta lines
        if (
            line.startswith("index ")
            or line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("old mode")
            or line.startswith("new mode")
            or line.startswith("deleted file")
            or line.startswith("new file")
        ):
            continue

        # Hunk header
        if _HUNK_HEADER_RE.match(line):
            if content_lines and not content_lines[-1].startswith("@@"):
                content_lines.append("")
            content_lines.append(line)
            in_hunk = True
            hunk_change_count = 0
            truncated = False
            leading_context = []
            trailing_count = 0
            continue

        if not in_hunk:
            continue

        if truncated:
            # Still count changes but skip content
            if line.startswith("+") or line.startswith("-"):
                change_count += 1
            continue

        if line.startswith("+") or line.startswith("-"):
            # Flush leading context (last 3 lines)
            for ctx in leading_context[-_CONTEXT_WINDOW:]:
                content_lines.append(ctx)
            leading_context = []
            trailing_count = _CONTEXT_WINDOW

            content_lines.append(line)
            change_count += 1
            hunk_change_count += 1

            if hunk_change_count >= _HUNK_CHANGE_LIMIT:
                content_lines.append("... (truncated after 50 changed lines)")
                truncated = True
        else:
            # Context line
            if trailing_count > 0:
                content_lines.append(line)
                trailing_count -= 1
            else:
                leading_context.append(line)
                if len(leading_context) > _CONTEXT_WINDOW:
                    leading_context.pop(0)

    flush_file()
    return rows


def _parse_stat(lines: list[str]) -> list[tuple[str, int, str]]:
    """Parse --stat format output."""
    rows = []
    for line in lines:
        m = _STAT_LINE_RE.match(line)
        if m:
            filepath = m.group(1).strip()
            count = int(m.group(2))
            rows.append((filepath, count, f"{count} changes"))
    return rows


class GitDiffParser(BaseParser):
    id = "git-diff"
    hint_values = ["git-diff", "git"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        for line in clean.splitlines():
            if re.match(r"^diff --git a/", line):
                score += 0.6
                break
        for line in clean.splitlines():
            if _HUNK_HEADER_RE.match(line):
                score += 0.3
                break
        if score == 0.0:
            stat_lines = sum(1 for line in clean.splitlines() if _STAT_LINE_RE.match(line))
            if stat_lines >= 2:
                score += 0.7
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        has_unified = any(re.match(r"^diff --git a/", line) for line in lines)

        if has_unified:
            rows_data = _parse_unified_diff(lines)
        else:
            rows_data = _parse_stat(lines)

        rows = [[f, str(c), ct] for f, c, ct in rows_data]

        n_files = len(rows_data)
        total_changes = sum(c for _, c, _ in rows_data)
        if n_files == 0:
            summary = "no changes"
        else:
            summary = f"{n_files} file{'s' if n_files != 1 else ''}, {total_changes} changes"

        return ParseResult(
            tool="git-diff",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
