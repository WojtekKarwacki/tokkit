"""cargo test output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["test", "status", "file", "line", "error"]

_RESULT_LINE_RE = re.compile(r"^test result:", re.MULTILINE)
_RUNNING_RE = re.compile(r"\brunning \d+ tests?\b")
_TEST_LINE_RE = re.compile(r"^test \S+ \.\.\. (ok|FAILED)", re.MULTILINE)

_SUMMARY_RE = re.compile(
    r"test result: (?:ok|FAILED)\.\s+(\d+) passed;\s+(\d+) failed"
)

# ---- tests::test_sub stdout ----
_FAILURE_HEADER_RE = re.compile(r"^---- (\S+) stdout ----")

# panicked at src/lib.rs:42:5:
_PANIC_RE = re.compile(r"panicked at ([^:]+):(\d+):\d+")

# test tests::test_sub ... FAILED
_ALL_TESTS_RE = re.compile(r"^test (\S+) \.\.\. (ok|FAILED)$")


class CargoTestParser(BaseParser):
    id = "cargo-test"
    hint_values = ["cargo-test"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _RESULT_LINE_RE.search(clean) and (
            _RUNNING_RE.search(clean) or re.search(r"\btest \S+", clean)
        ):
            return 0.9
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Collect failure blocks keyed by test name
        failure_blocks: dict[str, list[str]] = {}
        current_fail: str | None = None

        for line in lines:
            m = _FAILURE_HEADER_RE.match(line)
            if m:
                current_fail = m.group(1)
                failure_blocks[current_fail] = []
            elif current_fail is not None:
                if line.startswith("----") or line.strip() == "":
                    if line.startswith("----") and "stdout" in line:
                        # new block started — handled by next iteration
                        pass
                    failure_blocks[current_fail].append(line)
                else:
                    failure_blocks[current_fail].append(line)

        rows: list[list[str]] = []

        if verbose:
            # Include all tests
            for line in lines:
                m = _ALL_TESTS_RE.match(line.strip())
                if m:
                    test_name = m.group(1)
                    status = m.group(2)
                    if status == "FAILED" and test_name in failure_blocks:
                        block = failure_blocks[test_name]
                        block_text = "\n".join(block)
                        pm = _PANIC_RE.search(block_text)
                        file_ = pm.group(1) if pm else ""
                        line_no = pm.group(2) if pm else ""
                        # Get error message: first non-empty, non-panic, non-thread line
                        error_msg = _extract_error(block)
                    else:
                        file_ = ""
                        line_no = ""
                        error_msg = ""
                    rows.append([test_name, status, file_, line_no, error_msg])
        else:
            # Only failures
            for test_name, block in failure_blocks.items():
                block_text = "\n".join(block)
                pm = _PANIC_RE.search(block_text)
                file_ = pm.group(1) if pm else ""
                line_no = pm.group(2) if pm else ""
                error_msg = _extract_error(block)
                rows.append([test_name, "FAILED", file_, line_no, error_msg])

        # Summary
        sm = _SUMMARY_RE.search(clean)
        if sm:
            n_passed = sm.group(1)
            n_failed = sm.group(2)
            summary = f"{n_passed} passed, {n_failed} failed"
        else:
            n_failed = len(failure_blocks)
            summary = f"0 passed, {n_failed} failed"

        return ParseResult(
            tool="cargo-test",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )


def _extract_error(block_lines: list[str]) -> str:
    """Extract the first meaningful error message from a failure block."""
    for line in block_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("thread '"):
            continue
        if stripped.startswith("panicked at"):
            continue
        if stripped.startswith("note:"):
            continue
        if stripped.startswith("stack backtrace"):
            continue
        return stripped
    return ""
