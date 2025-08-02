"""Schema-based JSON compaction: schema header + CSV-like data rows.

Format:
  [field1;field2;nested_array:[{field1;field2}]]
  value1;value2;[{val1;val2};{val3;val4}]

The first line defines the structure (key names), subsequent lines
carry only values — no repeated keys. Nested arrays of objects use
[{...};{...}] syntax with the same recursive pattern.
"""


def to_schema_csv(obj) -> str:
    """Convert a parsed JSON value to schema+data format."""
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if isinstance(obj[0], dict):
            template = _union_keys(obj)
            schema = _build_schema(template)
            lines = [f"[{schema}]"]
            for item in obj:
                lines.append(_render_row(item, template))
            return "\n".join(lines)
        return "[" + ";".join(_render_primitive(v) for v in obj) + "]"

    if isinstance(obj, dict):
        schema = _build_schema(obj)
        return f"[{schema}]\n{_render_row(obj, obj)}"

    return _render_primitive(obj)


def _union_keys(items: list[dict]) -> dict:
    """Build a template dict with the union of all keys across items.

    Uses the first non-None value seen for each key as a type hint
    for schema generation. For nested arrays of dicts, merges keys
    across all nested items too.
    """
    template = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if key not in template or template[key] is None:
                template[key] = value
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                existing = template[key]
                if isinstance(existing, list) and existing and isinstance(existing[0], dict):
                    template[key] = [_union_keys(existing + value)]
                elif not isinstance(existing, list) or not existing:
                    template[key] = value
    return template


def _build_schema(obj: dict) -> str:
    """Build a schema string from a template object."""
    parts = []
    for key, value in obj.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            inner = value[0] if isinstance(value[0], dict) else _union_keys(value)
            inner_schema = _build_schema(inner)
            parts.append(f"{key}:[{{{inner_schema}}}]")
        elif isinstance(value, dict):
            inner_schema = _build_schema(value)
            parts.append(f"{key}:{{{inner_schema}}}")
        else:
            parts.append(key)
    return ";".join(parts)


def _render_row(obj: dict, template: dict) -> str:
    """Render one object's values following the template key order."""
    parts = []
    for key in template:
        value = obj.get(key)
        parts.append(_render_value(value))
    return ";".join(parts)


def _render_value(value) -> str:
    """Render a single value."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if any(c in value for c in ";{}[]\n"):
            escaped = value.replace('"', '""')
            return f'"{escaped}"'
        return value
    if isinstance(value, list):
        if not value:
            return "[]"
        if isinstance(value[0], dict):
            template = _union_keys(value)
            items = ["{" + _render_row(item, template) + "}" for item in value]
            return "[" + ";".join(items) + "]"
        return "[" + ";".join(_render_primitive(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + _render_row(value, value) + "}"
    return str(value)


def _render_primitive(value) -> str:
    """Render a primitive value."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        if any(c in value for c in ";{}[]\n"):
            escaped = value.replace('"', '""')
            return f'"{escaped}"'
        return value
    return str(value)
