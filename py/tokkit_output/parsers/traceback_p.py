"""Python traceback output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["exception", "file", "line", "function", "message"]

# Traceback header
_TB_HEADER_RE = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)

# Frame line: '  File "path", line N, in func_name'
_FRAME_RE = re.compile(r'^\s+File "([^"]+)", line (\d+), in (\S+)')

# Exception line: "ExceptionType: message" or just "ExceptionType"
_EXCEPTION_RE = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Interrupt|Exit|Stop|Fault|Break|Miss|Full|Empty|Overflow|Underflow|Mismatch|Timeout|Abort|Kill|Denied|Refused|Reset|Closed|Dropped|Lost|Expired|Invalid|Illegal|Bad|Corrupt|Failed|Panic|Fatal|Critical)[\w.]*|[A-Za-z_][\w.]*Error|[A-Za-z_][\w.]*Exception|KeyboardInterrupt|SystemExit|StopIteration|StopAsyncIteration|GeneratorExit)(?::\s*(.*))?$")

# Chained exception markers
_CHAINED_CAUSE_RE = re.compile(
    r"^(?:The above exception was the direct cause of the following exception:|"
    r"During handling of the above exception, another exception occurred:)$"
)


def _split_tracebacks(text: str) -> list[str]:
    """Split text into individual traceback blocks."""
    lines = text.splitlines(keepends=True)
    blocks: list[str] = []
    current: list[str] = []
    in_tb = False

    for line in lines:
        if _TB_HEADER_RE.match(line.rstrip()):
            if current and in_tb:
                blocks.append("".join(current))
            current = [line]
            in_tb = True
        elif in_tb:
            if _CHAINED_CAUSE_RE.match(line.strip()):
                # End current block at chained marker, then start fresh after
                blocks.append("".join(current))
                current = []
                in_tb = False
            else:
                current.append(line)
    if current and in_tb:
        blocks.append("".join(current))
    return blocks


def _parse_single_traceback(block: str) -> list[dict]:
    """Parse one traceback block into frame dicts."""
    lines = block.splitlines()
    frames: list[dict] = []
    exception_type = ""
    exception_msg = ""

    # Find all frames
    for line in lines:
        m = _FRAME_RE.match(line)
        if m:
            frames.append({
                "file": m.group(1),
                "line": m.group(2),
                "function": m.group(3),
            })

    # Find exception on the last non-blank line
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip frame source lines (indented code lines)
        if line.startswith("    ") and not stripped.startswith("File "):
            # Could be exception or source code — check if it looks like an exception
            em = _EXCEPTION_RE.match(stripped)
            if em:
                exception_type = em.group(1)
                exception_msg = em.group(2) or ""
                break
            continue
        em = _EXCEPTION_RE.match(stripped)
        if em:
            exception_type = em.group(1)
            exception_msg = em.group(2) or ""
            break
        # Check for bare exception line without "Error" suffix (e.g. "ValueError: ...")
        if ":" in stripped:
            parts = stripped.split(":", 1)
            if re.match(r"^[A-Za-z_][\w.]*$", parts[0]) and parts[0][0].isupper():
                exception_type = parts[0]
                exception_msg = parts[1].strip()
                break
        break

    return frames, exception_type, exception_msg


class TracebackParser(BaseParser):
    id = "python-traceback"
    hint_values = ["traceback"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _TB_HEADER_RE.search(clean):
            return 0.95
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        blocks = _split_tracebacks(clean)
        rows = []

        for block in blocks:
            frames, exc_type, exc_msg = _parse_single_traceback(block)
            if not frames:
                continue
            if verbose:
                for frame in frames:
                    rows.append([
                        exc_type,
                        frame["file"],
                        frame["line"],
                        frame["function"],
                        exc_msg,
                    ])
            else:
                # Default: only last frame per exception
                last = frames[-1]
                rows.append([
                    exc_type,
                    last["file"],
                    last["line"],
                    last["function"],
                    exc_msg,
                ])

        n = len(blocks)
        if n == 0:
            summary = "no traceback found"
        elif n == 1:
            if rows:
                exc = rows[0][0]
                summary = exc if exc else "1 exception"
            else:
                summary = "1 exception"
        else:
            summary = f"{n} exceptions"

        return ParseResult(
            tool="python-traceback",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
