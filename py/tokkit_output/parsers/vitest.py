"""Vitest output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["test", "status", "file", "line", "error"]

# Detection patterns
_TEST_FILES_RE = re.compile(r"Test Files")
_DURATION_RE = re.compile(r"\bDuration\b")
_CHECKMARK_RE = re.compile(r"[✓×✗]")
_TESTS_LINE_RE = re.compile(r"\bTests\b.*\d+")

# Failure block: "FAIL src/api.test.ts > suite name > test name"
_FAIL_BLOCK_RE = re.compile(r"^(?:FAIL|×)\s+([\w./\-]+\.(?:test|spec)\.[tj]sx?)\s*(?:>(.+))?$")

# Error location in vitest output: " › file.ts:42:5"
_LOCATION_RE = re.compile(r"([^\s(]+\.(?:[tj]sx?)):(\d+):\d+")

# Summary: "Tests  3 failed | 5 passed (8)"
_SUMMARY_RE = re.compile(r"Tests\s+(\d+)\s+failed\s*\|\s*(\d+)\s+passed")
_PASSED_ONLY_RE = re.compile(r"Tests\s+(\d+)\s+passed")


class VitestParser(BaseParser):
    id = "vitest"
    hint_values = ["vitest"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _TEST_FILES_RE.search(clean) and _DURATION_RE.search(clean):
            return 0.9
        if _CHECKMARK_RE.search(clean) and _TESTS_LINE_RE.search(clean):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        lines = clean.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m = _FAIL_BLOCK_RE.match(line.strip())
            if m:
                filepath = m.group(1)
                test_path = (m.group(2) or "").strip()
                # Look ahead for error message and location
                error_msg = ""
                file_ = filepath
                line_no = ""
                j = i + 1
                while j < len(lines) and j < i + 20:
                    inner = lines[j].strip()
                    if inner.startswith("FAIL ") or (inner and not inner.startswith(" ") and j > i + 2):
                        break
                    if inner and not error_msg and not inner.startswith("at "):
                        error_msg = inner
                    loc_m = _LOCATION_RE.search(inner)
                    if loc_m:
                        file_ = loc_m.group(1)
                        line_no = loc_m.group(2)
                    j += 1
                rows.append([test_path or filepath, "FAILED", file_, line_no, error_msg])
            i += 1

        # Build summary
        summary_m = _SUMMARY_RE.search(clean)
        if summary_m:
            n_failed = int(summary_m.group(1))
            n_passed = int(summary_m.group(2))
            summary = f"{n_passed} passed, {n_failed} failed"
        else:
            passed_m = _PASSED_ONLY_RE.search(clean)
            n_passed = int(passed_m.group(1)) if passed_m else 0
            summary = f"{n_passed} passed, 0 failed"

        return ParseResult(
            tool="vitest",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
