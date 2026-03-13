# Compact Graph Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply `compact_json` to all graph tool outputs in the MCP server layer so tokkit eats its own cooking.

**Architecture:** One helper function `_try_compact` in `tools.py` that pipes JSON results through `compact_json` before returning to the agent. `make_meta` gains a `display_size` parameter so baseline estimation still uses raw JSON (needs parsing) while content_tokens reflects the compacted size.

**Tech Stack:** Python, existing `tokkit_json.compact_json`

---

### Task 1: Add `_try_compact` helper

**Files:**
- Create: `tests/server/test_compact_graph.py`
- Modify: `py/tokkit_server/tools.py`

- [ ] **Step 1: Write failing tests for `_try_compact`**

```python
# tests/server/test_compact_graph.py
"""Tests for graph output compaction in the MCP layer."""
import json

from tokkit_server.tools import _try_compact


def test_try_compact_reduces_json_array():
    raw = json.dumps([
        {"id": 1, "name": "foo", "label": "Function", "file": "a.py"},
        {"id": 2, "name": "bar", "label": "Function", "file": "b.py"},
    ])
    result = _try_compact(raw)
    assert len(result) < len(raw)
    assert "foo" in result
    assert "bar" in result


def test_try_compact_passthrough_on_invalid_json():
    raw = "not json at all"
    result = _try_compact(raw)
    assert result == raw


def test_try_compact_passthrough_on_empty():
    assert _try_compact("") == ""
    assert _try_compact("[]") == "[]"


def test_try_compact_passthrough_when_larger():
    # Single small object — compact header overhead exceeds savings
    raw = '{"a":1}'
    result = _try_compact(raw)
    # Should return whichever is smaller (or raw if equal)
    assert len(result) <= len(raw) or result == raw
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/server/test_compact_graph.py -v`
Expected: ImportError — `_try_compact` does not exist yet

- [ ] **Step 3: Implement `_try_compact`**

Add to `py/tokkit_server/tools.py`, after the `_err` function (around line 45):

```python
def _try_compact(result: str) -> str:
    """Compact JSON result via compact_json. Fall back to raw on error or expansion."""
    if not result or not result.strip() or result.strip() in ("[]", "{}"):
        return result
    try:
        from tokkit_json import compact_json
        compacted = compact_json(result)
        if len(compacted) < len(result):
            return compacted
    except Exception:
        pass
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/server/test_compact_graph.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/server/test_compact_graph.py py/tokkit_server/tools.py
git commit -m "feat: add _try_compact helper for graph output compaction"
```

---

### Task 2: Add `display_size` parameter to `make_meta`

**Files:**
- Create: `tests/server/test_display_size.py`
- Modify: `py/tokkit_server/token_stats.py`

**Why:** `make_meta` computes `content_tokens` from `len(result_text)`. After compaction, the text sent to the agent is smaller than the raw JSON passed to `make_meta` for baseline estimation. `display_size` lets the caller say "the raw JSON is X bytes (use it for baseline parsing), but the agent actually sees Y bytes (use it for content_tokens)."

- [ ] **Step 1: Write failing test**

```python
# tests/server/test_display_size.py
"""Tests for make_meta display_size parameter."""
from unittest.mock import patch

from tokkit_server.token_stats import make_meta, CHARS_PER_TOKEN


def test_make_meta_uses_display_size_for_content_tokens():
    raw_json = '{"id":1,"name":"foo","label":"Function","file":"a.py","line_start":1,"line_end":10}'
    display_size = 40  # simulates compacted size being smaller

    with patch("tokkit_server.token_stats.record_query"):
        meta = make_meta(
            "search_graph", raw_json, "/tmp/repo",
            display_size=display_size, args={"query": "foo"},
        )

    assert meta["content_tokens"] == display_size // CHARS_PER_TOKEN
    # baseline should still be computed from raw_json (not display_size)
    assert meta["baseline_tokens"] > 0


def test_make_meta_without_display_size_unchanged():
    raw_json = '{"id":1,"name":"foo"}'

    with patch("tokkit_server.token_stats.record_query"):
        meta = make_meta(
            "search_graph", raw_json, "/tmp/repo",
            args={"query": "foo"},
        )

    assert meta["content_tokens"] == len(raw_json.encode("utf-8")) // CHARS_PER_TOKEN
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/server/test_display_size.py -v`
Expected: FAIL — `make_meta` does not accept `display_size`

- [ ] **Step 3: Implement `display_size` parameter**

In `py/tokkit_server/token_stats.py`, modify `make_meta` (line 459):

Change:
```python
def make_meta(
    tool_name: str, result_text: str, session_project_path: str | None,
    raw_size: int | None = None, args: dict | None = None,
) -> dict:
```

To:
```python
def make_meta(
    tool_name: str, result_text: str, session_project_path: str | None,
    raw_size: int | None = None, display_size: int | None = None,
    args: dict | None = None,
) -> dict:
```

And change the `content_tokens` computation (line 468):

Change:
```python
    content_tokens = len(result_text.encode("utf-8")) // CHARS_PER_TOKEN
```

To:
```python
    effective_size = display_size if display_size is not None else len(result_text.encode("utf-8"))
    content_tokens = effective_size // CHARS_PER_TOKEN
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/server/test_display_size.py tests/server/ -v`
Expected: all PASS (new tests + existing tests still pass)

- [ ] **Step 5: Commit**

```bash
git add tests/server/test_display_size.py py/tokkit_server/token_stats.py
git commit -m "feat: add display_size param to make_meta for compacted output"
```

---

### Task 3: Wire compaction into graph tool handlers

**Files:**
- Modify: `py/tokkit_server/tools.py`
- Modify: `tests/server/test_compact_graph.py`

**Which tools get compacted (7):** search_graph, trace_fan, trace_path, get_architecture, detect_changes, get_graph_schema, list_projects

**Which tools do NOT (6):** get_code_snippet (value is code content), index_repository (status string), index_status (73 chars), get_token_stats (stats object), clean_html/compact_json/search_markdown/compact_output (already non-JSON or already compact)

- [ ] **Step 1: Write failing integration test**

Add to `tests/server/test_compact_graph.py`:

```python
from unittest.mock import patch
import tokkit_server.tools as tools_module


def _reset():
    tools_module._session_project_path = "/tmp/repo"
    tools_module._session_db_path = "/tmp/tokkit/repo.redb"


_MOCK_NODES = json.dumps([
    {"id": 1, "label": "Function", "name": "setup", "qualified_name": "proj::main.py::setup",
     "file_path": "/tmp/repo/main.py", "line_start": 1, "line_end": 20, "properties": {}},
    {"id": 2, "label": "Function", "name": "init", "qualified_name": "proj::main.py::init",
     "file_path": "/tmp/repo/main.py", "line_start": 22, "line_end": 40, "properties": {}},
])

_MOCK_STEPS = json.dumps([
    {"node": {"id": 1, "label": "Function", "name": "setup", "qualified_name": "proj::main.py::setup",
              "file_path": "/tmp/repo/main.py", "line_start": 1, "line_end": 20, "properties": {}},
     "edge": None, "depth": 0},
    {"node": {"id": 2, "label": "Function", "name": "init", "qualified_name": "proj::main.py::init",
              "file_path": "/tmp/repo/main.py", "line_start": 22, "line_end": 40, "properties": {}},
     "edge": {"source_id": 1, "target_id": 2, "edge_type": "Calls", "confidence": 0.9, "properties": {}},
     "depth": 1},
])


def test_search_graph_returns_compact():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_NODES):
        result = tools_module.handle_tool_call("search_graph", {"query": "setup"})
    text = result["content"][0]["text"]
    # Should NOT be valid JSON (it's been compacted to CSV)
    try:
        json.loads(text)
        is_json = True
    except json.JSONDecodeError:
        is_json = False
    assert not is_json, f"Expected compact format, got JSON: {text[:200]}"
    # But should contain the data
    assert "setup" in text
    assert "proj::main.py::setup" in text


def test_trace_fan_returns_compact():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_STEPS):
        result = tools_module.handle_tool_call("trace_fan", {
            "function_name": "proj::main.py::setup",
            "direction": "outbound",
            "depth": 3,
        })
    text = result["content"][0]["text"]
    assert "setup" in text
    assert "init" in text
    assert len(text) < len(_MOCK_STEPS)


def test_search_graph_compact_smaller_than_raw():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_NODES):
        result = tools_module.handle_tool_call("search_graph", {"query": "setup"})
    text = result["content"][0]["text"]
    assert len(text) < len(_MOCK_NODES)


def test_meta_reflects_compact_size():
    _reset()
    with patch.object(tools_module, "_call_rust", return_value=_MOCK_NODES):
        result = tools_module.handle_tool_call("search_graph", {"query": "setup"})
    text = result["content"][0]["text"]
    meta = result.get("_meta", {}).get("token_savings", {})
    expected_content = len(text.encode("utf-8")) // 4
    assert meta["content_tokens"] == expected_content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/server/test_compact_graph.py::test_search_graph_returns_compact -v`
Expected: FAIL — search_graph still returns raw JSON

- [ ] **Step 3: Apply compaction to all 7 graph tool handlers**

In `py/tokkit_server/tools.py`, modify each handler to compact before returning. The pattern for each tool:

```python
        if tool_name == "search_graph":
            # ... existing args extraction ...
            result = _call_rust("search_nodes", ...)
            compacted = _try_compact(result)
            meta = make_meta(tool_name, result, _session_project_path,
                             display_size=len(compacted.encode("utf-8")), args=args)
            return _ok(compacted, meta)
```

Apply this pattern to all 7 handlers. Each one changes from:
```python
            result = _call_rust(...)
            meta = make_meta(tool_name, result, ...)
            return _ok(result, meta)
```
To:
```python
            result = _call_rust(...)
            compacted = _try_compact(result)
            meta = make_meta(tool_name, result, ...,
                             display_size=len(compacted.encode("utf-8")), args=args)
            return _ok(compacted, meta)
```

The 7 tools to modify (line numbers in current tools.py):
1. **search_graph** (line 64-81)
2. **trace_path** (line 83-91)
3. **trace_fan** (line 93-101)
4. **get_architecture** (line 112-118)
5. **detect_changes** (line 129-134)
6. **get_graph_schema** (line 158-163)
7. **list_projects** (line 145-148)

- [ ] **Step 4: Run all tests**

Run: `pytest tests/server/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add py/tokkit_server/tools.py tests/server/test_compact_graph.py
git commit -m "feat: compact graph tool outputs via compact_json"
```

---

### Task 4: Fix benchmark test_q2 compact parsing

**Files:**
- Modify: `tests/e2e/benchmark/test_simulation.py`

**Why:** `test_q2_trace_calls` does `json.loads(search_resp)` then `nodes[0]["qualified_name"]` on the search_graph response. After Task 3, search_graph returns compact CSV, not JSON. This test will break.

- [ ] **Step 1: Add a compact-format parser helper**

At the top of `tests/e2e/benchmark/test_simulation.py`, add:

```python
def _parse_compact_nodes(response: str) -> list[dict]:
    """Parse search_graph response — handles both JSON and compact CSV formats."""
    try:
        return json.loads(response)
    except (json.JSONDecodeError, ValueError):
        pass
    # Compact CSV: header line [col;col;...] then data lines
    lines = response.strip().splitlines()
    if len(lines) < 2:
        return []
    header = lines[0].strip("[]").split(";")
    # Clean nested type annotations from header (e.g., "properties:{}" -> "properties")
    header = [h.split(":")[0] if ":" in h and not h.startswith("{") else h for h in header]
    results = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split(";", len(header) - 1)
        results.append(dict(zip(header, values)))
    return results
```

- [ ] **Step 2: Update test_q2 to use the parser**

Change `test_q2_trace_calls` (line 60-61):

From:
```python
        nodes = json.loads(search_resp)
        assert len(nodes) > 0, "No 'setup' function found in index"
        start_qn = nodes[0]["qualified_name"]
```

To:
```python
        nodes = _parse_compact_nodes(search_resp)
        assert len(nodes) > 0, "No 'setup' function found in index"
        start_qn = nodes[0]["qualified_name"]
```

- [ ] **Step 3: Run the benchmark simulation tests**

Run: `pytest tests/e2e/benchmark/test_simulation.py -v -k "q1 or q2 or q3" --benchmark`
Expected: all PASS (q1 and q2 may show better savings now)

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark`
Expected: all PASS

Run: `pytest tests/e2e/benchmark/test_simulation.py -v --benchmark`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/benchmark/test_simulation.py
git commit -m "fix: handle compact graph output in benchmark test"
```
