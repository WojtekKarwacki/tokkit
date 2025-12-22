"""TypeScript compiler (tsc) output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "severity", "code", "message"]

# "src/api.ts(42,5): error TS2322: Type 'string' is not assignable to type 'number'."
_DIAG_RE = re.compile(
    r"^(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)$"
)


class TscParser(BaseParser):
    id = "tsc"
    hint_values = ["tsc", "typescript"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        count = sum(1 for line in clean.splitlines() if _DIAG_RE.match(line.strip()))
        if count > 0:
            return 0.9
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        for line in clean.splitlines():
            m = _DIAG_RE.match(line.strip())
            if m:
                filepath = m.group(1)
                lineno = m.group(2)
                col = m.group(3)
                severity = m.group(4)
                code = m.group(5)
                message = m.group(6).strip()
                rows.append([filepath, lineno, col, severity, code, message])

        n_errors = sum(1 for r in rows if r[3] == "error")
        summary = f"{n_errors} error{'s' if n_errors != 1 else ''}"

        return ParseResult(
            tool="tsc",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
