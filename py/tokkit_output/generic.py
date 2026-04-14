"""Generic fallback pipeline for unrecognized command output.

Five passes applied in sequence:
1. ANSI stripping
2. Progress bar removal
3. Consecutive identical line dedup
4. Similar-line dedup (numeric normalization)
5. Head/tail truncation
"""

import re

from tokkit_output.universal import strip_ansi

# --- Pass 2: Progress bar detection ---
_BAR_CHARS = re.compile(r"[━█▓░▒■□●○#=\->{}/|]+")
_SPINNER_CHARS = set("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⣾⣽⣻⢿⡿⣟⣯⣷")

# --- Pass 4: Numeric normalization ---
_NUMERIC_RE = re.compile(r"\d+")
_NUMERIC_HEAVY_RE = re.compile(r"\d")
_RATE_PATTERNS = re.compile(r"(%|[KMG]?B/s|ETA|--:--:--|[\d]+:[\d]+:[\d]+)")

# --- Thresholds ---
_MIN_LENGTH = 500  # Don't process output shorter than this
_TRUNCATE_THRESHOLD = 200  # Lines
_KEEP_HEAD = 100
_KEEP_TAIL = 50
_SIMILAR_GROUP_MIN = 5  # Minimum group size for similar-line collapse
_BAR_RATIO = 0.5  # Line is >50% bar characters


def _is_progress_bar_line(line: str) -> bool:
    """Return True if the line is predominantly progress bar characters."""
    stripped = line.strip()
    if not stripped:
        return False
    # Check for spinner characters
    if any(c in _SPINNER_CHARS for c in stripped):
        return True
    # Check ratio of bar characters
    bar_match = _BAR_CHARS.findall(stripped)
    bar_len = sum(len(m) for m in bar_match)
    return bar_len / len(stripped) >= _BAR_RATIO


def _is_numeric_heavy(line: str) -> bool:
    """Return True if line has >=30% digits or contains rate/progress patterns."""
    stripped = line.strip()
    if not stripped:
        return False
    if _RATE_PATTERNS.search(stripped):
        return True
    digit_count = len(_NUMERIC_HEAVY_RE.findall(stripped))
    return digit_count / len(stripped) >= 0.30


def _remove_progress_bars(lines: list[str]) -> list[str]:
    """Pass 2: Remove lines that are predominantly progress bars."""
    return [line for line in lines if not _is_progress_bar_line(line)]


def _consecutive_dedup(lines: list[str]) -> list[str]:
    """Pass 3: Collapse identical consecutive non-blank lines."""
    if not lines:
        return []
    result = []
    prev = lines[0]
    count = 1
    for line in lines[1:]:
        if line.strip() and line == prev:
            count += 1
        else:
            if count > 1:
                result.append(f"{prev} (x{count})")
            else:
                result.append(prev)
            prev = line
            count = 1
    if count > 1:
        result.append(f"{prev} (x{count})")
    else:
        result.append(prev)
    return result


def _similar_line_dedup(lines: list[str]) -> list[str]:
    """Pass 4: Collapse consecutive lines that differ only in numbers."""
    if not lines:
        return []

    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        normalized = _NUMERIC_RE.sub("N", line)

        if not _is_numeric_heavy(line):
            result.append(line)
            i += 1
            continue

        # Collect consecutive lines with same normalized form
        group = [line]
        j = i + 1
        while j < len(lines) and _NUMERIC_RE.sub("N", lines[j]) == normalized:
            group.append(lines[j])
            j += 1

        if len(group) >= _SIMILAR_GROUP_MIN:
            result.append(group[0])
            result.append(f"... ({len(group) - 2} similar lines)")
            result.append(group[-1])
        else:
            result.extend(group)
        i = j

    return result


def _head_tail_truncate(lines: list[str]) -> list[str]:
    """Pass 5: Truncate middle of output when over threshold."""
    if len(lines) <= _TRUNCATE_THRESHOLD:
        return lines
    removed = len(lines) - _KEEP_HEAD - _KEEP_TAIL
    return (
        lines[:_KEEP_HEAD]
        + [f"... ({removed} lines truncated, {len(lines)} total)"]
        + lines[-_KEEP_TAIL:]
    )


def generic_clean(text: str) -> str:
    """Apply the full generic fallback pipeline.

    Returns cleaned text. For short inputs (<500 chars), only strips ANSI.
    """
    if not text or not text.strip():
        return text.strip() if text else ""

    # Pass 1: ANSI stripping
    cleaned = strip_ansi(text)

    # Short output: ANSI strip only
    if len(cleaned) < _MIN_LENGTH:
        return cleaned

    lines = cleaned.splitlines()

    # Pass 2: Progress bar removal
    lines = _remove_progress_bars(lines)

    # Pass 3: Consecutive identical line dedup
    lines = _consecutive_dedup(lines)

    # Pass 4: Similar-line dedup
    lines = _similar_line_dedup(lines)

    # Pass 5: Head/tail truncation
    lines = _head_tail_truncate(lines)

    return "\n".join(lines)
