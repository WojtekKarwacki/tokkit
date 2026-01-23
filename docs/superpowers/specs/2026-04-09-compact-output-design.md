# compact_output — Token-Optimized Shell Output Compression

**Date:** 2026-04-09
**Status:** Approved

## Purpose

Compress shell command output (test results, build logs, lint reports, type-check errors) into token-optimized structured format for LLM agents. Extracts only actionable items (errors, failures, warnings) plus a summary line. Returns schema+CSV format (same as `compact_json`).

Target: 70-85% token savings on default mode, 30-50% on verbose mode.

## MCP Tool Interface

```
compact_output(text, hint?, verbose?)
```

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | yes | — | Raw command output |
| `hint` | string | no | auto-detect | Tool identifier (e.g. `"pytest"`, `"eslint"`, `"tsc"`) |
| `verbose` | boolean | no | `false` | Include all items, not just problems |

### Behavior by mode

- **Default** (`verbose=false`): Summary comment line + schema+CSV rows of **only actionable items** (errors, failures, warnings, violations). Passes/successes are counted in the summary but not emitted as rows.
- **Verbose** (`verbose=true`): Summary comment line + schema+CSV rows of **all items** including passes/successes. Still benefits from format compression + ANSI/noise removal.
- **Fallback** (no parser matched): ANSI stripped, blank lines collapsed, raw text returned. No schema+CSV — the tool can't structure what it doesn't understand.

### Output format

```
# {tool}: {summary}
[{schema}]
{row1}
{row2}
...
```

Example (pytest, default):
```
# pytest: 47 passed, 2 failed
[test;status;file;line;error]
test_login;FAIL;tests/test_auth.py;42;AssertionError: expected 200 got 401
test_signup;FAIL;tests/test_auth.py;87;KeyError: 'email'
```

Example (pytest, verbose):
```
# pytest (verbose): 47 passed, 2 failed
[test;status;file;line;duration;error]
test_login;PASS;tests/test_auth.py;10;0.03;
test_create_user;PASS;tests/test_auth.py;25;0.12;
test_signup;FAIL;tests/test_auth.py;87;0.45;KeyError: 'email'
```

Example (ruff, default):
```
# ruff: 3 violations, 14 files checked
[file;line;col;rule;message]
src/auth.py;42;5;E501;Line too long (127 > 88)
src/auth.py;89;1;F401;Unused import: os
src/db.py;15;9;E711;Comparison to None
```

Example (tsc, default):
```
# tsc: 2 errors
[file;line;col;code;message]
src/api.ts;42;5;TS2322;Type 'string' is not assignable to type 'number'
src/api.ts;89;12;TS2345;Argument of type 'null' is not assignable to parameter of type 'User'
```

Example (clean success, any tool):
```
# pytest: 47 passed, 0 failed
```

No data rows when there are zero actionable items.

## Detection Strategy

### Resolution order

1. If `hint` is provided and matches a known parser → use that parser
2. If no hint → run auto-detect: test each parser's signature pattern against the text, first match wins
3. If no parser matches → universal fallback (ANSI strip + blank line collapse)

### Auto-detect signatures

Each parser registers a detection function that returns a confidence score (0.0-1.0) based on signature patterns in the output. Highest confidence wins. Minimum threshold: 0.6.

Examples:
- pytest: `=====` separator + (`passed` or `failed` or `error`) in last 5 lines
- jest: `Test Suites:` + `Tests:` lines
- tsc: lines matching `filename.ts(line,col): error TS\d+`
- eslint: lines matching `filepath  line:col  error/warning  message  rule`
- ruff: lines matching `filepath:line:col: [A-Z]\d+`

## v1 Parsers

### Supported (v1)

**Python ecosystem:**

| Parser ID | Tools covered | Hint values | Actionable items |
|-----------|--------------|-------------|-----------------|
| `pytest` | pytest | `pytest`, `py.test` | Failed/errored tests with traceback |
| `unittest` | unittest, Django test | `unittest`, `django-test` | Failed/errored tests with traceback |
| `ruff` | ruff check | `ruff` | Violations with rule codes |
| `mypy` | mypy | `mypy` | Type errors with error codes |
| `pyright` | pyright | `pyright` | Type errors |
| `pip` | pip install | `pip` | Conflicts, build failures |
| `python-traceback` | any Python crash | `traceback` | Exception chain with frames |

**JavaScript/TypeScript ecosystem:**

| Parser ID | Tools covered | Hint values | Actionable items |
|-----------|--------------|-------------|-----------------|
| `jest` | jest | `jest` | Failed tests with diffs |
| `vitest` | vitest | `vitest` | Failed tests with diffs |
| `mocha` | mocha | `mocha` | Failed tests with stack traces |
| `tsc` | TypeScript compiler | `tsc`, `typescript` | Errors and warnings with codes |
| `eslint` | eslint | `eslint` | Violations with rule IDs |
| `webpack` | webpack | `webpack` | Build errors and warnings |
| `vite` | vite build | `vite` | Build errors |
| `npm` | npm install/run | `npm` | Conflicts, peer dep warnings, script failures |

**Cross-ecosystem:**

| Parser ID | Tools covered | Hint values | Actionable items |
|-----------|--------------|-------------|-----------------|
| `cargo-test` | cargo test | `cargo-test` | Failed tests with panic messages |
| `cargo-build` | cargo build | `cargo-build` | Errors and warnings with codes |
| `cargo-clippy` | cargo clippy | `cargo-clippy`, `clippy` | Lint warnings with codes |
| `docker` | docker build | `docker`, `docker-build` | Build step failures |

### Not yet supported (future)

Explicitly documented as unsupported so agents don't pass these hints:

- go test, go build, go vet
- gcc, clang, make, cmake
- gradle, maven
- ruby (rspec, minitest, rubocop)
- php (phpunit, phpstan)
- swift, kotlin
- terraform, ansible

## Architecture

### Module structure

```
py/tokkit_output/
    __init__.py          # compact_output() public API
    detect.py            # auto-detection engine
    base.py              # BaseParser protocol + shared utilities
    universal.py         # ANSI strip + blank line collapse fallback
    parsers/
        __init__.py      # parser registry
        pytest.py
        unittest_p.py
        ruff.py
        mypy.py
        pyright.py
        pip.py
        traceback.py
        jest.py
        vitest.py
        mocha.py
        tsc.py
        eslint.py
        webpack.py
        vite.py
        npm.py
        cargo_test.py
        cargo_build.py
        cargo_clippy.py
        docker.py
```

### BaseParser protocol

Every parser implements:

```python
class BaseParser:
    id: str                          # e.g. "pytest"
    hint_values: list[str]           # accepted hint strings
    
    def detect(self, text: str) -> float:
        """Return confidence 0.0-1.0 that this text is from this tool."""
    
    def parse(self, text: str, verbose: bool) -> ParseResult:
        """Extract structured data from the output."""
```

### ParseResult

```python
@dataclass
class ParseResult:
    tool: str              # parser ID
    summary: str           # e.g. "47 passed, 2 failed"
    schema: list[str]      # column names, e.g. ["test", "status", "file", "line", "error"]
    rows: list[list[str]]  # data rows
    verbose: bool          # whether all items or just problems
```

### Formatting

`ParseResult` is formatted using the same escaping rules as `compact_json`'s schema+CSV format:
- Semicolon-delimited
- Values containing `;`, `{`, `}`, `[`, `]`, or newlines are quoted with `""` escaping
- Summary line as `# {tool}: {summary}` comment
- Schema line as `[col1;col2;col3]`

### Schema per parser category

**Test runners** (pytest, unittest, jest, vitest, mocha, cargo-test):
```
[test;status;file;line;error]
```
`error` column contains the failure message/traceback. Empty string for passes (verbose mode).

**Compilers/type-checkers** (tsc, mypy, pyright, cargo-build):
```
[file;line;col;severity;code;message]
```

**Linters** (ruff, eslint, cargo-clippy):
```
[file;line;col;rule;severity;message]
```

**Build tools** (webpack, vite, docker):
```
[step;status;message]
```

**Package managers** (pip, npm):
```
[package;status;message]
```

**Python traceback**:
```
[exception;file;line;function;message]
```

## Integration

### Server dispatch (tools.py)

Same pattern as `clean_html` / `compact_json`:

```python
if tool_name == "compact_output":
    text = args.get("text", "")
    hint = args.get("hint")
    verbose = args.get("verbose", False)
    if not text:
        return _err("text is required")
    from tokkit_output import compact_output
    compacted = compact_output(text, hint=hint, verbose=verbose)
    meta = make_meta(tool_name, compacted, _session_project_path, raw_size=len(text))
    return _ok(compacted, meta)
```

### Token stats (token_stats.py)

Add `compact_output` to `estimate_tokens_avoided`:
```python
if tool_name == "compact_output":
    if raw_size:
        return raw_size // CHARS_PER_TOKEN
    return len(result_text) * 2 // CHARS_PER_TOKEN
```

### MCP tool definition (protocol.py)

```python
{
    "name": "compact_output",
    "description": (
        "Compress shell command output (test results, build logs, lint reports) "
        "into token-optimized structured format. Extracts only actionable items "
        "(errors, failures, warnings) plus a summary line. Returns schema+CSV format.\n\n"
        "Supported: pytest, unittest, ruff, mypy, pyright, pip, python tracebacks, "
        "jest, vitest, mocha, tsc, eslint, webpack, vite, npm, "
        "cargo test/build/clippy, docker build.\n\n"
        "Pass hint matching the command (e.g. hint=\"pytest\") for best results. "
        "Omit hint for auto-detection. Set verbose=true to include all items, "
        "not just problems."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Raw command output to compress."},
            "hint": {"type": "string", "description": "Tool identifier for parser selection (e.g. 'pytest', 'eslint', 'tsc'). Omit for auto-detection."},
            "verbose": {"type": "boolean", "description": "Include all items, not just problems. Default: false."},
        },
        "required": ["text"],
    },
}
```

### Skill docs (SKILL.md)

Add section:

```markdown
### 10. Compress Shell Output

For test results, build logs, lint reports, and other command output:

    compact_output(text="<raw output>", hint="pytest")
      → summary line + schema+CSV of failures only

    compact_output(text="...", verbose=true)
      → summary line + schema+CSV of all items

Supported tools: pytest, unittest, ruff, mypy, pyright, pip, python tracebacks,
jest, vitest, mocha, tsc, eslint, webpack, vite, npm,
cargo test/build/clippy, docker build.

Auto-detects the tool when hint is omitted. Pass hint for best results.
```

## Testing Strategy

### Unit tests per parser

Each parser gets a test file with real-world fixture output:
- Clean run (all pass / zero violations)
- Failures / errors present
- Mixed output (some pass, some fail)
- Verbose vs default mode
- Edge cases: empty output, ANSI-heavy output, very long tracebacks

### Integration test

Full MCP round-trip: send `compact_output` via JSON-RPC, verify response format.

### Benchmark

Add `compact_output` to the existing benchmark suite. Measure token savings against raw output for each parser.

### Inference eval

LLM accuracy test: give Haiku the compacted output and ask questions about it (which tests failed? what was the error? how many warnings?). Target: 95% accuracy matching the `compact_json` eval methodology.

## Estimated Savings

| Scenario | Raw tokens | Default tokens | Verbose tokens | Default savings | Verbose savings |
|----------|-----------|---------------|---------------|----------------|----------------|
| pytest: 50 tests, 2 fail | ~2,000 | ~200 | ~800 | 90% | 60% |
| ruff: 5 violations, 20 files | ~500 | ~150 | ~150 | 70% | 70% |
| tsc: 3 errors | ~800 | ~100 | ~100 | 87% | 87% |
| cargo test: 100 tests, 1 fail | ~4,000 | ~150 | ~1,500 | 96% | 62% |
| eslint: 10 warnings, 50 files | ~1,200 | ~250 | ~250 | 79% | 79% |
| pytest: 50 tests, 0 fail | ~1,500 | ~30 | ~800 | 98% | 47% |
