"""Vite build output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["step", "status", "message"]

# Detection: "error during build" or vite-specific build phrases
_ERROR_BUILD_RE = re.compile(r"error during build", re.IGNORECASE)
_VITE_RE = re.compile(r"\bvite\b", re.IGNORECASE)

# TS-style error inside vite output: "src/api.ts(42,5): error TS2322: ..."
_TSC_DIAG_RE = re.compile(r"^(.+?)\((\d+),\d+\):\s+error\s+(TS\d+):\s+(.+)$")

# Generic "Error: ..." lines
_GENERIC_ERR_RE = re.compile(r"^(Error|TypeError|ReferenceError|SyntaxError):\s+(.+)$", re.IGNORECASE)

# "Plugin vite:..." lines that wrap errors
_PLUGIN_RE = re.compile(r"Plugin\s+(\S+)\s+reported:", re.IGNORECASE)


class ViteParser(BaseParser):
    id = "vite"
    hint_values = ["vite"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _ERROR_BUILD_RE.search(clean):
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        for line in clean.splitlines():
            stripped = line.strip()

            # TypeScript diagnostic inside vite output
            m = _TSC_DIAG_RE.match(stripped)
            if m:
                step = f"{m.group(1)}:{m.group(2)}"
                code = m.group(3)
                message = m.group(4).strip()
                rows.append([step, "error", f"{code}: {message}"])
                continue

            # Generic error lines
            gm = _GENERIC_ERR_RE.match(stripped)
            if gm:
                rows.append(["build", "error", stripped])
                continue

        # If no structured errors found, add a single generic entry
        if not rows and _ERROR_BUILD_RE.search(clean):
            # Extract first meaningful line after "error during build"
            lines = clean.splitlines()
            found = False
            for line in lines:
                if _ERROR_BUILD_RE.search(line):
                    found = True
                    continue
                if found:
                    stripped = line.strip()
                    if stripped:
                        rows.append(["build", "error", stripped])
                        break

        n = len(rows)
        summary = f"{n} error{'s' if n != 1 else ''}"

        return ParseResult(
            tool="vite",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
