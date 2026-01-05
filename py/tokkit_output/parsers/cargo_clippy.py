"""cargo clippy output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["file", "line", "col", "rule", "severity", "message"]

# "warning: message" or "error: message" (without code brackets for clippy style)
_DIAG_START_RE = re.compile(r"^(warning|error):\s+(.+)$")

# --> src/main.rs:10:5
_LOCATION_RE = re.compile(r"^\s+-->\s+([^:]+):(\d+):(\d+)")

# = note: `#[warn(clippy::needless_return)]` on by default
_NOTE_RULE_RE = re.compile(r"clippy::([a-z_]+)")

# "generated N warning" or "generated N warnings"
_GENERATED_RE = re.compile(r"generated \d+ warning")


class CargoClippyParser(BaseParser):
    id = "cargo-clippy"
    hint_values = ["cargo-clippy", "clippy"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        has_generated = bool(_GENERATED_RE.search(clean))
        has_clippy = "clippy" in clean.lower() or bool(_LOCATION_RE.search(clean))
        if has_generated and has_clippy:
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()
        rows: list[list[str]] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            m = _DIAG_START_RE.match(line)
            if m:
                severity = m.group(1)
                message = m.group(2).strip()

                # Skip the unhelpful aborting/error summary lines
                if message in ("aborting due to previous error",
                               "aborting due to previous errors",
                               "could not compile"):
                    i += 1
                    continue

                # Skip lines that are just lint count summaries
                if _GENERATED_RE.search(line):
                    i += 1
                    continue

                # Scan ahead for location and rule
                file_ = ""
                line_no = ""
                col = ""
                rule = ""

                for j in range(i + 1, min(i + 15, len(lines))):
                    next_line = lines[j]

                    if not file_:
                        lm = _LOCATION_RE.match(next_line)
                        if lm:
                            file_ = lm.group(1)
                            line_no = lm.group(2)
                            col = lm.group(3)

                    if not rule:
                        rm = _NOTE_RULE_RE.search(next_line)
                        if rm:
                            rule = "clippy::" + rm.group(1)

                    # Stop scanning when we hit the next diagnostic header
                    if j > i + 1 and _DIAG_START_RE.match(next_line):
                        break

                rows.append([file_, line_no, col, rule, severity, message])

            i += 1

        n = len(rows)
        summary = f"{n} warning{'s' if n != 1 else ''}"

        return ParseResult(
            tool="cargo-clippy",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
