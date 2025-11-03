"""Integration tests for the search_markdown public API."""

from tokkit_markdown import search_markdown


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install to get started.

### Authentication
Set up your API key for auth.

## Configuration
Edit the config file.

# API Reference
Full API documentation.

## Auth Endpoints
POST /login to authenticate users.
"""


def test_search_with_matches_returns_formatted_string():
    output = search_markdown(SAMPLE_MD, "auth")
    assert "Matches:" in output
    assert "Savings:" in output
    assert "Authentication" in output


def test_search_no_matches_returns_header_tree():
    output = search_markdown(SAMPLE_MD, "xyznonexistent")
    assert "No matches" in output
    assert "# Getting Started" in output
    assert "## Installation" in output


def test_search_empty_query_returns_header_tree():
    output = search_markdown(SAMPLE_MD, "")
    assert "Document headers:" in output
    assert "# Getting Started" in output


def test_search_empty_markdown():
    output = search_markdown("", "test")
    assert output == ""


def test_search_returns_token_savings():
    output = search_markdown(SAMPLE_MD, "Authentication")
    assert "tokens" in output
    assert "Savings:" in output


def test_search_result_ordering():
    output = search_markdown(SAMPLE_MD, "auth")
    # Authentication (h3, header match) should appear before Auth Endpoints (h2, header match)
    auth_pos = output.index("Authentication")
    endpoints_pos = output.index("Auth Endpoints")
    assert auth_pos < endpoints_pos
