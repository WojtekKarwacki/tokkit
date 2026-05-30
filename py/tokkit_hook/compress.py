"""tokkit compress — run a command and compress its output."""

from __future__ import annotations

import subprocess
import sys

from tokkit_hook.match import match_command


def run_and_compress(command: str) -> int:
    """Run command, compress output via compact_output, print result, return exit code."""
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
    )

    raw_output = result.stdout.decode("utf-8", errors="replace")

    hint = match_command(command)

    from tokkit_output import compact_output
    compressed = compact_output(raw_output, hint=hint)

    print(compressed, end="")

    _record_savings(hint, raw_output, compressed)

    return result.returncode


def _record_savings(hint: str | None, raw_output: str, compressed: str) -> None:
    """Record this compression to persistent stats. Best-effort — never raises."""
    try:
        from tokkit_server.token_stats import record_bash_compression
        record_bash_compression(hint, raw_output, compressed)
    except Exception:
        pass


def main() -> None:
    """Entry point: python -m tokkit_hook.compress '<command>'."""
    if len(sys.argv) < 2:
        print("Usage: tokkit compress '<command>'", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    exit_code = run_and_compress(command)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
