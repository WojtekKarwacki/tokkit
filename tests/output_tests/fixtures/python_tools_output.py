"""Realistic fixtures for Python ecosystem tool output parsers."""

# ---------------------------------------------------------------------------
# ruff
# ---------------------------------------------------------------------------

RUFF_VIOLATIONS = """\
src/auth.py:42:5: E501 Line too long (127 > 88)
src/auth.py:89:1: F401 [*] `os` imported but unused
src/db.py:15:9: E711 Comparison to `None` (use `is` or `is not`)
Found 3 errors.
[*] 1 fixable with the `--fix` option.
"""

RUFF_CLEAN = """\
All checks passed!
"""

# ---------------------------------------------------------------------------
# mypy
# ---------------------------------------------------------------------------

MYPY_ERRORS = """\
src/auth.py:23:5: error: Argument 1 to "login" has incompatible type "int"; expected "str"  [arg-type]
src/auth.py:47:12: error: Item "None" of "Optional[User]" has no attribute "id"  [union-attr]
src/db.py:88:9: note: See: https://mypy.readthedocs.io/en/stable/protocols.html
Found 2 errors in 2 files (checked 15 source files)
"""

MYPY_CLEAN = """\
Success: no issues found (15 source files)
"""

# ---------------------------------------------------------------------------
# pyright
# ---------------------------------------------------------------------------

PYRIGHT_ERRORS = """\
/home/user/project/src/auth.py
  /home/user/project/src/auth.py:23:5 - error: Argument of type "int" cannot be assigned to parameter "username" of type "str" in function "login" (reportArgumentType)
  /home/user/project/src/auth.py:47:12 - error: Cannot access attribute "id" for class "None"  (reportOptionalMemberAccess)
/home/user/project/src/db.py
  /home/user/project/src/db.py:102:8 - warning: Variable "conn" is possibly unbound (reportPossiblyUnbound)
2 errors, 1 warning, 0 informations
"""

PYRIGHT_CLEAN = """\
0 errors, 0 warnings, 0 informations
"""

# ---------------------------------------------------------------------------
# pip
# ---------------------------------------------------------------------------

PIP_CONFLICTS = """\
Collecting requests==2.25.0
  Downloading requests-2.25.0-py3-none-any.whl (61 kB)
Collecting urllib3>=1.21.1 (from requests==2.25.0)
  Downloading urllib3-1.26.18-py2.py3-none-any.whl (143 kB)
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
botocore 1.29.76 requires urllib3<1.27,>=1.25.4, but you have urllib3 1.26.18 which is incompatible.
requests-toolbelt 0.10.1 requires requests>=2.29.0, but you have requests 2.25.0 which is incompatible.
Successfully installed requests-2.25.0 urllib3-1.26.18
"""

PIP_BUILD_FAILURE = """\
Collecting mypackage==9.9.9
  Downloading mypackage-9.9.9.tar.gz (512 kB)
  Preparing metadata (setup.py) ... done
Building wheels for collected packages: mypackage
  Building wheel for mypackage (setup.py) ... error
  error: subprocess-exited-with-error
  × python setup.py bdist_wheel did not run successfully.
  │ exit code: 1
  ╰─> See above for output.
ERROR: Could not build wheels for mypackage, which is required to install pyproject.toml-based projects
"""

# ---------------------------------------------------------------------------
# python traceback
# ---------------------------------------------------------------------------

TRACEBACK_SIMPLE = """\
Traceback (most recent call last):
  File "src/main.py", line 42, in run
    result = compute(data)
  File "src/compute.py", line 17, in compute
    return data["value"] / data["count"]
ZeroDivisionError: division by zero
"""

TRACEBACK_CHAINED = """\
Traceback (most recent call last):
  File "src/db.py", line 55, in connect
    conn = psycopg2.connect(dsn)
  File "/usr/lib/python3/dist-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
psycopg2.OperationalError: could not connect to server: Connection refused

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "src/app.py", line 88, in startup
    db.connect()
  File "src/db.py", line 60, in connect
    raise DatabaseError("Cannot reach database") from exc
DatabaseError: Cannot reach database
"""
