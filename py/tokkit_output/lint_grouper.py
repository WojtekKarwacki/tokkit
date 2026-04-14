"""Lint grouper post-processor: collapse repeated rule violations."""

from tokkit_output.base import ParseResult

_ELISION_THRESHOLD = 3

_LINT_PARSER_IDS = frozenset({"ruff", "eslint", "mypy", "pyright", "cargo-clippy", "tsc"})


def _find_rule_col(schema: list[str]) -> int:
    """Return the column index for the rule/code column, or -1 if absent."""
    for i, col in enumerate(schema):
        if col in ("rule", "code"):
            return i
    return -1


def group_by_rule(result: ParseResult) -> ParseResult:
    """Group lint violations by rule ID.

    Rules with >3 violations are collapsed to a header line, 2 example rows,
    and an elision row. Rules with <=3 violations are emitted individually.
    Verbose mode and results without a rule/code column are returned unchanged.
    """
    if result.verbose:
        return result

    if result.tool not in _LINT_PARSER_IDS:
        return result

    rule_col = _find_rule_col(result.schema)
    if rule_col == -1:
        return result

    if not result.rows:
        return result

    # Group rows by rule value, preserving insertion order
    groups: dict[str, list[list[str]]] = {}
    for row in result.rows:
        rule_val = row[rule_col] if rule_col < len(row) else ""
        groups.setdefault(rule_val, []).append(row)

    # Build collapsed output
    new_rows: list[list[str]] = []
    for rule_val, rule_rows in groups.items():
        if len(rule_rows) <= _ELISION_THRESHOLD:
            new_rows.extend(rule_rows)
        else:
            count = len(rule_rows)
            # Collect unique files for the header
            files = list(dict.fromkeys(r[0] for r in rule_rows if r))
            file_summary = files[0] if len(files) == 1 else f"{len(files)} files"
            # Header row: rule, count, files — padded to full schema width
            header = [""] * len(result.schema)
            header[rule_col] = rule_val
            # Place count and file summary in trailing positions if room
            if len(header) > rule_col + 1:
                header[rule_col + 1] = f"{count} occurrences"
            if len(header) > rule_col + 2:
                header[rule_col + 2] = file_summary
            new_rows.append(header)
            # 2 example rows
            new_rows.extend(rule_rows[:2])
            # Elision row
            remaining = count - 2
            elision = [""] * len(result.schema)
            elision[0] = f"... ({remaining} more)"
            new_rows.append(elision)

    # Update summary
    total = len(result.rows)
    n_rules = len(groups)
    summary = f"{total} issue{'s' if total != 1 else ''} across {n_rules} rule{'s' if n_rules != 1 else ''}"

    return ParseResult(
        tool=result.tool,
        summary=summary,
        schema=result.schema,
        rows=new_rows,
        verbose=result.verbose,
    )
