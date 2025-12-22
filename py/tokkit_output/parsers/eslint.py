"""ESLint output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]

# "✖ 5 problems (3 errors, 2 warnings)"
_PROBLEMS_RE = re.compile(r"[✖✗x]\s+(\d+)\s+problem")

# File header line: absolute or relative path ending in .js/.ts/.jsx/.tsx
_FILE_HEADER_RE = re.compile(r"^(/[\w./\- ]+|[\w./\-]+\.(?:[jt]sx?))$")

# Indented diagnostic: "   5:10  error  'unused' is defined but never used  no-unused-vars"
_DIAG_RE = re.compile(
    r"^\s+(\d+):(\d+)\s+(error|warning)\s+(.+?)\s{2,}(\S+)\s*$"
)


class EslintParser(BaseParser):
    id = "eslint"
    hint_values = ["eslint"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _PROBLEMS_RE.search(clean):
            return 0.9
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []
        current_file = ""

        for line in clean.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # File header (no leading whitespace, looks like a path)
            if not line.startswith(" ") and not line.startswith("\t"):
                if _FILE_HEADER_RE.match(stripped):
                    current_file = stripped
                    continue

            # Diagnostic line
            m = _DIAG_RE.match(line)
            if m:
                lineno = m.group(1)
                col = m.group(2)
                severity = m.group(3)
                message = m.group(4).strip()
                rule = m.group(5).strip()
                rows.append([current_file, lineno, col, rule, severity, message])

        n = len(rows)
        summary = f"{n} violation{'s' if n != 1 else ''}"

        return ParseResult(
            tool="eslint",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
