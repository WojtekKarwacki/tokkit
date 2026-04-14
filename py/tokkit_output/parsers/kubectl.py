"""Kubectl output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_TABLE_HEADER_RE = re.compile(r"^NAME\s+")
_POD_TABLE_RE = re.compile(r"\bSTATUS\b.*\bREADY\b|\bREADY\b.*\bSTATUS\b")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
_DESCRIBE_NAME_RE = re.compile(r"^Name:\s+\S")
_DESCRIBE_NS_RE = re.compile(r"^Namespace:\s+\S")

# ---------------------------------------------------------------------------
# Pod health classification
# ---------------------------------------------------------------------------

_UNHEALTHY_STATUSES = frozenset([
    "CrashLoopBackOff",
    "Error",
    "OOMKilled",
    "ImagePullBackOff",
    "ErrImagePull",
    "Pending",
    "Failed",
    "Terminating",
    "Unknown",
])

_SKIP_STATUSES = frozenset(["Completed", "Succeeded"])


def _is_pod_healthy(row: dict[str, str]) -> bool:
    """Return True if a pod row represents a healthy running pod."""
    status = row.get("status", "")
    if status in _UNHEALTHY_STATUSES:
        return False
    if status == "Running":
        ready = row.get("ready", "")
        if "/" in ready:
            parts = ready.split("/")
            try:
                return int(parts[0]) == int(parts[1])
            except ValueError:
                return False
        return True
    return False


def _is_pod_skip(row: dict[str, str]) -> bool:
    """Return True for terminal/completed pods to count but not show."""
    return row.get("status", "") in _SKIP_STATUSES


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

def _parse_table(lines: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """Parse a kubectl table into column names and row dicts."""
    if not lines:
        return [], []

    header = lines[0]
    # Build column boundaries from header
    col_names: list[str] = []
    col_starts: list[int] = []
    for m in re.finditer(r"\S+", header):
        col_names.append(m.group().lower())
        col_starts.append(m.start())

    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        row: dict[str, str] = {}
        for i, (name, start) in enumerate(zip(col_names, col_starts)):
            end = col_starts[i + 1] if i + 1 < len(col_starts) else len(line)
            value = line[start:end].strip() if start < len(line) else ""
            row[name] = value
        rows.append(row)
    return col_names, rows


# ---------------------------------------------------------------------------
# Describe parsing
# ---------------------------------------------------------------------------

_KEEP_SECTIONS = frozenset([
    "name", "namespace", "status", "node", "labels", "ip",
    "containers", "conditions", "events", "controlled by",
    "start time", "ready", "restart count", "state", "last state",
    "reason", "exit code",
])

_SKIP_ANNOTATION_KEYS = frozenset([
    "kubectl.kubernetes.io/last-applied-configuration",
    "kubernetes.io/config.seen",
    "kubernetes.io/config",
])


def _parse_describe(lines: list[str], verbose: bool) -> list[list[str]]:
    """Parse kubectl describe output into [section, key, value] rows."""
    rows: list[list[str]] = []
    current_section = "header"
    in_annotations = False
    annotation_depth = 0

    for line in lines:
        if not line.strip():
            in_annotations = False
            annotation_depth = 0
            continue

        # Detect section headers (lines ending with colon, minimal indent)
        section_m = re.match(r"^([A-Za-z][A-Za-z /\-]*):$", line.rstrip())
        if section_m:
            current_section = section_m.group(1).lower()
            in_annotations = False
            annotation_depth = 0
            continue

        # Key: value lines
        kv_m = re.match(r"^( *)([A-Za-z][A-Za-z /\-]*):\s*(.*)", line)
        if kv_m:
            indent = len(kv_m.group(1))
            key = kv_m.group(2).strip()
            value = kv_m.group(3).strip()
            key_lower = key.lower()

            # Handle annotations section
            if key_lower == "annotations":
                in_annotations = True
                annotation_depth = indent
                if verbose:
                    rows.append([current_section, key, value])
                continue

            if in_annotations:
                if indent > annotation_depth:
                    # Check if this annotation key should be skipped
                    ann_key = key.lower()
                    skip = any(skip_k in ann_key for skip_k in _SKIP_ANNOTATION_KEYS)
                    if not skip or verbose:
                        if verbose:
                            rows.append([current_section, key, value])
                    continue
                else:
                    in_annotations = False

            # Filter sections in non-verbose mode
            if not verbose:
                section_keep = any(
                    keep in current_section or current_section in keep
                    for keep in _KEEP_SECTIONS
                )
                key_keep = any(
                    keep in key_lower or key_lower in keep
                    for keep in _KEEP_SECTIONS
                )
                if not section_keep and not key_keep:
                    continue

            rows.append([current_section, key, value])
            continue

        # Continuation / indented lines (events table rows, conditions, etc.)
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            # Events table separator line
            if re.match(r"^[-\s]+$", stripped):
                continue
            if verbose or current_section in ("events", "conditions"):
                rows.append([current_section, "", stripped])

    return rows


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

_ERROR_RE = re.compile(r"\b(ERROR|FATAL|PANIC|Exception)\b", re.IGNORECASE)
_LOG_CONTEXT = 2
_HEAD_LINES = 10
_TAIL_LINES = 10


def _parse_logs(lines: list[str], verbose: bool) -> tuple[list[list[str]], str]:
    """Parse log lines with head/tail and error neighborhood."""
    if not lines:
        return [], "0 log lines"

    total = len(lines)
    error_count = sum(1 for ln in lines if _ERROR_RE.search(ln))

    if verbose:
        return [[ln] for ln in lines], f"{total} log lines, {error_count} error{'s' if error_count != 1 else ''}"

    # Collect indices to keep
    keep: set[int] = set()

    # Head
    for i in range(min(_HEAD_LINES, total)):
        keep.add(i)

    # Tail
    for i in range(max(0, total - _TAIL_LINES), total):
        keep.add(i)

    # Error neighborhoods
    for i, ln in enumerate(lines):
        if _ERROR_RE.search(ln):
            for j in range(max(0, i - _LOG_CONTEXT), min(total, i + _LOG_CONTEXT + 1)):
                keep.add(j)

    # Build output with gap markers
    output_rows: list[list[str]] = []
    sorted_indices = sorted(keep)
    prev_idx = -1
    for idx in sorted_indices:
        if prev_idx >= 0 and idx > prev_idx + 1:
            skipped = idx - prev_idx - 1
            output_rows.append([f"... ({skipped} line{'s' if skipped != 1 else ''} skipped)"])
        output_rows.append([lines[idx]])
        prev_idx = idx

    # Trailing gap
    if sorted_indices and sorted_indices[-1] < total - 1:
        remaining = total - 1 - sorted_indices[-1]
        output_rows.append([f"... ({remaining} line{'s' if remaining != 1 else ''} skipped)"])

    summary = f"{total} log lines, {error_count} error{'s' if error_count != 1 else ''}"
    return output_rows, summary


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class KubectlParser(BaseParser):
    id = "kubectl"
    hint_values = ["kubectl", "k8s"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()
        if not lines:
            return 0.0

        score = 0.0

        # Table detection
        for line in lines[:5]:
            if _TABLE_HEADER_RE.match(line.strip()):
                score += 0.6
                if _POD_TABLE_RE.search(line):
                    score += 0.2
                elif re.search(r"\bAGE\b", line):
                    # Other kubectl tables (services, nodes, etc.) — AGE column is k8s-specific
                    score += 0.15
                break

        # Describe detection
        has_name = any(_DESCRIBE_NAME_RE.match(ln) for ln in lines[:10])
        has_ns = any(_DESCRIBE_NS_RE.match(ln) for ln in lines[:15])
        if has_name and has_ns:
            score = max(score, 0.7)

        # Log detection
        if score < 0.4:
            ts_count = sum(1 for ln in lines if _TIMESTAMP_RE.match(ln))
            if ts_count >= 5:
                score = max(score, 0.4 + min(ts_count * 0.01, 0.55))

        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Detect sub-format
        is_table = any(_TABLE_HEADER_RE.match(ln.strip()) for ln in lines[:5])
        has_name = any(_DESCRIBE_NAME_RE.match(ln) for ln in lines[:10])
        has_ns = any(_DESCRIBE_NS_RE.match(ln) for ln in lines[:15])
        is_describe = has_name and has_ns

        ts_count = sum(1 for ln in lines if _TIMESTAMP_RE.match(ln))
        is_logs = ts_count >= 5

        if is_table:
            return self._parse_table_output(lines, verbose)
        elif is_describe:
            return self._parse_describe_output(lines, verbose)
        elif is_logs:
            return self._parse_log_output(lines, verbose)
        else:
            # Fallback: treat as generic lines
            rows = [[ln] for ln in lines if ln.strip()]
            return ParseResult(
                tool="kubectl",
                summary=f"{len(rows)} lines",
                schema=["line"],
                rows=rows,
                verbose=verbose,
            )

    def _parse_table_output(self, lines: list[str], verbose: bool) -> ParseResult:
        # Find header line
        header_idx = next(
            (i for i, ln in enumerate(lines) if _TABLE_HEADER_RE.match(ln.strip())),
            0,
        )
        col_names, dicts = _parse_table(lines[header_idx:])

        is_pod_table = "status" in col_names and "ready" in col_names

        if is_pod_table and not verbose:
            healthy = 0
            unhealthy_rows: list[list[str]] = []
            completed = 0

            for d in dicts:
                if _is_pod_skip(d):
                    completed += 1
                elif _is_pod_healthy(d):
                    healthy += 1
                else:
                    unhealthy_rows.append([d.get(c, "") for c in col_names])

            total = len(dicts)
            unhealthy_count = total - healthy - completed
            summary = (
                f"{total} pods ({healthy} healthy"
                + (f", {completed} completed" if completed else "")
                + (f", {unhealthy_count} unhealthy" if unhealthy_count else "")
                + ")"
            )
            return ParseResult(
                tool="kubectl",
                summary=summary,
                schema=col_names,
                rows=unhealthy_rows,
                verbose=verbose,
            )

        # Non-pod table or verbose: all rows
        rows = [[d.get(c, "") for c in col_names] for d in dicts]
        n = len(rows)
        kind = "pod" if is_pod_table else "row"
        summary = f"{n} {kind}{'s' if n != 1 else ''}"
        return ParseResult(
            tool="kubectl",
            summary=summary,
            schema=col_names,
            rows=rows,
            verbose=verbose,
        )

    def _parse_describe_output(self, lines: list[str], verbose: bool) -> ParseResult:
        rows = _parse_describe(lines, verbose)

        # Extract name for summary
        name = ""
        status = ""
        for row in rows:
            if row[1].lower() == "name" and not name:
                name = row[2]
            if row[1].lower() == "status" and not status:
                status = row[2]

        summary_parts = []
        if name:
            summary_parts.append(name)
        if status:
            summary_parts.append(status)
        summary = " — ".join(summary_parts) if summary_parts else f"{len(rows)} fields"

        return ParseResult(
            tool="kubectl",
            summary=summary,
            schema=["section", "key", "value"],
            rows=rows,
            verbose=verbose,
        )

    def _parse_log_output(self, lines: list[str], verbose: bool) -> ParseResult:
        log_lines = [ln for ln in lines if ln.strip()]
        rows, summary = _parse_logs(log_lines, verbose)
        return ParseResult(
            tool="kubectl",
            summary=summary,
            schema=["line"],
            rows=rows,
            verbose=verbose,
        )
