"""Package list output parser (pip list, pip freeze, npm ls)."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_HEADER_RE = re.compile(r"^Package\s+Version", re.MULTILINE)
_FREEZE_LINE_RE = re.compile(r"^\S+==\S+")
_NPM_TREE_RE = re.compile(r"[├└]──")

_FREEZE_PARSE_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==(\S+)")
_PIP_LIST_ROW_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s+(\S+)\s*$")

_UNMET_RE = re.compile(r"UNMET|ERR!|invalid", re.IGNORECASE)
_NPM_TOP_LEVEL_RE = re.compile(r"^[├└]── (.+)$")
_NPM_NESTED_RE = re.compile(r"^[│ ]+[├└]── ")

_TRUNCATE_THRESHOLD = 20
_SHOW_COUNT = 15


class PackageListParser(BaseParser):
    id = "package-list"
    hint_values = ["pip-list", "pip-freeze", "npm-ls"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _HEADER_RE.search(clean):
            return 0.8
        lines = clean.splitlines()
        freeze_count = sum(1 for ln in lines if _FREEZE_LINE_RE.match(ln.strip()))
        if freeze_count >= 3:
            return 0.7
        if _NPM_TREE_RE.search(clean):
            return 0.7
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)

        if _NPM_TREE_RE.search(clean):
            return _parse_npm_ls(clean, verbose)
        elif _HEADER_RE.search(clean):
            return _parse_pip_list(clean, verbose)
        else:
            return _parse_pip_freeze(clean, verbose)


# ---------------------------------------------------------------------------
# pip list
# ---------------------------------------------------------------------------

def _parse_pip_list(text: str, verbose: bool) -> ParseResult:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("-") or line.startswith("Package"):
            continue
        m = _PIP_LIST_ROW_RE.match(line)
        if m:
            rows.append([m.group(1), m.group(2)])

    total = len(rows)
    summary = f"{total} packages"

    if not verbose and total > _TRUNCATE_THRESHOLD:
        shown = rows[:_SHOW_COUNT]
        remaining = total - _SHOW_COUNT
        shown.append([f"... ({remaining} more)", ""])
        rows = shown

    return ParseResult(
        tool="package-list",
        summary=summary,
        schema=["package", "version"],
        rows=rows,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# pip freeze
# ---------------------------------------------------------------------------

def _parse_pip_freeze(text: str, verbose: bool) -> ParseResult:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _FREEZE_PARSE_RE.match(line)
        if m:
            rows.append([m.group(1), m.group(2)])

    total = len(rows)
    summary = f"{total} packages"

    if not verbose and total > _TRUNCATE_THRESHOLD:
        shown = rows[:_SHOW_COUNT]
        remaining = total - _SHOW_COUNT
        shown.append([f"... ({remaining} more)", ""])
        rows = shown

    return ParseResult(
        tool="package-list",
        summary=summary,
        schema=["package", "version"],
        rows=rows,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# npm ls
# ---------------------------------------------------------------------------

def _parse_npm_ls(text: str, verbose: bool) -> ParseResult:
    lines = text.splitlines()

    top_level_rows: list[list[str]] = []
    issue_rows: list[list[str]] = []
    nested_count = 0

    for line in lines:
        # Always capture UNMET/ERR!/invalid lines
        if _UNMET_RE.search(line):
            pkg_ver = _extract_npm_pkg(line)
            name, ver = pkg_ver
            issue_rows.append([name, ver, "UNMET"])
            continue

        if _NPM_NESTED_RE.match(line):
            nested_count += 1
            continue

        m = _NPM_TOP_LEVEL_RE.match(line)
        if m:
            name, ver = _parse_npm_name_ver(m.group(1))
            top_level_rows.append([name, ver, ""])

    total_top = len(top_level_rows)
    total_issues = len(issue_rows)
    total_deps = total_top + nested_count + total_issues
    summary = f"{total_deps} deps ({total_top} top-level, {total_issues} issues)"

    rows = top_level_rows + issue_rows

    return ParseResult(
        tool="package-list",
        summary=summary,
        schema=["package", "version", "status"],
        rows=rows,
        verbose=verbose,
    )


def _extract_npm_pkg(line: str) -> tuple[str, str]:
    """Extract package name and version from an npm ls line."""
    clean = re.sub(r"^[│ ]*[├└]── ", "", line).strip()
    clean = re.sub(r"^UNMET PEER DEPENDENCY\s+", "", clean)
    return _parse_npm_name_ver(clean)


def _parse_npm_name_ver(token: str) -> tuple[str, str]:
    """Split 'name@version' into (name, version)."""
    token = token.strip()
    at_idx = token.rfind("@")
    if at_idx > 0:
        return token[:at_idx], token[at_idx + 1:]
    return token, ""
