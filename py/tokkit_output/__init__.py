"""Tokkit Output — Token-optimized shell output compression."""

__version__ = "0.1.0"

_LINT_PARSER_IDS = frozenset({"ruff", "eslint", "mypy", "pyright", "cargo-clippy", "tsc"})


def compact_output(text: str, hint: str | None = None, verbose: bool = False) -> str:
    """Compress shell command output into schema+CSV structured format."""
    if not text or not text.strip():
        return ""

    from tokkit_output.universal import strip_ansi
    cleaned = strip_ansi(text)

    from tokkit_output.parsers import get_by_hint, all_parsers
    from tokkit_output.detect import detect_parser
    from tokkit_output.formatter import format_result

    parser = None
    if hint:
        parser = get_by_hint(hint)

    if parser is None:
        parser = detect_parser(cleaned, all_parsers())

    if parser is None:
        from tokkit_output.generic import generic_clean
        output = generic_clean(text)
        return output if len(output) <= len(cleaned) else cleaned

    result = parser.parse(cleaned, verbose=verbose)

    if result.tool in _LINT_PARSER_IDS:
        from tokkit_output.lint_grouper import group_by_rule
        result = group_by_rule(result)

    formatted = format_result(result)
    return formatted if len(formatted) <= len(cleaned) else cleaned
