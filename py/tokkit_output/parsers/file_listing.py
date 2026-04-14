"""File listing output parser (ls -la, tree, find)."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_TREE_CHAR_RE = re.compile(r"[├└│]")
_PERM_RE = re.compile(r"^[d\-lbcps][rwx\-sStT]{9}")
_PATH_LINE_RE = re.compile(r"^\./\S+|^/\S+")

_LS_ROW_RE = re.compile(
    r"^([d\-lbcps][rwx\-sStT]{9})\s+\d+\s+\S+\s+\S+\s+(\S+)\s+\S+\s+\S+\s+\S+\s+(.+)$"
)
_TREE_ENTRY_RE = re.compile(r"^([ │]*)[├└]── (.+)$")

_LS_TRUNCATE = 50
_LS_SHOW = 30
_FIND_TRUNCATE = 30
_FIND_SHOW_PER_DIR = 3
_FIND_MAX_DIRS = 15


class FileListingParser(BaseParser):
    id = "file-listing"
    hint_values = ["ls", "tree", "find"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _TREE_CHAR_RE.search(clean):
            return 0.8
        lines = clean.splitlines()
        perm_count = sum(1 for ln in lines if _PERM_RE.match(ln.strip()))
        if perm_count >= 2:
            return 0.7
        path_count = sum(1 for ln in lines if _PATH_LINE_RE.match(ln))
        if path_count >= 5:
            return 0.6
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)

        if _TREE_CHAR_RE.search(clean):
            return _parse_tree(clean, verbose)

        lines = clean.splitlines()
        perm_count = sum(1 for ln in lines if _PERM_RE.match(ln.strip()))
        if perm_count >= 2:
            return _parse_ls_la(clean, verbose)

        return _parse_find(clean, verbose)


# ---------------------------------------------------------------------------
# tree
# ---------------------------------------------------------------------------

def _tree_depth(prefix: str) -> int:
    """Compute depth from tree prefix characters."""
    return len(re.findall(r"[│ ]   |[│ ] {3}", prefix + " "))


def _parse_tree(text: str, verbose: bool) -> ParseResult:
    rows: list[list[str]] = []
    dir_children: dict[str, dict] = {}
    path_stack: list[str] = []

    for line in text.splitlines():
        m = _TREE_ENTRY_RE.match(line)
        if not m:
            continue

        prefix = m.group(1)
        name = m.group(2).strip()
        depth = prefix.count("│") + prefix.count(" ") // 4 + (1 if prefix else 0)
        # Simpler depth: count 4-char indent groups in prefix
        depth = len(prefix) // 4 + (1 if prefix and len(prefix) % 4 != 0 else (1 if prefix else 0))
        depth = max(1, (len(prefix) + 1) // 4)

        if depth <= 3 or verbose:
            # Build path
            if depth <= len(path_stack):
                path_stack = path_stack[:depth - 1]
            path_stack.append(name)
            full_path = "/".join(path_stack)
            rows.append([full_path])
        else:
            # Deep entry: count under parent at depth 3
            if depth - 1 <= len(path_stack):
                parent_path = "/".join(path_stack[:3])
            else:
                parent_path = "/".join(path_stack[:3]) if path_stack else "."
            dir_children[parent_path] = dir_children.get(parent_path, {"files": 0, "subdirs": 0})
            if name.endswith("/") or "." not in name.split("/")[-1]:
                dir_children[parent_path]["subdirs"] += 1
            else:
                dir_children[parent_path]["files"] += 1

    # Replace deep-dir entries with summary rows
    final_rows: list[list[str]] = []
    replaced: set[str] = set()
    for row in rows:
        path = row[0]
        if path in dir_children and path not in replaced:
            info = dir_children[path]
            summary = f"{path}/ ({info['files']} files, {info['subdirs']} subdirs)"
            final_rows.append([summary])
            replaced.add(path)
        else:
            final_rows.append(row)

    total = len(rows) + sum(
        v["files"] + v["subdirs"] for v in dir_children.values()
    )
    summary = f"{total} entries"

    return ParseResult(
        tool="file-listing",
        summary=summary,
        schema=["path"],
        rows=final_rows,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# ls -la
# ---------------------------------------------------------------------------

def _parse_ls_la(text: str, verbose: bool) -> ParseResult:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("total "):
            continue
        m = _LS_ROW_RE.match(line)
        if m:
            perms = m.group(1)
            size = m.group(2)
            name = m.group(3).strip()
            if perms.startswith("d"):
                ftype = "dir"
            elif perms.startswith("l"):
                ftype = "link"
            else:
                ftype = "file"
            rows.append([name, ftype, size])

    total = len(rows)
    summary = f"{total} entries"

    if not verbose and total > _LS_TRUNCATE:
        shown = rows[:_LS_SHOW]
        remaining = total - _LS_SHOW
        shown.append([f"... ({remaining} more)", "", ""])
        rows = shown

    return ParseResult(
        tool="file-listing",
        summary=summary,
        schema=["path", "type", "size"],
        rows=rows,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------

def _parse_find(text: str, verbose: bool) -> ParseResult:
    all_paths: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            all_paths.append(line)

    total = len(all_paths)

    if verbose or total <= _FIND_TRUNCATE:
        rows = [[p] for p in all_paths]
        return ParseResult(
            tool="file-listing",
            summary=f"{total} files",
            schema=["path"],
            rows=rows,
            verbose=verbose,
        )

    # Group by directory
    by_dir: dict[str, list[str]] = defaultdict(list)
    for path in all_paths:
        parts = path.rsplit("/", 1)
        if len(parts) == 2:
            directory = parts[0]
        else:
            directory = "."
        by_dir[directory].append(path)

    # Sort dirs by file count descending, take top dirs
    sorted_dirs = sorted(by_dir.items(), key=lambda x: len(x[1]), reverse=True)
    top_dirs = sorted_dirs[:_FIND_MAX_DIRS]

    rows: list[list[str]] = []
    for directory, paths in top_dirs:
        shown_paths = paths[:_FIND_SHOW_PER_DIR]
        for p in shown_paths:
            rows.append([p])
        remaining = len(paths) - _FIND_SHOW_PER_DIR
        if remaining > 0:
            rows.append([f"  {directory}/ ... ({remaining} more)"])

    return ParseResult(
        tool="file-listing",
        summary=f"{total} files",
        schema=["path"],
        rows=rows,
        verbose=verbose,
    )
