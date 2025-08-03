"""Tests for token savings tracking."""
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from tokkit_server import token_stats


@pytest.fixture(autouse=True)
def clean_stats(tmp_path):
    """Use a temp dir for stats and reset session identity to avoid pollution."""
    stats_file = str(tmp_path / "token_stats.json")
    orig_chat_id = token_stats._chat_id
    orig_agent = token_stats._agent
    orig_start = token_stats._session_start
    with patch.object(token_stats, "_stats_path", return_value=stats_file):
        token_stats._chat_id = "test-chat-1"
        token_stats._agent = "test-agent"
        yield
    token_stats._chat_id = orig_chat_id
    token_stats._agent = orig_agent
    token_stats._session_start = orig_start


def test_initial_stats_are_zero():
    stats = token_stats.get_stats()
    assert stats["total_queries"] == 0
    assert stats["total_content_saved"] == 0
    assert stats["savings_pct"] == 0.0
    assert stats["total_baseline_calls"] == 0
    assert stats["calls_saved"] == 0


def test_record_query_accumulates():
    token_stats.record_query("find_dead_code", 100, 5000, baseline_calls=50)
    token_stats.record_query("find_dead_code", 150, 6000, baseline_calls=60)

    stats = token_stats.get_stats()
    assert stats["total_queries"] == 2
    assert stats["total_content_tokens"] == 250
    assert stats["total_baseline_tokens"] == 11000
    assert stats["total_content_saved"] == 10750
    assert stats["total_baseline_calls"] == 110
    assert stats["calls_saved"] == 108  # (50-1) + (60-1)
    assert stats["by_tool"]["find_dead_code"]["queries"] == 2
    assert stats["by_tool"]["find_dead_code"]["baseline_calls"] == 110


def test_savings_percentage():
    token_stats.record_query("find_dead_code", 100, 10000)
    stats = token_stats.get_stats()
    assert stats["savings_pct"] == 99.0
    assert stats["efficiency_ratio"] == 100.0


def test_make_meta_returns_dict():
    meta = token_stats.make_meta("index_repository", '{"node_count":10}', "/tmp/repo")
    assert "content_tokens" in meta
    assert "baseline_tokens" in meta
    assert "content_saved" in meta
    assert "baseline_calls" in meta
    assert isinstance(meta["content_tokens"], int)


def test_estimate_find_dead_code(tmp_path):
    """Dead code baseline scales with repo file count, not result count."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for i in range(10):
        (pkg / f"mod_{i}.py").write_text("def f(): pass\n" * 8)

    result_text = json.dumps([{"name": "unused_func"}])
    baseline = token_stats.estimate_baseline_content_tokens(
        "find_dead_code",
        {},
        result_text,
        str(tmp_path),
    )
    # 11 files × 8 defs = 88 defs. Should produce substantial baseline.
    assert baseline > 500


def test_estimate_find_routes():
    """Route listing baseline: Grep(content, -A=1) for decorators."""
    nodes = [{"name": f"route_{i}"} for i in range(10)]
    result_text = json.dumps(nodes)
    baseline = token_stats.estimate_baseline_content_tokens(
        "find_routes",
        {},
        result_text,
        "/tmp/repo",
    )
    # 10 routes × 2 lines × 80 chars / 4 = 400 tokens
    assert baseline == 400


def test_estimate_architecture_not_entire_repo(tmp_path):
    """Architecture baseline reads targeted files, NOT the entire repo."""
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# init\n" * 5)
    for i in range(7):
        (pkg / f"module_{i}.py").write_text("x" * 2000)
    (tmp_path / "README.md").write_text("# My Project\n" * 50)

    baseline = token_stats.estimate_baseline_content_tokens(
        "get_architecture", {}, "{}", str(tmp_path),
    )
    # Should be reasonable, not inflated
    assert baseline >= 500
    # Total source = 7*2000 + init + README = ~15K chars = ~3750 tokens
    # Architecture baseline should be LESS than reading everything
    total_source = (7 * 2000 + 50 * 14 + 5 * 7) // 4
    assert baseline < total_source


def test_estimate_index_returns_zero():
    baseline = token_stats.estimate_baseline_content_tokens(
        "index_repository", {}, "{}", "/tmp",
    )
    assert baseline == 0


def test_estimate_clean_html_uses_raw_size():
    """Transformation tools use raw input size as baseline."""
    baseline = token_stats.estimate_baseline_content_tokens(
        "clean_html", {}, "short output", None, raw_size=10000,
    )
    assert baseline == 2500  # 10000 / 4


def test_reset_stats():
    token_stats.record_query("find_dead_code", 100, 5000)
    token_stats.reset_stats()
    stats = token_stats.get_stats()
    assert stats["total_queries"] == 0


def test_get_stats_includes_methodology():
    stats = token_stats.get_stats()
    assert "methodology" in stats
    m = stats["methodology"]
    assert "what_is_measured" in m
    assert "what_baseline_means" in m
    assert "estimated_total_model" in m
    assert "baseline_strategies" in m
    assert m["chars_per_token"] == 4


def test_show_savings_default_off():
    assert token_stats.show_savings() is False


def test_show_savings_enabled(monkeypatch):
    monkeypatch.setenv("TOKKIT_SHOW_SAVINGS", "1")
    assert token_stats.show_savings() is True


def test_show_savings_other_values_off(monkeypatch):
    monkeypatch.setenv("TOKKIT_SHOW_SAVINGS", "true")
    assert token_stats.show_savings() is False


def test_data_dir_default(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    d = token_stats._data_dir()
    assert d == str(tmp_path / ".local" / "share" / "tokkit")
    assert os.path.isdir(d)


def test_data_dir_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "custom"))
    d = token_stats._data_dir()
    assert d == str(tmp_path / "custom" / "tokkit")
    assert os.path.isdir(d)


def test_old_format_stats_reset_gracefully(tmp_path):
    """Old v1/v2 stats format is ignored and reset to empty."""
    stats_file = str(tmp_path / "old_stats.json")
    with open(stats_file, "w") as f:
        json.dump({
            "format_version": 2,
            "total_queries": 50,
            "total_content_tokens": 1000,
            "total_baseline_tokens": 50000,
            "total_content_saved": 49000,
            "by_tool": {},
            "sessions": [],
        }, f)

    with patch.object(token_stats, "_stats_path", return_value=stats_file):
        stats = token_stats.get_stats()
        assert stats["total_queries"] == 0
        assert stats["format_version"] == 4


def test_v3_format_migrated_to_v4(tmp_path):
    """v3 stats are migrated to v4 with chats dict preserved."""
    stats_file = str(tmp_path / "v3_stats.json")
    with open(stats_file, "w") as f:
        json.dump({
            "format_version": 3,
            "total_queries": 10,
            "total_content_tokens": 500,
            "total_baseline_tokens": 5000,
            "total_content_saved": 4500,
            "total_baseline_calls": 20,
            "calls_saved": 10,
            "by_tool": {},
            "sessions": [],
        }, f)

    with patch.object(token_stats, "_stats_path", return_value=stats_file):
        stats = token_stats.get_stats()
        assert stats["format_version"] == 4
        assert stats["total_queries"] == 10
        assert "chats" in stats


def test_trace_fan_baseline_not_zero():
    """trace_fan must use _baseline_trace, not return 0."""
    trace_result = json.dumps({
        "root": "myapp::src/main.py::setup",
        "levels": [
            {"depth": 1, "nodes": [
                {"name": "init_db"}, {"name": "load_config"}, {"name": "start_server"},
            ]},
            {"depth": 2, "nodes": [
                {"name": "connect"}, {"name": "read_env"},
            ]},
        ],
    })
    baseline = token_stats.estimate_baseline_content_tokens(
        "trace_fan", {}, trace_result, "/tmp/repo",
    )
    # 5 nodes + 1 root = 6, each needs grep+read → substantial baseline
    assert baseline > 500


def test_estimate_baseline_calls_trace_fan():
    """trace_fan baseline calls scale with node count."""
    trace_result = json.dumps({
        "root": "app::main",
        "levels": [
            {"depth": 1, "nodes": [{"name": "a"}, {"name": "b"}, {"name": "c"}]},
            {"depth": 2, "nodes": [{"name": "d"}, {"name": "e"}]},
        ],
    })
    calls = token_stats.estimate_baseline_calls("trace_fan", {}, trace_result)
    # 5 nodes + 1 root = 6, × 2 (grep+read) = 12
    assert calls == 12


def test_estimate_baseline_calls_find_dead_code(tmp_path):
    """find_dead_code baseline calls scale with repo size."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for i in range(10):
        (pkg / f"mod_{i}.py").write_text("def f(): pass\n" * 8)

    calls = token_stats.estimate_baseline_calls(
        "find_dead_code", {}, "[]", str(tmp_path),
    )
    # 11 files × 8 defs × 0.6 checkable = 52.8 → 1 + 52 = 53
    assert calls > 40


def test_estimate_baseline_calls_transform_tools():
    """Transformation tools replace exactly 1 Read call."""
    for tool in ("clean_html", "compact_json", "search_markdown", "compact_output"):
        calls = token_stats.estimate_baseline_calls(tool, {}, "result")
        assert calls == 1, f"{tool} should be 1 call"


def test_estimated_total_in_stats():
    """get_stats includes estimated_total with context-aware savings."""
    # Simulate trace_fan: 1 MCP call replacing 12 baseline calls
    token_stats.record_query("trace_fan", 500, 5000, baseline_calls=12)

    stats = token_stats.get_stats()
    est = stats["estimated_total"]
    assert est["with_tokkit"] > 0
    assert est["without_tokkit"] > est["with_tokkit"]
    assert est["saved"] > 0
    assert est["savings_pct"] > 0
    assert est["overhead_per_turn"] == 23_350


def test_estimated_total_overhead_matters():
    """More baseline calls = more overhead = higher estimated_total savings."""
    # Few baseline calls (transform tool)
    token_stats.record_query("clean_html", 500, 2000, baseline_calls=1)
    stats_few = token_stats.get_stats()

    token_stats.reset_stats()

    # Many baseline calls (dead code scan)
    token_stats.record_query("find_dead_code", 500, 2000, baseline_calls=50)
    stats_many = token_stats.get_stats()

    # Same content savings, but dead code should show more total savings
    # because of the overhead from 50 extra calls
    assert stats_many["estimated_total"]["saved"] > stats_few["estimated_total"]["saved"]


# ---------------------------------------------------------------------------
# Per-chat and per-agent tracking
# ---------------------------------------------------------------------------

def test_record_query_creates_chat_entry():
    token_stats.record_query("clean_html", 100, 2000, baseline_calls=1)
    stats = token_stats.get_stats()
    assert "test-chat-1" in stats["by_chat"]
    chat = stats["by_chat"]["test-chat-1"]
    assert chat["agent"] == "test-agent"
    assert chat["queries"] == 1
    assert chat["content_tokens"] == 100
    assert chat["baseline_tokens"] == 2000
    assert chat["content_saved"] == 1900
    assert chat["savings_pct"] == 95.0
    assert "by_tool" in chat
    assert "clean_html" in chat["by_tool"]


def test_multiple_queries_same_chat():
    token_stats.record_query("clean_html", 100, 2000, baseline_calls=1)
    token_stats.record_query("compact_json", 200, 3000, baseline_calls=1)
    stats = token_stats.get_stats()
    chat = stats["by_chat"]["test-chat-1"]
    assert chat["queries"] == 2
    assert chat["content_tokens"] == 300
    assert chat["baseline_tokens"] == 5000
    assert chat["content_saved"] == 4700


def test_multiple_chats_different_agents():
    """Simulate two chats from different agents."""
    token_stats._chat_id = "chat-aaa"
    token_stats._agent = "claude-code"
    token_stats.record_query("clean_html", 100, 2000, baseline_calls=1)

    token_stats._chat_id = "chat-bbb"
    token_stats._agent = "cursor"
    token_stats.record_query("compact_json", 200, 3000, baseline_calls=1)

    stats = token_stats.get_stats()
    assert len(stats["by_chat"]) == 2
    assert stats["by_chat"]["chat-aaa"]["agent"] == "claude-code"
    assert stats["by_chat"]["chat-bbb"]["agent"] == "cursor"


def test_by_agent_aggregation():
    """Per-agent summary aggregates across chats."""
    token_stats._chat_id = "chat-1"
    token_stats._agent = "claude-code"
    token_stats.record_query("clean_html", 100, 2000, baseline_calls=1)

    token_stats._chat_id = "chat-2"
    token_stats._agent = "claude-code"
    token_stats.record_query("compact_json", 200, 3000, baseline_calls=1)

    token_stats._chat_id = "chat-3"
    token_stats._agent = "cursor"
    token_stats.record_query("clean_html", 50, 1000, baseline_calls=1)

    stats = token_stats.get_stats()
    by_agent = stats["by_agent"]

    assert "claude-code" in by_agent
    assert "cursor" in by_agent

    cc = by_agent["claude-code"]
    assert cc["chats"] == 2
    assert cc["total_queries"] == 2
    assert cc["total_content_tokens"] == 300
    assert cc["total_baseline_tokens"] == 5000
    assert cc["total_content_saved"] == 4700
    assert cc["savings_pct"] == 94.0

    cur = by_agent["cursor"]
    assert cur["chats"] == 1
    assert cur["total_queries"] == 1
    assert cur["total_content_tokens"] == 50
    assert cur["savings_pct"] == 95.0


def test_set_session_info():
    token_stats.set_session_info("windsurf", chat_id="custom-id")
    assert token_stats._agent == "windsurf"
    assert token_stats._chat_id == "custom-id"

    token_stats.record_query("clean_html", 100, 500, baseline_calls=1)
    stats = token_stats.get_stats()
    assert "custom-id" in stats["by_chat"]
    assert stats["by_chat"]["custom-id"]["agent"] == "windsurf"


def test_get_session_info():
    info = token_stats.get_session_info()
    assert info["chat_id"] == "test-chat-1"
    assert info["agent"] == "test-agent"
    assert "started_at" in info


def test_reset_clears_chats():
    token_stats.record_query("clean_html", 100, 2000, baseline_calls=1)
    token_stats.reset_stats()
    stats = token_stats.get_stats()
    assert stats["by_chat"] == {}
# rev-18
    assert stats["by_agent"] == {}
