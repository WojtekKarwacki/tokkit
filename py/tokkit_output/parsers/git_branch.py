"""Git branch output parser."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["branch", "current", "info"]

# Matches lines that look like git branch output: leading spaces + optional * + branch name
# Branch names must not contain spaces; lines like "  feat/foo" or "* main" or "  main"
_BRANCH_LINE_RE = re.compile(r"^[ \t]*\*?[ \t]+[A-Za-z0-9_./@-][A-Za-z0-9_./~@^:-]*")
_BRANCH_RE = re.compile(r"^(\*?)\s*(\S+)(?:\s+([0-9a-f]{7,8}))?(?:\s+(.*))?$")
_GROUP_THRESHOLD = 20


class GitBranchParser(BaseParser):
    id = "git-branch"
    hint_values = ["git-branch"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = [line for line in clean.splitlines() if line.strip()]

        has_current = any(line.strip().startswith("*") for line in lines)
        branch_count = sum(1 for line in lines if _BRANCH_LINE_RE.match(line))

        if has_current and branch_count >= 2:
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        parsed: list[tuple[str, bool, str]] = []  # (name, is_current, info)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            is_current = stripped.startswith("*")
            rest = stripped.lstrip("* ").strip()
            parts = rest.split(None, 2)
            name = parts[0] if parts else ""
            if not name:
                continue
            info = ""
            if len(parts) >= 3:
                info = parts[2].strip()
            elif len(parts) == 2:
                # Could be just a hash
                if re.match(r"^[0-9a-f]{7,40}$", parts[1]):
                    pass
                else:
                    info = parts[1]
            parsed.append((name, is_current, info))

        if len(parsed) > _GROUP_THRESHOLD:
            rows = _group_by_prefix(parsed)
        else:
            rows = [[name, "true" if cur else "false", info] for name, cur, info in parsed]

        n = len(parsed)
        current_name = next((name for name, cur, _ in parsed if cur), "")
        if current_name:
            summary = f"{n} branch{'es' if n != 1 else ''}, current: {current_name}"
        else:
            summary = f"{n} branch{'es' if n != 1 else ''}"

        return ParseResult(
            tool="git-branch",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )


def _group_by_prefix(parsed: list[tuple[str, bool, str]]) -> list[list[str]]:
    groups: dict[str, list[tuple[str, bool, str]]] = defaultdict(list)
    no_prefix: list[tuple[str, bool, str]] = []

    for name, is_current, info in parsed:
        if "/" in name:
            prefix = name.split("/")[0]
            groups[prefix].append((name, is_current, info))
        else:
            no_prefix.append((name, is_current, info))

    rows: list[list[str]] = []

    # Individual branches without prefix
    for name, is_current, info in no_prefix:
        rows.append([name, "true" if is_current else "false", info])

    # Groups
    for prefix in sorted(groups):
        members = groups[prefix]
        count = len(members)
        current_in_group = next((name for name, cur, _ in members if cur), None)
        group_info = f"{count} branches"
        if current_in_group:
            group_info += f", current: {current_in_group}"
        rows.append([f"{prefix}/", "false", group_info])

    return rows
