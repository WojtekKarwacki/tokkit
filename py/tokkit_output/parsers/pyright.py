"""Pyright output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "severity", "code", "message"]

# Summary line: "N errors, N warnings, N informations"
_SUMMARY_RE = re.compile(
    r"(\d+)\s+error[s]?,\s*(\d+)\s+warning[s]?,\s*(\d+)\s+information[s]?"
)

# Indented diagnostic: "  /path/to/file.py:42:5 - error: message (reportXxx)"
# Pyright also uses: "  filepath:line:col - severity: message  (code)"
_DIAG_RE = re.compile(
    r"^\s+(.+?):(\d+):(\d+)\s+-\s+(error|warning|information):\s+(.+?)(?:\s+\(([^)]+)\))?$"
)

# File header line (not indented, ends with colon or is a plain path)
_FILE_HEADER_RE = re.compile(r"^([^\s].+\.py)\s*$")


class PyrightParser(BaseParser):
    id = "pyright"
    hint_values = ["pyright"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _SUMMARY_RE.search(clean):
            score += 0.6
        diag_count = sum(1 for line in clean.splitlines() if _DIAG_RE.match(line))
        if diag_count > 0:
            score += min(diag_count * 0.2, 0.4)
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []
        for line in clean.splitlines():
            m = _DIAG_RE.match(line)
            if m:
                filepath = m.group(1).strip()
                lineno = m.group(2)
                col = m.group(3)
                severity = m.group(4)
                message = m.group(5).strip()
                code = m.group(6) or ""
                # Skip informations in default mode
                if not verbose and severity == "information":
                    continue
                rows.append([filepath, lineno, col, severity, code, message])

        summary_m = _SUMMARY_RE.search(clean)
        if summary_m:
            errors = int(summary_m.group(1))
            warnings = int(summary_m.group(2))
            parts = []
            if errors:
                parts.append(f"{errors} error{'s' if errors != 1 else ''}")
            if warnings:
                parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
            summary = ", ".join(parts) if parts else "0 errors"
        else:
            n = len(rows)
            summary = f"{n} issue{'s' if n != 1 else ''}"

        return ParseResult(
            tool="pyright",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
