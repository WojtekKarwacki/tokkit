"""Universal fallback: ANSI strip + blank line collapse."""

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


def collapse_blanks(text: str) -> str:
    """Collapse runs of 3+ blank/whitespace-only lines to a single blank line."""
    return re.sub(r"(\n\s*){3,}", "\n\n", text)


def universal_clean(text: str) -> str:
    """Apply universal cleanup: ANSI strip + blank collapse."""
    return collapse_blanks(strip_ansi(text))
