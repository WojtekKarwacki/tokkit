"""Tool dispatch for the MCP server."""

import json
import os
from pathlib import Path

from tokkit_server.token_stats import make_meta, get_stats, show_savings

_session_project_path: str | None = None
_session_db_path: str | None = None


def _get_cache_dir() -> str:
    if val := os.environ.get("TOKKIT_CACHE_DIR"):
        return val
    return str(Path("/tmp/tokkit"))


def _db_path_for(repo_path: str) -> str:
    project = Path(repo_path).resolve().name
    cache = _get_cache_dir()
    return str(Path(cache) / f"{project}.redb")


def _call_rust(fn_name: str, *args, **kwargs):
    """Lazy import of tokkit_py to allow tests to mock this function."""
    import tokkit_py
    return getattr(tokkit_py, fn_name)(*args, **kwargs)


def _ok(text: str, meta: dict | None = None) -> dict:
    body = text
    if meta and show_savings():
        saved = meta["content_saved"]
        pct = round((1 - meta["content_tokens"] / meta["baseline_tokens"]) * 100, 1) if meta["baseline_tokens"] > 0 else 0.0
        stats = get_stats()
        body += f"\n\n[tokkit: saved ~{saved:,} content tokens ({pct}%) | session total: {stats['total_content_saved']:,} content tokens saved]"
    result = {"content": [{"type": "text", "text": body}]}
    if meta:
        result["_meta"] = {"token_savings": meta}
    return result


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


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


def handle_tool_call(tool_name: str, args: dict) -> dict:
    """Dispatch a tool call and return an MCP tool result dict."""
    global _session_project_path, _session_db_path

    try:
        if tool_name == "index_repository":
            path = args.get("path", "")
            mode = args.get("mode", "full")
            if not path:
                return _err("path is required")
            result = _call_rust("index_repository", path, mode)
            _session_project_path = path
            _session_db_path = _db_path_for(path)
            meta = make_meta(tool_name, result, _session_project_path, args=args)
            return _ok(result, meta)

        if tool_name == "get_architecture":
            if not _session_db_path:
                return _err("No project indexed. Call index_repository first.")
            project = args.get("project", "")
            result = _call_rust("get_architecture", _session_db_path, project)
            compacted = _try_compact(result)
            meta = make_meta(tool_name, result, _session_project_path,
                             display_size=len(compacted.encode("utf-8")), args=args)
            return _ok(compacted, meta)

        if tool_name == "find_dead_code":
            if not _session_db_path:
                return _err("No project indexed. Call index_repository first.")
            limit = args.get("limit", 200)
            result = _call_rust(
                "search_nodes", _session_db_path, "",
                max_degree=0, exclude_entry_points=True, limit=limit,
            )
            compacted = _try_compact(result)
            meta = make_meta(tool_name, result, _session_project_path,
                             display_size=len(compacted.encode("utf-8")), args=args)
            return _ok(compacted, meta)

        if tool_name == "find_routes":
            if not _session_db_path:
                return _err("No project indexed. Call index_repository first.")
            limit = args.get("limit", 200)
            result = _call_rust(
                "search_nodes", _session_db_path, "",
                relationship="HANDLES", limit=limit,
            )
            compacted = _try_compact(result)
            meta = make_meta(tool_name, result, _session_project_path,
                             display_size=len(compacted.encode("utf-8")), args=args)
            return _ok(compacted, meta)

        if tool_name == "trace_fan":
            if not _session_db_path:
                return _err("No project indexed. Call index_repository first.")
            function_name = args.get("function_name", "")
            if not function_name:
                return _err("function_name is required")
            direction = args.get("direction", "outbound")
            depth = args.get("depth", 3)
            result = _call_rust("trace_fan", _session_db_path, function_name, direction=direction, depth=depth)
            compacted = _try_compact(result)
            meta = make_meta(tool_name, result, _session_project_path,
                             display_size=len(compacted.encode("utf-8")), args=args)
            return _ok(compacted, meta)

        if tool_name == "clean_html":
            html = args.get("html", "")
            path = args.get("path", "")
            mode = args.get("mode", "markdown")
            if path:
                try:
                    with open(path) as f:
                        html = f.read()
                except (OSError, IOError) as exc:
                    return _err(f"Cannot read file: {exc}")
            if not html:
                return _err("html or path is required")
            from tokkit_scraper import clean_html
            cleaned = clean_html(html, mode=mode)
            meta = make_meta(tool_name, cleaned, _session_project_path, raw_size=len(html), args=args)
            return _ok(cleaned, meta)

        if tool_name == "compact_json":
            json_str = args.get("json", "")
            path = args.get("path", "")
            if path:
                try:
                    with open(path) as f:
                        json_str = f.read()
                except (OSError, IOError) as exc:
                    return _err(f"Cannot read file: {exc}")
            if not json_str:
                return _err("json or path is required")
            from tokkit_json import compact_json
            compacted = compact_json(json_str)
            meta = make_meta(tool_name, compacted, _session_project_path, raw_size=len(json_str), args=args)
            return _ok(compacted, meta)

        if tool_name == "search_markdown":
            path = args.get("path", "")
            query = args.get("query", "")
            if not path:
                return _err("path is required")
            try:
                with open(path) as f:
                    markdown = f.read()
            except (OSError, IOError) as exc:
                return _err(f"Cannot read file: {exc}")
            from tokkit_markdown import search_markdown
            result = search_markdown(markdown, query)
            meta = make_meta(tool_name, result, _session_project_path, raw_size=len(markdown), args=args)
            return _ok(result, meta)

        if tool_name == "compact_output":
            text = args.get("text", "")
            path = args.get("path", "")
            hint = args.get("hint")
            verbose = args.get("verbose", False)
            if path:
                try:
                    with open(path) as f:
                        text = f.read()
                except (OSError, IOError) as exc:
                    return _err(f"Cannot read file: {exc}")
            if not text:
                return _err("text or path is required")
            from tokkit_output import compact_output
            compacted = compact_output(text, hint=hint, verbose=verbose)
            meta = make_meta(tool_name, compacted, _session_project_path, raw_size=len(text), args=args)
            return _ok(compacted, meta)

        return _err(f"Unknown tool: {tool_name}")

    except Exception as exc:
# rev-10
        return _err(f"Tool error: {exc}")
