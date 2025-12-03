"""Ruff output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]

# filepath:line:col: RULE_CODE message
# E.g.: src/auth.py:42:5: E501 Line too long (127 > 88)
_VIOLATION_RE = re.compile(
    r"^([^\s:][^:]*):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$"
)

# "Found N errors."
_FOUND_RE = re.compile(r"Found (\d+) errors?")

# "All checks passed!"
_CLEAN_RE = re.compile(r"All checks passed", re.IGNORECASE)


def _severity(rule: str) -> str:
    """Derive severity letter from rule code prefix."""
    prefix = rule[0].upper()
    if prefix == "E":
        return "error"
    if prefix == "W":
        return "warning"
    return "convention"


class RuffParser(BaseParser):
    id = "ruff"
    hint_values = ["ruff"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _FOUND_RE.search(clean):
            score += 0.5
        if _CLEAN_RE.search(clean):
            score += 0.5
        violation_count = sum(1 for line in clean.splitlines() if _VIOLATION_RE.match(line.strip()))
        if violation_count > 0:
            score += min(violation_count * 0.15, 0.45)
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []
        for line in clean.splitlines():
            m = _VIOLATION_RE.match(line.strip())
            if m:
                filepath = m.group(1)
                lineno = m.group(2)
                col = m.group(3)
                rule = m.group(4)
                message = m.group(5).strip()
                severity = _severity(rule)
                rows.append([filepath, lineno, col, rule, severity, message])

        n = len(rows)
        if n == 0 and _CLEAN_RE.search(clean):
            summary = "All checks passed"
        else:
            summary = f"{n} violation{'s' if n != 1 else ''}"

        return ParseResult(
            tool="ruff",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
