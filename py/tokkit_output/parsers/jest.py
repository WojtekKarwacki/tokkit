"""Jest output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["test", "status", "file", "line", "error"]

# Detection patterns
_SUITES_RE = re.compile(r"Test Suites:")
_TESTS_RE = re.compile(r"\bTests:\s+\d+")

# Failure block header: "● SuiteName › testName"
_BLOCK_HEADER_RE = re.compile(r"^\s*●\s+(.+)$")

# Location line: "at Object.<anonymous> (tests/db.test.ts:15:27)"
_LOCATION_RE = re.compile(r"at\s+\S+\s+\(([^)]+):(\d+):\d+\)")

# Summary line: "Tests: 3 failed, 5 passed, 8 total"
_SUMMARY_RE = re.compile(r"Tests:\s+(.+)")

# Individual pass/fail counts
_FAILED_COUNT_RE = re.compile(r"(\d+)\s+failed")
_PASSED_COUNT_RE = re.compile(r"(\d+)\s+passed")


class JestParser(BaseParser):
    id = "jest"
    hint_values = ["jest"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _SUITES_RE.search(clean) and _TESTS_RE.search(clean):
            return 0.9
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        # Split into failure blocks by "● " header
        lines = clean.splitlines()
        blocks: list[tuple[str, list[str]]] = []
        current_name: str | None = None
        current_lines: list[str] = []

        for line in lines:
            m = _BLOCK_HEADER_RE.match(line)
            if m and not line.strip().startswith("●") is False:
                pass
            if re.match(r"^\s*●\s+\S", line):
                if current_name is not None:
                    blocks.append((current_name, current_lines))
                current_name = re.match(r"^\s*●\s+(.+)$", line).group(1).strip()
                current_lines = []
            elif current_name is not None:
                current_lines.append(line)

        if current_name is not None:
            blocks.append((current_name, current_lines))

        for name, block_lines in blocks:
            block_text = "\n".join(block_lines)
            # Get first error message (first non-empty line after header)
            error_msg = ""
            for bl in block_lines:
                stripped = bl.strip()
                if stripped and not stripped.startswith("at ") and not stripped.startswith("●"):
                    error_msg = stripped
                    break

            # Find location: last "at ... (file:line:col)" in block
            file_ = ""
            line_no = ""
            for m in _LOCATION_RE.finditer(block_text):
                file_ = m.group(1)
                line_no = m.group(2)

            rows.append([name, "FAILED", file_, line_no, error_msg])

        # Build summary
        summary_m = _SUMMARY_RE.search(clean)
        if summary_m:
            parts = summary_m.group(1)
            failed_m = _FAILED_COUNT_RE.search(parts)
            passed_m = _PASSED_COUNT_RE.search(parts)
            n_failed = int(failed_m.group(1)) if failed_m else 0
            n_passed = int(passed_m.group(1)) if passed_m else 0
            summary = f"{n_passed} passed, {n_failed} failed"
        else:
            summary = f"0 passed, 0 failed"

        return ParseResult(
            tool="jest",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
