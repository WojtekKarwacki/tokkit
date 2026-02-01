"""Realistic pytest output fixtures."""

ALL_PASS = """\
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.1.1, pluggy-1.4.0
rootdir: /home/user/project
collected 5 items

tests/test_auth.py::test_login PASSED                                   [ 20%]
tests/test_auth.py::test_logout PASSED                                  [ 40%]
tests/test_auth.py::test_refresh PASSED                                 [ 60%]
tests/test_api.py::test_get_users PASSED                                [ 80%]
tests/test_api.py::test_post_user PASSED                                [100%]

============================== 5 passed in 0.23s ===============================
"""

WITH_FAILURES = """\
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.1.1, pluggy-1.4.0
rootdir: /home/user/project
collected 5 items

tests/test_auth.py::test_login PASSED                                   [ 20%]
tests/test_auth.py::test_logout PASSED                                  [ 40%]
tests/test_auth.py::test_refresh PASSED                                 [ 60%]
tests/test_api.py::test_get_users FAILED                                [ 80%]
tests/test_api.py::test_post_user FAILED                                [100%]

=================================== FAILURES ===================================
_________________________ test_get_users __________________________

    def test_get_users():
        response = client.get("/users")
>       assert response.status_code == 200
E       AssertionError: assert 404 == 200
E        +  where 404 = <Response [404]>.status_code

tests/test_api.py:42: AssertionError

_________________________ test_post_user __________________________

    def test_post_user():
        payload = {"name": "Alice"}
        response = client.post("/users", json=payload)
>       assert response.status_code == 201
E       AssertionError: assert 500 == 201
E        +  where 500 = <Response [500]>.status_code

tests/test_api.py:58: AssertionError

=========================== short test summary info ============================
FAILED tests/test_api.py::test_get_users - AssertionError: assert 404 == 200
FAILED tests/test_api.py::test_post_user - AssertionError: assert 500 == 201
========================= 2 failed, 3 passed in 0.31s ==========================
"""

WITH_ERRORS = """\
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.1.1, pluggy-1.4.0
rootdir: /home/user/project
collected 3 items

tests/test_db.py::test_connect ERROR                                    [ 33%]
tests/test_db.py::test_query PASSED                                     [ 66%]
tests/test_db.py::test_close PASSED                                     [100%]

==================================== ERRORS ====================================
_____________________ ERROR at setup of test_connect _______________________

    @pytest.fixture
    def db_conn():
>       conn = connect("postgresql://localhost/testdb")
E       ConnectionRefusedError: [Errno 111] Connection refused

tests/test_db.py:12: ConnectionRefusedError

=========================== short test summary info ============================
ERROR tests/test_db.py::test_connect - ConnectionRefusedError: [Errno 111] Connection refused
========================= 1 error, 2 passed in 0.18s ===========================
"""

WITH_ANSI = (
    "\x1b[1m============================= test session starts ==============================\x1b[0m\n"
    "platform linux -- Python 3.12.3, pytest-8.1.1, pluggy-1.4.0\n"
    "rootdir: /home/user/project\n"
    "collected 2 items\n"
    "\n"
    "tests/test_foo.py::\x1b[32mtest_bar\x1b[0m \x1b[32mPASSED\x1b[0m                                  [ 50%]\n"
    "tests/test_foo.py::\x1b[31mtest_baz\x1b[0m \x1b[31mFAILED\x1b[0m                                  [100%]\n"
    "\n"
    "\x1b[31m=================================== FAILURES ===================================\x1b[0m\n"
    "\x1b[31m_________________________ test_baz __________________________\x1b[0m\n"
    "\n"
    "    def test_baz():\n"
    ">       assert 1 == 2\n"
    "\x1b[31mE       AssertionError: assert 1 == 2\x1b[0m\n"
    "\n"
    "tests/test_foo.py:8: AssertionError\n"
    "\n"
    "\x1b[36m=========================== short test summary info ============================\x1b[0m\n"
    "FAILED tests/test_foo.py::test_baz - AssertionError: assert 1 == 2\n"
    "\x1b[31m========================= 1 failed, 1 passed in 0.09s ==========================\x1b[0m\n"
)
