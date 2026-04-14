"""Command-to-hint pattern matching for tokkit hook."""

from __future__ import annotations

# Source file extensions that should not be compressed
_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".rb", ".go", ".rs", ".java",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala",
    ".sh", ".bash", ".zsh", ".fish",
})

# Commands that should always pass through (no compression)
_PASSTHROUGH_COMMANDS = frozenset({
    "bat", "batcat", "vim", "nvim", "nano", "less", "more", "ssh", "sudo",
})

# Ordered table: (prefix, hint). First match wins.
_PATTERNS: list[tuple[str, str]] = [
    # git
    ("git diff", "git-diff"),
    ("git status", "git-status"),
    ("git log", "git-log"),
    ("git show", "git-show"),
    ("git blame", "git-blame"),
    ("git branch", "git-branch"),
    ("git stash list", "git-stash"),
    # python test
    ("pytest", "pytest"),
    ("python -m pytest", "pytest"),
    ("python3 -m pytest", "pytest"),
    # python unittest
    ("python -m unittest", "unittest"),
    ("python3 -m unittest", "unittest"),
    # python lint/type
    ("ruff check", "ruff"),
    ("ruff .", "ruff"),
    ("mypy", "mypy"),
    ("pyright", "pyright"),
    # pip
    ("pip list", "pip-list"),
    ("pip freeze", "pip-freeze"),
    ("pip install", "pip"),
    # js test
    ("jest", "jest"),
    ("npx jest", "jest"),
    ("yarn jest", "jest"),
    ("pnpm jest", "jest"),
    # js vitest
    ("vitest", "vitest"),
    ("npx vitest", "vitest"),
    ("yarn vitest", "vitest"),
    # js mocha
    ("mocha", "mocha"),
    ("npx mocha", "mocha"),
    # js lint/type
    ("eslint", "eslint"),
    ("npx eslint", "eslint"),
    ("tsc", "tsc"),
    ("npx tsc", "tsc"),
    # js build
    ("webpack", "webpack"),
    ("npx webpack", "webpack"),
    ("vite build", "vite"),
    ("npx vite build", "vite"),
    # npm
    ("npm install", "npm"),
    ("npm ci", "npm"),
    ("npm run build", "npm"),
    ("npm test", "npm"),
    ("npm run", "npm"),
    # cargo
    ("cargo test", "cargo-test"),
    ("cargo build", "cargo-build"),
    ("cargo check", "cargo-build"),
    ("cargo clippy", "cargo-clippy"),
    # docker
    ("docker compose", "docker-compose"),
    ("docker-compose", "docker-compose"),
    ("docker build", "docker"),
    ("docker ps", "docker-ps"),
    ("docker images", "docker-images"),
    ("docker logs", "docker-logs"),
    # kubernetes
    ("kubectl", "kubectl"),
    # shell search
    ("grep -r", "grep"),
    ("grep -rn", "grep"),
    ("grep --include", "grep"),
    ("rg ", "rg"),
    ("ag ", "ag"),
    # file listing
    ("ls", "ls"),
    ("tree", "tree"),
    ("find ", "find"),
    # github cli
    ("gh pr", "gh"),
    ("gh issue", "gh"),
    ("gh run", "gh"),
    # env
    ("env", "env"),
    ("printenv", "env"),
]


def _has_source_file_arg(command: str) -> bool:
    """Return True if command has a source file argument (e.g. cat src/main.py)."""
    parts = command.split()
    if len(parts) < 2:
        return False
    for part in parts[1:]:
        # Strip leading/trailing quotes
        stripped = part.strip("\"'")
        dot = stripped.rfind(".")
        if dot != -1:
            ext = stripped[dot:]
            if ext in _SOURCE_EXTENSIONS:
                return True
    return False


def match_command(command: str) -> str | None:
    """Return hint for known commands, None for pass-through."""
    stripped = command.strip()

    # Pipes and redirects pass through
    if "|" in stripped:
        return None
    if ">" in stripped:
        return None

    # Split to get the base command name
    parts = stripped.split()
    if not parts:
        return None

    base = parts[0]

    # Passthrough commands
    if base in _PASSTHROUGH_COMMANDS:
        return None

    # Source-reading commands (cat/head/tail with source files)
    if base in ("cat", "head", "tail") and _has_source_file_arg(stripped):
        return None

    # Pattern matching — first wins
    for prefix, hint in _PATTERNS:
        if stripped == prefix or stripped.startswith(prefix + " ") or stripped.startswith(prefix + "\t"):
            return hint
        # For patterns that end with a space (like "rg ", "ag ", "find ")
        if prefix.endswith(" ") and stripped.startswith(prefix):
            return hint

    return None
