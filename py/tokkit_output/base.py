"""Base parser protocol and shared types."""

from dataclasses import dataclass, field


@dataclass
class ParseResult:
    tool: str
    summary: str
    schema: list[str]
    rows: list[list[str]]
    verbose: bool = False


class BaseParser:
    """Protocol for output parsers."""

    id: str = ""
    hint_values: list[str] = []

    def detect(self, text: str) -> float:
        """Return confidence 0.0-1.0 that this text is from this tool."""
        return 0.0

    def parse(self, text: str, verbose: bool = False) -> ParseResult:
        """Extract structured data from the output."""
        raise NotImplementedError
