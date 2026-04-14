"""Environment variable output parser with sensitive value redaction."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_ENV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

_MIN_LINES_FOR_DETECT = 5

_SENSITIVE_RE = re.compile(
    r"KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AUTH|PRIVATE",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


class EnvRedactParser(BaseParser):
    id = "env-redact"
    hint_values = ["env", "printenv"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        lines = clean.splitlines()
        count = sum(1 for ln in lines if _ENV_LINE_RE.match(ln))
        if count >= _MIN_LINES_FOR_DETECT:
            return 0.8
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()

        rows: list[list[str]] = []
        redacted_count = 0

        for line in lines:
            m = _ENV_LINE_RE.match(line)
            if not m:
                continue
            key = m.group(1)
            value = m.group(2)

            if _SENSITIVE_RE.search(key):
                rows.append([key, _REDACTED])
                redacted_count += 1
            else:
                rows.append([key, value])

        total = len(rows)
        summary = f"{total} vars ({redacted_count} redacted)"

        return ParseResult(
            tool="env-redact",
            summary=summary,
            schema=["key", "value"],
            rows=rows,
            verbose=verbose,
        )
