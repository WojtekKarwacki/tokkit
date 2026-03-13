# Compact Graph Output

**Date:** 2026-04-10
**Status:** Draft

## Problem

Tokkit's graph tools (search_graph, trace_fan, trace_path, etc.) return raw JSON with full Node/Edge structs. Meanwhile tokkit has `compact_json` that compresses exactly this kind of flat-array-of-objects data by 26-65%. The tools don't use it on their own output.

Measured on fastapi/fastapi:

| Tool call | Raw JSON | After compact_json | Savings |
|---|---|---|---|
| search_graph (routes, 200) | 3,395 chars | 1,214 chars | 65% |
| trace_fan (depth 3) | 2,181 chars | 1,297 chars | 41% |
| search_graph (setup, Function) | 2,143 chars | 1,448 chars | 33% |
| search_graph (Depends pattern) | 470 chars | 351 chars | 26% |
| get_graph_schema | 209 chars | 175 chars | 17% |

get_architecture returns up to 17K chars of JSON — largest graph output. Not measured with compact_json yet due to a state issue during testing, but expected savings are significant given it returns arrays of file paths, packages, and entry points.

## Design

### Where

One change in `py/tokkit_server/tools.py`. Add a helper that runs `compact_json` on a result string, with a fallback to raw if compaction fails or produces larger output.

### Which tools

Apply to every tool that returns JSON arrays or objects from the Rust backend:

| Tool | Output type | Apply |
|---|---|---|
| search_graph | `Vec<Node>` JSON array | yes |
| trace_fan | `Vec<PathStep>` JSON array | yes |
| trace_path | `Vec<PathStep>` JSON array | yes |
| get_architecture | JSON object with arrays | yes |
| detect_changes | `Vec<ChangedFile>` JSON array | yes |
| get_graph_schema | JSON object | yes |
| list_projects | JSON array | yes |
| get_code_snippet | JSON object (code content) | no |
| index_repository | status string | no |
| index_status | small JSON (73 chars) | no |
| get_token_stats | small JSON stats | no |

**get_code_snippet excluded**: its value is the source code content, not metadata. Compacting would mangle code.

**index_status excluded**: 73 chars, compaction overhead not worth it.

Tools already producing non-JSON output (clean_html, compact_json, search_markdown, compact_output) are unaffected.

### How

```python
def _try_compact(result: str) -> str:
    """Compact JSON result via compact_json. Fall back to raw on error or expansion."""
    try:
        from tokkit_json import compact_json
        compacted = compact_json(result)
        if len(compacted) < len(result):
            return compacted
        return result
    except Exception:
        return result
```

Call `_try_compact(result)` before passing to `_ok()` in each applicable tool handler.

### Token stats integration

The `make_meta` function in `token_stats.py` currently computes savings against an estimated baseline. After this change, `make_meta` should receive both the raw result (for baseline estimation) and the compacted result (for actual output size), so savings reporting reflects the compaction.

### Always-on

No opt-in parameter. Graph tools always return compact format. Rationale:
- Tokkit is an LLM tool; LLMs read CSV/compact format fine
- Programmatic consumers can use `tokkit_py` Python bindings directly for raw JSON
- Adding a parameter increases tool definition size (which itself costs tokens)

## Testing

1. **Unit test in `tests/test_server.py`**: mock `_call_rust` to return known JSON, verify `handle_tool_call` returns compact format for each applicable tool.
2. **Verify `_try_compact` fallback**: pass invalid JSON, verify raw passthrough.
3. **Verify no expansion**: pass tiny JSON where compact adds header overhead, verify raw returned.
4. **Benchmark regression**: re-run `pytest tests/e2e/benchmark/test_simulation.py` — content compression ratios for Q1-Q5 should improve.

## Scope

- `py/tokkit_server/tools.py` — add `_try_compact`, apply to 7 tool handlers
- `py/tokkit_server/token_stats.py` — adjust `make_meta` to track pre/post compaction
- `tests/test_server.py` — add tests for compact output
- `tests/e2e/benchmark/test_simulation.py` — update expected baselines if needed

## Out of scope

- Replacing/redesigning benchmark Q1 and Q2 (separate task)
- Stripping Node fields (id, empty properties) in Rust before serialization (separate optimization)
- Reducing MCP tool definition size (separate optimization)
