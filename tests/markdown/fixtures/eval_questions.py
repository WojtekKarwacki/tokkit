"""Inference eval: markdown search questions, response models, and gold answers.

Each question targets a specific fact buried in a markdown document.
The gold answer is deterministic — computed from the fixture text itself.
"""

import os
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TextAnswer(BaseModel):
    answer: str


class ListAnswer(BaseModel):
    items: list[str]


class CountAnswer(BaseModel):
    count: int


class BoolAnswer(BaseModel):
    answer: bool


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "e2e", "benchmark", "fixtures", "markdown"
)


def load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


def load_readme() -> str:
    return load_fixture("project_readme.md")


def load_api_docs() -> str:
    return load_fixture("api_documentation.md")


def load_claude_md() -> str:
    return load_fixture("claude_md.md")


# ---------------------------------------------------------------------------
# Gold answers — project_readme.md
# ---------------------------------------------------------------------------

def gold_q1_auth_method(_md: str) -> TextAnswer:
    """Q1: What hashing algorithm does the OAuth2 example use?"""
    return TextAnswer(answer="bcrypt")


def gold_q2_test_client(_md: str) -> TextAnswer:
    """Q2: What library is the TestClient based on?"""
    return TextAnswer(answer="HTTPX")


def gold_q3_docker_base_image(_md: str) -> TextAnswer:
    """Q3: What Python base image does the Dockerfile use?"""
    return TextAnswer(answer="python:3.11-slim")


def gold_q4_cors_origins(_md: str) -> TextAnswer:
    """Q4: What value is set for allow_origins in the CORS middleware?"""
    return TextAnswer(answer='["*"]')


def gold_q5_changelog_versions(_md: str) -> CountAnswer:
    """Q5: How many changelog versions are listed?"""
    return CountAnswer(count=3)


# ---------------------------------------------------------------------------
# Gold answers — api_documentation.md
# ---------------------------------------------------------------------------

def gold_q6_test_key_prefix(_md: str) -> TextAnswer:
    """Q6: What prefix do test mode secret keys have?"""
    return TextAnswer(answer="sk_test_")


def gold_q7_error_types(_md: str) -> CountAnswer:
    """Q7: How many error types are listed in the error types table?"""
    return CountAnswer(count=4)


def gold_q8_pagination_params(_md: str) -> ListAnswer:
    """Q8: What are the pagination parameters?"""
    return ListAnswer(items=["limit", "starting_after", "ending_before"])


def gold_q9_webhook_events(_md: str) -> ListAnswer:
    """Q9: Which two events are enabled in the webhook endpoint example?"""
    return ListAnswer(items=["charge.succeeded", "charge.failed"])


def gold_q10_card_declined_code(_md: str) -> BoolAnswer:
    """Q10: Is 'card_declined' listed as an error code?"""
    return BoolAnswer(answer=True)


# ---------------------------------------------------------------------------
# Gold answers — claude_md.md
# ---------------------------------------------------------------------------

def gold_q11_auth_provider(_md: str) -> TextAnswer:
    """Q11: What authentication provider does the project use?"""
    return TextAnswer(answer="Clerk")


def gold_q12_rate_limit(_md: str) -> TextAnswer:
    """Q12: What is the authenticated rate limit?"""
    return TextAnswer(answer="1000 req/min per user")


def gold_q13_db_orm(_md: str) -> TextAnswer:
    """Q13: What ORM does the project use?"""
    return TextAnswer(answer="Prisma")


def gold_q14_retry_count(_md: str) -> CountAnswer:
    """Q14: How many retries does the background job retry policy specify?"""
    return CountAnswer(count=3)


def gold_q15_environments(_md: str) -> ListAnswer:
    """Q15: What deployment environments are listed?"""
    return ListAnswer(items=["Development", "Staging", "Production"])


# ---------------------------------------------------------------------------
# Gold answers — realistic agent questions (added post-fix)
# ---------------------------------------------------------------------------

def gold_q16_webhook_verify(_md: str) -> TextAnswer:
    """Q16: What Stripe method verifies webhook signatures?"""
    return TextAnswer(answer="stripe.Webhook.construct_event")


def gold_q17_cors_origins(_md: str) -> TextAnswer:
    """Q17: What is allow_origins set to in CORS config?"""
    return TextAnswer(answer='["*"]')


def gold_q18_async_test_decorator(_md: str) -> TextAnswer:
    """Q18: What pytest marker is used for async tests?"""
    return TextAnswer(answer="anyio")


def gold_q19_e2e_command(_md: str) -> TextAnswer:
    """Q19: What command runs E2E tests?"""
    return TextAnswer(answer="pnpm test:e2e")


def gold_q20_retry_backoff(_md: str) -> ListAnswer:
    """Q20: What are the retry backoff delays?"""
    return ListAnswer(items=["1s", "4s", "16s"])


def gold_q21_test_framework(_md: str) -> TextAnswer:
    """Q21: What E2E test framework is used?"""
    return TextAnswer(answer="Playwright")


# ---------------------------------------------------------------------------
# Question registry
# ---------------------------------------------------------------------------

QUESTIONS = [
    # --- project_readme.md ---
    {
        "id": "md_q1",
        "fixture": "project_readme.md",
        "query": "authentication OAuth2 hashing",
        "question": "In the OAuth2 authentication example, what password hashing algorithm/scheme is used? Return just the algorithm name.",
        "model": TextAnswer,
        "gold_fn": gold_q1_auth_method,
    },
    {
        "id": "md_q2",
        "fixture": "project_readme.md",
        "query": "testing TestClient",
        "question": "What HTTP library is FastAPI's TestClient based on? Return just the library name.",
        "model": TextAnswer,
        "gold_fn": gold_q2_test_client,
    },
    {
        "id": "md_q3",
        "fixture": "project_readme.md",
        "query": "deployment docker",
        "question": "What is the exact Python base image specified in the Dockerfile example? Return the full image:tag string.",
        "model": TextAnswer,
        "gold_fn": gold_q3_docker_base_image,
    },
    {
        "id": "md_q4",
        "fixture": "project_readme.md",
        "query": "CORS middleware",
        "question": "What value is set for allow_origins in the CORS middleware configuration? Return the exact value.",
        "model": TextAnswer,
        "gold_fn": gold_q4_cors_origins,
    },
    {
        "id": "md_q5",
        "fixture": "project_readme.md",
        "query": "changelog versions",
        "question": "How many distinct version entries are listed in the Changelog section?",
        "model": CountAnswer,
        "gold_fn": gold_q5_changelog_versions,
    },
    # --- api_documentation.md ---
    {
        "id": "md_q6",
        "fixture": "api_documentation.md",
        "query": "secret key prefix test live",
        "question": "What prefix do test mode secret keys have in Stripe? Return just the prefix string.",
        "model": TextAnswer,
        "gold_fn": gold_q6_test_key_prefix,
    },
    {
        "id": "md_q7",
        "fixture": "api_documentation.md",
        "query": "error types",
        "question": "How many distinct error types are listed in the Error Types table?",
        "model": CountAnswer,
        "gold_fn": gold_q7_error_types,
    },
    {
        "id": "md_q8",
        "fixture": "api_documentation.md",
        "query": "pagination parameters",
        "question": "What are the three pagination parameters listed? Return them as a list.",
        "model": ListAnswer,
        "gold_fn": gold_q8_pagination_params,
    },
    {
        "id": "md_q9",
        "fixture": "api_documentation.md",
        "query": "webhook endpoint events",
        "question": "In the 'create a webhook endpoint' example, which two events are enabled? Return them as a list.",
        "model": ListAnswer,
        "gold_fn": gold_q9_webhook_events,
    },
    {
        "id": "md_q10",
        "fixture": "api_documentation.md",
        "query": "error codes card_declined",
        "question": "Is 'card_declined' listed as one of the error codes in the Error Codes table? Return true or false.",
        "model": BoolAnswer,
        "gold_fn": gold_q10_card_declined_code,
    },
    # --- claude_md.md ---
    {
        "id": "md_q11",
        "fixture": "claude_md.md",
        "query": "authentication provider",
        "question": "What authentication provider does this project use? Return just the provider name.",
        "model": TextAnswer,
        "gold_fn": gold_q11_auth_provider,
    },
    {
        "id": "md_q12",
        "fixture": "claude_md.md",
        "query": "rate limiting",
        "question": "What is the rate limit for authenticated requests? Return the exact limit string.",
        "model": TextAnswer,
        "gold_fn": gold_q12_rate_limit,
    },
    {
        "id": "md_q13",
        "fixture": "claude_md.md",
        "query": "database ORM",
        "question": "What ORM does this project use for database access? Return just the ORM name.",
        "model": TextAnswer,
        "gold_fn": gold_q13_db_orm,
    },
    {
        "id": "md_q14",
        "fixture": "claude_md.md",
        "query": "background jobs retry",
        "question": "How many retries does the background job retry policy allow before sending to dead letter queue?",
        "model": CountAnswer,
        "gold_fn": gold_q14_retry_count,
    },
    {
        "id": "md_q15",
        "fixture": "claude_md.md",
        "query": "deployment environments",
        "question": "What are the deployment environment names listed in the Environments table? Return them as a list.",
        "model": ListAnswer,
        "gold_fn": gold_q15_environments,
    },
    # --- Realistic agent questions (post-fix, from live testing) ---
    {
        "id": "md_q16",
        "fixture": "api_documentation.md",
        "query": "webhook signature verify python",
        "question": "What is the exact Stripe Python method/function call used to verify webhook signatures? Return the full dotted method name.",
        "model": TextAnswer,
        "gold_fn": gold_q16_webhook_verify,
    },
    {
        "id": "md_q17",
        "fixture": "project_readme.md",
        "query": "CORS middleware configuration",
        "question": "What value is set for allow_origins in the CORS middleware example? Return the exact value.",
        "model": TextAnswer,
        "gold_fn": gold_q17_cors_origins,
    },
    {
        "id": "md_q18",
        "fixture": "project_readme.md",
        "query": "async testing pytest",
        "question": "What pytest marker decorator is used for async tests in the example? Return just the marker name (not the full decorator).",
        "model": TextAnswer,
        "gold_fn": gold_q18_async_test_decorator,
    },
    {
        "id": "md_q19",
        "fixture": "claude_md.md",
        "query": "e2e tests playwright",
        "question": "What is the exact command to run E2E tests? Return the full command string.",
        "model": TextAnswer,
        "gold_fn": gold_q19_e2e_command,
    },
    {
        "id": "md_q20",
        "fixture": "claude_md.md",
        "query": "background jobs retry backoff",
        "question": "What are the three exponential backoff delay values in the retry policy? Return them as a list with their units.",
        "model": ListAnswer,
        "gold_fn": gold_q20_retry_backoff,
    },
    {
        "id": "md_q21",
        "fixture": "claude_md.md",
        "query": "e2e tests framework",
        "question": "What testing framework is used for E2E tests? Return just the framework name.",
        "model": TextAnswer,
        "gold_fn": gold_q21_test_framework,
    },
]
