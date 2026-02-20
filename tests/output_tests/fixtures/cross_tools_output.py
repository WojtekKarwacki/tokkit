"""Fixture data for cross-ecosystem parser tests (cargo test/build/clippy, docker)."""

CARGO_TEST_PASS = """\
   Compiling myproject v0.1.0 (/home/user/project)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.34s
     Running unittests src/lib.rs (target/debug/deps/myproject-abc123)

running 3 tests
test tests::test_add ... ok
test tests::test_sub ... ok
test tests::test_mul ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
"""

CARGO_TEST_FAIL = """\
   Compiling myproject v0.1.0 (/home/user/project)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.34s
     Running unittests src/lib.rs (target/debug/deps/myproject-abc123)

running 3 tests
test tests::test_add ... ok
test tests::test_sub ... FAILED
test tests::test_mul ... ok

failures:

---- tests::test_sub stdout ----
thread 'tests::test_sub' panicked at src/lib.rs:42:5:
assertion `left == right` failed
  left: 5
 right: 3

note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace


failures:
    tests::test_sub

test result: FAILED. 2 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
"""

CARGO_BUILD_ERRORS = """\
   Compiling myproject v0.1.0 (/home/user/project)
error[E0308]: mismatched types
 --> src/main.rs:15:18
  |
15|     let x: i32 = "hello";
  |            ---   ^^^^^^^ expected `i32`, found `&str`
  |            |
  |            expected due to this

error[E0425]: cannot find value `undefined_var` in this scope
 --> src/lib.rs:27:9
  |
27|         undefined_var + 1
  |         ^^^^^^^^^^^^^ not found in this scope

warning[W0001]: unused variable `count`
 --> src/main.rs:8:9
  |
8 |     let count = 0;
  |         ^^^^^ help: if this is intentional, prefix it with an underscore: `_count`

error: aborting due to 2 previous errors

For more information about this error, try `rustc --explain E0308`.
"""

CARGO_CLIPPY_WARNINGS = """\
   Compiling myproject v0.1.0 (/home/user/project)
warning: needless return
 --> src/lib.rs:10:5
  |
10|     return x + 1;
  |     ^^^^^^^^^^^^^ help: remove `return`
  |
  = note: `#[warn(clippy::needless_return)]` on by default

warning: useless use of `format!`
 --> src/main.rs:22:19
  |
22|     let s = format!("hello");
  |             ^^^^^^^^^^^^^^^^ help: consider using `.to_string()`: `"hello".to_string()`
  |
  = note: `#[warn(clippy::useless_format)]` on by default

warning: `myproject` (lib) generated 2 warnings
"""

DOCKER_BUILD_SUCCESS = """\
[+] Building 8.4s (10/10) FINISHED
 => [internal/load build definition from Dockerfile]              0.0s
 => [internal/load .dockerignore]                                  0.0s
 => [1/7] FROM docker.io/library/python:3.11-slim                  0.0s
 => [2/7] WORKDIR /app                                             0.1s
 => [3/7] COPY requirements.txt .                                  0.0s
 => [4/7] RUN pip install -r requirements.txt                      4.2s
 => [5/7] COPY . .                                                  0.1s
 => [6/7] RUN python -m pytest tests/                              2.1s
 => [7/7] EXPOSE 8080                                              0.0s
 => exporting to image                                              0.3s
"""

DOCKER_BUILD_FAIL = """\
[+] Building 6.1s (7/8) FAILED
 => [internal/load build definition from Dockerfile]              0.0s
 => [internal/load .dockerignore]                                  0.0s
 => [1/5] FROM docker.io/library/node:18-alpine                    0.0s
 => [2/5] WORKDIR /app                                             0.1s
 => [3/5] COPY package.json package-lock.json ./                   0.0s
 => [4/5] RUN npm install                                          3.2s
 => ERROR [5/5] RUN npm run build
------
 > [5/5] RUN npm run build:
#12 1.234 > myapp@1.0.0 build
#12 1.235 > tsc --noEmit && vite build
#12 2.891 src/api.ts(15,7): error TS2322: Type 'string' is not assignable to type 'number'.
#12 3.012 src/api.ts(23,3): error TS2345: Argument of type 'null' is not assignable to parameter.
------
ERROR: failed to solve: process "/bin/sh -c npm run build" did not complete successfully: exit code: 1
"""
