"""Pytest output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["test", "status", "file", "line", "error"]

# Detection patterns
_SEP_RE = re.compile(r"={5,}")
_RESULT_RE = re.compile(r"\b(passed|failed|error)\b")
_SESSION_RE = re.compile(r"test session starts")

# Short summary line: FAILED tests/test_foo.py::test_bar - AssertionError: ...
_SHORT_FAIL_RE = re.compile(
    r"^(FAILED|ERROR)\s+([\w./\-]+)(?:::([\w\[\]<>]+))?\s*-\s*(.+)$"
)

# Location from Python traceback: File "path/to/file.py", line 42, in test_name
_LOCATION_RE = re.compile(r'File "([^"]+)", line (\d+)')
# Location from pytest assertion line: "tests/test_api.py:42: AssertionError"
_PYTEST_LOC_RE = re.compile(r"^([\w./\-]+\.py):(\d+):\s+\w")

# Failure block header: underscores with test name in the middle
# Matches: "_________________________ test_get_users __________________________"
_BLOCK_HEADER_RE = re.compile(r"^_+\s+([\w\[\]<>]+)\s+_+$")

# PASSED/FAILED lines with optional progress percentage
# Matches: "tests/file.py::test_name PASSED                                   [ 20%]"
# and:      "PASSED tests/file.py::test_name"
_PROGRESS_RE = re.compile(r"\s+\[\s*\d+%\]")


def _parse_final_summary(text: str) -> str:
    """Extract the summary string from the final === line."""
    lines = text.splitlines()
    for line in reversed(lines):
        if _SEP_RE.search(line) and ("passed" in line or "failed" in line or "error" in line):
            summary = _SEP_RE.sub("", line).strip()
            return summary
    return ""


def _parse_short_summary_failures(text: str) -> list[dict]:
    """Parse the '=== short test summary info ===' section."""
    failures = []
    in_summary = False
    for line in text.splitlines():
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary:
            if _SEP_RE.search(line):
                break
            m = _SHORT_FAIL_RE.match(line.strip())
            if m:
                status = m.group(1)
                path = m.group(2)
                test_name = m.group(3) or ""
                error = m.group(4).strip()
                failures.append({
                    "status": status,
                    "path": path,
                    "test": test_name,
                    "error": error,
                })
    return failures


def _find_traceback_location(block: str) -> tuple[str, str]:
    """Return (file, line) from the last traceback File reference.

    Checks both standard Python traceback format and pytest assertion format.
    """
    # Try standard Python traceback format first
    matches = _LOCATION_RE.findall(block)
    if matches:
        return matches[-1]
    # Try pytest assertion line format: "tests/test_api.py:42: AssertionError"
    for line in block.splitlines():
        m = _PYTEST_LOC_RE.match(line.strip())
        if m:
            return m.group(1), m.group(2)
    return ("", "")


def _parse_verbose_tests(text: str) -> list[dict]:
    """Parse PASSED/FAILED/ERROR lines from verbose output."""
    results = []
    for line in text.splitlines():
        stripped = line.strip()
        # Remove trailing progress percentage "[  20%]"
        clean_line = _PROGRESS_RE.sub("", stripped).rstrip()
        if "::" in clean_line:
            parts = clean_line.rsplit(None, 1)
            if len(parts) == 2 and parts[1] in ("PASSED", "FAILED", "ERROR"):
                full_path = parts[0].strip()
                if "::" in full_path:
                    path, test = full_path.rsplit("::", 1)
                    results.append({
                        "status": parts[1],
                        "path": path,
                        "test": test,
                    })
    return results


def _split_failure_blocks(text: str) -> dict[str, str]:
    """Return {test_name: block_text} keyed by test name from block headers."""
    blocks = {}
    current_key = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = _BLOCK_HEADER_RE.match(line)
        if m:
            if current_key:
                blocks[current_key] = "\n".join(current_lines)
            current_key = m.group(1).strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key:
        blocks[current_key] = "\n".join(current_lines)
    return blocks


class PytestParser(BaseParser):
    id = "pytest"
    hint_values = ["pytest", "py.test"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _SESSION_RE.search(clean):
            score += 0.5
        if _SEP_RE.search(clean):
            score += 0.2
        if _RESULT_RE.search(clean.lower()):
            score += 0.2
        if "::test_" in clean or "::Test" in clean:
            score += 0.1
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        summary = _parse_final_summary(clean)

        failures = _parse_short_summary_failures(clean)
        failure_blocks = _split_failure_blocks(clean)

        def _get_location(failure: dict) -> tuple[str, str]:
            test_name = failure["test"]
            block = failure_blocks.get(test_name, "")
            if not block:
                for key, val in failure_blocks.items():
                    if test_name in key:
                        block = val
                        break
            return _find_traceback_location(block)

        if not verbose:
            rows = []
            for f in failures:
                file_, line = _get_location(f)
                rows.append([
                    f["test"] or f["path"],
                    f["status"],
                    file_ or f["path"],
                    line,
                    f["error"],
                ])
        else:
            verbose_tests = _parse_verbose_tests(clean)
            rows = []
            fail_detail = {f["test"]: f for f in failures}
            for t in verbose_tests:
                test_name = t["test"]
                status = t["status"]
                if status in ("FAILED", "ERROR") and test_name in fail_detail:
                    f = fail_detail[test_name]
                    file_, line = _get_location(f)
                    rows.append([
                        test_name,
                        status,
                        file_ or t["path"],
                        line,
                        f["error"],
                    ])
                else:
                    rows.append([test_name, status, t["path"], "", ""])

        return ParseResult(
            tool="pytest",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
