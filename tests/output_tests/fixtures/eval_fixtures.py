"""Eval fixtures: real output samples + questions with gold answers."""

from pydantic import BaseModel


# --- Answer models ---

class CountAnswer(BaseModel):
    count: int

class ListAnswer(BaseModel):
    items: list[str]

class FileLineAnswer(BaseModel):
    file: str
    line: int

class StatusAnswer(BaseModel):
    status: str  # "pass" or "fail"


# --- Fixture data ---

PYTEST_FIXTURE = """\
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
collected 8 items

tests/test_auth.py::test_login PASSED                                    [ 12%]
tests/test_auth.py::test_logout PASSED                                   [ 25%]
tests/test_auth.py::test_signup FAILED                                   [ 37%]
tests/test_api.py::test_get_users PASSED                                 [ 50%]
tests/test_api.py::test_create_user PASSED                               [ 62%]
tests/test_api.py::test_delete_user FAILED                               [ 75%]
tests/test_db.py::test_connect PASSED                                    [ 87%]
tests/test_db.py::test_query PASSED                                      [100%]

=================================== FAILURES ===================================
_________________________________ test_signup __________________________________

    def test_signup():
        result = signup("alice@test.com", "pass")
>       assert result.status_code == 200
E       AssertionError: assert 401 == 200

tests/test_auth.py:42: AssertionError
_______________________________ test_delete_user _______________________________

    def test_delete_user():
        resp = client.delete("/users/999")
>       assert resp.status_code == 200
E       AssertionError: assert 404 == 200

tests/test_api.py:67: AssertionError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_signup - AssertionError: assert 401 == 200
FAILED tests/test_api.py::test_delete_user - AssertionError: assert 404 == 200
========================= 6 passed, 2 failed in 0.45s =========================
"""

RUFF_FIXTURE = """\
src/auth.py:42:5: E501 Line too long (127 > 88)
src/auth.py:89:1: F401 [*] `os` imported but unused
src/db.py:15:9: E711 Comparison to `None` (use `is` or `is not`)
src/api.py:23:10: W291 Trailing whitespace
src/api.py:55:1: F841 Local variable `x` is assigned to but never used
Found 5 errors.
[*] 1 fixable with the `--fix` option.
"""

TSC_FIXTURE = """\
src/api.ts(42,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/api.ts(89,12): error TS2345: Argument of type 'null' is not assignable to parameter of type 'User'.
src/db.ts(15,3): error TS2304: Cannot find name 'Connection'.
src/auth.ts(7,1): error TS2307: Cannot find module 'bcrypt' or its corresponding type declarations.

Found 4 errors in 3 files.
"""


# --- Questions ---

QUESTIONS = [
    {
        "id": "q1",
        "fixture_name": "pytest",
        "question": "How many tests failed?",
        "model": CountAnswer,
        "gold": CountAnswer(count=2),
    },
    {
        "id": "q2",
        "fixture_name": "pytest",
        "question": "How many tests passed?",
        "model": CountAnswer,
        "gold": CountAnswer(count=6),
    },
    {
        "id": "q3",
        "fixture_name": "pytest",
        "question": "List the names of the failing tests.",
        "model": ListAnswer,
        "gold": ListAnswer(items=["test_signup", "test_delete_user"]),
    },
    {
        "id": "q4",
        "fixture_name": "pytest",
        "question": "In which file and on what line did test_signup fail?",
        "model": FileLineAnswer,
        "gold": FileLineAnswer(file="tests/test_auth.py", line=42),
    },
    {
        "id": "q5",
        "fixture_name": "pytest",
        "question": "Did the overall test suite pass or fail?",
        "model": StatusAnswer,
        "gold": StatusAnswer(status="fail"),
    },
    {
        "id": "q6",
        "fixture_name": "ruff",
        "question": "How many linting violations were found?",
        "model": CountAnswer,
        "gold": CountAnswer(count=5),
    },
    {
        "id": "q7",
        "fixture_name": "ruff",
        "question": "List the files that have linting violations.",
        "model": ListAnswer,
        "gold": ListAnswer(items=["src/auth.py", "src/db.py", "src/api.py"]),
    },
    {
        "id": "q8",
        "fixture_name": "tsc",
        "question": "How many TypeScript errors were found?",
        "model": CountAnswer,
        "gold": CountAnswer(count=4),
    },
    {
        "id": "q9",
        "fixture_name": "tsc",
        "question": "List the TypeScript error codes found.",
        "model": ListAnswer,
        "gold": ListAnswer(items=["TS2322", "TS2345", "TS2304", "TS2307"]),
    },
    {
        "id": "q10",
        "fixture_name": "tsc",
        "question": "How many files contain errors?",
        "model": CountAnswer,
        "gold": CountAnswer(count=3),
    },
]

FIXTURES = {
    "pytest": PYTEST_FIXTURE,
    "ruff": RUFF_FIXTURE,
    "tsc": TSC_FIXTURE,
}
