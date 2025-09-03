"""Bundled skill documentation for tokkit."""

from pathlib import Path

SKILL_DIR = Path(__file__).parent


def skill_path() -> Path:
    """Return the path to the bundled SKILL.md."""
    return SKILL_DIR / "SKILL.md"


def tool_guide_path() -> Path:
    """Return the path to the bundled tool-guide.md."""
    return SKILL_DIR / "references" / "tool-guide.md"
