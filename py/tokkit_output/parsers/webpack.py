"""Webpack output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["step", "status", "message"]

# Detection
_WEBPACK_RE = re.compile(r"\bwebpack\b", re.IGNORECASE)
_ERROR_IN_RE = re.compile(r"ERROR in\b")
_COMPILED_RE = re.compile(r"\bcompiled\b", re.IGNORECASE)

# "ERROR in ./src/index.ts" block header
_ERROR_BLOCK_RE = re.compile(r"^ERROR in\s+(.+)$")

# "webpack compiled with N error(s)"
_COMPILED_SUMMARY_RE = re.compile(r"webpack compiled(?: with (\d+) error[s]?)?", re.IGNORECASE)
_ERROR_COUNT_RE = re.compile(r"(\d+)\s+error", re.IGNORECASE)


class WebpackParser(BaseParser):
    id = "webpack"
    hint_values = ["webpack"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _WEBPACK_RE.search(clean):
            score += 0.4
        if _ERROR_IN_RE.search(clean) or _COMPILED_RE.search(clean):
            score += 0.45
        return min(score, 0.85)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        lines = clean.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m = _ERROR_BLOCK_RE.match(line.strip())
            if m:
                step = m.group(1).strip()
                # Collect message lines until blank line or next ERROR
                msg_parts = []
                j = i + 1
                while j < len(lines):
                    inner = lines[j].strip()
                    if not inner or _ERROR_BLOCK_RE.match(inner):
                        break
                    msg_parts.append(inner)
                    j += 1
                message = " ".join(msg_parts[:3])  # cap at 3 lines
                rows.append([step, "error", message])
                i = j
                continue
            i += 1

        n = len(rows)
        summary = f"{n} error{'s' if n != 1 else ''}"

        return ParseResult(
            tool="webpack",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
