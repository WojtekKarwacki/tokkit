# compact_json — Token-Optimized JSON Compaction for LLM Payloads

**Date:** 2026-04-07
**Status:** Approved

## Purpose

Reduce token consumption when JSON data is sent to LLMs by converting it to a more compact format. The tool auto-detects the optimal output format based on data shape:

- **CSV** (semicolon-delimited) — for flat/flattenable data. Saves 50-70% by eliminating repeated keys.
- **YAML** — for data containing lists of complex objects. Saves 20-30% over JSON.

## Detection Rule

Walk the parsed JSON. If **any value anywhere in the structure is a list containing at least one dict**, use YAML. Otherwise use CSV.

Examples:
- `{"users": [{"name": "alice"}]}` → YAML (list of dicts)
- `{"name": "alice", "tags": ["a", "b"]}` → CSV (list of scalars, not dicts)
- `[{"name": "alice", "project": {"name": "test"}}]` → CSV (nested dict, but no list of dicts)

## CSV Conversion Rules

**Delimiter:** semicolon (`;`)

**Input shapes:**
- Single object `{...}` → one header row + one data row
- Array of objects `[{...}, {...}]` → one header row + N data rows

**Flattening:**
- Nested dicts: keys joined with `_` prefix of parent key
  - `{"project": {"name": "x", "desc": "y"}}` → columns `project_name`, `project_desc`
  - Recursive: `{"a": {"b": {"c": 1}}}` → column `a_b_c`
- Simple lists (scalars): comma-joined in cell
  - `{"tags": ["a", "b"]}` → cell value `a,b`
- Array of objects input: union of all flattened keys across all objects as header; missing keys get empty cells

**Value formatting:**
- Strings: as-is (no quoting unless contains semicolon or newline)
- Numbers/booleans: string representation
- null: empty string

## YAML Conversion Rules

- `yaml.dump()` with `default_flow_style=False`, `allow_unicode=True`, `sort_keys=False`
- No custom formatting — rely on PyYAML defaults

## Module Structure

Note: placed at `core/json/` (parallel to `core/web/`) because `core/web/pyproject.toml` is already the `tokkit-scraper` package. Same pattern, separate editable install.

```
core/json/
├── pyproject.toml
├── tokkit_json/
│   ├── __init__.py      # Public API: compact_json(json_str: str) -> str
│   ├── detect.py        # has_complex_lists(obj) -> bool
│   ├── csv_conv.py      # to_csv(obj) -> str
│   └── yaml_conv.py     # to_yaml(obj) -> str
└── tests/
    └── test_compact_json.py   # Unit tests
```

### Public API

```python
def compact_json(json_str: str) -> str:
    """Convert JSON string to a token-optimized format.

    Auto-detects whether CSV or YAML is more appropriate.
    Returns the compacted string.
    """
```

- Raises `ValueError` on invalid JSON
- Returns empty string for empty/whitespace input

### detect.py

```python
def has_complex_lists(obj) -> bool:
    """Return True if any value in obj is a list containing at least one dict."""
```

Recursive walk. Handles: dicts, lists, nested combinations. Does not traverse into list items that are scalars.

### csv_conv.py

```python
def to_csv(obj) -> str:
    """Convert a JSON object or array of objects to semicolon-delimited CSV."""
```

Internal helpers:
- `flatten_dict(d: dict, prefix: str = "") -> dict` — recursive flattening
- `format_value(v) -> str` — value to cell string

### yaml_conv.py

```python
def to_yaml(obj) -> str:
    """Convert a parsed JSON object to YAML."""
```

Thin wrapper around `yaml.dump()`.

## MCP Tool Registration

### protocol.py — TOOL_DEFINITIONS

```python
{
    "name": "compact_json",
    "description": "Convert JSON data to a token-optimized format for LLM consumption. "
                   "Auto-detects the best output: CSV (semicolon-delimited) for flat/tabular data, "
                   "YAML for data with nested lists of objects. Typically saves 30-60% of tokens.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "json": {
                "type": "string",
                "description": "Raw JSON string to compact.",
            },
        },
        "required": ["json"],
    },
}
```

### tools.py — dispatch

```python
if tool_name == "compact_json":
    json_str = args.get("json", "")
    if not json_str:
        return _err("json is required")
    from tokkit_json import compact_json
    compacted = compact_json(json_str)
    meta = make_meta(tool_name, compacted, _session_project_path, raw_size=len(json_str))
    return _ok(compacted, meta)
```

### token_stats.py — estimate_tokens_avoided

Add `compact_json` case, same logic as `clean_html`:

```python
if tool_name == "compact_json":
    if raw_size:
        return raw_size // CHARS_PER_TOKEN
    return len(result_text) * 2 // CHARS_PER_TOKEN
```

## Tests

### Unit Tests — `core/web/tests/test_compact_json.py`

**Detection tests:**
- `test_detects_list_of_dicts` — `{"users": [{"name": "alice"}]}` → True
- `test_no_complex_lists_flat` — `{"name": "alice", "age": 30}` → False
- `test_no_complex_lists_scalar_list` — `{"tags": ["a", "b"]}` → False
- `test_nested_complex_list` — deeply nested list of dicts → True
- `test_empty_list_no_complex` — `{"items": []}` → False

**CSV conversion tests:**
- `test_csv_single_flat_object` — basic key-value object
- `test_csv_array_of_objects` — multiple objects, union of keys
- `test_csv_nested_dict_flattening` — `project.name` → `project_name`
- `test_csv_deep_nesting` — `a.b.c` → `a_b_c`
- `test_csv_scalar_list_comma_joined` — `["a","b"]` → `a,b`
- `test_csv_missing_keys_empty_cells` — sparse array of objects
- `test_csv_semicolon_delimiter` — verify `;` not `,` between columns
- `test_csv_value_formatting` — numbers, booleans, null

**YAML conversion tests:**
- `test_yaml_preserves_structure` — round-trip fidelity
- `test_yaml_complex_nested` — lists of dicts output correctly

**Integration (public API) tests:**
- `test_compact_json_auto_csv` — flat input → CSV output
- `test_compact_json_auto_yaml` — complex list input → YAML output
- `test_compact_json_empty_input` — returns empty string
- `test_compact_json_invalid_json` — raises ValueError

### Integration Tests — `server/tests/test_json_integration.py`

- `test_compact_json_tool_dispatch` — correct dispatch + output
- `test_compact_json_no_session_required` — works without index
- `test_compact_json_token_stats_recorded` — _meta field populated
- `test_compact_json_error_on_missing_json` — isError response

### E2E Tests — `e2e/test_mcp_json.py`

- `test_compact_json_in_tools_list` — tool appears in tools/list
- `test_compact_json_csv_via_mcp` — flat JSON → CSV through full MCP flow
- `test_compact_json_yaml_via_mcp` — nested JSON → YAML through full MCP flow
- `test_compact_json_saves_tokens` — compacted output fewer tokens than raw JSON

### Benchmark — `e2e/benchmark/test_json_benchmark.py`

**Fixtures** (`e2e/benchmark/fixtures/json/`):

1. `flat_records.json` — ~2,000 tokens of flat/flattenable objects (array of ~50 records with nested simple fields like address, scalar tag lists). Triggers CSV path.

2. `nested_complex.json` — ~2,000 tokens of nested data with lists of complex objects (repos with contributors with permissions). Triggers YAML path.

Both fixtures are synthetically generated, balanced at roughly equal raw token count.

**Benchmark tests:**
- `test_q1_csv_path` — flat_records.json through compact_json, measure savings
- `test_q2_yaml_path` — nested_complex.json through compact_json, measure savings
- `test_z_generate_report` — generate `JSON_BENCHMARK_RESULTS.md`

Report format matches existing `SCRAPER_BENCHMARK_RESULTS.md`.

## Dependency

`PyYAML>=6.0` declared in `core/json/pyproject.toml` dependencies.

## Skill Documentation Update

Add to `skill/SKILL.md` under a new section "8. Compact JSON Data":

```
compact_json(json="<raw json string>") → token-optimized CSV or YAML
```

Add to Tool Selection Guide table:
```
| Compact JSON for LLM | `compact_json` | CSV/YAML output, saves 30-60% tokens |
```

## Performance

Python is sufficient. Worst case: 500K tokens = ~2MB of JSON. `json.loads()` + recursive walk + string building on 2MB is <100ms. No Rust needed.
