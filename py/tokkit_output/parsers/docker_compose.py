"""Docker Compose ps + logs output parser."""

import re
from collections import defaultdict

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_PS_HEADER_RE = re.compile(r"NAME\s+IMAGE\s+COMMAND\s+SERVICE", re.IGNORECASE)
_LOG_PREFIX_RE = re.compile(r"^[\w][\w.-]*\s*\|\s")

# ---------------------------------------------------------------------------
# PS parsing
# ---------------------------------------------------------------------------

_PS_SCHEMA = ["service", "status", "ports"]

_UNHEALTHY_STATUS_RE = re.compile(r"\b(Exited|Restarting|Dead|Error|OOMKilled)\b", re.IGNORECASE)
_HEALTHY_STATUS_RE = re.compile(r"\bUp\b", re.IGNORECASE)
_HEALTH_CHECK_RE = re.compile(r"\((healthy|running)\)", re.IGNORECASE)


def _is_compose_healthy(status: str) -> bool:
    """Return True if status represents a healthy service."""
    if not _HEALTHY_STATUS_RE.search(status):
        return False
    if _UNHEALTHY_STATUS_RE.search(status):
        return False
    return True


def _is_compose_unhealthy(status: str) -> bool:
    """Return True if status represents an unhealthy service."""
    return bool(_UNHEALTHY_STATUS_RE.search(status))


def _parse_compose_ps_table(lines: list[str]) -> list[dict[str, str]]:
    """Parse docker compose ps table into row dicts keyed by header column."""
    if not lines:
        return []

    # Find header line
    header_idx = next(
        (i for i, ln in enumerate(lines) if _PS_HEADER_RE.search(ln)),
        None,
    )
    if header_idx is None:
        return []

    header = lines[header_idx]

    # Build column boundaries from header positions
    col_names: list[str] = []
    col_starts: list[int] = []
    for m in re.finditer(r"\S+", header):
        col_names.append(m.group().lower())
        col_starts.append(m.start())

    rows: list[dict[str, str]] = []
    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        if not stripped or re.match(r"^[-\s]+$", stripped):
            continue
        row: dict[str, str] = {}
        for i, (name, start) in enumerate(zip(col_names, col_starts)):
            end = col_starts[i + 1] if i + 1 < len(col_starts) else len(line)
            value = line[start:end].strip() if start < len(line) else ""
            row[name] = value
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Logs parsing
# ---------------------------------------------------------------------------

_LOG_SCHEMA = ["service", "line"]
_ERROR_RE = re.compile(r"\b(ERROR|FATAL|PANIC|Exception)\b")
_LOG_HEAD = 5
_LOG_TAIL = 5
_LOG_CONTEXT = 1


def _parse_compose_logs(lines: list[str], verbose: bool) -> tuple[list[list[str]], str]:
    """Group compose log lines by service, compress per-service."""
    # Group lines by service
    service_lines: dict[str, list[str]] = defaultdict(list)
    service_order: list[str] = []

    for line in lines:
        m = _LOG_PREFIX_RE.match(line)
        if m:
            service = line[:m.end()].split("|")[0].strip()
            rest = line[m.end():]
            if service not in service_lines:
                service_order.append(service)
            service_lines[service].append(rest)
        else:
            # Continuation line — attach to last service or generic
            svc = service_order[-1] if service_order else "_"
            service_lines[svc].append(line)

    total_lines = sum(len(v) for v in service_lines.values())
    n_services = len(service_order)

    rows: list[list[str]] = []

    if verbose:
        for svc in service_order:
            for ln in service_lines[svc]:
                rows.append([svc, ln])
        summary = f"{n_services} services, {total_lines} log lines"
        return rows, summary

    for svc in service_order:
        svc_lines = service_lines[svc]
        total = len(svc_lines)

        # Collect indices to keep
        keep: set[int] = set()
        for i in range(min(_LOG_HEAD, total)):
            keep.add(i)
        for i in range(max(0, total - _LOG_TAIL), total):
            keep.add(i)
        for i, ln in enumerate(svc_lines):
            if _ERROR_RE.search(ln):
                for j in range(max(0, i - _LOG_CONTEXT), min(total, i + _LOG_CONTEXT + 1)):
                    keep.add(j)

        sorted_indices = sorted(keep)
        prev_idx = -1
        for idx in sorted_indices:
            if prev_idx >= 0 and idx > prev_idx + 1:
                skipped = idx - prev_idx - 1
                rows.append([svc, f"... ({skipped} line{'s' if skipped != 1 else ''} skipped)"])
            rows.append([svc, svc_lines[idx]])
            prev_idx = idx

        if sorted_indices and sorted_indices[-1] < total - 1:
            remaining = total - 1 - sorted_indices[-1]
            rows.append([svc, f"... ({remaining} line{'s' if remaining != 1 else ''} skipped)"])

    summary = f"{n_services} services, {total_lines} log lines"
    return rows, summary


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class DockerComposeParser(BaseParser):
    id = "docker-compose"
    hint_values = ["docker-compose", "docker compose"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # PS table header
        for line in lines[:5]:
            if _PS_HEADER_RE.search(line):
                return 0.7

        # Compose logs prefix pattern — require 3+ matching lines
        prefix_count = sum(1 for ln in lines if _LOG_PREFIX_RE.match(ln))
        if prefix_count >= 3:
            return 0.7

        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        # Detect sub-format
        is_ps = any(_PS_HEADER_RE.search(ln) for ln in lines[:5])
        prefix_count = sum(1 for ln in lines if _LOG_PREFIX_RE.match(ln))
        is_logs = prefix_count >= 3

        if is_ps:
            return self._parse_ps(lines, verbose)
        elif is_logs:
            return self._parse_logs(lines, verbose)
        else:
            rows = [[ln] for ln in lines if ln.strip()]
            return ParseResult(
                tool="docker-compose",
                summary=f"{len(rows)} lines",
                schema=["line"],
                rows=rows,
                verbose=verbose,
            )

    def _parse_ps(self, lines: list[str], verbose: bool) -> ParseResult:
        dicts = _parse_compose_ps_table(lines)
        total = len(dicts)

        unhealthy_rows: list[list[str]] = []
        healthy_count = 0

        for d in dicts:
            status = d.get("status", "")
            service = d.get("service", d.get("name", ""))
            ports = d.get("ports", "")

            if _is_compose_unhealthy(status):
                unhealthy_rows.append([service, status, ports])
            elif verbose:
                unhealthy_rows.append([service, status, ports])
            else:
                healthy_count += 1

        unhealthy_count = total - healthy_count

        if unhealthy_count == 0:
            summary = f"{total} services, all healthy"
        else:
            summary = f"{total} services ({healthy_count} healthy, {unhealthy_count} unhealthy)"

        return ParseResult(
            tool="docker-compose",
            summary=summary,
            schema=_PS_SCHEMA,
            rows=unhealthy_rows,
            verbose=verbose,
        )

    def _parse_logs(self, lines: list[str], verbose: bool) -> ParseResult:
        rows, summary = _parse_compose_logs(lines, verbose)
        return ParseResult(
            tool="docker-compose",
            summary=summary,
            schema=_LOG_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
