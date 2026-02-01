"""Realistic unittest output fixtures."""

ALL_PASS = """\
..
----------------------------------------------------------------------
Ran 2 tests in 0.003s

OK
"""

WITH_FAILURE = """\
.F
======================================================================
FAIL: test_addition (tests.test_math.TestMath)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/user/project/tests/test_math.py", line 14, in test_addition
    self.assertEqual(add(2, 2), 5)
AssertionError: 4 != 5

----------------------------------------------------------------------
Ran 2 tests in 0.004s

FAILED (failures=1)
"""

WITH_ERROR = """\
.E
======================================================================
ERROR: test_connect (tests.test_db.TestDatabase)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/user/project/tests/test_db.py", line 22, in setUp
    self.conn = connect("postgresql://localhost/testdb")
ConnectionRefusedError: [Errno 111] Connection refused

----------------------------------------------------------------------
Ran 2 tests in 0.005s

FAILED (errors=1)
"""

WITH_FAILURE_AND_ERROR = """\
FE
======================================================================
FAIL: test_subtract (tests.test_math.TestMath)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/user/project/tests/test_math.py", line 20, in test_subtract
    self.assertEqual(subtract(5, 3), 1)
AssertionError: 2 != 1

======================================================================
ERROR: test_divide (tests.test_math.TestMath)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/user/project/tests/test_math.py", line 27, in test_divide
    result = divide(10, 0)
ZeroDivisionError: division by zero

----------------------------------------------------------------------
Ran 2 tests in 0.006s

FAILED (failures=1, errors=1)
"""
