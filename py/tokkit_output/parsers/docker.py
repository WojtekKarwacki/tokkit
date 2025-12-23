"""Docker build output parser."""

import re

from tokkit_output.base import BaseParser, ParseResult
from tokkit_output.universal import strip_ansi

_SCHEMA = ["step", "status", "message"]

# [+] Building 12.3s (8/8) FINISHED
_BUILDING_RE = re.compile(r"^\[\\+\] Building")
_BUILDING_ALT_RE = re.compile(r"^\[\+\] Building")

# => [N/M] RUN apt-get install ...
# => ERROR [N/M] RUN npm install
_STEP_RE = re.compile(r"^\s*=> (?:(ERROR) )?\[(\d+)/(\d+)\]\s+(.+)$")

# ERROR: failed to solve: ...
_FINAL_ERROR_RE = re.compile(r"^ERROR:\s+(.+)$")

# => [internal/docker] ...  (these are not user steps)
_INTERNAL_RE = re.compile(r"\[internal/")


class DockerParser(BaseParser):
    id = "docker"
    hint_values = ["docker", "docker-build"]

    def detect(self, text: str) -> float:
        clean = strip_ansi(text)
        if _BUILDING_ALT_RE.search(clean) or re.search(r"=> \[", clean):
            return 0.85
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        clean = strip_ansi(text)
        lines = clean.splitlines()
        rows: list[list[str]] = []
        n_errors = 0

        for line in lines:
            sm = _STEP_RE.match(line)
            if sm:
                is_error = sm.group(1) == "ERROR"
                step_num = sm.group(2)
                step_total = sm.group(3)
                command = sm.group(4).strip()
                step_label = f"[{step_num}/{step_total}]"

                if _INTERNAL_RE.search(command):
                    continue

                if is_error:
                    n_errors += 1
                    rows.append([step_label, "ERROR", command])
                elif verbose:
                    rows.append([step_label, "ok", command])
                continue

            em = _FINAL_ERROR_RE.match(line.strip())
            if em:
                n_errors += 1
                rows.append(["", "ERROR", em.group(1)])

        if n_errors == 0:
            summary = "Build succeeded"
        else:
            summary = f"{n_errors} error{'s' if n_errors != 1 else ''}"

        return ParseResult(
            tool="docker",
            summary=summary,
            schema=_SCHEMA,
            rows=rows,
            verbose=verbose,
        )
