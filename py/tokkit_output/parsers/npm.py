"""npm output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["package", "status", "message"]

# Detection
_NPM_WARN_RE = re.compile(r"npm warn\b", re.IGNORECASE)
_NPM_ERROR_RE = re.compile(r"npm (?:error|ERR!)\b", re.IGNORECASE)

# "npm warn ERESOLVE overriding peer dependency"
# "npm warn peer dep missing: react@^18.0.0, required by some-package@1.0.0"
_PEER_WARN_RE = re.compile(
    r"^npm warn\s+(?:peer dep\w*\s+)?(.+)$", re.IGNORECASE
)

# "npm error code ERESOLVE"  or  "npm ERR! code ERESOLVE"
_ERR_CODE_RE = re.compile(r"^npm\s+(?:error|ERR!)\s+(.+)$", re.IGNORECASE)

# Peer dependency conflict:
# "npm warn While resolving: foo@1.0.0"  +  "npm warn Found: bar@2.0.0"
# "npm warn Could not resolve dependency: peer bar@"^1.0.0" from foo@1.0.0"
_CONFLICT_RE = re.compile(
    r"Could not resolve dependency:\s+peer\s+(\S+)\s+from\s+(\S+)",
    re.IGNORECASE,
)

# "npm warn deprecated package@version: message"
_DEPRECATED_RE = re.compile(
    r"^npm warn\s+deprecated\s+(\S+):\s+(.+)$", re.IGNORECASE
)


class NpmParser(BaseParser):
    id = "npm"
    hint_values = ["npm"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _NPM_WARN_RE.search(clean) or _NPM_ERROR_RE.search(clean):
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        rows = []

        for line in clean.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Peer dependency conflict
            cm = _CONFLICT_RE.search(stripped)
            if cm:
                peer_dep = cm.group(1)
                from_pkg = cm.group(2)
                rows.append([peer_dep, "peer-conflict", f"required by {from_pkg}"])
                continue

            # Deprecated package warning
            dm = _DEPRECATED_RE.match(stripped)
            if dm:
                package = dm.group(1)
                message = dm.group(2).strip()
                rows.append([package, "deprecated", message])
                continue

            # Generic error lines
            em = _ERR_CODE_RE.match(stripped)
            if em:
                msg = em.group(1).strip()
                # Skip pure code/path lines that add noise
                if msg.startswith("code ") or msg.startswith("path ") or msg.startswith("node "):
                    pkg_m = re.search(r"node_modules/([^/\s]+)", msg)
                    if pkg_m:
                        rows.append([pkg_m.group(1), "error", msg])
                    else:
                        rows.append(["npm", "error", msg])
                else:
                    rows.append(["npm", "error", msg])
                continue

        n = len(rows)
        summary = f"{n} issue{'s' if n != 1 else ''}"

        return ParseResult(
            tool="npm",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
