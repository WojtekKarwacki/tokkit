"""GitHub CLI output parser (gh pr list, gh issue list, gh run list)."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SHOWING_RE = re.compile(r"Showing \d+ of \d+")
_NUMBER_TAB_RE = re.compile(r"^#\d+\t")
_STATUS_TAB_RE = re.compile(r"^(completed|failed|in_progress|queued|cancelled)\t", re.IGNORECASE)

_MAX_ENTRIES = 20


class GhCliParser(BaseParser):
    id = "gh-cli"
    hint_values = ["gh", "gh-pr", "gh-issue", "gh-run"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _SHOWING_RE.search(clean):
            return 0.8
        lines = clean.splitlines()
        tab_number_lines = sum(1 for ln in lines if _NUMBER_TAB_RE.match(ln))
        if tab_number_lines >= 2:
            return 0.8
        tab_status_lines = sum(1 for ln in lines if _STATUS_TAB_RE.match(ln))
        if tab_status_lines >= 2:
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Detect sub-format
        data_lines = [ln for ln in lines if ln.strip() and not ln.startswith("Showing")]

        if not data_lines:
            return ParseResult(
                tool="gh-cli",
                summary="0 results",
                schema=["number", "title", "branch", "status"],
                rows=[],
                verbose=verbose,
            )

        first = data_lines[0]

        if _NUMBER_TAB_RE.match(first):
            # PR or issue list: #N\ttitle\t...
            return _parse_number_table(lines, verbose)
        elif _STATUS_TAB_RE.match(first):
            return _parse_run_list(lines, verbose)
        else:
            # Try header-based detection
            if "STATUS" in first and "NAME" in first:
                return _parse_run_list(lines, verbose)
            return _parse_number_table(lines, verbose)


# ---------------------------------------------------------------------------
# PR / Issue list  (#N\ttitle\tbranch\tstatus)
# ---------------------------------------------------------------------------

def _parse_number_table(lines: list[str], verbose: bool) -> ParseResult:
    rows: list[list[str]] = []
    is_issue = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("Showing"):
            continue
        parts = line.split("\t")
        if not parts or not parts[0].startswith("#"):
            continue

        number = parts[0].lstrip("#")

        if len(parts) >= 4:
            title = parts[1]
            col3 = parts[2]
            col4 = parts[3]
            # Heuristic: issues have labels (comma-separated words, no /)
            # PRs have branch names (often contain /)
            if "/" in col3 or col3.upper() in ("OPEN", "CLOSED", "MERGED", "DRAFT"):
                # PR: #, title, branch, status
                rows.append([number, title, col3, col4])
            else:
                # Issue: #, title, labels, status
                is_issue = True
                rows.append([number, title, col3, col4])
        elif len(parts) == 3:
            rows.append([number, parts[1], "", parts[2]])
        elif len(parts) == 2:
            rows.append([number, parts[1], "", ""])

    total = len(rows)
    entity = "issues" if is_issue else "pull requests"

    # Check Showing header for total count
    for line in lines:
        m = re.search(r"Showing \d+ of (\d+)", line)
        if m:
            total_str = m.group(1)
            entity_match = re.search(r"(\d+) (?:open )?(\w+)", line)
            if entity_match:
                entity_label = entity_match.group(2).rstrip("s")
                if "issue" in entity_label.lower():
                    entity = "issues"
                elif "pull" in entity_label.lower() or "pr" in entity_label.lower():
                    entity = "pull requests"
            summary = f"{total_str} {entity}"
            break
    else:
        summary = f"{total} {entity}"

    if not verbose and total > _MAX_ENTRIES:
        rows = rows[:_MAX_ENTRIES]

    schema = ["number", "title", "labels" if is_issue else "branch", "status"]

    return ParseResult(
        tool="gh-cli",
        summary=summary,
        schema=schema,
        rows=rows,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# Run list (STATUS\tNAME\t...)
# ---------------------------------------------------------------------------

def _parse_run_list(lines: list[str], verbose: bool) -> ParseResult:
    rows: list[list[str]] = []
    skip_header = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("Showing"):
            continue

        # Skip header row
        if "STATUS" in line and "NAME" in line and not skip_header:
            skip_header = True
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        branch = ""
        elapsed = ""

        # Find branch and elapsed from available columns
        # Format: STATUS NAME WORKFLOW BRANCH EVENT ID ELAPSED AGE
        if len(parts) >= 8:
            branch = parts[3]
            elapsed = parts[6]
        elif len(parts) >= 4:
            branch = parts[3]
        elif len(parts) >= 3:
            branch = parts[2]

        rows.append([status, name, branch, elapsed])

    total = len(rows)
    summary = f"{total} runs"

    for line in lines:
        m = re.search(r"Showing \d+ of (\d+)", line)
        if m:
            summary = f"{m.group(1)} runs"
            break

    if not verbose and total > _MAX_ENTRIES:
        rows = rows[:_MAX_ENTRIES]

    return ParseResult(
        tool="gh-cli",
        summary=summary,
        schema=["status", "name", "branch", "elapsed"],
        rows=rows,
        verbose=verbose,
    )
