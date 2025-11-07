"""Unit tests for markdown search output formatting."""

from tokkit_markdown.formatter import format_results, format_header_tree
from tokkit_markdown.parser import parse_markdown


SAMPLE_MD = """# Getting Started
Welcome to the project.

## Installation
Run pip install.

### Authentication
Set up your API key.

## Configuration
Edit the config.

# API Reference
Full API docs.
"""


def test_format_results_header_line():
    results = [
        {
            "title": "Authentication",
            "path": "# Getting Started > ## Installation > ### Authentication",
            "score": 1.15,
            "match_type": "header",
            "content": "Set up your API key.",
            "tokens": 5,
        }
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "Matches: 1" in output
    assert "Document: ~500 tokens" in output
    assert "Returned: ~5 tokens" in output
    assert "Savings:" in output


def test_format_results_section_block():
    results = [
        {
            "title": "Authentication",
            "path": "# Getting Started > ## Installation > ### Authentication",
            "score": 1.15,
            "match_type": "header",
            "content": "Set up your API key.",
            "tokens": 5,
        }
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "### Authentication" in output
    assert "score: 1.15" in output
    assert "match: header" in output
    assert "~5 tokens" in output
    assert "Path:" in output
    assert "Set up your API key." in output


def test_format_results_multiple():
    results = [
        {
            "title": "First",
            "path": "# First",
            "score": 1.1,
            "match_type": "header",
            "content": "Content one.",
            "tokens": 3,
        },
        {
            "title": "Second",
            "path": "# Second",
            "score": 0.3,
            "match_type": "content",
            "content": "Content two.",
            "tokens": 3,
        },
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "Matches: 2" in output
    first_pos = output.index("First")
    second_pos = output.index("Second")
    assert first_pos < second_pos


def test_format_results_savings_percentage():
    results = [
        {
            "title": "Small",
            "path": "# Small",
            "score": 1.0,
            "match_type": "header",
            "content": "Tiny.",
            "tokens": 50,
        }
    ]
    output = format_results(results, total_doc_tokens=500)
    assert "90%" in output


def test_format_header_tree():
    sections = parse_markdown(SAMPLE_MD)
    output = format_header_tree(sections, query="foobar")
    assert 'No matches for "foobar"' in output
    assert "# Getting Started" in output
    assert "  ## Installation" in output
    assert "    ### Authentication" in output
    assert "  ## Configuration" in output
    assert "# API Reference" in output
    assert "tokens" in output


def test_format_header_tree_indentation():
    sections = parse_markdown(SAMPLE_MD)
    output = format_header_tree(sections, query="xyz")
    lines = output.strip().split("\n")
    # Find the Authentication line — should be indented more than Installation
    install_line = next(l for l in lines if "Installation" in l)
    auth_line = next(l for l in lines if "Authentication" in l)
    assert len(auth_line) - len(auth_line.lstrip()) > len(install_line) - len(install_line.lstrip())


def test_format_header_tree_empty_query():
    sections = parse_markdown(SAMPLE_MD)
    output = format_header_tree(sections, query="")
    assert "Document headers:" in output


def test_format_results_empty():
    output = format_results([], total_doc_tokens=500)
    assert output == ""
