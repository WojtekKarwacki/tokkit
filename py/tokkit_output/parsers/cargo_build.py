"""cargo build output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "severity", "code", "message"]

# error[E0308]: mismatched types
_DIAG_HEADER_RE = re.compile(
    r"^(error|warning)\[([A-Z]\d+)\]:\s+(.+)$"
)

# --> src/main.rs:42:5
_LOCATION_RE = re.compile(r"^\s+-->\s+([^:]+):(\d+):(\d+)")

_COMPILING_RE = re.compile(r"^\s*Compiling ")

_ERROR_CODE_RE = re.compile(r"error\[[A-Z]\d+\]")
_WARNING_CODE_RE = re.compile(r"warning\[[^\]]+\]")


class CargoBuildParser(BaseParser):
    id = "cargo-build"
    hint_values = ["cargo-build"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        has_diag = bool(_ERROR_CODE_RE.search(clean) or _WARNING_CODE_RE.search(clean))
        has_compiling = bool(_COMPILING_RE.search(clean))
        if has_diag and has_compiling:
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()
        rows: list[list[str]] = []

        i = 0
        n_errors = 0
        n_warnings = 0

        while i < len(lines):
            line = lines[i]
            m = _DIAG_HEADER_RE.match(line)
            if m:
                severity = m.group(1)   # "error" or "warning"
                code = m.group(2)       # "E0308"
                message = m.group(3)

                if severity == "error":
                    n_errors += 1
                else:
                    n_warnings += 1

                # Look ahead for location line
                file_ = ""
                line_no = ""
                col = ""
                for j in range(i + 1, min(i + 5, len(lines))):
                    lm = _LOCATION_RE.match(lines[j])
                    if lm:
                        file_ = lm.group(1)
                        line_no = lm.group(2)
                        col = lm.group(3)
                        break

                rows.append([file_, line_no, col, severity, code, message])

            i += 1

        summary = f"{n_errors} error{'s' if n_errors != 1 else ''}, {n_warnings} warning{'s' if n_warnings != 1 else ''}"

        return ParseResult(
            tool="cargo-build",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
