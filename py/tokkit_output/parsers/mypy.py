"""Mypy output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "severity", "code", "message"]

# filepath:line:col: severity: message  [error-code]
# Col is optional in mypy output.
_DIAG_RE = re.compile(
    r"^([^\s:][^:]*):(\d+)(?::(\d+))?:\s+(error|warning|note):\s+(.+?)(?:\s+\[([^\]]+)\])?$"
)

# "Found N errors in M files (checked K source files)"
_FOUND_RE = re.compile(r"Found (\d+) error")

# "Success: no issues found (N source files)"
_SUCCESS_RE = re.compile(r"Success:\s*no issues found", re.IGNORECASE)


class MypyParser(BaseParser):
    id = "mypy"
    hint_values = ["mypy"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _FOUND_RE.search(clean):
            score += 0.5
        if _SUCCESS_RE.search(clean):
            score += 0.5
        diag_count = sum(1 for line in clean.splitlines() if _DIAG_RE.match(line.strip()))
        if diag_count > 0:
            score += min(diag_count * 0.15, 0.45)
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []
        for line in clean.splitlines():
            m = _DIAG_RE.match(line.strip())
            if m:
                filepath = m.group(1)
                lineno = m.group(2)
                col = m.group(3) or ""
                severity = m.group(4)
                message = m.group(5).strip()
                code = m.group(6) or ""
                # Skip notes in default mode; include all in verbose
                if not verbose and severity == "note":
                    continue
                rows.append([filepath, lineno, col, severity, code, message])

        found_m = _FOUND_RE.search(clean)
        if found_m:
            n = int(found_m.group(1))
            summary = f"{n} error{'s' if n != 1 else ''}"
        elif _SUCCESS_RE.search(clean):
            summary = "no issues found"
        else:
            n = sum(1 for r in rows if r[3] == "error")
            summary = f"{n} error{'s' if n != 1 else ''}"

        return ParseResult(
            tool="mypy",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
