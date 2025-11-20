"""Auto-detection engine for shell output."""

from tokkit_output.base import BaseParser

_DETECT_THRESHOLD = 0.6


def detect_parser(text: str, parsers: list[BaseParser]) -> BaseParser | None:
    """Run all parsers' detect() and return highest-confidence match above threshold."""
    best_parser = None
    best_score = 0.0
    for parser in parsers:
        score = parser.detect(text)
        if score > best_score:
            best_score = score
            best_parser = parser
    if best_score >= _DETECT_THRESHOLD:
        return best_parser
    return None
