"""Benchmark scenarios: formalized prompts for real agent dispatch.

Each scenario defines:
- question: the natural-language task (identical for both agents)
- tokkit_prompt: full prompt for the tokkit agent (question + system instruction)
- baseline_prompt: full prompt for the baseline agent (question + restriction)
- expected_tool: the MCP tool the tokkit agent should call
- fixture_path: relative path to fixture file (for content tools), or None
- category: grouping for report

The tokkit agent gets a system instruction to prefer tokkit MCP tools.
The baseline agent gets a restriction to use only built-in tools.
Both receive the same question so the comparison is fair.

The key principle: prompts include file paths and content-type hints so the
agent can match the task to the right MCP tool based on tool descriptions.
Without file paths, agents default to Read/Grep even when better tools exist.
"""

from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CACHE_DIR = Path(__file__).parent / ".cache"


# ---------------------------------------------------------------------------
# System instructions
# ---------------------------------------------------------------------------

TOKKIT_SYSTEM = (
    "You have access to tokkit MCP tools for code intelligence and content processing. "
    "These tools process data server-side so raw content never enters your context — "
    "always prefer them over built-in Read/Grep when the task matches a tokkit tool. "
    "Available tokkit tools: index_repository, get_architecture, find_dead_code, "
    "find_routes, trace_fan, clean_html, compact_json, search_markdown, compact_output."
)

BASELINE_SYSTEM = (
    "Answer the question using only the built-in tools: Read, Grep, Glob, Bash. "
    "Do NOT use any MCP tools even if they are available."
)


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    id: str                 # e.g. "q1"
    category: str           # e.g. "Code graph"
    task: str               # short label for reports
    question: str           # the natural-language question
    expected_tool: str      # MCP tool the tokkit agent should call
    fixture_path: str | None = None  # relative to repo root


def _repo_path() -> str:
    """Return absolute path to the cached benchmark repo."""
    return str(CACHE_DIR / "fastapi")


def _fixture(name: str) -> str:
    """Return absolute path to a benchmark fixture."""
    return str(FIXTURES_DIR / name)


# ---------------------------------------------------------------------------
# The 12 benchmark scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    # --- Code graph (Q1-Q5) ---
    Scenario(
        id="q1",
        category="Code graph",
        task="Blast radius analysis",
        question=(
            "Which functions are affected if I change `get_openapi`? "
            "Show all callers, transitively."
        ),
        expected_tool="trace_fan",
    ),
    Scenario(
        id="q2",
        category="Code graph",
        task="Trace setup call chain",
        question=(
            "Trace the call chain starting from the `setup` function, "
            "going 3 levels deep. Show what functions it calls, and what those call in turn."
        ),
        expected_tool="trace_fan",
    ),
    Scenario(
        id="q3",
        category="Code graph",
        task="Dead code detection",
        question=(
            "Find functions in the fastapi codebase that appear to be dead code "
            "— defined but never referenced anywhere."
        ),
        expected_tool="find_dead_code",
    ),
    Scenario(
        id="q4",
        category="Code graph",
        task="List route handlers",
        question=(
            "List all HTTP route handlers in this project — show the HTTP method, "
            "route path, and handler function name."
        ),
        expected_tool="find_routes",
    ),
    Scenario(
        id="q5",
        category="Code graph",
        task="Architecture overview",
        question=(
            "Give me an architecture overview of this project. What are the main modules, "
            "key abstractions, and how is the code organized?"
        ),
        expected_tool="get_architecture",
    ),
    # --- Markdown (Q6) ---
    Scenario(
        id="q6",
        category="Markdown",
        task="Search README",
        question=(
            "What are the dependencies and requirements for this project? "
            "Search the README at {repo}/README.md for the relevant sections."
        ),
        expected_tool="search_markdown",
    ),
    # --- HTML (Q7-Q8) ---
    Scenario(
        id="q7",
        category="HTML",
        task="Clean Python docs (14KB)",
        question=(
            "Summarize the Python datetime documentation from the HTML file at "
            "{fixtures}/html/python_docs.html"
        ),
        expected_tool="clean_html",
        fixture_path="html/python_docs.html",
    ),
    Scenario(
        id="q8",
        category="HTML",
        task="Clean blog post (24KB)",
        question=(
            "Summarize the blog post about async/await from the HTML file at "
            "{fixtures}/html/blog_post.html"
        ),
        expected_tool="clean_html",
        fixture_path="html/blog_post.html",
    ),
    # --- JSON (Q9-Q10) ---
    Scenario(
        id="q9",
        category="JSON",
        task="Compact flat records (14KB)",
        question=(
            "Summarize the records in the JSON file at "
            "{fixtures}/json/flat_records.json"
        ),
        expected_tool="compact_json",
        fixture_path="json/flat_records.json",
    ),
    Scenario(
        id="q10",
        category="JSON",
        task="Compact nested data (10KB)",
        question=(
            "Summarize the structure of the JSON data at "
            "{fixtures}/json/nested_complex.json"
        ),
        expected_tool="compact_json",
        fixture_path="json/nested_complex.json",
    ),
    # --- Shell output (Q11-Q12) ---
    Scenario(
        id="q11",
        category="Shell output",
        task="Compress pytest (13.7KB)",
        question=(
            "Summarize the pytest results in "
            "{fixtures}/shell/pytest_output.txt — what passed, what failed, and why."
        ),
        expected_tool="compact_output",
        fixture_path="shell/pytest_output.txt",
    ),
    Scenario(
        id="q12",
        category="Shell output",
        task="Compress ruff lint (8.3KB)",
        question=(
            "Summarize the ruff lint violations in "
            "{fixtures}/shell/ruff_output.txt"
        ),
        expected_tool="compact_output",
        fixture_path="shell/ruff_output.txt",
    ),
]


def resolve_prompt(scenario: Scenario, *, agent: str) -> str:
    """Build the full prompt for a scenario.

    Args:
        scenario: The benchmark scenario.
        agent: Either "tokkit" or "baseline".

    Returns:
        Complete prompt string with system instruction + resolved question.
    """
    repo = _repo_path()
    fixtures = str(FIXTURES_DIR)
    question = scenario.question.format(repo=repo, fixtures=fixtures)

    if agent == "tokkit":
        system = TOKKIT_SYSTEM
        # For code graph tools, remind about indexing
        if scenario.expected_tool in ("trace_fan", "find_dead_code", "find_routes", "get_architecture"):
            system += (
                f"\n\nThe repository is at {repo}. "
                "Call index_repository first, then use the appropriate graph tool."
            )
    elif agent == "baseline":
        system = BASELINE_SYSTEM
    else:
        raise ValueError(f"Unknown agent type: {agent}")

    return f"{system}\n\n{question}"
