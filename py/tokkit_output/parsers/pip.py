"""Pip output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["package", "status", "message"]

# pip's dependency resolver does not currently take into account all the packages...
_RESOLVER_RE = re.compile(r"pip'?s? dependency resolver", re.IGNORECASE)

# "Collecting <package>"
_COLLECTING_RE = re.compile(r"^Collecting\s+(\S+)", re.IGNORECASE)

# "Successfully installed ..."
_SUCCESS_RE = re.compile(r"Successfully installed\s+(.+)", re.IGNORECASE)

# "ERROR: ..."
_ERROR_RE = re.compile(r"^ERROR:\s+(.+)$", re.IGNORECASE | re.MULTILINE)

# Conflict lines from resolver output:
# "package1 X.Y requires package2>=A.B, but you have package2 C.D which is incompatible."
_CONFLICT_RE = re.compile(
    r"^(\S+)\s+[\d.]+\s+requires\s+(\S+),\s+but you have\s+(.+)\s+which is incompatible",
    re.IGNORECASE,
)

# "Installing collected packages: ..."
_INSTALLING_RE = re.compile(r"^Installing collected packages", re.IGNORECASE)


class PipParser(BaseParser):
    id = "pip"
    hint_values = ["pip"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        score = 0.0
        if _RESOLVER_RE.search(clean):
            score += 0.5
        if _COLLECTING_RE.search(clean):
            score += 0.3
        if _INSTALLING_RE.search(clean) or _SUCCESS_RE.search(clean):
            score += 0.2
        if _ERROR_RE.search(clean):
            score += 0.3
        return min(score, 1.0)

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        for line in clean.splitlines():
            stripped = line.strip()

            # Dependency conflict lines
            m = _CONFLICT_RE.match(stripped)
            if m:
                package = m.group(1)
                required = m.group(2)
                installed = m.group(3).strip()
                rows.append([package, "conflict", f"requires {required}, have {installed}"])
                continue

            # ERROR lines
            em = _ERROR_RE.match(stripped)
            if em:
                msg = em.group(1).strip()
                # Extract package name if present
                pkg_m = re.match(r"Could not (?:find|install) a version.*?for\s+(\S+)", msg, re.IGNORECASE)
                if pkg_m:
                    rows.append([pkg_m.group(1), "error", msg])
                else:
                    rows.append(["pip", "error", msg])
                continue

        success_m = _SUCCESS_RE.search(clean)
        if rows:
            n = len(rows)
            summary = f"{n} issue{'s' if n != 1 else ''}"
        elif success_m:
            packages = success_m.group(1).strip()
            summary = f"installed successfully: {packages}"
        else:
            summary = "0 issues"

        return ParseResult(
            tool="pip",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
