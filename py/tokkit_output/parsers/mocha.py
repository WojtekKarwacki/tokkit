"""Mocha output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["test", "status", "file", "line", "error"]

# Detection: "N passing" and optional "M failing" or checkmark/cross lines
_PASSING_RE = re.compile(r"\d+\s+passing")
_FAILING_RE = re.compile(r"\d+\s+failing")
_CHECKMARK_RE = re.compile(r"[✓✗]")

# Numbered failure block header: "  1) SuiteName TestName:"
_FAIL_NUM_RE = re.compile(r"^\s+(\d+)\)\s+(.+):?\s*$")

# Location: "at Context.<anonymous> (test/db.test.js:42:7)"
_LOCATION_RE = re.compile(r"at\s+\S+\s+\(([^)]+):(\d+):\d+\)")

# Summary counts
_PASSING_COUNT_RE = re.compile(r"(\d+)\s+passing")
_FAILING_COUNT_RE = re.compile(r"(\d+)\s+failing")


class MochaParser(BaseParser):
    id = "mocha"
    hint_values = ["mocha"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _PASSING_RE.search(clean):
            score += 0.5
        if _FAILING_RE.search(clean) or _CHECKMARK_RE.search(clean):
            score += 0.35
        return min(score, 0.85)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        lines = clean.splitlines()
        i = 0
        # Find the "failing" section (after the passing summary)
        in_failures = False

        while i < len(lines):
            line = lines[i]
            if _FAILING_RE.search(line):
                in_failures = True
                i += 1
                continue

            if in_failures:
                m = _FAIL_NUM_RE.match(line)
                if m:
                    test_name = m.group(2).strip().rstrip(":")
                    # Collect the block until next numbered failure or end
                    error_msg = ""
                    file_ = ""
                    line_no = ""
                    j = i + 1
                    while j < len(lines):
                        inner = lines[j]
                        next_m = _FAIL_NUM_RE.match(inner)
                        if next_m:
                            break
                        stripped = inner.strip()
                        if stripped and not error_msg and not stripped.startswith("at "):
                            error_msg = stripped
                        loc_m = _LOCATION_RE.search(stripped)
                        if loc_m:
                            candidate_file = loc_m.group(1)
                            candidate_line = loc_m.group(2)
                            # Prefer non-node_modules locations
                            if not file_ or "node_modules" not in candidate_file:
                                file_ = candidate_file
                                line_no = candidate_line
                        j += 1
                    rows.append([test_name, "FAILED", file_, line_no, error_msg])
                    i = j
                    continue
            i += 1

        # Summary
        passing_m = _PASSING_COUNT_RE.search(clean)
        failing_m = _FAILING_COUNT_RE.search(clean)
        n_passed = int(passing_m.group(1)) if passing_m else 0
        n_failed = int(failing_m.group(1)) if failing_m else 0
        summary = f"{n_passed} passed, {n_failed} failed"

        return ParseResult(
            tool="mocha",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
