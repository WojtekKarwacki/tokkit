"""Unit tests for markdown section search and ranking."""

from tokkit_markdown.search import search_markdown, _score_section
from tokkit_markdown.parser import parse_markdown, Section


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install to get started.

### Authentication
Set up your API key for authentication.

### Database Setup
Configure your database connection string.

## Configuration
Edit the config file.

# API Reference
Full API documentation.

## Auth Endpoints
POST /login to authenticate users.

## User Endpoints
GET /users returns user list.
"""


def test_exact_header_match():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert results[0]["title"] == "Authentication"
    assert results[0]["match_type"] == "header"


def test_case_insensitive_header():
    results = search_markdown(SAMPLE_MD, "authentication")
    assert len(results) > 0
    assert results[0]["title"] == "Authentication"


def test_partial_header_match():
    results = search_markdown(SAMPLE_MD, "auth")
    assert len(results) > 0
    # Should match Authentication and Auth Endpoints
    titles = [r["title"] for r in results]
    assert "Authentication" in titles
    assert "Auth Endpoints" in titles


def test_deeper_header_ranks_higher():
    results = search_markdown(SAMPLE_MD, "auth")
    titles = [r["title"] for r in results]
    # h3 Authentication should rank above h2 Auth Endpoints
    auth_idx = titles.index("Authentication")
    endpoints_idx = titles.index("Auth Endpoints")
    assert auth_idx < endpoints_idx


def test_content_match_lower_rank():
    results = search_markdown(SAMPLE_MD, "authenticate")
    # "authenticate" appears in Auth Endpoints content ("POST /login to authenticate users")
    # and in Authentication header ("Authentication")
    assert len(results) > 0
    header_matches = [r for r in results if r["match_type"] == "header"]
    content_matches = [r for r in results if r["match_type"] == "content"]
    if header_matches and content_matches:
        assert header_matches[0]["score"] > content_matches[0]["score"]


def test_content_match_found():
    results = search_markdown(SAMPLE_MD, "pip install")
    assert len(results) > 0
    assert results[0]["title"] == "Installation"
    assert results[0]["match_type"] == "content"


def test_no_match_returns_empty():
    results = search_markdown(SAMPLE_MD, "xyznonexistent")
    assert results == []


def test_empty_query_returns_empty():
    results = search_markdown(SAMPLE_MD, "")
    assert results == []


def test_multi_word_query():
    results = search_markdown(SAMPLE_MD, "database setup")
    assert len(results) > 0
    assert results[0]["title"] == "Database Setup"


def test_multi_word_partial_match():
    # "API auth" — should match sections containing either word
    results = search_markdown(SAMPLE_MD, "API auth")
    titles = [r["title"] for r in results]
    assert len(results) > 0


def test_result_has_path():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    path = results[0]["path"]
    assert "Getting Started" in path
    assert "Installation" in path
    assert "Authentication" in path


def test_result_has_content():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert "API key" in results[0]["content"]


def test_result_has_score():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert isinstance(results[0]["score"], float)
    assert results[0]["score"] > 0


def test_result_has_token_estimate():
    results = search_markdown(SAMPLE_MD, "Authentication")
    assert len(results) > 0
    assert "tokens" in results[0]
    assert results[0]["tokens"] > 0


def test_section_with_children_includes_subtree():
    results = search_markdown(SAMPLE_MD, "Installation")
    assert len(results) > 0
    content = results[0]["content"]
    # Installation's children (Authentication, Database Setup) should be in content
    assert "Authentication" in content
    assert "Database Setup" in content


def test_results_sorted_by_score():
    results = search_markdown(SAMPLE_MD, "auth")
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_empty_markdown():
    results = search_markdown("", "test")
    assert results == []


def test_no_headers_markdown():
    results = search_markdown("Just plain text with auth keyword.", "auth")
    assert len(results) > 0
    assert results[0]["match_type"] == "content"


def test_depth_bonus_scoring():
    """Verify h3 header match scores higher than h1 header match."""
    md = """# Auth Overview
Overview of auth.

## Details
Some details.

### Auth Config
Specific auth config.
"""
    results = search_markdown(md, "auth")
    titles = [r["title"] for r in results]
    # h3 "Auth Config" should rank above h1 "Auth Overview" due to depth bonus
    config_idx = titles.index("Auth Config")
    overview_idx = titles.index("Auth Overview")
    assert config_idx < overview_idx
