"""Format ParseResult to schema+CSV output."""

from tokkit_output.base import ParseResult  # noqa: F401 — re-exported


def format_result(result: ParseResult) -> str:
    """Format a ParseResult as summary comment + schema+CSV."""
    verbose_tag = " (verbose)" if result.verbose else ""
    summary = f"# {result.tool}{verbose_tag}: {result.summary}"

    if not result.rows:
        return summary

    schema_line = "[" + ";".join(result.schema) + "]"
    data_lines = []
    for row in result.rows:
        data_lines.append(";".join(_escape(v) for v in row))

    return "\n".join([summary, schema_line] + data_lines)


def _escape(value: str) -> str:
    """Escape a value for schema+CSV format."""
    if not value:
        return ""
    if any(c in value for c in ";{}[]\n"):
        escaped = value.replace('"', '""')
        return f'"{escaped}"'
    return value
