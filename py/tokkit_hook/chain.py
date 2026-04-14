"""Chain splitting — split shell command chains respecting quotes."""

from __future__ import annotations

_SILENT_PREFIXES: tuple[str, ...] = (
    "cd ",
    "cd\t",
    "mkdir",
    "cp ",
    "cp\t",
    "mv ",
    "mv\t",
    "rm ",
    "rm\t",
    "export ",
    "source ",
    ". ",
    ".\t",
    "pushd",
    "popd",
    "set ",
    "set\t",
    "unset ",
    "unset\t",
    "alias",
    "ulimit",
    "git add",
    "git checkout",
    "git stash push",
    "git stash pop",
    "git stash drop",
)

# Commands that are silent when alone (no args needed)
_SILENT_EXACT: frozenset[str] = frozenset({"pushd", "popd", "alias"})


def split_chain(command: str) -> list[str]:
    """Split a shell command on && and ; while respecting single and double quotes."""
    parts: list[str] = []
    current: list[str] = []
    i = 0
    n = len(command)

    while i < n:
        ch = command[i]

        if ch in ('"', "'"):
            quote = ch
            current.append(ch)
            i += 1
            while i < n:
                c = command[i]
                current.append(c)
                if c == quote:
                    i += 1
                    break
                i += 1
            continue

        if ch == '&' and i + 1 < n and command[i + 1] == '&':
            parts.append("".join(current).strip())
            current = []
            i += 2
            continue

        if ch == ';':
            parts.append("".join(current).strip())
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)

    return [p for p in parts if p]


def _is_silent(cmd: str) -> bool:
    """Return True if command is a silent side-effect command."""
    stripped = cmd.strip()
    for prefix in _SILENT_PREFIXES:
        if stripped.startswith(prefix):
            return True
    if stripped in _SILENT_EXACT:
        return True
    return False


def find_primary(commands: list[str]) -> str:
    """Return the last non-silent command; fall back to last command if all are silent."""
    for cmd in reversed(commands):
        if not _is_silent(cmd):
            return cmd
    return commands[-1] if commands else ""
