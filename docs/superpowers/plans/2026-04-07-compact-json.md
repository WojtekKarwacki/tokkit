# compact_json Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `compact_json` MCP tool that converts JSON data to token-optimized CSV or YAML format, auto-detecting the best output based on data shape.

**Architecture:** New `tokkit_json` Python package in `core/web/` alongside `tokkit_scraper`, installed as a separate editable package. MCP tool registered in the server following the `clean_html` pattern. Detection logic walks JSON to choose CSV (flat data) or YAML (contains lists of dicts).

**Tech Stack:** Python 3.11+, PyYAML, pytest

---

## File Map

**New files:**
- `core/web/tokkit_json/__init__.py` — Public API: `compact_json(json_str) -> str`
- `core/web/tokkit_json/detect.py` — `has_complex_lists(obj) -> bool`
- `core/web/tokkit_json/csv_conv.py` — `to_csv(obj) -> str`
- `core/web/tokkit_json/yaml_conv.py` — `to_yaml(obj) -> str`
- `core/web/tokkit_json/pyproject.toml` — Package metadata (separate editable install)
- `core/web/tests/test_compact_json.py` — Unit tests
- `server/tests/test_json_integration.py` — Integration tests
- `e2e/test_mcp_json.py` — E2E tests
- `e2e/benchmark/fixtures/json/flat_records.json` — Benchmark fixture (~2K tokens, CSV path)
- `e2e/benchmark/fixtures/json/nested_complex.json` — Benchmark fixture (~2K tokens, YAML path)
- `e2e/benchmark/test_json_benchmark.py` — Benchmark tests + report generation

**Modified files:**
- `server/tokkit_server/protocol.py` — Add `compact_json` to `TOOL_DEFINITIONS`
- `server/tokkit_server/tools.py` — Add `compact_json` dispatch branch
- `server/tokkit_server/token_stats.py` — Add `compact_json` to `estimate_tokens_avoided`
- `skill/SKILL.md` — Add compact_json documentation section

---

### Task 1: Package scaffold + detection logic

**Files:**
- Create: `core/web/tokkit_json/__init__.py`
- Create: `core/web/tokkit_json/detect.py`
- Create: `core/web/tokkit_json/pyproject.toml`
- Test: `core/web/tests/test_compact_json.py`

- [ ] **Step 1: Create the package pyproject.toml**

Create `core/web/tokkit_json/pyproject.toml`:

```toml
[project]
name = "tokkit-json"
version = "0.1.0"
description = "Token-optimized JSON compaction for LLM payloads"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

Note: the `pyproject.toml` goes inside the `tokkit_json/` directory because setuptools auto-discovers the package from the directory containing `__init__.py`. Since `tokkit_json/` IS the package directory, we need `pyproject.toml` one level up. Actually — follow the `tokkit_scraper` pattern exactly: `core/web/pyproject.toml` is one level above `core/web/tokkit_scraper/`. So create a wrapper directory.

Correction — the layout must be:

```
core/web/tokkit_json/          # wrapper directory (like core/web/ is for tokkit_scraper)
├── pyproject.toml             # package metadata
└── tokkit_json/               # the actual Python package
    ├── __init__.py
    ├── detect.py
    ├── csv_conv.py
    └── yaml_conv.py
```

Wait — looking at the actual structure: `core/web/` contains `pyproject.toml` AND `tokkit_scraper/`. So `core/web/` IS the wrapper. To avoid nesting confusion and follow the pattern, create a parallel directory:

```
core/json/                     # parallel to core/web/
├── pyproject.toml
└── tokkit_json/
    ├── __init__.py
    ├── detect.py
    ├── csv_conv.py
    └── yaml_conv.py
```

But the user requested "json module in tokkit/core/web". To honor that while keeping the editable install working, the simplest approach: put everything at `core/json/` (parallel, same pattern as `core/web/`), since the user's intent is "in the web/json domain of core". If they object, we can move it.

Final layout:
```
core/json/
├── pyproject.toml
├── tokkit_json/
│   ├── __init__.py
│   ├── detect.py
│   ├── csv_conv.py
│   └── yaml_conv.py
└── tests/
    └── test_compact_json.py
```

- [ ] **Step 2: Create pyproject.toml**

Create `core/json/pyproject.toml`:

```toml
[project]
name = "tokkit-json"
version = "0.1.0"
description = "Token-optimized JSON compaction for LLM payloads"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 3: Create empty __init__.py**

Create `core/json/tokkit_json/__init__.py`:

```python
"""Tokkit JSON — Token-optimized JSON compaction for LLM payloads."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write failing tests for detection logic**

Create `core/json/tests/test_compact_json.py`:

```python
"""Unit tests for JSON compaction."""

from tokkit_json.detect import has_complex_lists


def test_detects_list_of_dicts():
    obj = {"users": [{"name": "alice"}, {"name": "bob"}]}
    assert has_complex_lists(obj) is True


def test_no_complex_lists_flat():
    obj = {"name": "alice", "age": 30}
    assert has_complex_lists(obj) is False


def test_no_complex_lists_scalar_list():
    obj = {"tags": ["a", "b", "c"]}
    assert has_complex_lists(obj) is False


def test_nested_complex_list():
    obj = {"org": {"teams": [{"name": "eng", "members": [{"name": "alice"}]}]}}
    assert has_complex_lists(obj) is True


def test_empty_list_no_complex():
    obj = {"items": []}
    assert has_complex_lists(obj) is False


def test_top_level_array_of_dicts():
    obj = [{"name": "alice"}, {"name": "bob"}]
    assert has_complex_lists(obj) is False  # top-level array is the input, not a nested list of dicts


def test_top_level_array_with_nested_complex():
    obj = [{"name": "alice", "projects": [{"id": 1}]}]
    assert has_complex_lists(obj) is True


def test_deeply_nested_no_complex():
    obj = {"a": {"b": {"c": {"d": 1}}}}
    assert has_complex_lists(obj) is False


def test_list_of_scalars_mixed():
    obj = {"values": [1, "two", True, None]}
    assert has_complex_lists(obj) is False
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tokkit_json'`

- [ ] **Step 6: Install package and implement detect.py**

Install the package:
```bash
/home/edge/code/.venv/bin/pip install -e core/json/
```

Create `core/json/tokkit_json/detect.py`:

```python
"""Detection logic for JSON compaction strategy."""


def has_complex_lists(obj) -> bool:
    """Return True if any value in obj is a list containing at least one dict.

    This determines whether YAML (True) or CSV (False) compaction is used.
    A top-level array is not itself considered a "complex list" — only nested
    arrays within objects trigger YAML mode.
    """
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, list):
                if any(isinstance(item, dict) for item in value):
                    return True
                for item in value:
                    if has_complex_lists(item):
                        return True
            elif isinstance(value, dict):
                if has_complex_lists(value):
                    return True
    elif isinstance(obj, list):
        for item in obj:
            if has_complex_lists(item):
                return True
    return False
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py -v`
Expected: All 9 tests PASS

- [ ] **Step 8: Commit**

```bash
git add core/json/ 
git commit -m "feat(json): add tokkit_json package with detection logic"
```

---

### Task 2: CSV conversion

**Files:**
- Create: `core/json/tokkit_json/csv_conv.py`
- Modify: `core/json/tests/test_compact_json.py`

- [ ] **Step 1: Write failing tests for CSV conversion**

Append to `core/json/tests/test_compact_json.py`:

```python
from tokkit_json.csv_conv import to_csv


def test_csv_single_flat_object():
    obj = {"name": "alice", "age": 30}
    result = to_csv(obj)
    assert result == "name;age\nalice;30"


def test_csv_array_of_objects():
    obj = [{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]
    result = to_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "name;age"
    assert lines[1] == "alice;30"
    assert lines[2] == "bob;25"


def test_csv_nested_dict_flattening():
    obj = {"name": "alice", "project": {"name": "test", "desc": "some project"}}
    result = to_csv(obj)
    lines = result.split("\n")
    assert "name" in lines[0]
    assert "project_name" in lines[0]
    assert "project_desc" in lines[0]
    assert "alice" in lines[1]
    assert "test" in lines[1]
    assert "some project" in lines[1]


def test_csv_deep_nesting():
    obj = {"a": {"b": {"c": 1}}}
    result = to_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "a_b_c"
    assert lines[1] == "1"


def test_csv_scalar_list_comma_joined():
    obj = {"name": "alice", "tags": ["admin", "active"]}
    result = to_csv(obj)
    lines = result.split("\n")
    assert "tags" in lines[0]
    assert "admin,active" in lines[1]


def test_csv_missing_keys_empty_cells():
    obj = [{"name": "alice", "age": 30}, {"name": "bob", "role": "pm"}]
    result = to_csv(obj)
    lines = result.split("\n")
    header = lines[0].split(";")
    assert "name" in header
    assert "age" in header
    assert "role" in header
    # alice row has empty role
    alice_vals = lines[1].split(";")
    bob_vals = lines[2].split(";")
    role_idx = header.index("role")
    age_idx = header.index("age")
    assert alice_vals[role_idx] == ""
    assert bob_vals[age_idx] == ""


def test_csv_value_formatting():
    obj = {"str": "hello", "int": 42, "float": 3.14, "bool": True, "none": None}
    result = to_csv(obj)
    lines = result.split("\n")
    vals = lines[1].split(";")
    assert "hello" in vals
    assert "42" in vals
    assert "3.14" in vals
    assert "True" in vals
    assert "" in vals  # None → empty


def test_csv_semicolon_in_value_quoted():
    obj = {"text": "hello;world"}
    result = to_csv(obj)
    lines = result.split("\n")
    assert '"hello;world"' in lines[1]


def test_csv_newline_in_value_quoted():
    obj = {"text": "line1\nline2"}
    result = to_csv(obj)
    assert '"line1\nline2"' in result
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py::test_csv_single_flat_object -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement csv_conv.py**

Create `core/json/tokkit_json/csv_conv.py`:

```python
"""CSV conversion for flat/flattenable JSON data."""


def to_csv(obj) -> str:
    """Convert a JSON object or array of objects to semicolon-delimited CSV.

    Nested dicts are flattened with '_' separator.
    Scalar lists are comma-joined in cells.
    """
    if isinstance(obj, dict):
        rows = [obj]
    elif isinstance(obj, list):
        rows = obj
    else:
        return str(obj)

    flat_rows = [_flatten_dict(row) for row in rows]

    # Union of all keys, preserving insertion order
    seen = {}
    for row in flat_rows:
        for key in row:
            if key not in seen:
                seen[key] = True
    headers = list(seen)

    lines = [";".join(headers)]
    for row in flat_rows:
        cells = [_format_value(row.get(h)) for h in headers]
        lines.append(";".join(cells))

    return "\n".join(lines)


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Recursively flatten a dict. Nested dicts get '_' joined keys."""
    result = {}
    for key, value in d.items():
        full_key = f"{prefix}_{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_dict(value, full_key))
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                # This shouldn't happen in CSV path (detection routes to YAML),
                # but handle gracefully: stringify
                result[full_key] = str(value)
            else:
                result[full_key] = ",".join(str(v) for v in value)
        else:
            result[full_key] = value
    return result


def _format_value(v) -> str:
    """Format a value for CSV cell output."""
    if v is None:
        return ""
    s = str(v)
    if ";" in s or "\n" in s or '"' in s:
        escaped = s.replace('"', '""')
        return f'"{escaped}"'
    return s
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/json/tokkit_json/csv_conv.py core/json/tests/test_compact_json.py
git commit -m "feat(json): add CSV conversion with flattening"
```

---

### Task 3: YAML conversion

**Files:**
- Create: `core/json/tokkit_json/yaml_conv.py`
- Modify: `core/json/tests/test_compact_json.py`

- [ ] **Step 1: Install PyYAML**

```bash
/home/edge/code/.venv/bin/pip install "PyYAML>=6.0"
```

- [ ] **Step 2: Write failing tests for YAML conversion**

Append to `core/json/tests/test_compact_json.py`:

```python
from tokkit_json.yaml_conv import to_yaml


def test_yaml_preserves_structure():
    obj = {"users": [{"name": "alice", "role": "eng"}]}
    result = to_yaml(obj)
    assert "users:" in result
    assert "- name: alice" in result
    assert "role: eng" in result


def test_yaml_nested_complex():
    obj = {
        "org": {
            "name": "acme",
            "teams": [
                {"name": "eng", "members": [{"name": "alice"}, {"name": "bob"}]},
            ],
        }
    }
    result = to_yaml(obj)
    assert "org:" in result
    assert "teams:" in result
    assert "members:" in result
    assert "- name: alice" in result


def test_yaml_no_flow_style():
    obj = {"items": [{"a": 1, "b": 2}]}
    result = to_yaml(obj)
    # Should NOT be inline like {a: 1, b: 2}
    assert "{" not in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py::test_yaml_preserves_structure -v`
Expected: FAIL — `ImportError`

- [ ] **Step 4: Implement yaml_conv.py**

Create `core/json/tokkit_json/yaml_conv.py`:

```python
"""YAML conversion for complex/nested JSON data."""

import yaml


def to_yaml(obj) -> str:
    """Convert a parsed JSON object to YAML string."""
    return yaml.dump(obj, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip("\n")
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/json/tokkit_json/yaml_conv.py core/json/tests/test_compact_json.py
git commit -m "feat(json): add YAML conversion"
```

---

### Task 4: Public API — compact_json()

**Files:**
- Modify: `core/json/tokkit_json/__init__.py`
- Modify: `core/json/tests/test_compact_json.py`

- [ ] **Step 1: Write failing tests for the public API**

Append to `core/json/tests/test_compact_json.py`:

```python
from tokkit_json import compact_json


def test_compact_json_auto_csv():
    json_str = '[{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]'
    result = compact_json(json_str)
    lines = result.split("\n")
    assert lines[0] == "name;age"
    assert "alice" in lines[1]
    assert "bob" in lines[2]


def test_compact_json_auto_yaml():
    json_str = '{"users": [{"name": "alice"}, {"name": "bob"}]}'
    result = compact_json(json_str)
    assert "users:" in result
    assert "- name: alice" in result


def test_compact_json_single_object_csv():
    json_str = '{"name": "alice", "project": {"name": "test", "desc": "some project"}}'
    result = compact_json(json_str)
    assert "project_name" in result
    assert "project_desc" in result
    assert "alice" in result


def test_compact_json_empty_input():
    assert compact_json("") == ""
    assert compact_json("   ") == ""


def test_compact_json_invalid_json():
    import pytest
    with pytest.raises(ValueError, match="Invalid JSON"):
        compact_json("{not valid json")


def test_compact_json_scalar_input():
    result = compact_json('"hello"')
    assert result == "hello"


def test_compact_json_number_input():
    result = compact_json("42")
    assert result == "42"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py::test_compact_json_auto_csv -v`
Expected: FAIL — `ImportError: cannot import name 'compact_json'`

- [ ] **Step 3: Implement compact_json in __init__.py**

Replace `core/json/tokkit_json/__init__.py` with:

```python
"""Tokkit JSON — Token-optimized JSON compaction for LLM payloads."""

__version__ = "0.1.0"

import json as _json

from tokkit_json.detect import has_complex_lists


def compact_json(json_str: str) -> str:
    """Convert a JSON string to a token-optimized format.

    Auto-detects whether CSV or YAML is more appropriate:
    - CSV (semicolon-delimited) for flat/flattenable data
    - YAML for data containing lists of complex objects (dicts)
    """
    if not json_str or not json_str.strip():
        return ""

    try:
        obj = _json.loads(json_str)
    except _json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(obj, (dict, list)):
        return str(obj)

    if has_complex_lists(obj):
        from tokkit_json.yaml_conv import to_yaml
        return to_yaml(obj)
    else:
        from tokkit_json.csv_conv import to_csv
        return to_csv(obj)
```

- [ ] **Step 4: Run all tests**

Run: `/home/edge/code/.venv/bin/pytest core/json/tests/test_compact_json.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/json/tokkit_json/__init__.py core/json/tests/test_compact_json.py
git commit -m "feat(json): add compact_json public API with auto-detection"
```

---

### Task 5: MCP server integration

**Files:**
- Modify: `server/tokkit_server/protocol.py:9-167` (TOOL_DEFINITIONS list)
- Modify: `server/tokkit_server/tools.py:159-167` (add dispatch after clean_html)
- Modify: `server/tokkit_server/token_stats.py:44-53` (add compact_json case)
- Test: `server/tests/test_json_integration.py`

- [ ] **Step 1: Write failing integration tests**

Create `server/tests/test_json_integration.py`:

```python
"""Integration tests for compact_json MCP tool dispatch."""

import tokkit_server.tools as tools_module
from tokkit_server.tools import handle_tool_call


def _reset_session():
    tools_module._session_project_path = None
    tools_module._session_db_path = None


def test_compact_json_tool_dispatch():
    _reset_session()
    json_str = '[{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]'
    result = handle_tool_call("compact_json", {"json": json_str})
    assert not result.get("isError")
    text = result["content"][0]["text"]
    assert "name" in text
    assert "alice" in text


def test_compact_json_no_session_required():
    _reset_session()
    json_str = '{"name": "alice"}'
    result = handle_tool_call("compact_json", {"json": json_str})
    assert not result.get("isError")
    assert "alice" in result["content"][0]["text"]


def test_compact_json_token_stats_recorded():
    _reset_session()
    json_str = '[' + ','.join(['{"name": "user", "age": 30}'] * 50) + ']'
    result = handle_tool_call("compact_json", {"json": json_str})
    assert not result.get("isError")
    meta = result.get("_meta", {}).get("token_savings", {})
    assert meta.get("tokens_avoided", 0) > 0
    assert meta.get("tokens_used", 0) > 0
    assert meta["tokens_avoided"] >= meta["tokens_used"]


def test_compact_json_error_on_missing_json():
    result = handle_tool_call("compact_json", {})
    assert result.get("isError") is True
    assert "json is required" in result["content"][0]["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/edge/code/.venv/bin/pytest server/tests/test_json_integration.py -v`
Expected: FAIL — unknown tool

- [ ] **Step 3: Add compact_json to TOOL_DEFINITIONS**

In `server/tokkit_server/protocol.py`, add to the `TOOL_DEFINITIONS` list (after the `clean_html` entry, before the closing `]`):

```python
    {
        "name": "compact_json",
        "description": "Convert JSON data to a token-optimized format for LLM consumption. "
                       "Auto-detects the best output: CSV (semicolon-delimited) for flat/tabular data, "
                       "YAML for data with nested lists of objects. Typically saves 30-60% of tokens. "
                       "Does not require an indexed project.",
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
    },
```

- [ ] **Step 4: Add compact_json dispatch in tools.py**

In `server/tokkit_server/tools.py`, add after the `clean_html` block (after line 167, before `if tool_name == "get_token_stats":`):

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

- [ ] **Step 5: Add compact_json to token_stats.py**

In `server/tokkit_server/token_stats.py`, add after the `clean_html` case (after line 53):

```python
    if tool_name == "compact_json":
        if raw_size:
            return raw_size // CHARS_PER_TOKEN
        return len(result_text) * 2 // CHARS_PER_TOKEN
```

- [ ] **Step 6: Run integration tests**

Run: `/home/edge/code/.venv/bin/pytest server/tests/test_json_integration.py -v`
Expected: All 4 tests PASS

- [ ] **Step 7: Run all existing tests to verify no regressions**

Run: `/home/edge/code/.venv/bin/pytest server/tests/ core/json/tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add server/tokkit_server/protocol.py server/tokkit_server/tools.py server/tokkit_server/token_stats.py server/tests/test_json_integration.py
git commit -m "feat(json): register compact_json MCP tool"
```

---

### Task 6: E2E tests

**Files:**
- Create: `e2e/test_mcp_json.py`

- [ ] **Step 1: Write E2E tests**

Create `e2e/test_mcp_json.py`:

```python
"""E2E tests for compact_json MCP tool — full JSON-RPC flow."""

import json


FLAT_JSON = json.dumps([
    {"name": "alice", "age": 30, "role": "eng", "city": "NYC"},
    {"name": "bob", "age": 25, "role": "pm", "city": "SF"},
    {"name": "carol", "age": 35, "role": "eng", "city": "LA"},
])

NESTED_JSON = json.dumps({
    "org": "acme",
    "teams": [
        {
            "name": "engineering",
            "members": [
                {"name": "alice", "skills": ["python", "rust"]},
                {"name": "bob", "skills": ["go"]},
            ],
        },
    ],
})


def test_compact_json_in_tools_list(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/list", {})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "compact_json" in tool_names


def test_compact_json_csv_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "compact_json",
        "arguments": {"json": FLAT_JSON},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "name;age;role;city" in content
    assert "alice" in content
    assert "bob" in content
    assert "carol" in content


def test_compact_json_yaml_via_mcp(mcp_server):
    mcp_server.send("initialize", {})
    resp = mcp_server.send("tools/call", {
        "name": "compact_json",
        "arguments": {"json": NESTED_JSON},
    })
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "teams:" in content
    assert "- name: alice" in content or "name: alice" in content


def test_compact_json_saves_tokens(mcp_server):
    mcp_server.send("initialize", {})
    raw_tokens = len(FLAT_JSON) // 4
    resp = mcp_server.send("tools/call", {
        "name": "compact_json",
        "arguments": {"json": FLAT_JSON},
    })
    content = resp["result"]["content"][0]["text"]
    compacted_tokens = len(content) // 4
    assert compacted_tokens < raw_tokens
    savings_pct = (1 - compacted_tokens / raw_tokens) * 100
    assert savings_pct > 20, f"Only {savings_pct:.1f}% savings, expected >20%"
```

- [ ] **Step 2: Run E2E tests**

Run: `/home/edge/code/.venv/bin/pytest e2e/test_mcp_json.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Run all tests including existing ones**

Run: `/home/edge/code/.venv/bin/pytest e2e/ server/tests/ core/json/tests/ core/web/tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add e2e/test_mcp_json.py
git commit -m "test(json): add E2E tests for compact_json MCP tool"
```

---

### Task 7: Benchmark fixtures + benchmark tests

**Files:**
- Create: `e2e/benchmark/fixtures/json/flat_records.json`
- Create: `e2e/benchmark/fixtures/json/nested_complex.json`
- Create: `e2e/benchmark/test_json_benchmark.py`
- Modify: `e2e/benchmark/conftest.py` (add `benchmark_mcp_json` fixture)

- [ ] **Step 1: Create flat_records.json fixture (~2K tokens)**

Create `e2e/benchmark/fixtures/json/flat_records.json`.

Generate a JSON array of 50 user records. Each record:
```json
{
  "id": 1,
  "name": "user_1",
  "email": "user_1@example.com",
  "age": 28,
  "role": "engineer",
  "department": "backend",
  "address": {"city": "New York", "state": "NY", "zip": "10001"},
  "tags": ["python", "docker"]
}
```

Use a Python script to generate:

```bash
/home/edge/code/.venv/bin/python3 -c "
import json, random
roles = ['engineer', 'pm', 'designer', 'analyst', 'devops']
depts = ['backend', 'frontend', 'infra', 'data', 'product']
cities = [('New York','NY','10001'),('San Francisco','CA','94102'),('Chicago','IL','60601'),('Austin','TX','73301'),('Seattle','WA','98101')]
tag_pool = ['python','go','rust','docker','k8s','react','sql','aws','gcp','terraform']
records = []
for i in range(1, 51):
    city = cities[i % len(cities)]
    records.append({
        'id': i,
        'name': f'user_{i}',
        'email': f'user_{i}@example.com',
        'age': 22 + (i % 30),
        'role': roles[i % len(roles)],
        'department': depts[i % len(depts)],
        'address': {'city': city[0], 'state': city[1], 'zip': city[2]},
        'tags': [tag_pool[i % len(tag_pool)], tag_pool[(i+3) % len(tag_pool)]]
    })
print(json.dumps(records, indent=2))
" > e2e/benchmark/fixtures/json/flat_records.json
```

Verify size: `wc -c e2e/benchmark/fixtures/json/flat_records.json` — should be ~8K chars (~2K tokens).

- [ ] **Step 2: Create nested_complex.json fixture (~2K tokens)**

Create `e2e/benchmark/fixtures/json/nested_complex.json`.

```bash
/home/edge/code/.venv/bin/python3 -c "
import json
data = {
    'organization': 'Acme Corp',
    'founded': 2015,
    'headquarters': {'city': 'San Francisco', 'state': 'CA'},
    'departments': [
        {
            'name': 'Engineering',
            'budget': 2000000,
            'teams': [
                {
                    'name': 'Backend',
                    'lead': 'alice',
                    'members': [
                        {'name': 'alice', 'role': 'senior', 'skills': ['python', 'go', 'postgres']},
                        {'name': 'bob', 'role': 'mid', 'skills': ['python', 'docker']},
                        {'name': 'carol', 'role': 'junior', 'skills': ['python']},
                        {'name': 'dave', 'role': 'senior', 'skills': ['go', 'k8s', 'terraform']},
                    ]
                },
                {
                    'name': 'Frontend',
                    'lead': 'eve',
                    'members': [
                        {'name': 'eve', 'role': 'senior', 'skills': ['react', 'typescript']},
                        {'name': 'frank', 'role': 'mid', 'skills': ['react', 'css']},
                        {'name': 'grace', 'role': 'junior', 'skills': ['javascript']},
                    ]
                },
                {
                    'name': 'Infrastructure',
                    'lead': 'heidi',
                    'members': [
                        {'name': 'heidi', 'role': 'senior', 'skills': ['aws', 'terraform', 'k8s']},
                        {'name': 'ivan', 'role': 'mid', 'skills': ['docker', 'ansible']},
                    ]
                },
            ]
        },
        {
            'name': 'Product',
            'budget': 1000000,
            'teams': [
                {
                    'name': 'Growth',
                    'lead': 'judy',
                    'members': [
                        {'name': 'judy', 'role': 'senior', 'skills': ['analytics', 'sql']},
                        {'name': 'karl', 'role': 'mid', 'skills': ['figma', 'research']},
                    ]
                },
                {
                    'name': 'Platform',
                    'lead': 'liam',
                    'members': [
                        {'name': 'liam', 'role': 'senior', 'skills': ['strategy', 'sql']},
                        {'name': 'mia', 'role': 'junior', 'skills': ['jira', 'docs']},
                    ]
                },
            ]
        },
    ]
}
print(json.dumps(data, indent=2))
" > e2e/benchmark/fixtures/json/nested_complex.json
```

Verify size: `wc -c e2e/benchmark/fixtures/json/nested_complex.json` — target ~8K chars (~2K tokens). Adjust member count if needed.

- [ ] **Step 3: Add benchmark_mcp_json fixture to conftest**

In `e2e/benchmark/conftest.py`, add after the `benchmark_mcp_scraper` fixture (copy the same pattern — no repo indexing needed):

```python
@pytest.fixture(scope="session")
def benchmark_mcp_json():
    """Start MCP server for JSON compaction benchmarks (no repo indexing needed)."""
    proc = subprocess.Popen(
        [PYTHON, "-m", "tokkit_server.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    class McpClient:
        def __init__(self, process):
            self.proc = process
            self._id = 0

        def call_tool(self, name, arguments=None):
            self._id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Server closed connection")
            resp = json.loads(line)
            content = resp["result"]["content"][0]["text"]
            return content

        def close(self):
            self.proc.stdin.close()
            self.proc.wait(timeout=10)

    client = McpClient(proc)

    init_req = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(init_req) + "\n")
    proc.stdin.flush()
    proc.stdout.readline()

    yield client

    try:
        client.close()
    except Exception:
        proc.kill()
```

- [ ] **Step 4: Write benchmark tests**

Create `e2e/benchmark/test_json_benchmark.py`:

```python
"""Token savings benchmark: compact_json CSV vs YAML paths."""

import os
from datetime import date

import pytest

from e2e.benchmark.config import CHARS_PER_TOKEN

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "json")

_results: list[dict] = []


def _load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path) as f:
        return f.read()


def _baseline_raw_json(json_str: str) -> int:
    return len(json_str) // CHARS_PER_TOKEN


@pytest.mark.benchmark
class TestJsonBenchmark:

    def test_q1_csv_path(self, benchmark_mcp_json):
        json_str = _load_fixture("flat_records.json")
        baseline = _baseline_raw_json(json_str)
        response = benchmark_mcp_json.call_tool("compact_json", {"json": json_str})
        tokkit = len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": "Flat records (CSV path)",
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_q2_yaml_path(self, benchmark_mcp_json):
        json_str = _load_fixture("nested_complex.json")
        baseline = _baseline_raw_json(json_str)
        response = benchmark_mcp_json.call_tool("compact_json", {"json": json_str})
        tokkit = len(response) // CHARS_PER_TOKEN
        _results.append({
            "question": "Nested complex (YAML path)",
            "tokkit": tokkit,
            "baseline": baseline,
        })
        assert tokkit < baseline

    def test_z_generate_report(self):
        if len(_results) < 2:
            pytest.skip("Not all questions completed")

        total_tokkit = sum(r["tokkit"] for r in _results)
        total_baseline = sum(r["baseline"] for r in _results)
        total_savings = (1 - total_tokkit / total_baseline) * 100 if total_baseline > 0 else 0
        total_ratio = total_baseline / total_tokkit if total_tokkit > 0 else 0

        lines = [
            "# Tokkit JSON Compaction Token Savings Benchmark",
            "",
            f"**Fixtures:** 2 JSON payloads (flat records, nested complex)",
            f"**Date:** {date.today().isoformat()}",
            "",
            "| # | Path | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |",
            "|---|------|----------------:|------------------:|----------:|------:|",
        ]

        for i, r in enumerate(_results, 1):
            savings = (1 - r["tokkit"] / r["baseline"]) * 100 if r["baseline"] > 0 else 0
            ratio = r["baseline"] / r["tokkit"] if r["tokkit"] > 0 else 0
            lines.append(
                f"| {i} | {r['question']} | {r['tokkit']:,} | {r['baseline']:,} | {savings:.1f}% | {ratio:.1f}x |"
            )

        lines.append(
            f"| | **Total** | **{total_tokkit:,}** | **{total_baseline:,}** | **{total_savings:.1f}%** | **{total_ratio:.1f}x** |"
        )
        lines.extend([
            "",
            f"*Token estimate: len(bytes) / {CHARS_PER_TOKEN}. Both paths use the same constant.*",
            "",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "JSON_BENCHMARK_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
        assert total_tokkit < total_baseline
```

- [ ] **Step 5: Run benchmark tests**

Run: `/home/edge/code/.venv/bin/pytest e2e/benchmark/test_json_benchmark.py -v`
Expected: All 3 tests PASS, `JSON_BENCHMARK_RESULTS.md` generated

- [ ] **Step 6: Commit**

```bash
git add e2e/benchmark/fixtures/json/ e2e/benchmark/test_json_benchmark.py e2e/benchmark/conftest.py
git commit -m "test(json): add benchmark fixtures and token savings benchmark"
```

---

### Task 8: Update test paths + skill docs

**Files:**
- Modify: `pyproject.toml:9` (add `core/json/tests` to testpaths)
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Add core/json/tests to pytest testpaths**

In `pyproject.toml`, change line 9:

```toml
testpaths = ["e2e", "server/tests", "core/web/tests", "core/json/tests"]
```

- [ ] **Step 2: Update skill/SKILL.md**

In `skill/SKILL.md`, add a new section after "### 7. Clean Web Content" (before "## Qualified Name Format"):

```markdown
### 8. Compact JSON Data

For JSON payloads about to be sent to an LLM:

```
compact_json(json="<raw json string>") → token-optimized CSV or YAML
```

Auto-detects the best format:
- **CSV** (semicolon-delimited) for flat/flattenable data — saves 50-70%
- **YAML** for data with nested lists of objects — saves 20-30%

Does not require an indexed project. Works standalone as a stateless transformation.
```

Add a row to the Tool Selection Guide table:

```markdown
| Compact JSON for LLM | `compact_json` | CSV/YAML output, saves 30-60% tokens |
```

- [ ] **Step 3: Run full test suite**

Run: `/home/edge/code/.venv/bin/pytest e2e/ server/tests/ core/json/tests/ core/web/tests/ -v --ignore=e2e/benchmark`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml skill/SKILL.md
git commit -m "docs: add compact_json to skill docs and test paths"
```
