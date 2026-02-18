"""Realistic fixtures for JS/TS ecosystem tool output parsers."""

# ---------------------------------------------------------------------------
# jest
# ---------------------------------------------------------------------------

JEST_ALL_PASS = """\
 PASS  tests/auth.test.ts
 PASS  tests/db.test.ts

Test Suites: 2 passed, 2 total
Tests:       8 passed, 8 total
Snapshots:   0 total
Time:        1.234 s
Ran all test suites.
"""

JEST_WITH_FAILURES = """\
 FAIL  tests/db.test.ts
 PASS  tests/auth.test.ts

  ● TestDB › should connect

    expect(received).toBe(expected)

    Expected: true
    Received: false

      at Object.<anonymous> (tests/db.test.ts:15:27)
      at Promise.then.completed (node_modules/jest-jasmine2/build/jasmine/Env.js:357:25)

  ● TestDB › should query users

    TypeError: Cannot read properties of undefined (reading 'query')

      at Object.<anonymous> (tests/db.test.ts:42:18)

Test Suites: 1 failed, 1 passed, 2 total
Tests:       2 failed, 6 passed, 8 total
Snapshots:   0 total
Time:        2.345 s
"""

# ---------------------------------------------------------------------------
# vitest
# ---------------------------------------------------------------------------

VITEST_WITH_FAILURES = """\
 RUN  v1.2.0 /home/user/project

FAIL src/api.test.ts > ApiService > should fetch users
AssertionError: expected false to be true

  - Expected: true
  + Received: false

  src/api.test.ts:28:20

FAIL src/auth.test.ts > AuthService > should validate token
Error: Token validation failed unexpectedly

  src/auth.test.ts:55:10

 Test Files  2 failed | 1 passed (3)
 Tests  2 failed | 5 passed (7)
 Duration  3.45s
"""

# ---------------------------------------------------------------------------
# mocha
# ---------------------------------------------------------------------------

MOCHA_WITH_FAILURES = """\


  UserService
    ✓ should create user (45ms)
    ✓ should find user by id (12ms)
    ✗ should delete user

  DatabasePool
    ✓ should acquire connection (8ms)
    ✗ should release connection on error


  3 passing (234ms)
  2 failing

  1) UserService should delete user:
     AssertionError: expected 0 to equal 1
      at Context.<anonymous> (test/user.test.js:88:14)
      at callFn (node_modules/mocha/lib/runnable.js:372:21)

  2) DatabasePool should release connection on error:
     Error: Pool exhausted after 5 attempts
      at Context.<anonymous> (test/db.test.js:134:7)

"""

# ---------------------------------------------------------------------------
# tsc
# ---------------------------------------------------------------------------

TSC_ERRORS = """\
src/api.ts(42,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/api.ts(78,12): error TS2345: Argument of type 'null' is not assignable to parameter of type 'User'.
src/auth.ts(23,8): warning TS2802: This iteration protocol is not supported.
"""

TSC_CLEAN = ""

# ---------------------------------------------------------------------------
# eslint
# ---------------------------------------------------------------------------

ESLINT_VIOLATIONS = """\
/home/user/src/auth.ts
   5:10  error    'unused' is defined but never used         no-unused-vars
  12:1   error    Expected indentation of 2 spaces           indent
  34:30  warning  Unexpected trailing comma                  comma-dangle

/home/user/src/db.ts
   8:1   error    Strings must use singlequote               quotes

✖ 4 problems (3 errors, 1 warning)
"""

# ---------------------------------------------------------------------------
# webpack
# ---------------------------------------------------------------------------

WEBPACK_ERROR = """\
asset main.js 1.23 MiB [emitted] (name: main)
runtime modules 891 bytes 4 modules
cacheable modules 512 KiB
  modules by path ./src/ 128 KiB

ERROR in ./src/index.ts
Module build failed (from ./node_modules/ts-loader/index.js):
TypeScript diagnostics (customize using `[jest-config] reporters` config option in `tsconfig.json`):
  src/index.ts:10:5 - error TS2304: Cannot find name 'process'.

ERROR in ./src/api.ts
Module build failed (from ./node_modules/ts-loader/index.js):
  src/api.ts:55:8 - error TS2345: Argument of type 'undefined' is not assignable to parameter of type 'string'.

webpack 5.75.0 compiled with 2 errors in 3456 ms
"""

# ---------------------------------------------------------------------------
# vite
# ---------------------------------------------------------------------------

VITE_ERROR = """\
vite v4.5.0 building for production...

transforming...
✓ 42 modules transformed.

error during build:
src/api.ts(55,8): error TS2345: Argument of type 'undefined' is not assignable to parameter of type 'string'.
src/utils.ts(12,3): error TS2304: Cannot find name 'Buffer'.
"""

# ---------------------------------------------------------------------------
# npm
# ---------------------------------------------------------------------------

NPM_ERROR = """\
npm warn ERESOLVE overriding peer dependency
npm warn While resolving: my-app@1.0.0
npm warn Found: react@17.0.2
npm warn node_modules/react
npm warn   react@"^17.0.2" from the root project
npm warn
npm warn Could not resolve dependency: peer react@"^18.0.0" from some-ui-lib@3.0.0
npm warn node_modules/some-ui-lib
npm warn   some-ui-lib@"^3.0.0" from the root project
npm warn
npm warn deprecated source-map-resolve@0.5.3: See https://github.com/lydell/source-map-resolve#deprecated
npm error code ERESOLVE
npm error ERESOLVE unable to resolve dependency tree
"""
