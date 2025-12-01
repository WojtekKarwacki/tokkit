"""Unittest output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["test", "status", "file", "line", "error"]

# "Ran N tests in X.XXXs"
_RAN_RE = re.compile(r"Ran (\d+) tests? in")

# Long divider lines (both - and = variants)
_DASH_DIVIDER_RE = re.compile(r"^-{6,}$")
_EQ_DIVIDER_RE = re.compile(r"^={6,}$")

# FAIL/ERROR block header: "FAIL: test_foo (tests.test_module.TestClass)"
_BLOCK_HEADER_RE = re.compile(r"^(FAIL|ERROR):\s+(\w+)\s+\(([^)]+)\)")

# Traceback location
_LOCATION_RE = re.compile(r'File "([^"]+)", line (\d+)')

# Final result line
_OK_RE = re.compile(r"^OK$")
_FAILED_LINE_RE = re.compile(r"^FAILED\s*\((.+)\)$")


def _parse_ran_line(text: str) -> tuple[int, int, int]:
    """Return (total, failures, errors) from the output."""
    total = 0
    failures = 0
    errors = 0
    for line in text.splitlines():
        m = _RAN_RE.search(line)
        if m:
            total = int(m.group(1))
        fm = _FAILED_LINE_RE.match(line.strip())
        if fm:
            inner = fm.group(1)
            f_m = re.search(r"failures=(\d+)", inner)
            e_m = re.search(r"errors=(\d+)", inner)
            if f_m:
                failures = int(f_m.group(1))
            if e_m:
                errors = int(e_m.group(1))
    return total, failures, errors


def _parse_failure_blocks(text: str) -> list[dict]:
    """Parse FAIL/ERROR blocks from unittest output.

    Unittest output structure:
        ======================================================================
        FAIL: test_foo (module.Class)
        ----------------------------------------------------------------------
        Traceback (most recent call last):
          File "...", line N, in test_foo
            ...
        AssertionError: ...

        ----------------------------------------------------------------------
        Ran N tests in Xs

    The first `------` line after the header is the divider before the traceback
    (skip it); subsequent `------` or `======` lines end the block.
    """
    results = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        # Look for === divider that precedes a FAIL/ERROR header
        if _EQ_DIVIDER_RE.match(lines[i].strip()):
            # Peek at next non-empty line for FAIL/ERROR header
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                m = _BLOCK_HEADER_RE.match(lines[j].strip())
                if m:
                    status = m.group(1)
                    test_name = m.group(2)
                    module_path = m.group(3)
                    # Skip the header line and the dashes line that follows it
                    k = j + 1
                    if k < len(lines) and _DASH_DIVIDER_RE.match(lines[k].strip()):
                        k += 1  # skip the "------" separator line
                    # Collect traceback lines until next === or --- divider or "Ran"
                    block_lines = []
                    while k < len(lines):
                        if _EQ_DIVIDER_RE.match(lines[k].strip()):
                            break
                        if _DASH_DIVIDER_RE.match(lines[k].strip()):
                            break
                        if _RAN_RE.search(lines[k]):
                            break
                        block_lines.append(lines[k])
                        k += 1

                    block = "\n".join(block_lines)

                    # Extract file and line from traceback
                    locs = _LOCATION_RE.findall(block)
                    if locs:
                        file_, line = locs[-1]
                    else:
                        file_, line = "", ""

                    # Error message — last non-empty line of block
                    error = ""
                    for bl in reversed(block_lines):
                        stripped = bl.strip()
                        if stripped:
                            error = stripped
                            break

                    results.append({
                        "status": status,
                        "test": test_name,
                        "module": module_path,
                        "file": file_,
                        "line": line,
                        "error": error,
                    })
                    i = k
                    continue
        i += 1
    return results


class UnittestParser(BaseParser):
    id = "unittest"
    hint_values = ["unittest", "python-unittest"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _DASH_DIVIDER_RE.search(clean) or any(
            _DASH_DIVIDER_RE.match(l.strip()) for l in clean.splitlines()
        ):
            score += 0.2
        if _RAN_RE.search(clean):
            score += 0.5
        if any(_OK_RE.match(l.strip()) for l in clean.splitlines()) or \
                any(_FAILED_LINE_RE.match(l.strip()) for l in clean.splitlines()):
            score += 0.2
        if _BLOCK_HEADER_RE.search(clean):
            score += 0.1
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        total, failures, errors = _parse_ran_line(clean)
        passed = total - failures - errors

        parts = []
        if passed > 0:
            parts.append(f"{passed} passed")
        if failures > 0:
            parts.append(f"{failures} failed")
        if errors > 0:
            parts.append(f"{errors} error{'s' if errors > 1 else ''}")
        if not parts:
            parts.append(f"{total} passed")
        summary = ", ".join(parts)

        blocks = _parse_failure_blocks(clean)

        if not verbose:
            rows = [
                [b["test"], b["status"], b["file"], b["line"], b["error"]]
                for b in blocks
            ]
        else:
            rows = []
            verbose_re = re.compile(
                r"^(\w+)\s+\(.+\)\s+\.\.\.\s*(ok|FAIL|ERROR)$"
            )
            fail_lookup = {b["test"]: b for b in blocks}
            for line in clean.splitlines():
                vm = verbose_re.match(line.strip())
                if vm:
                    test_name = vm.group(1)
                    raw_status = vm.group(2)
                    status = "PASS" if raw_status == "ok" else raw_status
                    if status in ("FAIL", "ERROR") and test_name in fail_lookup:
                        b = fail_lookup[test_name]
                        rows.append([test_name, status, b["file"], b["line"], b["error"]])
                    else:
                        rows.append([test_name, status, "", "", ""])
            if not rows:
                rows = [
                    [b["test"], b["status"], b["file"], b["line"], b["error"]]
                    for b in blocks
                ]

        return ParseResult(
            tool="unittest",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
