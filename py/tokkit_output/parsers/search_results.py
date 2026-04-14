"""Search results output parser (grep, rg, ag)."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_MATCH_LINE_COL_RE = re.compile(r"^([^:\n]+):(\d+):(.+)$")
_MATCH_LINE_RE = re.compile(r"^([^:\n]+):(.+)$")
_BINARY_RE = re.compile(r"^Binary file .+ matches$")

_MIN_MATCHES_FOR_DETECT = 3
_MAX_PER_FILE = 3
_MAX_FILES = 15
_DIR_GROUP_THRESHOLD = 30


class SearchResultsParser(BaseParser):
    id = "search-results"
    hint_values = ["grep", "rg", "ag"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = [ln for ln in clean.splitlines() if not _BINARY_RE.match(ln)]
        matches = sum(1 for ln in lines if _MATCH_LINE_COL_RE.match(ln))
        if matches >= _MIN_MATCHES_FOR_DETECT:
            return 0.8
        # file:content format (no line numbers)
        matches2 = sum(1 for ln in lines if _MATCH_LINE_RE.match(ln) and ":" in ln)
        if matches2 >= _MIN_MATCHES_FOR_DETECT:
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Group matches by file
        by_file: dict[str, list[tuple[str, str]]] = defaultdict(list)
        total_matches = 0

        for line in lines:
            if _BINARY_RE.match(line):
                continue
            m = _MATCH_LINE_COL_RE.match(line)
            if m:
                filepath = m.group(1)
                lineno = m.group(2)
                content = m.group(3)
                by_file[filepath].append((lineno, content))
                total_matches += 1
                continue
            m2 = _MATCH_LINE_RE.match(line)
            if m2:
                filepath = m2.group(1)
                content = m2.group(2)
                by_file[filepath].append(("", content))
                total_matches += 1

        total_files = len(by_file)
        summary = f"{total_matches} matches across {total_files} files"

        if verbose:
            rows: list[list[str]] = []
            for filepath, matches_list in sorted(by_file.items()):
                for lineno, content in matches_list:
                    rows.append([filepath, lineno, content.strip()])
            return ParseResult(
                tool="search-results",
                summary=summary,
                schema=["file", "line", "match"],
                rows=rows,
                verbose=verbose,
            )

        # Sort files by match count descending
        sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)

        use_dir_grouping = total_files > _DIR_GROUP_THRESHOLD

        if use_dir_grouping:
            rows = _group_by_directory(sorted_files, summary)
        else:
            rows = _truncate_per_file(sorted_files[:_MAX_FILES])

        return ParseResult(
            tool="search-results",
            summary=summary,
            schema=["file", "line", "match"],
            rows=rows,
            verbose=verbose,
        )


def _truncate_per_file(
    sorted_files: list[tuple[str, list[tuple[str, str]]]]
) -> list[list[str]]:
    rows: list[list[str]] = []
    for filepath, matches_list in sorted_files:
        shown = matches_list[:_MAX_PER_FILE]
        for lineno, content in shown:
            rows.append([filepath, lineno, content.strip()])
        remaining = len(matches_list) - _MAX_PER_FILE
        if remaining > 0:
            rows.append([filepath, "", f"... ({remaining} more matches)"])
    return rows


def _group_by_directory(
    sorted_files: list[tuple[str, list[tuple[str, str]]]],
    summary: str,
) -> list[list[str]]:
    by_dir: dict[str, list[tuple[str, list[tuple[str, str]]]]] = defaultdict(list)
    for filepath, matches_list in sorted_files:
        parts = filepath.rsplit("/", 1)
        directory = parts[0] if len(parts) == 2 else "."
        by_dir[directory].append((filepath, matches_list))

    sorted_dirs = sorted(
        by_dir.items(),
        key=lambda x: sum(len(m) for _, m in x[1]),
        reverse=True,
    )

    rows: list[list[str]] = []
    for directory, files in sorted_dirs[:_MAX_FILES]:
        dir_total = sum(len(m) for _, m in files)
        rows.append([f"{directory}/", "", f"({len(files)} files, {dir_total} matches)"])
    return rows
