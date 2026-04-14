"""Docker ps + images output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_PS_HEADER_RE = re.compile(r"CONTAINER\s+ID", re.IGNORECASE)
_IMAGES_HEADER_RE = re.compile(r"REPOSITORY\s+TAG", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_PS_SCHEMA = ["name", "image", "status", "ports"]
_IMAGES_SCHEMA = ["repository", "tag", "size", "created"]

# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

_RUNNING_RE = re.compile(r"^Up\b", re.IGNORECASE)
_STOPPED_RE = re.compile(r"^(Exited|Created|Paused|Dead|Restarting)\b", re.IGNORECASE)


def _is_running(status: str) -> bool:
    return bool(_RUNNING_RE.match(status.strip()))


def _is_stopped(status: str) -> bool:
    return bool(_STOPPED_RE.match(status.strip()))


# ---------------------------------------------------------------------------
# Generic table parser
# ---------------------------------------------------------------------------

def _parse_table(lines: list[str], header_re: re.Pattern) -> tuple[list[str], list[dict[str, str]]]:
    """Parse a docker table into (column_names, row_dicts)."""
    header_idx = next(
        (i for i, ln in enumerate(lines) if header_re.search(ln)),
        None,
    )
    if header_idx is None:
        return [], []

    header = lines[header_idx]
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
    return col_names, rows


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class DockerPsParser(BaseParser):
    id = "docker-ps"
    hint_values = ["docker-ps", "docker-images"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        for line in lines[:5]:
            if _PS_HEADER_RE.search(line):
                return 0.85
            if _IMAGES_HEADER_RE.search(line):
                return 0.8

        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        is_images = any(_IMAGES_HEADER_RE.search(ln) for ln in lines[:5])
        is_ps = any(_PS_HEADER_RE.search(ln) for ln in lines[:5])

        if is_images:
            return self._parse_images(lines, verbose)
        elif is_ps:
            return self._parse_ps(lines, verbose)
        else:
            rows = [[ln] for ln in lines if ln.strip()]
            return ParseResult(
                tool="docker-ps",
                summary=f"{len(rows)} lines",
                schema=["line"],
                rows=rows,
                verbose=verbose,
            )

    def _parse_ps(self, lines: list[str], verbose: bool) -> ParseResult:
        col_names, dicts = _parse_table(lines, _PS_HEADER_RE)
        total = len(dicts)
        running_count = 0
        stopped_count = 0
        result_rows: list[list[str]] = []

        for d in dicts:
            status = d.get("status", "")
            name = d.get("names", "")
            image = d.get("image", "")
            ports = d.get("ports", "")

            if _is_running(status):
                running_count += 1
                if verbose:
                    result_rows.append([name, image, status, ports])
                else:
                    result_rows.append([name, image, status, ports])
            else:
                stopped_count += 1
                if verbose:
                    result_rows.append([name, image, status, ports])
                # In default mode: stopped containers are elided (counted only)

        if stopped_count == 0:
            summary = f"{total} containers ({running_count} running)"
        else:
            summary = f"{total} containers ({running_count} running, {stopped_count} stopped)"

        rows_out = result_rows if verbose else [r for r in result_rows if _is_running(r[2])]
        return ParseResult(
            tool="docker-ps",
            summary=summary,
            schema=_PS_SCHEMA,
            rows=rows_out,
            verbose=verbose,
        )

    def _parse_images(self, lines: list[str], verbose: bool) -> ParseResult:
        col_names, dicts = _parse_table(lines, _IMAGES_HEADER_RE)
        total = len(dicts)
        result_rows: list[list[str]] = []

        for d in dicts:
            repo = d.get("repository", "")
            tag = d.get("tag", "")
            size = d.get("size", "")
            created = d.get("created", "")
            result_rows.append([repo, tag, size, created])

        summary = f"{total} image{'s' if total != 1 else ''}"
        return ParseResult(
            tool="docker-ps",
            summary=summary,
            schema=_IMAGES_SCHEMA,
            rows=result_rows,
            verbose=verbose,
        )
