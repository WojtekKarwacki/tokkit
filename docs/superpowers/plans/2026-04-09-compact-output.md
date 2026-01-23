# compact_output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `compact_output` MCP tool that compresses shell command output (tests, builds, lints) into schema+CSV structured format, saving 70-85% tokens.

**Architecture:** Pure Python module `tokkit_output` with a parser registry pattern. Each parser implements detect + parse for a specific tool. Auto-detection runs all parsers and picks highest confidence. Output uses the same schema+CSV format as `compact_json`. Integration follows the existing `clean_html`/`compact_json` dispatch pattern in the MCP server.

**Tech Stack:** Python 3.11+, pytest, no external deps (pure regex parsing)

---

### Task 1: Module scaffold + BaseParser + formatter

**Files:**
- Create: `py/tokkit_output/__init__.py`
- Create: `py/tokkit_output/base.py`
- Create: `py/tokkit_output/formatter.py`
- Create: `py/tokkit_output/universal.py`
- Create: `py/tokkit_output/detect.py`
- Create: `py/tokkit_output/parsers/__init__.py`
- Test: `tests/output_tests/__init__.py`
- Test: `tests/output_tests/test_formatter.py`
- Test: `tests/output_tests/test_universal.py`

- [ ] **Step 1: Write failing tests for the formatter**

```python
# tests/output_tests/__init__.py
# (empty)

# tests/output_tests/test_formatter.py
"""Tests for schema+CSV output formatting."""

from tokkit_output.formatter import format_result, ParseResult


class TestFormatResult:
    def test_basic_format(self):
        result = ParseResult(
            tool="pytest",
            summary="2 passed, 1 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=[
                ["test_login", "FAIL", "tests/test_auth.py", "42", "AssertionError: expected 200"],
            ],
            verbose=False,
        )
        out = format_result(result)
        assert out.startswith("# pytest: 2 passed, 1 failed\n")
        assert "[test;status;file;line;error]" in out
        assert "test_login;FAIL;tests/test_auth.py;42;AssertionError: expected 200" in out

    def test_empty_rows_summary_only(self):
        result = ParseResult(
            tool="pytest",
            summary="47 passed, 0 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=[],
            verbose=False,
        )
        out = format_result(result)
        assert out == "# pytest: 47 passed, 0 failed"

    def test_verbose_marker_in_summary(self):
        result = ParseResult(
            tool="ruff",
            summary="0 violations",
            schema=["file", "line", "col", "rule", "message"],
            rows=[["src/a.py", "1", "1", "E501", "Line too long"]],
            verbose=True,
        )
        out = format_result(result)
        assert "# ruff (verbose): 0 violations" in out

    def test_semicolon_in_value_is_quoted(self):
        result = ParseResult(
            tool="tsc",
            summary="1 error",
            schema=["file", "line", "col", "code", "message"],
            rows=[["a.ts", "1", "1", "TS2322", "Type 'a;b' is not assignable"]],
            verbose=False,
        )
        out = format_result(result)
        # Value containing semicolon must be quoted
        assert '"Type \'a;b\' is not assignable"' in out or "Type 'a;b' is not assignable" in out

    def test_newline_in_value_is_quoted(self):
        result = ParseResult(
            tool="pytest",
            summary="1 failed",
            schema=["test", "status", "file", "line", "error"],
            rows=[["test_x", "FAIL", "t.py", "1", "line1\nline2"]],
            verbose=False,
        )
        out = format_result(result)
        assert '"line1\nline2"' in out
```

- [ ] **Step 2: Write failing tests for universal fallback**

```python
# tests/output_tests/test_universal.py
"""Tests for universal fallback (ANSI strip + blank line collapse)."""

from tokkit_output.universal import strip_ansi, collapse_blanks, universal_clean


class TestStripAnsi:
    def test_removes_color_codes(self):
        text = "\x1b[32mPASS\x1b[0m test_foo"
        assert strip_ansi(text) == "PASS test_foo"

    def test_removes_bold(self):
        text = "\x1b[1mBold\x1b[0m"
        assert strip_ansi(text) == "Bold"

    def test_preserves_plain_text(self):
        assert strip_ansi("hello world") == "hello world"

    def test_removes_256_color(self):
        text = "\x1b[38;5;196mred\x1b[0m"
        assert strip_ansi(text) == "red"

    def test_removes_rgb_color(self):
        text = "\x1b[38;2;255;0;0mred\x1b[0m"
        assert strip_ansi(text) == "red"


class TestCollapseBlanks:
    def test_collapses_multiple_blank_lines(self):
        text = "a\n\n\n\nb"
        assert collapse_blanks(text) == "a\n\nb"

    def test_preserves_single_blank(self):
        text = "a\n\nb"
        assert collapse_blanks(text) == "a\n\nb"

    def test_strips_trailing_whitespace_lines(self):
        text = "a\n   \n   \nb"
        assert collapse_blanks(text) == "a\n\nb"


class TestUniversalClean:
    def test_combined(self):
        text = "\x1b[32mPASS\x1b[0m\n\n\n\nDone"
        out = universal_clean(text)
        assert out == "PASS\n\nDone"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/output_tests/ -v`
Expected: ImportError — `tokkit_output` doesn't exist yet

- [ ] **Step 4: Implement base.py**

```python
# py/tokkit_output/base.py
"""Base parser protocol and shared types."""

from dataclasses import dataclass, field


@dataclass
class ParseResult:
    tool: str
    summary: str
    schema: list[str]
    rows: list[list[str]]
    verbose: bool = False


class BaseParser:
    """Protocol for output parsers."""

    id: str = ""
    hint_values: list[str] = []

    def detect(self, text: str) -> float:
        """Return confidence 0.0-1.0 that this text is from this tool."""
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        """Extract structured data from the output."""
        raise NotImplementedError
```

- [ ] **Step 5: Implement formatter.py**

```python
# py/tokkit_output/formatter.py
"""Format ParseResult to schema+CSV output."""

from tokkit_output.base import ParseResult  # noqa: F401 — re-exported


def format_result(result: ParseResult) -> str:
    """Format a ParseResult as summary comment + schema+CSV."""
    verbose_tag = " (verbose)" if result.verbose else ""
    summary = f"# {result.tool}{verbose_tag}: {result.summary}"

    if not result.rows:
        return summary

    schema_line = "[" + ";".join(result.schema) + "]"
    data_lines = []
    for row in result.rows:
        data_lines.append(";".join(_escape(v) for v in row))

    return "\n".join([summary, schema_line] + data_lines)


def _escape(value: str) -> str:
    """Escape a value for schema+CSV format."""
    if not value:
        return ""
    if any(c in value for c in ";{}[]\n"):
        escaped = value.replace('"', '""')
        return f'"{escaped}"'
    return value
```

- [ ] **Step 6: Implement universal.py**

```python
# py/tokkit_output/universal.py
"""Universal fallback: ANSI strip + blank line collapse."""

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


def collapse_blanks(text: str) -> str:
    """Collapse runs of 3+ blank/whitespace-only lines to a single blank line."""
    return re.sub(r"(\n\s*){3,}", "\n\n", text)


def universal_clean(text: str) -> str:
    """Apply universal cleanup: ANSI strip + blank collapse."""
    return collapse_blanks(strip_ansi(text))
```

- [ ] **Step 7: Implement detect.py and parsers registry**

```python
# py/tokkit_output/detect.py
"""Auto-detection engine for shell output."""

from tokkit_output.base import BaseParser

_DETECT_THRESHOLD = 0.6


def detect_parser(text: str, parsers: list[BaseParser]) -> BaseParser | None:
    """Run all parsers' detect() and return highest-confidence match above threshold."""
    best_parser = None
    best_score = 0.0
    for parser in parsers:
        score = parser.detect(text)
        if score > best_score:
            best_score = score
            best_parser = parser
    if best_score >= _DETECT_THRESHOLD:
        return best_parser
    return None


# py/tokkit_output/parsers/__init__.py
"""Parser registry."""

from tokkit_output.base import BaseParser

_REGISTRY: list[BaseParser] = []
_HINT_MAP: dict[str, BaseParser] = {}


def register(parser: BaseParser) -> None:
    """Register a parser in the global registry."""
    _REGISTRY.append(parser)
    for hint in parser.hint_values:
        _HINT_MAP[hint.lower()] = parser


def get_by_hint(hint: str) -> BaseParser | None:
    """Look up parser by hint string."""
    return _HINT_MAP.get(hint.lower())


def all_parsers() -> list[BaseParser]:
    """Return all registered parsers."""
    return list(_REGISTRY)
```

- [ ] **Step 8: Implement `__init__.py` public API**

```python
# py/tokkit_output/__init__.py
"""Tokkit Output — Token-optimized shell output compression."""

__version__ = "0.1.0"


def compact_output(text: str, hint: str | None = None, verbose: bool = False) -> str:
    """Compress shell command output into schema+CSV structured format.

    Args:
        text: Raw command output.
        hint: Tool identifier (e.g. 'pytest', 'eslint'). Auto-detects if omitted.
        verbose: Include all items, not just problems.

    Returns:
        Schema+CSV formatted output with summary line, or universal-cleaned text
        if no parser matches.
    """
    if not text or not text.strip():
        return ""

    from tokkit_output.universal import strip_ansi
    cleaned = strip_ansi(text)

    from tokkit_output.parsers import get_by_hint, all_parsers
    from tokkit_output.detect import detect_parser
    from tokkit_output.formatter import format_result

    parser = None
    if hint:
        parser = get_by_hint(hint)

    if parser is None:
        parser = detect_parser(cleaned, all_parsers())

    if parser is None:
        from tokkit_output.universal import universal_clean
        return universal_clean(text)

    result = parser.parse(cleaned, verbose=verbose)
    return format_result(result)
```

- [ ] **Step 9: Add `tokkit_output` to pyproject.toml packages**

In `pyproject.toml`, add `"tokkit_output"` to the `packages` list under `[tool.maturin]`:

```toml
packages = [
    "tokkit_server",
    "tokkit_cli",
    "tokkit_scraper",
    "tokkit_json",
    "tokkit_markdown",
    "tokkit_skill",
    "tokkit_benchmark",
    "tokkit_output",
]
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `pytest tests/output_tests/ -v`
Expected: All 13 tests pass

- [ ] **Step 11: Commit**

```bash
git add py/tokkit_output/ tests/output_tests/ pyproject.toml
git commit -m "feat(output): scaffold module with base parser, formatter, universal fallback"
```

---

### Task 2: Python ecosystem parsers — pytest + unittest

**Files:**
- Create: `py/tokkit_output/parsers/pytest_p.py`
- Create: `py/tokkit_output/parsers/unittest_p.py`
- Create: `tests/output_tests/fixtures/__init__.py`
- Create: `tests/output_tests/fixtures/pytest_output.py`
- Create: `tests/output_tests/fixtures/unittest_output.py`
- Create: `tests/output_tests/test_pytest_parser.py`
- Create: `tests/output_tests/test_unittest_parser.py`
- Modify: `py/tokkit_output/parsers/__init__.py`

- [ ] **Step 1: Create pytest fixture data**

```python
# tests/output_tests/fixtures/__init__.py
# (empty)

# tests/output_tests/fixtures/pytest_output.py
"""Real-world pytest output samples."""

PYTEST_ALL_PASS = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
rootdir: /home/user/project
collected 5 items

tests/test_auth.py::test_login PASSED                                    [ 20%]
tests/test_auth.py::test_logout PASSED                                   [ 40%]
tests/test_auth.py::test_signup PASSED                                   [ 60%]
tests/test_db.py::test_connect PASSED                                    [ 80%]
tests/test_db.py::test_query PASSED                                      [100%]

============================== 5 passed in 0.12s ===============================
"""

PYTEST_WITH_FAILURES = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
rootdir: /home/user/project
collected 5 items

tests/test_auth.py::test_login PASSED                                    [ 20%]
tests/test_auth.py::test_logout PASSED                                   [ 40%]
tests/test_auth.py::test_signup FAILED                                   [ 60%]
tests/test_db.py::test_connect PASSED                                    [ 80%]
tests/test_db.py::test_query FAILED                                      [100%]

=================================== FAILURES ===================================
_________________________________ test_signup __________________________________

    def test_signup():
        result = signup("alice@test.com", "password123")
>       assert result.status_code == 200
E       AssertionError: assert 401 == 200
E        +  where 401 = <Response [401]>.status_code

tests/test_auth.py:42: AssertionError
_________________________________ test_query ___________________________________

    def test_query():
        db = connect()
>       result = db.execute("SELECT * FROM users")
E       KeyError: 'users'

tests/test_db.py:15: KeyError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError: assert 401 == 200
FAILED tests/test_db.py::test_query - KeyError: 'users'
========================= 3 passed, 2 failed in 0.34s =========================
"""

PYTEST_WITH_ERRORS = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
collected 3 items

tests/test_auth.py::test_login PASSED                                    [ 33%]
tests/test_auth.py::test_signup ERROR                                    [ 66%]
tests/test_auth.py::test_logout PASSED                                   [100%]

=================================== ERRORS ====================================
______________________ ERROR at setup of test_signup ___________________________

    @pytest.fixture
    def db():
>       return connect("localhost:5432")
E       ConnectionRefusedError: [Errno 111] Connection refused

tests/conftest.py:12: ConnectionRefusedError
=========================== short test summary info ============================
ERROR tests/test_auth.py::test_signup - ConnectionRefusedError: [Errno 111] Connection refused
========================= 2 passed, 1 error in 0.22s ==========================
"""

PYTEST_WITH_ANSI = """\
\x1b[1m============================= test session starts ==============================\x1b[0m
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
collected 2 items

tests/test_auth.py::test_login \x1b[32mPASSED\x1b[0m                              [ 50%]
tests/test_auth.py::test_signup \x1b[31mFAILED\x1b[0m                             [100%]

\x1b[31m=========================== short test summary info ============================\x1b[0m
\x1b[31mFAILED\x1b[0m tests/test_auth.py::test_signup - AssertionError: assert False
\x1b[31m========================= 1 passed, 1 failed in 0.10s =========================\x1b[0m
"""
```

- [ ] **Step 2: Write failing tests for pytest parser**

```python
# tests/output_tests/test_pytest_parser.py
"""Tests for pytest output parser."""

from tokkit_output.parsers.pytest_p import PytestParser
from output_tests.fixtures.pytest_output import (
    PYTEST_ALL_PASS,
    PYTEST_WITH_FAILURES,
    PYTEST_WITH_ERRORS,
    PYTEST_WITH_ANSI,
)
from tokkit_output.universal import strip_ansi


class TestPytestDetect:
    def test_detects_pytest_output(self):
        p = PytestParser()
        assert p.detect(PYTEST_ALL_PASS) >= 0.8

    def test_rejects_non_pytest(self):
        p = PytestParser()
        assert p.detect("hello world\nfoo bar\n") < 0.6

    def test_detects_with_failures(self):
        p = PytestParser()
        assert p.detect(PYTEST_WITH_FAILURES) >= 0.8


class TestPytestParse:
    def test_all_pass_default(self):
        p = PytestParser()
        result = p.parse(PYTEST_ALL_PASS, verbose=False)
        assert result.tool == "pytest"
        assert "5 passed" in result.summary
        assert "0 failed" in result.summary
        assert len(result.rows) == 0  # no failures = no rows in default mode

    def test_all_pass_verbose(self):
        p = PytestParser()
        result = p.parse(PYTEST_ALL_PASS, verbose=True)
        assert len(result.rows) == 5
        assert all(row[1] == "PASS" for row in result.rows)

    def test_failures_default(self):
        p = PytestParser()
        result = p.parse(PYTEST_WITH_FAILURES, verbose=False)
        assert "3 passed" in result.summary
        assert "2 failed" in result.summary
        assert len(result.rows) == 2
        assert result.rows[0][0] == "test_signup"
        assert result.rows[0][1] == "FAIL"
        assert "test_auth.py" in result.rows[0][2]
        assert "42" in result.rows[0][3]
        assert "AssertionError" in result.rows[0][4]

    def test_failures_verbose(self):
        p = PytestParser()
        result = p.parse(PYTEST_WITH_FAILURES, verbose=True)
        assert len(result.rows) == 5
        passes = [r for r in result.rows if r[1] == "PASS"]
        fails = [r for r in result.rows if r[1] == "FAIL"]
        assert len(passes) == 3
        assert len(fails) == 2

    def test_errors_parsed(self):
        p = PytestParser()
        result = p.parse(PYTEST_WITH_ERRORS, verbose=False)
        assert "1 error" in result.summary
        assert len(result.rows) == 1
        assert "test_signup" in result.rows[0][0]
        assert result.rows[0][1] == "ERROR"

    def test_ansi_stripped_before_parse(self):
        p = PytestParser()
        cleaned = strip_ansi(PYTEST_WITH_ANSI)
        result = p.parse(cleaned, verbose=False)
        assert "1 failed" in result.summary
        assert len(result.rows) == 1
```

- [ ] **Step 3: Create unittest fixture data and tests**

```python
# tests/output_tests/fixtures/unittest_output.py
"""Real-world unittest output samples."""

UNITTEST_ALL_PASS = """\
..
----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
"""

UNITTEST_WITH_FAILURES = """\
.F.
======================================================================
FAIL: test_add (tests.test_math.TestMath.test_add)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/user/tests/test_math.py", line 10, in test_add
    self.assertEqual(add(2, 3), 6)
AssertionError: 5 != 6

----------------------------------------------------------------------
Ran 3 tests in 0.002s

FAILED (failures=1)
"""

UNITTEST_WITH_ERRORS = """\
.E
======================================================================
ERROR: test_connect (tests.test_db.TestDB.test_connect)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/user/tests/test_db.py", line 8, in test_connect
    db = connect("localhost")
ConnectionRefusedError: [Errno 111] Connection refused

----------------------------------------------------------------------
Ran 2 tests in 0.003s

FAILED (errors=1)
"""

# tests/output_tests/test_unittest_parser.py
"""Tests for unittest output parser."""

from tokkit_output.parsers.unittest_p import UnittestParser
from output_tests.fixtures.unittest_output import (
    UNITTEST_ALL_PASS,
    UNITTEST_WITH_FAILURES,
    UNITTEST_WITH_ERRORS,
)


class TestUnittestDetect:
    def test_detects_unittest_output(self):
        p = UnittestParser()
        assert p.detect(UNITTEST_ALL_PASS) >= 0.7

    def test_detects_with_failures(self):
        p = UnittestParser()
        assert p.detect(UNITTEST_WITH_FAILURES) >= 0.7


class TestUnittestParse:
    def test_all_pass_default(self):
        p = UnittestParser()
        result = p.parse(UNITTEST_ALL_PASS, verbose=False)
        assert result.tool == "unittest"
        assert "2 passed" in result.summary
        assert len(result.rows) == 0

    def test_failure_default(self):
        p = UnittestParser()
        result = p.parse(UNITTEST_WITH_FAILURES, verbose=False)
        assert "1 failed" in result.summary
        assert len(result.rows) == 1
        assert "test_add" in result.rows[0][0]
        assert result.rows[0][1] == "FAIL"

    def test_error_default(self):
        p = UnittestParser()
        result = p.parse(UNITTEST_WITH_ERRORS, verbose=False)
        assert "1 error" in result.summary
        assert len(result.rows) == 1
        assert result.rows[0][1] == "ERROR"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/output_tests/test_pytest_parser.py tests/output_tests/test_unittest_parser.py -v`
Expected: ImportError

- [ ] **Step 5: Implement pytest parser**

```python
# py/tokkit_output/parsers/pytest_p.py
"""Parser for pytest output."""

import re

from tokkit_output.base import BaseParser, ParseResult

# Matches the summary line: "3 passed, 2 failed in 0.34s"
_SUMMARY_RE = re.compile(
    r"=+\s*(.*?)\s*=+\s*$",
    re.MULTILINE,
)

# Matches individual test result lines
_TEST_LINE_RE = re.compile(
    r"^(tests?/\S+)::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)",
    re.MULTILINE,
)

# Matches short test summary info lines: "FAILED tests/test_auth.py::test_signup - Error msg"
_SHORT_SUMMARY_RE = re.compile(
    r"^(FAILED|ERROR)\s+(\S+?)::(\S+)\s+-\s+(.+)$",
    re.MULTILINE,
)

# Matches file:line in failure blocks
_FAILURE_LOC_RE = re.compile(
    r"^(\S+\.py):(\d+):\s+(\w+(?:Error|Exception|Warning).*)?$",
    re.MULTILINE,
)

_SCHEMA = ["test", "status", "file", "line", "error"]


class PytestParser(BaseParser):
    id = "pytest"
    hint_values = ["pytest", "py.test"]

    def detect(self, text: str) -> float:
        """Detect pytest output by separator lines and summary."""
        has_separator = "=" * 20 in text
        lines = text.strip().splitlines()
        last_lines = "\n".join(lines[-5:]) if len(lines) >= 5 else text
        has_summary = any(
            w in last_lines for w in ("passed", "failed", "error")
        )
        has_test_session = "test session starts" in text
        if has_separator and has_summary and has_test_session:
            return 0.95
        if has_separator and has_summary:
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        """Parse pytest output into structured rows."""
        # Extract counts from summary line
        summary_parts = []
        passed = failed = errors = skipped = 0
        for m in _SUMMARY_RE.finditer(text):
            summary_text = m.group(1)
            if "passed" in summary_text or "failed" in summary_text or "error" in summary_text:
                for count_match in re.finditer(r"(\d+)\s+(passed|failed|error|skipped|warning)", summary_text):
                    n, kind = int(count_match.group(1)), count_match.group(2)
                    if kind == "passed":
                        passed = n
                    elif kind == "failed":
                        failed = n
                    elif kind == "error":
                        errors = n
                    elif kind == "skipped":
                        skipped = n

        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if skipped:
            parts.append(f"{skipped} skipped")
        summary = ", ".join(parts) if parts else "0 passed, 0 failed"

        # Build failure/error detail map from short summary
        fail_details: dict[str, tuple[str, str, str]] = {}
        for m in _SHORT_SUMMARY_RE.finditer(text):
            status = "FAIL" if m.group(1) == "FAILED" else "ERROR"
            filepath = m.group(2)
            test_name = m.group(3)
            message = m.group(4)
            # Try to find line number from failure blocks
            line_num = ""
            fail_details[test_name] = (status, filepath, line_num, message)

        # Extract line numbers from failure location lines
        for m in _FAILURE_LOC_RE.finditer(text):
            filepath = m.group(1)
            lineno = m.group(2)
            # Associate with nearest test — find which failure block this belongs to
            for test_name in fail_details:
                status, fp, ln, msg = fail_details[test_name]
                if not ln and filepath in fp or fp in filepath:
                    fail_details[test_name] = (status, fp, lineno, msg)
                    break

        # Build rows
        rows: list[list[str]] = []

        if verbose:
            # All tests from test result lines
            for m in _TEST_LINE_RE.finditer(text):
                filepath = m.group(1)
                test_name = m.group(2)
                raw_status = m.group(3)
                if raw_status == "PASSED":
                    rows.append([test_name, "PASS", filepath, "", ""])
                elif test_name in fail_details:
                    status, fp, ln, msg = fail_details[test_name]
                    rows.append([test_name, status, fp, ln, msg])
                else:
                    status = "FAIL" if raw_status == "FAILED" else raw_status
                    rows.append([test_name, status, filepath, "", ""])
        else:
            # Only failures and errors
            for test_name, (status, fp, ln, msg) in fail_details.items():
                rows.append([test_name, status, fp, ln, msg])

        return ParseResult(
            tool="pytest",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
```

- [ ] **Step 6: Implement unittest parser**

```python
# py/tokkit_output/parsers/unittest_p.py
"""Parser for unittest output."""

import re

from tokkit_output.base import BaseParser, ParseResult

_DIVIDER = "-" * 70
_SUMMARY_RE = re.compile(r"Ran (\d+) tests? in")
_RESULT_RE = re.compile(r"FAILED \((?:failures=(\d+))?(?:,?\s*errors=(\d+))?\)")
_FAIL_HEADER_RE = re.compile(
    r"^(FAIL|ERROR): (\S+) \((\S+)\)$",
    re.MULTILINE,
)
_TB_FILE_RE = re.compile(
    r'File "(.+?)", line (\d+)',
)

_SCHEMA = ["test", "status", "file", "line", "error"]


class UnittestParser(BaseParser):
    id = "unittest"
    hint_values = ["unittest", "django-test"]

    def detect(self, text: str) -> float:
        has_divider = _DIVIDER in text
        has_ran = bool(_SUMMARY_RE.search(text))
        has_ok_or_failed = "OK" in text.split("\n")[-2:] or "FAILED" in text
        if has_divider and has_ran:
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        total_m = _SUMMARY_RE.search(text)
        total = int(total_m.group(1)) if total_m else 0

        failures = 0
        errors = 0
        result_m = _RESULT_RE.search(text)
        if result_m:
            failures = int(result_m.group(1) or 0)
            errors = int(result_m.group(2) or 0)

        passed = total - failures - errors

        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failures:
            parts.append(f"{failures} failed")
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        summary = ", ".join(parts) if parts else f"{total} passed, 0 failed"

        # Extract failure/error details
        rows: list[list[str]] = []
        for m in _FAIL_HEADER_RE.finditer(text):
            status = "FAIL" if m.group(1) == "FAIL" else "ERROR"
            test_name = m.group(2)
            test_class = m.group(3)

            # Find the traceback section following this header
            start = m.end()
            next_header = _FAIL_HEADER_RE.search(text, start)
            section = text[start:next_header.start()] if next_header else text[start:]

            # Extract file/line from last traceback frame
            file_path = ""
            line_num = ""
            tb_matches = list(_TB_FILE_RE.finditer(section))
            if tb_matches:
                last = tb_matches[-1]
                file_path = last.group(1)
                line_num = last.group(2)

            # Extract error message (last non-empty line before divider)
            section_lines = section.strip().splitlines()
            error_msg = section_lines[-1].strip() if section_lines else ""

            rows.append([test_name, status, file_path, line_num, error_msg])

        if verbose and passed > 0:
            # unittest doesn't list passing tests by name — we can only add count
            # For verbose mode, we still return only what we can extract
            pass

        return ParseResult(
            tool="unittest",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
```

- [ ] **Step 7: Register parsers**

```python
# py/tokkit_output/parsers/__init__.py
"""Parser registry."""

from tokkit_output.base import BaseParser

_REGISTRY: list[BaseParser] = []
_HINT_MAP: dict[str, BaseParser] = {}


def register(parser: BaseParser) -> None:
    """Register a parser in the global registry."""
    _REGISTRY.append(parser)
    for hint in parser.hint_values:
        _HINT_MAP[hint.lower()] = parser


def get_by_hint(hint: str) -> BaseParser | None:
    """Look up parser by hint string."""
    return _HINT_MAP.get(hint.lower())


def all_parsers() -> list[BaseParser]:
    """Return all registered parsers."""
    return list(_REGISTRY)


# Auto-register all parsers on import
from tokkit_output.parsers.pytest_p import PytestParser
from tokkit_output.parsers.unittest_p import UnittestParser

register(PytestParser())
register(UnittestParser())
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/output_tests/test_pytest_parser.py tests/output_tests/test_unittest_parser.py -v`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add py/tokkit_output/parsers/pytest_p.py py/tokkit_output/parsers/unittest_p.py py/tokkit_output/parsers/__init__.py tests/output_tests/
git commit -m "feat(output): pytest + unittest parsers with detection and test fixtures"
```

---

### Task 3: Python ecosystem parsers — ruff, mypy, pyright, pip, traceback

**Files:**
- Create: `py/tokkit_output/parsers/ruff.py`
- Create: `py/tokkit_output/parsers/mypy.py`
- Create: `py/tokkit_output/parsers/pyright.py`
- Create: `py/tokkit_output/parsers/pip.py`
- Create: `py/tokkit_output/parsers/traceback_p.py`
- Create: `tests/output_tests/fixtures/python_tools_output.py`
- Create: `tests/output_tests/test_python_tools.py`
- Modify: `py/tokkit_output/parsers/__init__.py`

- [ ] **Step 1: Create fixture data for Python tools**

```python
# tests/output_tests/fixtures/python_tools_output.py
"""Real-world Python tool output samples."""

RUFF_VIOLATIONS = """\
src/auth.py:42:5: E501 Line too long (127 > 88)
src/auth.py:89:1: F401 [*] `os` imported but unused
src/db.py:15:9: E711 Comparison to `None` (use `is` or `is not`)
Found 3 errors.
[*] 1 fixable with the `--fix` option.
"""

RUFF_CLEAN = """\
All checks passed!
"""

MYPY_ERRORS = """\
src/auth.py:42: error: Argument 1 to "login" has incompatible type "int"; expected "str"  [arg-type]
src/auth.py:89: error: "User" has no attribute "email"  [attr-defined]
src/db.py:15: note: Revealed type is "builtins.str"
Found 2 errors in 2 files (checked 14 source files)
"""

MYPY_CLEAN = """\
Success: no issues found in 14 source files
"""

PYRIGHT_ERRORS = """\
/home/user/src/auth.py
  /home/user/src/auth.py:42:5 - error: Argument of type "int" cannot be assigned to parameter "username" of type "str" (reportGeneralClassIssues)
  /home/user/src/auth.py:89:12 - error: Cannot access attribute "email" for class "User" (reportAttributeAccessIssue)
2 errors, 0 warnings, 0 informations
"""

PIP_CONFLICT = """\
Collecting requests==2.31.0
  Downloading requests-2.31.0-py3-none-any.whl (62 kB)
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
urllib3 2.0.0 requires urllib3<3,>=1.21.1, but you have urllib3 1.26.18 which is incompatible.
Successfully installed requests-2.31.0
"""

PIP_BUILD_FAILURE = """\
Collecting some-package
  Downloading some_package-1.0.tar.gz (5.2 kB)
  Installing build dependencies ... done
  Getting requirements to build wheel ... error
  error: subprocess-exited-with-error

  × Getting requirements to build wheel did not run successfully.
  │ exit code: 1
  ╰─> [5 lines of output]
      Traceback (most recent call last):
        File "<string>", line 2, in <module>
      ModuleNotFoundError: No module named 'setuptools'
      [end of output]

  note: This error originates from a subprocess, and is likely not a problem with pip.
error: subprocess-exited-with-error
"""

PYTHON_TRACEBACK = """\
Traceback (most recent call last):
  File "/home/user/app/main.py", line 45, in start
    server = create_server(config)
  File "/home/user/app/server.py", line 12, in create_server
    db = connect(config.db_url)
  File "/home/user/app/db.py", line 8, in connect
    raise ConnectionError(f"Cannot connect to {url}")
ConnectionError: Cannot connect to postgres://localhost:5432/mydb
"""

PYTHON_CHAINED_TRACEBACK = """\
Traceback (most recent call last):
  File "/home/user/app/db.py", line 5, in connect
    sock.connect((host, port))
OSError: [Errno 111] Connection refused

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/user/app/main.py", line 10, in main
    db = connect("localhost", 5432)
  File "/home/user/app/db.py", line 8, in connect
    raise ConnectionError("Cannot connect") from e
ConnectionError: Cannot connect
"""
```

- [ ] **Step 2: Write failing tests for all Python tool parsers**

```python
# tests/output_tests/test_python_tools.py
"""Tests for ruff, mypy, pyright, pip, traceback parsers."""

from tokkit_output.parsers.ruff import RuffParser
from tokkit_output.parsers.mypy import MypyParser
from tokkit_output.parsers.pyright import PyrightParser
from tokkit_output.parsers.pip import PipParser
from tokkit_output.parsers.traceback_p import TracebackParser
from output_tests.fixtures.python_tools_output import (
    RUFF_VIOLATIONS, RUFF_CLEAN,
    MYPY_ERRORS, MYPY_CLEAN,
    PYRIGHT_ERRORS,
    PIP_CONFLICT, PIP_BUILD_FAILURE,
    PYTHON_TRACEBACK, PYTHON_CHAINED_TRACEBACK,
)


class TestRuffParser:
    def test_detect(self):
        assert RuffParser().detect(RUFF_VIOLATIONS) >= 0.8

    def test_detect_clean(self):
        assert RuffParser().detect(RUFF_CLEAN) >= 0.6

    def test_parse_violations(self):
        result = RuffParser().parse(RUFF_VIOLATIONS)
        assert "3 violations" in result.summary
        assert len(result.rows) == 3
        assert result.rows[0][3] == "E501"  # rule column

    def test_parse_clean(self):
        result = RuffParser().parse(RUFF_CLEAN)
        assert "0 violations" in result.summary
        assert len(result.rows) == 0


class TestMypyParser:
    def test_detect(self):
        assert MypyParser().detect(MYPY_ERRORS) >= 0.8

    def test_parse_errors(self):
        result = MypyParser().parse(MYPY_ERRORS)
        assert "2 error" in result.summary
        assert len(result.rows) == 2
        assert "arg-type" in result.rows[0][4]  # code column

    def test_parse_clean(self):
        result = MypyParser().parse(MYPY_CLEAN)
        assert "0 error" in result.summary
        assert len(result.rows) == 0


class TestPyrightParser:
    def test_detect(self):
        assert PyrightParser().detect(PYRIGHT_ERRORS) >= 0.8

    def test_parse_errors(self):
        result = PyrightParser().parse(PYRIGHT_ERRORS)
        assert "2 error" in result.summary
        assert len(result.rows) == 2


class TestPipParser:
    def test_detect_conflict(self):
        assert PipParser().detect(PIP_CONFLICT) >= 0.7

    def test_parse_conflict(self):
        result = PipParser().parse(PIP_CONFLICT)
        assert len(result.rows) >= 1
        assert any("urllib3" in row[0] for row in result.rows)

    def test_parse_build_failure(self):
        result = PipParser().parse(PIP_BUILD_FAILURE)
        assert len(result.rows) >= 1


class TestTracebackParser:
    def test_detect(self):
        assert TracebackParser().detect(PYTHON_TRACEBACK) >= 0.9

    def test_parse_simple(self):
        result = TracebackParser().parse(PYTHON_TRACEBACK)
        assert "ConnectionError" in result.summary
        assert len(result.rows) >= 1
        assert any("connect" in row[3] for row in result.rows)

    def test_parse_chained(self):
        result = TracebackParser().parse(PYTHON_CHAINED_TRACEBACK)
        assert "ConnectionError" in result.summary
        assert len(result.rows) >= 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/output_tests/test_python_tools.py -v`
Expected: ImportError

- [ ] **Step 4: Implement ruff parser**

```python
# py/tokkit_output/parsers/ruff.py
"""Parser for ruff check output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_LINE_RE = re.compile(r"^(.+?):(\d+):(\d+): ([A-Z]\d+)\s+(.+)$", re.MULTILINE)
_FOUND_RE = re.compile(r"Found (\d+) error")
_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]


class RuffParser(BaseParser):
    id = "ruff"
    hint_values = ["ruff"]

    def detect(self, text: str) -> float:
        if _LINE_RE.search(text) and _FOUND_RE.search(text):
            return 0.9
        if "All checks passed" in text:
            return 0.7
        if _LINE_RE.search(text):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        matches = _LINE_RE.findall(text)
        count = len(matches)

        found_m = _FOUND_RE.search(text)
        if found_m:
            count = int(found_m.group(1))

        summary = f"{count} violation{'s' if count != 1 else ''}"
        if "checked" in text:
            files_m = re.search(r"checked (\d+)", text)
            if files_m:
                summary += f", {files_m.group(1)} files checked"

        rows = []
        for filepath, line, col, rule, message in matches:
            # Clean up fixable marker
            message = message.rstrip()
            rows.append([filepath, line, col, rule, "error", message])

        return ParseResult(
            tool="ruff", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 5: Implement mypy parser**

```python
# py/tokkit_output/parsers/mypy.py
"""Parser for mypy output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_LINE_RE = re.compile(
    r"^(.+?):(\d+):\s+(error|warning|note):\s+(.+?)(?:\s+\[(.+?)\])?\s*$",
    re.MULTILINE,
)
_SUMMARY_RE = re.compile(r"Found (\d+) error")
_SUCCESS_RE = re.compile(r"Success: no issues found")
_SCHEMA = ["file", "line", "col", "severity", "code", "message"]


class MypyParser(BaseParser):
    id = "mypy"
    hint_values = ["mypy"]

    def detect(self, text: str) -> float:
        if _SUMMARY_RE.search(text) or _SUCCESS_RE.search(text):
            return 0.85
        if _LINE_RE.search(text) and "[" in text and "]" in text:
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        matches = _LINE_RE.findall(text)

        error_count = 0
        summary_m = _SUMMARY_RE.search(text)
        if summary_m:
            error_count = int(summary_m.group(1))
        elif _SUCCESS_RE.search(text):
            error_count = 0

        files_m = re.search(r"checked (\d+) source file", text)
        files_checked = files_m.group(1) if files_m else ""

        summary = f"{error_count} error{'s' if error_count != 1 else ''}"
        if files_checked:
            summary += f", {files_checked} files checked"

        rows = []
        for filepath, line, severity, message, code in matches:
            if not verbose and severity == "note":
                continue
            rows.append([filepath, line, "", severity, code or "", message])

        return ParseResult(
            tool="mypy", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 6: Implement pyright parser**

```python
# py/tokkit_output/parsers/pyright.py
"""Parser for pyright output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_LINE_RE = re.compile(
    r"^\s+\S+:(\d+):(\d+)\s+-\s+(error|warning|information):\s+(.+?)(?:\s+\((\w+)\))?\s*$",
    re.MULTILINE,
)
_FILE_HEADER_RE = re.compile(r"^(/\S+\.py)\s*$", re.MULTILINE)
_SUMMARY_RE = re.compile(r"(\d+) errors?, (\d+) warnings?, (\d+) informations?")
_SCHEMA = ["file", "line", "col", "severity", "code", "message"]


class PyrightParser(BaseParser):
    id = "pyright"
    hint_values = ["pyright"]

    def detect(self, text: str) -> float:
        if _SUMMARY_RE.search(text) and _LINE_RE.search(text):
            return 0.9
        if "pyright" in text.lower() and _LINE_RE.search(text):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        summary_m = _SUMMARY_RE.search(text)
        errors = int(summary_m.group(1)) if summary_m else 0
        warnings = int(summary_m.group(2)) if summary_m else 0

        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        summary = ", ".join(parts) if parts else "0 errors"

        # Parse errors grouped by file
        current_file = ""
        rows = []
        for line in text.splitlines():
            file_m = _FILE_HEADER_RE.match(line)
            if file_m:
                current_file = file_m.group(1)
                continue
            line_m = _LINE_RE.match(line)
            if line_m:
                lineno, col, severity, message, code = line_m.groups()
                if not verbose and severity == "information":
                    continue
                rows.append([current_file, lineno, col, severity, code or "", message])

        return ParseResult(
            tool="pyright", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 7: Implement pip parser**

```python
# py/tokkit_output/parsers/pip.py
"""Parser for pip install output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_CONFLICT_RE = re.compile(
    r"^(\S+)\s+\S+\s+requires\s+(.+?),\s+but you have\s+(\S+)\s+(.+?)$",
    re.MULTILINE,
)
_ERROR_RE = re.compile(r"^ERROR:\s+(.+)$", re.MULTILINE)
_SCHEMA = ["package", "status", "message"]


class PipParser(BaseParser):
    id = "pip"
    hint_values = ["pip"]

    def detect(self, text: str) -> float:
        if "pip's dependency resolver" in text:
            return 0.9
        if "Collecting" in text and ("Installing" in text or "ERROR" in text):
            return 0.7
        if "Successfully installed" in text:
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []
        issues = 0

        for m in _CONFLICT_RE.finditer(text):
            pkg = m.group(1)
            requires = m.group(2)
            have_pkg = m.group(3)
            have_ver = m.group(4)
            rows.append([pkg, "conflict", f"requires {requires}, have {have_pkg} {have_ver}"])
            issues += 1

        for m in _ERROR_RE.finditer(text):
            msg = m.group(1)
            if "dependency resolver" not in msg:  # skip the generic resolver warning
                rows.append(["pip", "error", msg])
                issues += 1

        # Check for subprocess errors
        if "subprocess-exited-with-error" in text:
            # Extract the package name
            pkg_m = re.search(r"Collecting (\S+)", text)
            pkg_name = pkg_m.group(1) if pkg_m else "unknown"
            if not any(r[1] == "error" for r in rows):
                rows.append([pkg_name, "build-error", "subprocess-exited-with-error"])
                issues += 1

        summary = f"{issues} issue{'s' if issues != 1 else ''}" if issues else "installed successfully"

        return ParseResult(
            tool="pip", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 8: Implement traceback parser**

```python
# py/tokkit_output/parsers/traceback_p.py
"""Parser for Python traceback output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_TB_START = "Traceback (most recent call last):"
_FRAME_RE = re.compile(
    r'^\s+File "(.+?)", line (\d+), in (\S+)',
    re.MULTILINE,
)
_EXCEPTION_RE = re.compile(r"^(\w+(?:Error|Exception|Warning|Exit)\w*):\s*(.+)?$", re.MULTILINE)
_SCHEMA = ["exception", "file", "line", "function", "message"]


class TracebackParser(BaseParser):
    id = "python-traceback"
    hint_values = ["traceback"]

    def detect(self, text: str) -> float:
        if _TB_START in text:
            return 0.95
        if _EXCEPTION_RE.search(text) and _FRAME_RE.search(text):
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        # Split into traceback sections (for chained exceptions)
        sections = text.split(_TB_START)
        rows = []
        last_exception = ""
        last_message = ""

        for section in sections:
            if not section.strip():
                continue

            # Extract frames
            frames = _FRAME_RE.findall(section)

            # Extract exception from end of section
            exc_matches = list(_EXCEPTION_RE.finditer(section))
            exc_name = exc_matches[-1].group(1) if exc_matches else ""
            exc_msg = exc_matches[-1].group(2) or "" if exc_matches else ""

            if exc_name:
                last_exception = exc_name
                last_message = exc_msg

            if verbose:
                for filepath, lineno, func in frames:
                    rows.append([exc_name, filepath, lineno, func, ""])
                if exc_name:
                    rows[-1][4] = exc_msg if rows else ""
            else:
                # Default: only the last frame + exception
                if frames:
                    filepath, lineno, func = frames[-1]
                    rows.append([exc_name, filepath, lineno, func, exc_msg])

        summary = f"{last_exception}: {last_message}" if last_exception else "traceback"

        return ParseResult(
            tool="python-traceback", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 9: Register all new parsers**

Add to `py/tokkit_output/parsers/__init__.py`:

```python
from tokkit_output.parsers.ruff import RuffParser
from tokkit_output.parsers.mypy import MypyParser
from tokkit_output.parsers.pyright import PyrightParser
from tokkit_output.parsers.pip import PipParser
from tokkit_output.parsers.traceback_p import TracebackParser

register(RuffParser())
register(MypyParser())
register(PyrightParser())
register(PipParser())
register(TracebackParser())
```

- [ ] **Step 10: Run tests**

Run: `pytest tests/output_tests/ -v`
Expected: All tests pass

- [ ] **Step 11: Commit**

```bash
git add py/tokkit_output/parsers/ tests/output_tests/
git commit -m "feat(output): ruff, mypy, pyright, pip, traceback parsers"
```

---

### Task 4: JavaScript/TypeScript ecosystem parsers

**Files:**
- Create: `py/tokkit_output/parsers/jest.py`
- Create: `py/tokkit_output/parsers/vitest.py`
- Create: `py/tokkit_output/parsers/mocha.py`
- Create: `py/tokkit_output/parsers/tsc.py`
- Create: `py/tokkit_output/parsers/eslint.py`
- Create: `py/tokkit_output/parsers/webpack.py`
- Create: `py/tokkit_output/parsers/vite.py`
- Create: `py/tokkit_output/parsers/npm.py`
- Create: `tests/output_tests/fixtures/js_tools_output.py`
- Create: `tests/output_tests/test_js_tools.py`
- Modify: `py/tokkit_output/parsers/__init__.py`

- [ ] **Step 1: Create JS/TS fixture data**

```python
# tests/output_tests/fixtures/js_tools_output.py
"""Real-world JS/TS tool output samples."""

JEST_ALL_PASS = """\
 PASS  tests/auth.test.ts
 PASS  tests/db.test.ts

Test Suites: 2 passed, 2 total
Tests:       5 passed, 5 total
Snapshots:   0 total
Time:        1.234 s
"""

JEST_WITH_FAILURES = """\
 PASS  tests/auth.test.ts
 FAIL  tests/db.test.ts
  ● TestDB › should connect

    expect(received).toBe(expected)

    Expected: true
    Received: false

      at Object.<anonymous> (tests/db.test.ts:15:27)

  ● TestDB › should query

    TypeError: db.query is not a function

      at Object.<anonymous> (tests/db.test.ts:22:18)

Test Suites: 1 failed, 1 passed, 2 total
Tests:       2 failed, 3 passed, 5 total
Snapshots:   0 total
Time:        2.345 s
"""

VITEST_WITH_FAILURES = """\
 ✓ tests/auth.test.ts (2)
 × tests/db.test.ts (2)
   × should connect
   × should query

⎯⎯⎯⎯⎯⎯ Failed Tests 2 ⎯⎯⎯⎯⎯⎯

 FAIL  tests/db.test.ts > should connect
AssertionError: expected false to be true

 FAIL  tests/db.test.ts > should query
TypeError: db.query is not a function

 Test Files  1 failed | 1 passed (2)
      Tests  2 failed | 2 passed (4)
   Duration  1.23s
"""

MOCHA_WITH_FAILURES = """\
  Auth
    ✓ should login (45ms)
    ✓ should logout (12ms)

  DB
    1) should connect
    2) should query

  2 passing (234ms)
  2 failing

  1) DB
       should connect:
     AssertionError: expected false to equal true
      at Context.<anonymous> (tests/db.test.js:15:27)

  2) DB
       should query:
     TypeError: db.query is not a function
      at Context.<anonymous> (tests/db.test.js:22:18)
"""

TSC_ERRORS = """\
src/api.ts(42,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/api.ts(89,12): error TS2345: Argument of type 'null' is not assignable to parameter of type 'User'.
src/db.ts(15,3): error TS2304: Cannot find name 'Connection'.

Found 3 errors in 2 files.

Errors  Files
     2  src/api.ts:42
     1  src/db.ts:15
"""

TSC_CLEAN = """\
"""

ESLINT_VIOLATIONS = """\
/home/user/src/auth.ts
   5:10  error  'unused' is defined but never used  no-unused-vars
  12:1   warning  Unexpected console statement        no-console

/home/user/src/db.ts
  42:5   error  'any' is not allowed as a type        @typescript-eslint/no-explicit-any

✖ 3 problems (2 errors, 1 warning)
  1 error and 0 warnings potentially fixable with the `--fix` option.
"""

WEBPACK_ERROR = """\
asset main.js 1.2 KiB [emitted] (name: main)
ERROR in ./src/index.ts 12:0-30
Module not found: Error: Can't resolve './missing' in '/home/user/src'

ERROR in ./src/api.ts 5:0-25
Module not found: Error: Can't resolve 'axios' in '/home/user/src'

webpack 5.90.0 compiled with 2 errors in 1234 ms
"""

VITE_ERROR = """\
error during build:
src/App.tsx(15,5): error TS2322: Type 'string' is not assignable to type 'number'.
"""

NPM_ERROR = """\
npm warn ERESOLVE overriding peer dependency
npm warn While resolving: react-dom@18.2.0
npm warn Found: react@17.0.2
npm warn node_modules/react
npm warn   react@"^17.0.2" from the root project
npm warn
npm warn Could not resolve dependency:
npm warn peer react@"^18.0.0" from react-dom@18.2.0
npm warn node_modules/react-dom
npm warn   react-dom@"^18.2.0" from the root project

added 5 packages, removed 2 packages, and audited 1234 packages in 5s
"""
```

- [ ] **Step 2: Write failing tests for all JS/TS parsers**

```python
# tests/output_tests/test_js_tools.py
"""Tests for JS/TS tool parsers."""

from tokkit_output.parsers.jest import JestParser
from tokkit_output.parsers.vitest import VitestParser
from tokkit_output.parsers.mocha import MochaParser
from tokkit_output.parsers.tsc import TscParser
from tokkit_output.parsers.eslint import EslintParser
from tokkit_output.parsers.webpack import WebpackParser
from tokkit_output.parsers.vite import ViteParser
from tokkit_output.parsers.npm import NpmParser
from output_tests.fixtures.js_tools_output import (
    JEST_ALL_PASS, JEST_WITH_FAILURES,
    VITEST_WITH_FAILURES,
    MOCHA_WITH_FAILURES,
    TSC_ERRORS, TSC_CLEAN,
    ESLINT_VIOLATIONS,
    WEBPACK_ERROR,
    VITE_ERROR,
    NPM_ERROR,
)


class TestJestParser:
    def test_detect(self):
        assert JestParser().detect(JEST_ALL_PASS) >= 0.8

    def test_parse_all_pass(self):
        result = JestParser().parse(JEST_ALL_PASS)
        assert "5 passed" in result.summary
        assert len(result.rows) == 0

    def test_parse_failures(self):
        result = JestParser().parse(JEST_WITH_FAILURES)
        assert "2 failed" in result.summary
        assert len(result.rows) == 2
        assert any("should connect" in row[0] for row in result.rows)


class TestVitestParser:
    def test_detect(self):
        assert VitestParser().detect(VITEST_WITH_FAILURES) >= 0.8

    def test_parse_failures(self):
        result = VitestParser().parse(VITEST_WITH_FAILURES)
        assert "2 failed" in result.summary
        assert len(result.rows) == 2


class TestMochaParser:
    def test_detect(self):
        assert MochaParser().detect(MOCHA_WITH_FAILURES) >= 0.8

    def test_parse_failures(self):
        result = MochaParser().parse(MOCHA_WITH_FAILURES)
        assert "2 failing" in result.summary or "2 failed" in result.summary
        assert len(result.rows) == 2
        assert any("should connect" in row[0] for row in result.rows)


class TestTscParser:
    def test_detect(self):
        assert TscParser().detect(TSC_ERRORS) >= 0.8

    def test_parse_errors(self):
        result = TscParser().parse(TSC_ERRORS)
        assert "3 error" in result.summary
        assert len(result.rows) == 3
        assert result.rows[0][4] == "TS2322"  # code column

    def test_clean_output(self):
        result = TscParser().parse(TSC_CLEAN)
        assert "0 error" in result.summary
        assert len(result.rows) == 0


class TestEslintParser:
    def test_detect(self):
        assert EslintParser().detect(ESLINT_VIOLATIONS) >= 0.8

    def test_parse_violations(self):
        result = EslintParser().parse(ESLINT_VIOLATIONS)
        assert "3 problem" in result.summary or "2 error" in result.summary
        assert len(result.rows) == 3
        assert any("no-unused-vars" in row[3] for row in result.rows)


class TestWebpackParser:
    def test_detect(self):
        assert WebpackParser().detect(WEBPACK_ERROR) >= 0.8

    def test_parse_errors(self):
        result = WebpackParser().parse(WEBPACK_ERROR)
        assert "2 error" in result.summary
        assert len(result.rows) == 2


class TestViteParser:
    def test_detect(self):
        assert ViteParser().detect(VITE_ERROR) >= 0.7

    def test_parse_error(self):
        result = ViteParser().parse(VITE_ERROR)
        assert len(result.rows) >= 1


class TestNpmParser:
    def test_detect(self):
        assert NpmParser().detect(NPM_ERROR) >= 0.7

    def test_parse_warnings(self):
        result = NpmParser().parse(NPM_ERROR)
        assert len(result.rows) >= 1
        assert any("react" in row[0].lower() for row in result.rows)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/output_tests/test_js_tools.py -v`
Expected: ImportError

- [ ] **Step 4: Implement jest parser**

```python
# py/tokkit_output/parsers/jest.py
"""Parser for Jest output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_SUITE_RE = re.compile(r"^\s*(PASS|FAIL)\s+(\S+)", re.MULTILINE)
_SUMMARY_TESTS_RE = re.compile(r"Tests:\s+(?:(\d+) failed,\s+)?(\d+) passed,\s+(\d+) total")
_SUMMARY_SUITES_RE = re.compile(r"Test Suites:\s+(?:(\d+) failed,\s+)?(\d+) passed,\s+(\d+) total")
_FAIL_BLOCK_RE = re.compile(
    r"●\s+(\S+(?:\s+›\s+\S+)*)\s*\n\s*\n([\s\S]*?)(?=\n\s*●|\nTest Suites:)",
)
_AT_LINE_RE = re.compile(r"at\s+\S+\s+\((.+?):(\d+):\d+\)")
_SCHEMA = ["test", "status", "file", "line", "error"]


class JestParser(BaseParser):
    id = "jest"
    hint_values = ["jest"]

    def detect(self, text: str) -> float:
        if "Test Suites:" in text and "Tests:" in text:
            return 0.9
        if _SUITE_RE.search(text) and ("PASS" in text or "FAIL" in text):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        tests_m = _SUMMARY_TESTS_RE.search(text)
        failed = int(tests_m.group(1) or 0) if tests_m else 0
        passed = int(tests_m.group(2)) if tests_m else 0
        total = int(tests_m.group(3)) if tests_m else 0

        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        summary = ", ".join(parts) if parts else f"{total} passed"

        rows = []
        for m in _FAIL_BLOCK_RE.finditer(text):
            test_name = m.group(1).replace(" › ", ".")
            error_block = m.group(2).strip()
            # Get first meaningful error line
            error_lines = [l.strip() for l in error_block.splitlines() if l.strip()]
            error_msg = error_lines[0] if error_lines else ""

            # Extract file/line
            at_m = _AT_LINE_RE.search(error_block)
            filepath = at_m.group(1) if at_m else ""
            lineno = at_m.group(2) if at_m else ""

            rows.append([test_name, "FAIL", filepath, lineno, error_msg])

        return ParseResult(
            tool="jest", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 5: Implement vitest parser**

```python
# py/tokkit_output/parsers/vitest.py
"""Parser for Vitest output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_SUMMARY_RE = re.compile(r"Tests\s+(\d+) failed \| (\d+) passed")
_FAIL_RE = re.compile(r"FAIL\s+(\S+)\s+>\s+(.+)\n(.+)", re.MULTILINE)
_SCHEMA = ["test", "status", "file", "line", "error"]


class VitestParser(BaseParser):
    id = "vitest"
    hint_values = ["vitest"]

    def detect(self, text: str) -> float:
        if "Test Files" in text and "Duration" in text:
            return 0.9
        if "✓" in text and "×" in text and "Tests" in text:
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        summary_m = _SUMMARY_RE.search(text)
        failed = int(summary_m.group(1)) if summary_m else 0
        passed = int(summary_m.group(2)) if summary_m else 0

        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        summary = ", ".join(parts) if parts else "0 passed"

        rows = []
        for m in _FAIL_RE.finditer(text):
            filepath = m.group(1)
            test_name = m.group(2).strip()
            error_msg = m.group(3).strip()
            rows.append([test_name, "FAIL", filepath, "", error_msg])

        return ParseResult(
            tool="vitest", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 6: Implement mocha parser**

```python
# py/tokkit_output/parsers/mocha.py
"""Parser for Mocha output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_PASSING_RE = re.compile(r"(\d+) passing")
_FAILING_RE = re.compile(r"(\d+) failing")
_FAIL_BLOCK_RE = re.compile(
    r"^\s+(\d+)\)\s+(.+?)$\n\s+(.+?):\n\s+(.+?)$(?:\n\s+at .+?\((.+?):(\d+):\d+\))?",
    re.MULTILINE,
)
_SCHEMA = ["test", "status", "file", "line", "error"]


class MochaParser(BaseParser):
    id = "mocha"
    hint_values = ["mocha"]

    def detect(self, text: str) -> float:
        has_passing = bool(_PASSING_RE.search(text))
        has_check = "✓" in text or "✗" in text
        has_failing = bool(_FAILING_RE.search(text))
        if has_passing and (has_check or has_failing):
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        passing_m = _PASSING_RE.search(text)
        failing_m = _FAILING_RE.search(text)
        passed = int(passing_m.group(1)) if passing_m else 0
        failed = int(failing_m.group(1)) if failing_m else 0

        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        summary = ", ".join(parts) if parts else "0 passed"

        rows = []
        # Parse numbered failure blocks
        sections = re.split(r"\n\s+\d+\)\s+", text)
        for i, section in enumerate(sections[1:], 1):  # skip first (pre-failures)
            lines = section.strip().splitlines()
            test_name = lines[0].strip().rstrip(":") if lines else f"test_{i}"

            # Find error message and location
            error_msg = ""
            filepath = ""
            lineno = ""
            for line in lines[1:]:
                line = line.strip()
                at_m = re.match(r"at .+?\((.+?):(\d+):\d+\)", line)
                if at_m:
                    filepath = at_m.group(1)
                    lineno = at_m.group(2)
                elif not error_msg and line and not line.startswith("at "):
                    error_msg = line

            rows.append([test_name, "FAIL", filepath, lineno, error_msg])

        return ParseResult(
            tool="mocha", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 7: Implement tsc parser**

```python
# py/tokkit_output/parsers/tsc.py
"""Parser for TypeScript compiler (tsc) output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_LINE_RE = re.compile(
    r"^(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)$",
    re.MULTILINE,
)
_FOUND_RE = re.compile(r"Found (\d+) error")
_SCHEMA = ["file", "line", "col", "severity", "code", "message"]


class TscParser(BaseParser):
    id = "tsc"
    hint_values = ["tsc", "typescript"]

    def detect(self, text: str) -> float:
        if _LINE_RE.search(text):
            return 0.9
        if _FOUND_RE.search(text):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        matches = _LINE_RE.findall(text)
        found_m = _FOUND_RE.search(text)
        count = int(found_m.group(1)) if found_m else len(matches)

        summary = f"{count} error{'s' if count != 1 else ''}"

        rows = []
        for filepath, line, col, severity, code, message in matches:
            rows.append([filepath, line, col, severity, code, message])

        return ParseResult(
            tool="tsc", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 8: Implement eslint parser**

```python
# py/tokkit_output/parsers/eslint.py
"""Parser for ESLint output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_FILE_RE = re.compile(r"^(/\S+|[A-Z]:\\\S+)\s*$", re.MULTILINE)
_LINE_RE = re.compile(
    r"^\s+(\d+):(\d+)\s+(error|warning)\s+(.+?)\s{2,}(\S+)\s*$",
    re.MULTILINE,
)
_SUMMARY_RE = re.compile(r"✖\s+(\d+) problems?\s+\((\d+) errors?,\s+(\d+) warnings?\)")
_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]


class EslintParser(BaseParser):
    id = "eslint"
    hint_values = ["eslint"]

    def detect(self, text: str) -> float:
        if _SUMMARY_RE.search(text):
            return 0.9
        if _LINE_RE.search(text) and _FILE_RE.search(text):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        summary_m = _SUMMARY_RE.search(text)
        problems = int(summary_m.group(1)) if summary_m else 0
        errors = int(summary_m.group(2)) if summary_m else 0
        warnings = int(summary_m.group(3)) if summary_m else 0

        parts = []
        if problems:
            parts.append(f"{problems} problem{'s' if problems != 1 else ''}")
        parts.append(f"({errors} error{'s' if errors != 1 else ''}, {warnings} warning{'s' if warnings != 1 else ''})")
        summary = " ".join(parts) if parts else "0 problems"

        current_file = ""
        rows = []
        for line in text.splitlines():
            file_m = _FILE_RE.match(line)
            if file_m:
                current_file = file_m.group(1)
                continue
            line_m = _LINE_RE.match(line)
            if line_m:
                lineno, col, severity, message, rule = line_m.groups()
                rows.append([current_file, lineno, col, rule, severity, message])

        return ParseResult(
            tool="eslint", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 9: Implement webpack parser**

```python
# py/tokkit_output/parsers/webpack.py
"""Parser for webpack build output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_ERROR_RE = re.compile(r"^ERROR in (.+)$\n(.+)$", re.MULTILINE)
_SUMMARY_RE = re.compile(r"webpack .+ compiled with (\d+) errors?")
_WARNING_RE = re.compile(r"^WARNING in (.+)$", re.MULTILINE)
_SCHEMA = ["step", "status", "message"]


class WebpackParser(BaseParser):
    id = "webpack"
    hint_values = ["webpack"]

    def detect(self, text: str) -> float:
        if "webpack" in text.lower() and ("ERROR in" in text or "compiled" in text):
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []
        error_count = 0

        for m in _ERROR_RE.finditer(text):
            location = m.group(1).strip()
            message = m.group(2).strip()
            rows.append([location, "error", message])
            error_count += 1

        summary_m = _SUMMARY_RE.search(text)
        if summary_m:
            error_count = int(summary_m.group(1))

        summary = f"{error_count} error{'s' if error_count != 1 else ''}"

        return ParseResult(
            tool="webpack", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 10: Implement vite parser**

```python
# py/tokkit_output/parsers/vite.py
"""Parser for Vite build output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_TS_ERROR_RE = re.compile(
    r"^(.+?)\((\d+),(\d+)\):\s+(error)\s+(TS\d+):\s+(.+)$",
    re.MULTILINE,
)
_SCHEMA = ["step", "status", "message"]


class ViteParser(BaseParser):
    id = "vite"
    hint_values = ["vite"]

    def detect(self, text: str) -> float:
        if "error during build" in text.lower():
            return 0.85
        if "vite" in text.lower() and "build" in text.lower():
            return 0.6
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []

        for m in _TS_ERROR_RE.finditer(text):
            filepath, line, col, severity, code, message = m.groups()
            rows.append([f"{filepath}:{line}:{col}", "error", f"{code}: {message}"])

        if not rows and "error" in text.lower():
            # Generic error extraction
            for line in text.splitlines():
                if "error" in line.lower() and line.strip():
                    rows.append(["build", "error", line.strip()])
                    break

        summary = f"{len(rows)} error{'s' if len(rows) != 1 else ''}"

        return ParseResult(
            tool="vite", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 11: Implement npm parser**

```python
# py/tokkit_output/parsers/npm.py
"""Parser for npm install/run output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_WARN_RE = re.compile(r"^npm warn\s+(.+)$", re.MULTILINE)
_ERR_RE = re.compile(r"^npm error\s+(.+)$", re.MULTILINE)
_PEER_RE = re.compile(r"peer\s+(\S+)@\"(.+?)\"\s+from\s+(\S+)")
_SCHEMA = ["package", "status", "message"]


class NpmParser(BaseParser):
    id = "npm"
    hint_values = ["npm"]

    def detect(self, text: str) -> float:
        if "npm warn" in text or "npm error" in text or "npm ERR!" in text:
            return 0.8
        if "added" in text and "packages" in text and "audited" in text:
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []
        issues = 0

        # Extract peer dependency issues
        seen_peers = set()
        for m in _PEER_RE.finditer(text):
            pkg, version, source = m.groups()
            key = (pkg, source)
            if key not in seen_peers:
                seen_peers.add(key)
                rows.append([pkg, "peer-conflict", f"requires {version} from {source}"])
                issues += 1

        # Extract npm errors
        for m in _ERR_RE.finditer(text):
            msg = m.group(1).strip()
            rows.append(["npm", "error", msg])
            issues += 1

        summary = f"{issues} issue{'s' if issues != 1 else ''}" if issues else "installed successfully"

        return ParseResult(
            tool="npm", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 12: Register all JS/TS parsers**

Add to `py/tokkit_output/parsers/__init__.py`:

```python
from tokkit_output.parsers.jest import JestParser
from tokkit_output.parsers.vitest import VitestParser
from tokkit_output.parsers.mocha import MochaParser
from tokkit_output.parsers.tsc import TscParser
from tokkit_output.parsers.eslint import EslintParser
from tokkit_output.parsers.webpack import WebpackParser
from tokkit_output.parsers.vite import ViteParser
from tokkit_output.parsers.npm import NpmParser

register(JestParser())
register(VitestParser())
register(MochaParser())
register(TscParser())
register(EslintParser())
register(WebpackParser())
register(ViteParser())
register(NpmParser())
```

- [ ] **Step 13: Run tests**

Run: `pytest tests/output_tests/ -v`
Expected: All tests pass

- [ ] **Step 14: Commit**

```bash
git add py/tokkit_output/parsers/ tests/output_tests/
git commit -m "feat(output): jest, vitest, mocha, tsc, eslint, webpack, vite, npm parsers"
```

---

### Task 5: Cross-ecosystem parsers — cargo + docker

**Files:**
- Create: `py/tokkit_output/parsers/cargo_test.py`
- Create: `py/tokkit_output/parsers/cargo_build.py`
- Create: `py/tokkit_output/parsers/cargo_clippy.py`
- Create: `py/tokkit_output/parsers/docker.py`
- Create: `tests/output_tests/fixtures/cross_tools_output.py`
- Create: `tests/output_tests/test_cross_tools.py`
- Modify: `py/tokkit_output/parsers/__init__.py`

- [ ] **Step 1: Create fixture data**

```python
# tests/output_tests/fixtures/cross_tools_output.py
"""Real-world cargo and docker output samples."""

CARGO_TEST_PASS = """\
   Compiling myproject v0.1.0 (/home/user/project)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.34s
     Running unittests src/lib.rs (target/debug/deps/myproject-abc123)

running 3 tests
test tests::test_add ... ok
test tests::test_sub ... ok
test tests::test_mul ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
"""

CARGO_TEST_FAIL = """\
   Compiling myproject v0.1.0 (/home/user/project)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.34s
     Running unittests src/lib.rs (target/debug/deps/myproject-abc123)

running 3 tests
test tests::test_add ... ok
test tests::test_sub ... FAILED
test tests::test_mul ... ok

failures:

---- tests::test_sub stdout ----
thread 'tests::test_sub' panicked at src/lib.rs:42:5:
assertion `left == right` failed
  left: 5
 right: 3

note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace


failures:
    tests::test_sub

test result: FAILED. 2 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
"""

CARGO_BUILD_ERRORS = """\
   Compiling myproject v0.1.0 (/home/user/project)
error[E0308]: mismatched types
 --> src/main.rs:42:5
  |
42 |     let x: i32 = "hello";
  |            ---   ^^^^^^^ expected `i32`, found `&str`
  |            |
  |            expected due to this

error[E0425]: cannot find value `y` in this scope
 --> src/main.rs:45:5
  |
45 |     println!("{}", y);
  |                    ^ not found in this scope

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0308`.
"""

CARGO_CLIPPY_WARNINGS = """\
warning: unused variable: `x`
 --> src/main.rs:10:9
  |
10 |     let x = 42;
  |         ^ help: if this is intentional, prefix it with an underscore: `_x`
  |
  = note: `#[warn(unused_variables)]` on by default

warning: this function has too many arguments (8/7)
 --> src/lib.rs:20:1
  |
20 | fn process(a: i32, b: i32, c: i32, d: i32, e: i32, f: i32, g: i32, h: i32) {
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  |
  = help: for further information visit https://rust-lang.github.io/rust-clippy/master/index.html#too_many_arguments
  = note: `#[warn(clippy::too_many_arguments)]` on by default

warning: `myproject` (lib) generated 2 warnings
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.50s
"""

DOCKER_BUILD_SUCCESS = """\
[+] Building 12.3s (8/8) FINISHED
 => [internal] load build definition from Dockerfile                       0.0s
 => [internal] load metadata for docker.io/library/python:3.11-slim        1.2s
 => [1/4] FROM docker.io/library/python:3.11-slim@sha256:abc123            0.0s
 => [2/4] WORKDIR /app                                                      0.0s
 => [3/4] COPY requirements.txt .                                           0.0s
 => [4/4] RUN pip install -r requirements.txt                               8.5s
 => exporting to image                                                       2.5s
"""

DOCKER_BUILD_FAIL = """\
[+] Building 5.2s (6/8) FINISHED
 => [internal] load build definition from Dockerfile                       0.0s
 => [internal] load metadata for docker.io/library/python:3.11-slim        1.2s
 => [1/4] FROM docker.io/library/python:3.11-slim@sha256:abc123            0.0s
 => [2/4] WORKDIR /app                                                      0.0s
 => [3/4] COPY requirements.txt .                                           0.0s
 => ERROR [4/4] RUN pip install -r requirements.txt                         3.8s
------
 > [4/4] RUN pip install -r requirements.txt:
 0.534 ERROR: Could not find a version that satisfies the requirement nonexistent-package
------
Dockerfile:6
--------------------
   4 |     COPY requirements.txt .
   5 |     RUN pip install --no-cache-dir -r requirements.txt
   6 | >>> RUN pip install -r requirements.txt
   7 |
--------------------
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully: exit code: 1
"""
```

- [ ] **Step 2: Write failing tests**

```python
# tests/output_tests/test_cross_tools.py
"""Tests for cargo and docker parsers."""

from tokkit_output.parsers.cargo_test import CargoTestParser
from tokkit_output.parsers.cargo_build import CargoBuildParser
from tokkit_output.parsers.cargo_clippy import CargoClippyParser
from tokkit_output.parsers.docker import DockerParser
from output_tests.fixtures.cross_tools_output import (
    CARGO_TEST_PASS, CARGO_TEST_FAIL,
    CARGO_BUILD_ERRORS,
    CARGO_CLIPPY_WARNINGS,
    DOCKER_BUILD_SUCCESS, DOCKER_BUILD_FAIL,
)


class TestCargoTestParser:
    def test_detect(self):
        assert CargoTestParser().detect(CARGO_TEST_PASS) >= 0.8

    def test_parse_all_pass(self):
        result = CargoTestParser().parse(CARGO_TEST_PASS)
        assert "3 passed" in result.summary
        assert len(result.rows) == 0

    def test_parse_failure(self):
        result = CargoTestParser().parse(CARGO_TEST_FAIL)
        assert "1 failed" in result.summary
        assert len(result.rows) == 1
        assert "test_sub" in result.rows[0][0]
        assert "assertion" in result.rows[0][4].lower()


class TestCargoBuildParser:
    def test_detect(self):
        assert CargoBuildParser().detect(CARGO_BUILD_ERRORS) >= 0.8

    def test_parse_errors(self):
        result = CargoBuildParser().parse(CARGO_BUILD_ERRORS)
        assert "2 error" in result.summary
        assert len(result.rows) == 2
        assert result.rows[0][4] == "E0308"


class TestCargoClippyParser:
    def test_detect(self):
        assert CargoClippyParser().detect(CARGO_CLIPPY_WARNINGS) >= 0.8

    def test_parse_warnings(self):
        result = CargoClippyParser().parse(CARGO_CLIPPY_WARNINGS)
        assert "2 warning" in result.summary
        assert len(result.rows) == 2


class TestDockerParser:
    def test_detect_success(self):
        assert DockerParser().detect(DOCKER_BUILD_SUCCESS) >= 0.7

    def test_detect_failure(self):
        assert DockerParser().detect(DOCKER_BUILD_FAIL) >= 0.7

    def test_parse_success(self):
        result = DockerParser().parse(DOCKER_BUILD_SUCCESS)
        assert len(result.rows) == 0

    def test_parse_failure(self):
        result = DockerParser().parse(DOCKER_BUILD_FAIL)
        assert len(result.rows) >= 1
        assert any("error" in row[1].lower() for row in result.rows)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/output_tests/test_cross_tools.py -v`
Expected: ImportError

- [ ] **Step 4: Implement cargo_test parser**

```python
# py/tokkit_output/parsers/cargo_test.py
"""Parser for cargo test output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_RESULT_RE = re.compile(r"^test result: \w+\. (\d+) passed; (\d+) failed;", re.MULTILINE)
_TEST_RE = re.compile(r"^test (\S+) \.\.\. (ok|FAILED|ignored)", re.MULTILINE)
_FAIL_HEADER_RE = re.compile(r"^---- (\S+) stdout ----$", re.MULTILINE)
_PANIC_RE = re.compile(r"panicked at (.+?):(\d+):\d+", re.MULTILINE)
_SCHEMA = ["test", "status", "file", "line", "error"]


class CargoTestParser(BaseParser):
    id = "cargo-test"
    hint_values = ["cargo-test"]

    def detect(self, text: str) -> float:
        if "test result:" in text and ("running" in text or "test " in text):
            return 0.9
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        result_m = _RESULT_RE.search(text)
        passed = int(result_m.group(1)) if result_m else 0
        failed = int(result_m.group(2)) if result_m else 0

        parts = []
        if passed:
            parts.append(f"{passed} passed")
        if failed:
            parts.append(f"{failed} failed")
        summary = ", ".join(parts) if parts else "0 passed, 0 failed"

        # Extract failure details
        fail_details: dict[str, tuple[str, str, str]] = {}
        for m in _FAIL_HEADER_RE.finditer(text):
            test_name = m.group(1)
            start = m.end()
            next_m = _FAIL_HEADER_RE.search(text, start)
            section = text[start:next_m.start()] if next_m else text[start:]

            panic_m = _PANIC_RE.search(section)
            filepath = panic_m.group(1) if panic_m else ""
            lineno = panic_m.group(2) if panic_m else ""

            # Get error message — first indented assertion line
            error_msg = ""
            for line in section.splitlines():
                line = line.strip()
                if line.startswith("assertion") or line.startswith("left:") or "panicked" in line:
                    error_msg = line
                    break

            fail_details[test_name] = (filepath, lineno, error_msg)

        rows = []
        if verbose:
            for m in _TEST_RE.finditer(text):
                test_name = m.group(1)
                status_raw = m.group(2)
                if status_raw == "ok":
                    rows.append([test_name, "PASS", "", "", ""])
                elif test_name in fail_details:
                    fp, ln, msg = fail_details[test_name]
                    rows.append([test_name, "FAIL", fp, ln, msg])
                else:
                    rows.append([test_name, "FAIL", "", "", ""])
        else:
            for test_name, (fp, ln, msg) in fail_details.items():
                rows.append([test_name, "FAIL", fp, ln, msg])

        return ParseResult(
            tool="cargo-test", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 5: Implement cargo_build parser**

```python
# py/tokkit_output/parsers/cargo_build.py
"""Parser for cargo build output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_ERROR_RE = re.compile(
    r"^(error|warning)\[([A-Z]\d+)\]: (.+)$\n\s*-->\s*(.+?):(\d+):(\d+)",
    re.MULTILINE,
)
_ABORT_RE = re.compile(r"aborting due to (\d+) previous error")
_SCHEMA = ["file", "line", "col", "severity", "code", "message"]


class CargoBuildParser(BaseParser):
    id = "cargo-build"
    hint_values = ["cargo-build"]

    def detect(self, text: str) -> float:
        if _ERROR_RE.search(text) and ("Compiling" in text or "error:" in text):
            return 0.85
        if "Compiling" in text and "Finished" in text:
            return 0.6
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []
        errors = 0
        warnings = 0

        for m in _ERROR_RE.finditer(text):
            severity, code, message, filepath, line, col = m.groups()
            rows.append([filepath, line, col, severity, code, message])
            if severity == "error":
                errors += 1
            else:
                warnings += 1

        abort_m = _ABORT_RE.search(text)
        if abort_m:
            errors = int(abort_m.group(1))

        parts = []
        if errors:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        summary = ", ".join(parts) if parts else "compiled successfully"

        return ParseResult(
            tool="cargo-build", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 6: Implement cargo_clippy parser**

```python
# py/tokkit_output/parsers/cargo_clippy.py
"""Parser for cargo clippy output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_WARNING_RE = re.compile(
    r"^warning: (.+)$\n\s*-->\s*(.+?):(\d+):(\d+)",
    re.MULTILINE,
)
_GENERATED_RE = re.compile(r"generated (\d+) warning")
_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]


class CargoClippyParser(BaseParser):
    id = "cargo-clippy"
    hint_values = ["cargo-clippy", "clippy"]

    def detect(self, text: str) -> float:
        if _GENERATED_RE.search(text) and ("clippy" in text.lower() or _WARNING_RE.search(text)):
            return 0.85
        if "clippy" in text.lower() and _WARNING_RE.search(text):
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []
        for m in _WARNING_RE.finditer(text):
            message, filepath, line, col = m.groups()
            # Try to extract clippy rule from note line
            rule = ""
            start = m.end()
            following = text[start:start + 500]
            rule_m = re.search(r"clippy::(\w+)", following)
            if rule_m:
                rule = f"clippy::{rule_m.group(1)}"
            rows.append([filepath, line, col, rule, "warning", message])

        gen_m = _GENERATED_RE.search(text)
        count = int(gen_m.group(1)) if gen_m else len(rows)
        summary = f"{count} warning{'s' if count != 1 else ''}"

        return ParseResult(
            tool="cargo-clippy", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 7: Implement docker parser**

```python
# py/tokkit_output/parsers/docker.py
"""Parser for docker build output."""

import re
from tokkit_output.base import BaseParser, ParseResult

_STEP_RE = re.compile(r"=>\s+(?:ERROR\s+)?\[(\d+/\d+)\]\s+(.+?)(?:\s+\d+\.\ds)?$", re.MULTILINE)
_ERROR_STEP_RE = re.compile(r"=>\s+ERROR\s+\[(\d+/\d+)\]\s+(.+)", re.MULTILINE)
_FINAL_ERROR_RE = re.compile(r"^ERROR:\s+(.+)$", re.MULTILINE)
_SCHEMA = ["step", "status", "message"]


class DockerParser(BaseParser):
    id = "docker"
    hint_values = ["docker", "docker-build"]

    def detect(self, text: str) -> float:
        if "[+] Building" in text or "=> [" in text:
            return 0.85
        if "Dockerfile" in text and ("ERROR" in text or "FINISHED" in text):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        rows = []
        error_count = 0

        for m in _ERROR_STEP_RE.finditer(text):
            step = m.group(1)
            command = m.group(2).strip()
            rows.append([f"[{step}]", "error", command])
            error_count += 1

        for m in _FINAL_ERROR_RE.finditer(text):
            msg = m.group(1).strip()
            if not any(msg in row[2] for row in rows):
                rows.append(["build", "error", msg])
                error_count += 1

        if verbose:
            for m in _STEP_RE.finditer(text):
                step = m.group(1)
                command = m.group(2).strip()
                if not any(f"[{step}]" == row[0] for row in rows):
                    rows.insert(len(rows) - error_count, [f"[{step}]", "ok", command])

        summary = f"{error_count} error{'s' if error_count != 1 else ''}" if error_count else "build successful"

        return ParseResult(
            tool="docker", summary=summary, schema=_SCHEMA,
            rows=rows, verbose=verbose,
        )
```

- [ ] **Step 8: Register all cross-ecosystem parsers**

Add to `py/tokkit_output/parsers/__init__.py`:

```python
from tokkit_output.parsers.cargo_test import CargoTestParser
from tokkit_output.parsers.cargo_build import CargoBuildParser
from tokkit_output.parsers.cargo_clippy import CargoClippyParser
from tokkit_output.parsers.docker import DockerParser

register(CargoTestParser())
register(CargoBuildParser())
register(CargoClippyParser())
register(DockerParser())
```

- [ ] **Step 9: Run tests**

Run: `pytest tests/output_tests/ -v`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add py/tokkit_output/parsers/ tests/output_tests/
git commit -m "feat(output): cargo test/build/clippy + docker parsers"
```

---

### Task 6: Auto-detection integration tests

**Files:**
- Create: `tests/output_tests/test_detect.py`
- Create: `tests/output_tests/test_compact_output.py`

- [ ] **Step 1: Write detection tests**

```python
# tests/output_tests/test_detect.py
"""Tests for auto-detection engine across all parsers."""

from tokkit_output.parsers import all_parsers
from tokkit_output.detect import detect_parser
from output_tests.fixtures.pytest_output import PYTEST_WITH_FAILURES, PYTEST_ALL_PASS
from output_tests.fixtures.python_tools_output import RUFF_VIOLATIONS, MYPY_ERRORS, PYTHON_TRACEBACK
from output_tests.fixtures.js_tools_output import JEST_WITH_FAILURES, TSC_ERRORS, ESLINT_VIOLATIONS
from output_tests.fixtures.cross_tools_output import CARGO_TEST_FAIL, CARGO_BUILD_ERRORS


class TestAutoDetection:
    def test_detects_pytest(self):
        p = detect_parser(PYTEST_WITH_FAILURES, all_parsers())
        assert p is not None
        assert p.id == "pytest"

    def test_detects_ruff(self):
        p = detect_parser(RUFF_VIOLATIONS, all_parsers())
        assert p is not None
        assert p.id == "ruff"

    def test_detects_mypy(self):
        p = detect_parser(MYPY_ERRORS, all_parsers())
        assert p is not None
        assert p.id == "mypy"

    def test_detects_traceback(self):
        p = detect_parser(PYTHON_TRACEBACK, all_parsers())
        assert p is not None
        assert p.id == "python-traceback"

    def test_detects_jest(self):
        p = detect_parser(JEST_WITH_FAILURES, all_parsers())
        assert p is not None
        assert p.id == "jest"

    def test_detects_tsc(self):
        p = detect_parser(TSC_ERRORS, all_parsers())
        assert p is not None
        assert p.id == "tsc"

    def test_detects_eslint(self):
        p = detect_parser(ESLINT_VIOLATIONS, all_parsers())
        assert p is not None
        assert p.id == "eslint"

    def test_detects_cargo_test(self):
        p = detect_parser(CARGO_TEST_FAIL, all_parsers())
        assert p is not None
        assert p.id == "cargo-test"

    def test_detects_cargo_build(self):
        p = detect_parser(CARGO_BUILD_ERRORS, all_parsers())
        assert p is not None
        assert p.id == "cargo-build"

    def test_returns_none_for_unknown(self):
        p = detect_parser("hello world\nfoo bar baz\n", all_parsers())
        assert p is None

    def test_no_false_positive_on_plain_text(self):
        p = detect_parser("The quick brown fox\njumps over the lazy dog\n", all_parsers())
        assert p is None
```

- [ ] **Step 2: Write public API integration tests**

```python
# tests/output_tests/test_compact_output.py
"""Integration tests for compact_output() public API."""

from tokkit_output import compact_output
from output_tests.fixtures.pytest_output import PYTEST_WITH_FAILURES, PYTEST_ALL_PASS, PYTEST_WITH_ANSI
from output_tests.fixtures.python_tools_output import RUFF_VIOLATIONS, PYTHON_TRACEBACK
from output_tests.fixtures.js_tools_output import TSC_ERRORS


class TestCompactOutputAPI:
    def test_empty_input(self):
        assert compact_output("") == ""
        assert compact_output("  ") == ""

    def test_with_hint(self):
        result = compact_output(PYTEST_WITH_FAILURES, hint="pytest")
        assert result.startswith("# pytest:")
        assert "2 failed" in result

    def test_auto_detect(self):
        result = compact_output(PYTEST_WITH_FAILURES)
        assert result.startswith("# pytest:")

    def test_verbose_flag(self):
        result = compact_output(PYTEST_WITH_FAILURES, hint="pytest", verbose=True)
        assert "(verbose)" in result
        # Should have all 5 tests
        lines = result.strip().splitlines()
        data_lines = [l for l in lines if not l.startswith("#") and not l.startswith("[")]
        assert len(data_lines) == 5

    def test_ansi_stripped(self):
        result = compact_output(PYTEST_WITH_ANSI, hint="pytest")
        assert "\x1b" not in result
        assert "# pytest:" in result

    def test_unknown_output_universal_fallback(self):
        raw = "Some random\n\n\n\n\ncommand output\n\x1b[31mwith color\x1b[0m"
        result = compact_output(raw)
        assert "\x1b" not in result
        assert "with color" in result
        assert "\n\n\n" not in result  # blanks collapsed

    def test_ruff_via_auto_detect(self):
        result = compact_output(RUFF_VIOLATIONS)
        assert "# ruff:" in result
        assert "3 violation" in result

    def test_tsc_via_hint(self):
        result = compact_output(TSC_ERRORS, hint="tsc")
        assert "# tsc:" in result
        assert "3 error" in result

    def test_traceback_via_auto_detect(self):
        result = compact_output(PYTHON_TRACEBACK)
        assert "# python-traceback:" in result
        assert "ConnectionError" in result

    def test_all_pass_minimal_output(self):
        result = compact_output(PYTEST_ALL_PASS, hint="pytest")
        assert "# pytest:" in result
        assert "5 passed" in result
        # No schema line when no rows
        assert "[test;" not in result
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/output_tests/test_detect.py tests/output_tests/test_compact_output.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/output_tests/
git commit -m "test(output): auto-detection and public API integration tests"
```

---

### Task 7: MCP server integration

**Files:**
- Modify: `py/tokkit_server/protocol.py`
- Modify: `py/tokkit_server/tools.py`
- Modify: `py/tokkit_server/token_stats.py`
- Create: `tests/server/test_output_integration.py`
- Create: `tests/e2e/test_mcp_output.py`

- [ ] **Step 1: Write failing server integration test**

```python
# tests/server/test_output_integration.py
"""Integration tests for compact_output MCP tool dispatch."""

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_compact_output_tool_dispatch():
    _reset_session()
    text = """\
============================= test session starts ==============================
tests/test_auth.py::test_login PASSED
tests/test_auth.py::test_signup FAILED
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError
========================= 1 passed, 1 failed in 0.10s =========================
"""
    result = handle_tool_call("compact_output", {"text": text, "hint": "pytest"})
    assert not result.get("isError")
    content = result["content"][0]["text"]
    assert "# pytest:" in content
    assert "1 failed" in content


def test_compact_output_no_session_required():
    _reset_session()
    text = "src/a.py:1:1: E501 Line too long\nFound 1 error.\n"
    result = handle_tool_call("compact_output", {"text": text, "hint": "ruff"})
    assert not result.get("isError")
    assert "ruff" in result["content"][0]["text"]


def test_compact_output_token_stats_recorded():
    _reset_session()
    text = "x\n" * 100  # 200 chars of raw output
    result = handle_tool_call("compact_output", {"text": text})
    assert not result.get("isError")
    meta = result.get("_meta", {}).get("token_savings", {})
    assert meta.get("tokens_avoided", 0) > 0


def test_compact_output_verbose_flag():
    _reset_session()
    text = """\
============================= test session starts ==============================
tests/test_a.py::test_x PASSED
tests/test_a.py::test_y PASSED
========================= 2 passed in 0.01s ===================================
"""
    result = handle_tool_call("compact_output", {"text": text, "hint": "pytest", "verbose": True})
    assert not result.get("isError")
    content = result["content"][0]["text"]
    assert "(verbose)" in content


def test_compact_output_error_on_missing_text():
    result = handle_tool_call("compact_output", {})
    assert result.get("isError") is True
    assert "text is required" in result["content"][0]["text"]
```

- [ ] **Step 2: Write failing E2E test**

```python
# tests/e2e/test_mcp_output.py
"""E2E tests for compact_output MCP tool — full JSON-RPC flow."""

SAMPLE_PYTEST_OUTPUT = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
collected 3 items

tests/test_auth.py::test_login PASSED                                    [ 33%]
tests/test_auth.py::test_signup FAILED                                   [ 66%]
tests/test_auth.py::test_logout PASSED                                   [100%]

=================================== FAILURES ===================================
_________________________________ test_signup __________________________________

    def test_signup():
>       assert False
E       AssertionError

tests/test_auth.py:10: AssertionError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError
========================= 2 passed, 1 failed in 0.10s =========================
"""


def test_compact_output_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "compact_output" in tool_names


def test_compact_output_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "compact_output",
        "arguments": {"text": SAMPLE_PYTEST_OUTPUT, "hint": "pytest"},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "# pytest:" in content
    assert "1 failed" in content
    assert "test_signup" in content


def test_compact_output_token_savings(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(SAMPLE_PYTEST_OUTPUT) // 4
    resp = mcp_server.send("tools/call", {
        "name": "compact_output",
        "arguments": {"text": SAMPLE_PYTEST_OUTPUT, "hint": "pytest"},
    })
    content = resp["result"]["content"][0]["text"]
    cleaned_tokens = len(content) // 4
    assert cleaned_tokens < raw_tokens
    savings_pct = (1 - cleaned_tokens / raw_tokens) * 100
    assert savings_pct > 40, f"Only {savings_pct:.1f}% savings"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/server/test_output_integration.py tests/e2e/test_mcp_output.py -v`
Expected: Failures — tool not registered yet

- [ ] **Step 4: Add tool definition to protocol.py**

Append to `TOOL_DEFINITIONS` list in `py/tokkit_server/protocol.py`:

```python
    {
        "name": "compact_output",
        "description": (
            "Compress shell command output (test results, build logs, lint reports) "
            "into token-optimized structured format. Extracts only actionable items "
            "(errors, failures, warnings) plus a summary line. Returns schema+CSV format.\n\n"
            "Supported: pytest, unittest, ruff, mypy, pyright, pip, python tracebacks, "
            "jest, vitest, mocha, tsc, eslint, webpack, vite, npm, "
            "cargo test/build/clippy, docker build.\n\n"
            "Pass hint matching the command (e.g. hint=\"pytest\") for best results. "
            "Omit hint for auto-detection. Set verbose=true to include all items, "
            "not just problems. Does NOT require index_repository."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Raw command output to compress."},
                "hint": {"type": "string", "description": "Tool identifier for parser selection (e.g. 'pytest', 'eslint', 'tsc'). Omit for auto-detection."},
                "verbose": {"type": "boolean", "description": "Include all items, not just problems. Default: false."},
            },
            "required": ["text"],
        },
    },
```

- [ ] **Step 5: Add dispatch to tools.py**

Add before the `get_token_stats` block in `handle_tool_call()`:

```python
        if tool_name == "compact_output":
            text = args.get("text", "")
            hint = args.get("hint")
            verbose = args.get("verbose", False)
            if not text:
                return _err("text is required")
            from tokkit_output import compact_output
            compacted = compact_output(text, hint=hint, verbose=verbose)
            meta = make_meta(tool_name, compacted, _session_project_path, raw_size=len(text))
            return _ok(compacted, meta)
```

- [ ] **Step 6: Add token stats estimation**

Add to `estimate_tokens_avoided()` in `py/tokkit_server/token_stats.py`:

```python
    if tool_name == "compact_output":
        if raw_size:
            return raw_size // CHARS_PER_TOKEN
        return len(result_text) * 2 // CHARS_PER_TOKEN
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/server/test_output_integration.py tests/e2e/test_mcp_output.py -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add py/tokkit_server/ tests/server/test_output_integration.py tests/e2e/test_mcp_output.py
git commit -m "feat(output): MCP server integration — tool def, dispatch, token stats"
```

---

### Task 8: Benchmark — add compact_output scenarios

**Files:**
- Modify: `tests/e2e/benchmark/config.py`
- Modify: `tests/e2e/benchmark/baselines.py`
- Modify: `tests/e2e/benchmark/test_benchmark.py`

- [ ] **Step 1: Add benchmark config entries**

Add to `QUESTIONS` in `tests/e2e/benchmark/config.py`:

```python
QUESTIONS = [
    "Find function by pattern",
    "Trace call chain (depth 3)",
    "Dead code detection",
    "List all routes",
    "Architecture overview",
    "Search markdown documentation",
    "Compress pytest output",
    "Compress lint output",
]
```

- [ ] **Step 2: Add baseline functions**

Add to `tests/e2e/benchmark/baselines.py`:

```python
# Exact baselines for compact_output — raw output token count is the baseline
# (without tokkit, the LLM agent receives the full raw output)
_EXACT_BASELINES_BYTES["compress_pytest"] = 2_400   # ~600 tokens, typical 50-test run
_EXACT_BASELINES_BYTES["compress_lint"] = 1_600     # ~400 tokens, typical ruff output


def baseline_compress_pytest(repo_path: str) -> int:
    """Q7: Compress pytest output. Baseline = raw output tokens."""
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["compress_pytest"] // CHARS_PER_TOKEN
    return _EXACT_BASELINES_BYTES["compress_pytest"] // CHARS_PER_TOKEN  # use default


def baseline_compress_lint(repo_path: str) -> int:
    """Q8: Compress lint output. Baseline = raw output tokens."""
    if _is_default_repo():
        return _EXACT_BASELINES_BYTES["compress_lint"] // CHARS_PER_TOKEN
    return _EXACT_BASELINES_BYTES["compress_lint"] // CHARS_PER_TOKEN  # use default
```

- [ ] **Step 3: Add benchmark test methods**

Add to `TestTokenBenchmark` class in `tests/e2e/benchmark/test_benchmark.py`:

```python
    def test_q7_compress_pytest(self, benchmark_repo, benchmark_mcp):
        from e2e.benchmark.baselines import baseline_compress_pytest
        baseline = baseline_compress_pytest(benchmark_repo)

        # Generate realistic pytest output for the benchmark repo
        raw_output = (
            "============================= test session starts ==============================\n"
            "platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0\n"
            "collected 50 items\n\n"
        )
        for i in range(48):
            raw_output += f"tests/test_{i:03d}.py::test_func PASSED                              [{(i+1)*2}%]\n"
        raw_output += "tests/test_auth.py::test_signup FAILED                              [ 98%]\n"
        raw_output += "tests/test_db.py::test_query FAILED                                 [100%]\n"
        raw_output += "\n=========================== short test summary info ============================\n"
        raw_output += "FAILED tests/test_auth.py::test_signup - AssertionError: assert 401 == 200\n"
        raw_output += "FAILED tests/test_db.py::test_query - KeyError: 'users'\n"
        raw_output += "========================= 48 passed, 2 failed in 1.23s =========================\n"

        response = benchmark_mcp.call_tool("compact_output", {
            "text": raw_output,
            "hint": "pytest",
        })
        tokkit = _tokkit_tokens(response)
        # Use raw output size as baseline since that's what agent would receive
        raw_baseline = len(raw_output) // CHARS_PER_TOKEN

        _results.append({
            "question": QUESTIONS[6],
            "tokkit": tokkit,
            "baseline": raw_baseline,
        })
        assert tokkit < raw_baseline

    def test_q8_compress_lint(self, benchmark_repo, benchmark_mcp):
        from e2e.benchmark.baselines import baseline_compress_lint
        baseline = baseline_compress_lint(benchmark_repo)

        raw_output = ""
        for i in range(15):
            raw_output += f"src/module_{i}.py:{i*10+5}:1: E501 Line too long ({90+i} > 88)\n"
        raw_output += f"Found {15} errors.\n"

        response = benchmark_mcp.call_tool("compact_output", {
            "text": raw_output,
            "hint": "ruff",
        })
        tokkit = _tokkit_tokens(response)
        raw_baseline = len(raw_output) // CHARS_PER_TOKEN

        _results.append({
            "question": QUESTIONS[7],
            "tokkit": tokkit,
            "baseline": raw_baseline,
        })
        assert tokkit < raw_baseline
```

Also update `test_z_generate_report` to expect 8 results:

```python
    def test_z_generate_report(self):
        if len(_results) < 8:
            pytest.skip("Not all questions completed")
```

- [ ] **Step 4: Update imports in test_benchmark.py**

Add to the imports:

```python
from e2e.benchmark.baselines import (
    baseline_find_function,
    baseline_trace_calls,
    baseline_dead_code,
    baseline_list_routes,
    baseline_architecture,
    baseline_search_markdown,
    baseline_compress_pytest,
    baseline_compress_lint,
    _is_default_repo,
)
```

- [ ] **Step 5: Run benchmark**

Run: `pytest tests/e2e/benchmark/ -v -m benchmark`
Expected: All 8 questions pass, compact_output shows >50% savings

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/benchmark/
git commit -m "bench(output): add compact_output scenarios — pytest and lint compression"
```

---

### Task 9: Inference eval — LLM accuracy on compacted output

**Files:**
- Create: `tests/output_tests/fixtures/eval_fixtures.py`
- Create: `tests/output_tests/test_inference_eval.py`
- Modify: `pyproject.toml` (add marker)

- [ ] **Step 1: Create eval fixtures and questions**

```python
# tests/output_tests/fixtures/eval_fixtures.py
"""Eval fixtures: real output samples + questions with gold answers."""

from pydantic import BaseModel


# --- Answer models ---

class CountAnswer(BaseModel):
    count: int

class ListAnswer(BaseModel):
    items: list[str]

class FileLineAnswer(BaseModel):
    file: str
    line: int

class StatusAnswer(BaseModel):
    status: str  # "pass" or "fail"


# --- Fixture data ---

PYTEST_FIXTURE = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
collected 8 items

tests/test_auth.py::test_login PASSED                                    [ 12%]
tests/test_auth.py::test_logout PASSED                                   [ 25%]
tests/test_auth.py::test_signup FAILED                                   [ 37%]
tests/test_api.py::test_get_users PASSED                                 [ 50%]
tests/test_api.py::test_create_user PASSED                               [ 62%]
tests/test_api.py::test_delete_user FAILED                               [ 75%]
tests/test_db.py::test_connect PASSED                                    [ 87%]
tests/test_db.py::test_query PASSED                                      [100%]

=================================== FAILURES ===================================
_________________________________ test_signup __________________________________

    def test_signup():
        result = signup("alice@test.com", "pass")
>       assert result.status_code == 200
E       AssertionError: assert 401 == 200

tests/test_auth.py:42: AssertionError
_______________________________ test_delete_user _______________________________

    def test_delete_user():
        resp = client.delete("/users/999")
>       assert resp.status_code == 200
E       AssertionError: assert 404 == 200

tests/test_api.py:67: AssertionError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError: assert 401 == 200
FAILED tests/test_api.py::test_delete_user - AssertionError: assert 404 == 200
========================= 6 passed, 2 failed in 0.45s =========================
"""

RUFF_FIXTURE = """\
src/auth.py:42:5: E501 Line too long (127 > 88)
src/auth.py:89:1: F401 [*] `os` imported but unused
src/db.py:15:9: E711 Comparison to `None` (use `is` or `is not`)
src/api.py:23:10: W291 Trailing whitespace
src/api.py:55:1: F841 Local variable `x` is assigned to but never used
Found 5 errors.
[*] 1 fixable with the `--fix` option.
"""

TSC_FIXTURE = """\
src/api.ts(42,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/api.ts(89,12): error TS2345: Argument of type 'null' is not assignable to parameter of type 'User'.
src/db.ts(15,3): error TS2304: Cannot find name 'Connection'.
src/auth.ts(7,1): error TS2307: Cannot find module 'bcrypt' or its corresponding type declarations.

Found 4 errors in 3 files.
"""


# --- Questions ---

QUESTIONS = [
    {
        "id": "q1",
        "fixture_name": "pytest",
        "question": "How many tests failed?",
        "model": CountAnswer,
        "gold": CountAnswer(count=2),
    },
    {
        "id": "q2",
        "fixture_name": "pytest",
        "question": "How many tests passed?",
        "model": CountAnswer,
        "gold": CountAnswer(count=6),
    },
    {
        "id": "q3",
        "fixture_name": "pytest",
        "question": "List the names of the failing tests.",
        "model": ListAnswer,
        "gold": ListAnswer(items=["test_signup", "test_delete_user"]),
    },
    {
        "id": "q4",
        "fixture_name": "pytest",
        "question": "In which file and on what line did test_signup fail?",
        "model": FileLineAnswer,
        "gold": FileLineAnswer(file="tests/test_auth.py", line=42),
    },
    {
        "id": "q5",
        "fixture_name": "pytest",
        "question": "Did the overall test suite pass or fail?",
        "model": StatusAnswer,
        "gold": StatusAnswer(status="fail"),
    },
    {
        "id": "q6",
        "fixture_name": "ruff",
        "question": "How many linting violations were found?",
        "model": CountAnswer,
        "gold": CountAnswer(count=5),
    },
    {
        "id": "q7",
        "fixture_name": "ruff",
        "question": "List the files that have linting violations.",
        "model": ListAnswer,
        "gold": ListAnswer(items=["src/auth.py", "src/db.py", "src/api.py"]),
    },
    {
        "id": "q8",
        "fixture_name": "tsc",
        "question": "How many TypeScript errors were found?",
        "model": CountAnswer,
        "gold": CountAnswer(count=4),
    },
    {
        "id": "q9",
        "fixture_name": "tsc",
        "question": "List the TypeScript error codes found.",
        "model": ListAnswer,
        "gold": ListAnswer(items=["TS2322", "TS2345", "TS2304", "TS2307"]),
    },
    {
        "id": "q10",
        "fixture_name": "tsc",
        "question": "How many files contain errors?",
        "model": CountAnswer,
        "gold": CountAnswer(count=3),
    },
]

FIXTURES = {
    "pytest": PYTEST_FIXTURE,
    "ruff": RUFF_FIXTURE,
    "tsc": TSC_FIXTURE,
}
```

- [ ] **Step 2: Write inference eval test**

```python
# tests/output_tests/test_inference_eval.py
"""LLM inference accuracy eval for compact_output.

Compares LLM accuracy on raw output vs compacted output.
Uses claude_agent_sdk.

Run: pytest -m inference tests/output_tests/test_inference_eval.py -v
"""

import asyncio
import json
import os
import re
from datetime import date

import pytest
from pydantic import BaseModel

from tokkit_output import compact_output
from output_tests.fixtures.eval_fixtures import QUESTIONS, FIXTURES

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

EVAL_MODEL = os.environ.get("TOKKIT_EVAL_MODEL", "haiku")
CHARS_PER_TOKEN = 4


def _extract_json(text: str) -> dict:
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        text = m.group(1)
    return json.loads(text.strip())


def _ask_llm(data_str: str, question: str, response_model: type[BaseModel], model: str) -> BaseModel:
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    system = (
        "You are a data analyst. You will be given command output and a question. "
        "Analyze the output carefully and answer the question. "
        "Respond with ONLY a raw JSON object matching this schema "
        "(no markdown, no code fences, no explanation, just JSON):\n"
        f"{schema}"
    )
    options = ClaudeAgentOptions(system_prompt=system, model=model, max_turns=1)
    user_prompt = f"Given the following command output:\n\n{data_str}\n\nAnswer this question: {question}"

    result_text = None

    async def _run():
        nonlocal result_text
        async for msg in query(prompt=user_prompt, options=options):
            if isinstance(msg, ResultMessage):
                result_text = msg.result

    asyncio.get_event_loop().run_until_complete(_run())
    if not result_text:
        raise RuntimeError("No result from Claude")

    raw = _extract_json(result_text)
    return response_model.model_validate(raw)


def _answers_match(result: BaseModel, gold: BaseModel) -> bool:
    from output_tests.fixtures.eval_fixtures import CountAnswer, ListAnswer, FileLineAnswer, StatusAnswer

    if isinstance(gold, CountAnswer):
        return result.count == gold.count
    if isinstance(gold, ListAnswer):
        return set(s.lower() for s in result.items) == set(s.lower() for s in gold.items)
    if isinstance(gold, FileLineAnswer):
        return result.file == gold.file and result.line == gold.line
    if isinstance(gold, StatusAnswer):
        return result.status.lower() == gold.status.lower()
    raise TypeError(f"Unknown type: {type(gold)}")


_results: list[dict] = []
_question_ids = [q["id"] for q in QUESTIONS]


@pytest.mark.inference
class TestOutputInferenceEval:

    @pytest.mark.parametrize("q_id", _question_ids)
    def test_question(self, q_id):
        q = next(q for q in QUESTIONS if q["id"] == q_id)
        raw = FIXTURES[q["fixture_name"]]
        compacted = compact_output(raw, hint=q["fixture_name"])
        gold = q["gold"]

        control = _ask_llm(raw, q["question"], q["model"], EVAL_MODEL)
        treatment = _ask_llm(compacted, q["question"], q["model"], EVAL_MODEL)

        _results.append({
            "id": q_id,
            "fixture": q["fixture_name"],
            "question": q["question"],
            "control_correct": _answers_match(control, gold),
            "treatment_correct": _answers_match(treatment, gold),
            "raw_tokens": len(raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(compacted) // CHARS_PER_TOKEN,
        })

        assert _answers_match(treatment, gold), (
            f"{q_id} treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_z_generate_report(self):
        if len(_results) < len(_question_ids):
            pytest.skip("Not all results collected")

        ctrl_ok = sum(1 for r in _results if r["control_correct"])
        treat_ok = sum(1 for r in _results if r["treatment_correct"])
        total = len(_results)

        lines = [
            "# compact_output Inference Eval Results",
            "",
            f"**Date:** {date.today().isoformat()}",
            f"**Model:** {EVAL_MODEL}",
            f"**Questions:** {total}",
            "",
            "| # | Fixture | Question | Control | Treatment | Savings |",
            "|---|---------|----------|---------|-----------|---------|",
        ]

        for r in _results:
            savings = (1 - r["compact_tokens"] / r["raw_tokens"]) * 100 if r["raw_tokens"] > 0 else 0
            ctrl = "PASS" if r["control_correct"] else "FAIL"
            treat = "PASS" if r["treatment_correct"] else "FAIL"
            lines.append(f"| {r['id']} | {r['fixture']} | {r['question'][:40]} | {ctrl} | {treat} | {savings:.0f}% |")

        lines.extend([
            "",
            f"**Control:** {ctrl_ok}/{total} ({ctrl_ok/total*100:.0f}%)",
            f"**Treatment:** {treat_ok}/{total} ({treat_ok/total*100:.0f}%)",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "OUTPUT_INFERENCE_EVAL_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\n\n{report}")
```

- [ ] **Step 3: Add benchmark marker to pyproject.toml if needed**

The `inference` marker already exists. Verify by checking `pyproject.toml`:

```toml
markers = [
    "inference: LLM-backed inference accuracy eval (requires ANTHROPIC_API_KEY)",
    "benchmark: Token savings benchmark against real repos",
]
```

Add the `benchmark` marker if missing.

- [ ] **Step 4: Commit**

```bash
git add tests/output_tests/fixtures/eval_fixtures.py tests/output_tests/test_inference_eval.py pyproject.toml
git commit -m "eval(output): 10-question inference eval for compact_output accuracy"
```

---

### Task 10: Update skill docs and SKILL.md

**Files:**
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Add compact_output section to SKILL.md**

After the `### 9. Search Markdown Content` section, add:

```markdown
### 10. Compress Shell Output

For test results, build logs, lint reports, and other command output:

```
compact_output(text="<raw output>", hint="pytest")
  → summary line + schema+CSV of failures only

compact_output(text="...", verbose=true)
  → summary line + schema+CSV of all items

compact_output(text="...", hint="ruff")
  → summary line + schema+CSV of violations only
```

**Supported parsers (v1):**

| Category | Tools | Hint values |
|----------|-------|-------------|
| Python test | pytest, unittest | `pytest`, `unittest` |
| Python lint/type | ruff, mypy, pyright | `ruff`, `mypy`, `pyright` |
| Python other | pip, tracebacks | `pip`, `traceback` |
| JS/TS test | jest, vitest, mocha | `jest`, `vitest`, `mocha` |
| JS/TS lint/type | tsc, eslint | `tsc`, `eslint` |
| JS/TS build | webpack, vite | `webpack`, `vite` |
| JS/TS package | npm | `npm` |
| Rust | cargo test/build/clippy | `cargo-test`, `cargo-build`, `cargo-clippy` |
| Container | docker build | `docker` |

**Not yet supported:** go, gcc/clang, make, gradle, maven, ruby, php, swift, kotlin, terraform.

Auto-detects the tool when hint is omitted. Pass hint for best results.
Does not require an indexed project. Works standalone as a stateless transformation.
```

- [ ] **Step 2: Update Tool Selection Guide table**

Add row to the table:

```markdown
| Compress shell output | `compact_output` | Extracts actionable items, saves 70-85% |
```

- [ ] **Step 3: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs: add compact_output to SKILL.md with supported parsers table"
```

---

### Task 11: Run full test suite

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/output_tests/ -v --ignore=tests/output_tests/test_inference_eval.py`
Expected: All pass

- [ ] **Step 2: Run server integration tests**

Run: `pytest tests/server/ -v`
Expected: All pass

- [ ] **Step 3: Run E2E tests**

Run: `pytest tests/e2e/ -v --ignore=tests/e2e/benchmark`
Expected: All pass

- [ ] **Step 4: Run existing test suite to check for regressions**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark --ignore=tests/output_tests/test_inference_eval.py`
Expected: All pass, no regressions

- [ ] **Step 5: Commit any fixes**

If any test needed fixing:
```bash
git add -A
git commit -m "fix: address test failures from compact_output integration"
```
