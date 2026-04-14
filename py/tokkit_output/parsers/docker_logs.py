"""Docker logs output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")

# ---------------------------------------------------------------------------
# Log parsing constants
# ---------------------------------------------------------------------------

_ERROR_RE = re.compile(r"\b(ERROR|FATAL|PANIC|Exception)\b")
_HEAD_LINES = 10
_TAIL_LINES = 10
_LOG_CONTEXT = 2
_SHORT_THRESHOLD = 20


def _parse_logs(lines: list[str], verbose: bool) -> tuple[list[list[str]], str]:
    """Parse docker log lines with head/tail/error neighborhood compression."""
    if not lines:
        return [], "0 log lines, 0 errors"

    total = len(lines)
    error_count = sum(1 for ln in lines if _ERROR_RE.search(ln))
    summary = f"{total} log lines, {error_count} error{'s' if error_count != 1 else ''}"

    if verbose or total <= _SHORT_THRESHOLD:
        return [[ln] for ln in lines], summary

    # Collect indices to keep
    keep: set[int] = set()

    for i in range(min(_HEAD_LINES, total)):
        keep.add(i)

    for i in range(max(0, total - _TAIL_LINES), total):
        keep.add(i)

    for i, ln in enumerate(lines):
        if _ERROR_RE.search(ln):
            for j in range(max(0, i - _LOG_CONTEXT), min(total, i + _LOG_CONTEXT + 1)):
                keep.add(j)

    output_rows: list[list[str]] = []
    sorted_indices = sorted(keep)
    prev_idx = -1
    for idx in sorted_indices:
        if prev_idx >= 0 and idx > prev_idx + 1:
            skipped = idx - prev_idx - 1
            output_rows.append([f"... ({skipped} line{'s' if skipped != 1 else ''} skipped)"])
        output_rows.append([lines[idx]])
        prev_idx = idx

    if sorted_indices and sorted_indices[-1] < total - 1:
        remaining = total - 1 - sorted_indices[-1]
        output_rows.append([f"... ({remaining} line{'s' if remaining != 1 else ''} skipped)"])

    return output_rows, summary


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class DockerLogsParser(BaseParser):
    id = "docker-logs"
    hint_values = ["docker-logs"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        ts_count = sum(1 for ln in lines if _TIMESTAMP_RE.match(ln.strip()))
        if ts_count >= 5:
            return 0.7

        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = [ln for ln in clean.splitlines() if ln.strip()]
        rows, summary = _parse_logs(lines, verbose)
        return ParseResult(
            tool="docker-logs",
            summary=summary,
            schema=["line"],
            rows=rows,
            verbose=verbose,
        )
