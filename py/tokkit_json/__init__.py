"""Tokkit JSON — Token-optimized JSON compaction for LLM payloads."""

__version__ = "0.1.0"

import json as _json


def compact_json(json_str: str) -> str:
    """Convert a JSON string to a token-optimized schema+data format.

    Output format: schema header line with key names, followed by data rows
    with only values. Nested arrays of objects use [{...};{...}] syntax.
    """
    if not json_str or not json_str.strip():
        return ""

    try:
        obj = _json.loads(json_str)
    except _json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(obj, (dict, list)):
        return str(obj)

    from tokkit_json.schema_conv import to_schema_csv
    return to_schema_csv(obj)
