# Decorator-Based Route Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect HTTP routes from framework decorators and call expressions (FastAPI, Flask, Express, NestJS, Hono, Next.js, etc.) instead of only name-based heuristics.

**Architecture:** Add a `RouteHint` type to `FileResult` that carries extracted route metadata through the pipeline. The tree-sitter walker detects route decorators (Python, NestJS) and call-expression patterns (Express, Hono). The pipeline sets `route_path`/`route_method` properties on function graph nodes, which the existing enrichment Branch A already consumes to create Route nodes + HANDLES edges.

**Tech Stack:** Rust, tree-sitter, regex crate (already a dependency)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `crates/tokkit-core/src/types.rs` | Modify | Add `RouteHint` struct, update `FileResult` |
| `crates/tokkit-core/src/graph/mod.rs` | Modify | Add `set_node_property` method |
| `crates/tokkit-core/src/extract/route_patterns.rs` | Create | Regex-based route pattern parsing (pure functions) |
| `crates/tokkit-core/src/extract/mod.rs` | Modify | Register `route_patterns` module |
| `crates/tokkit-core/src/extract/walker.rs` | Modify | Detect decorators + call-expression routes during walk |
| `crates/tokkit-core/src/pipeline/mod.rs` | Modify | Wire route hints into graph node properties |
| `crates/tokkit-core/src/enrich/routes.rs` | Modify | Support comma-separated methods, add file-based routing |

---

### Task 1: Add RouteHint type and GraphBuffer helper

**Files:**
- Modify: `crates/tokkit-core/src/types.rs:168-213`
- Modify: `crates/tokkit-core/src/graph/mod.rs:111-147`

- [ ] **Step 1: Write failing test for RouteHint**

Add to the `#[cfg(test)] mod tests` block in `types.rs`:

```rust
#[test]
fn route_hint_default_in_file_result() {
    let fr = FileResult::default();
    assert!(fr.route_hints.is_empty());
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test -p tokkit-core route_hint_default_in_file_result`
Expected: FAIL — `route_hints` field does not exist on `FileResult`

- [ ] **Step 3: Add RouteHint struct and update FileResult**

Add after the `TypeReference` struct (around line 204) in `types.rs`:

```rust
#[derive(Debug, Clone)]
pub struct RouteHint {
    pub def_qn: String,        // qualified name of decorated function (empty for Express-style)
    pub handler_name: String,  // handler reference name for Express-style (empty for decorators)
    pub route_path: String,    // "/users", "/items/{id}"
    pub route_method: String,  // "GET", "POST", etc.
    pub line: u32,
}
```

Add `route_hints: Vec<RouteHint>` to `FileResult`:

```rust
#[derive(Debug, Clone, Default)]
pub struct FileResult {
    pub definitions: Vec<Definition>,
    pub calls: Vec<CallRef>,
    pub imports: Vec<ImportRef>,
    pub usages: Vec<UsageRef>,
    pub type_refs: Vec<TypeReference>,
    pub route_hints: Vec<RouteHint>,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test -p tokkit-core route_hint_default_in_file_result`
Expected: PASS

- [ ] **Step 5: Write failing test for set_node_property**

Add to the `#[cfg(test)] mod tests` block in `graph/mod.rs`:

```rust
#[test]
fn set_node_property_works() {
    let mut g = GraphBuffer::new("proj", "/root");
    g.add_node(NodeLabel::Function, "foo", "proj::foo", None, 1, 5);
    assert!(g.set_node_property("proj::foo", "route_path", "/users"));
    assert_eq!(
        g.find_by_qn("proj::foo").unwrap().properties.get("route_path").unwrap(),
        "/users"
    );
    assert!(!g.set_node_property("proj::missing", "route_path", "/nope"));
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cargo test -p tokkit-core set_node_property_works`
Expected: FAIL — `set_node_property` method does not exist

- [ ] **Step 7: Implement set_node_property**

Add to `impl GraphBuffer` in `graph/mod.rs`, after the `find_by_id` method:

```rust
pub fn set_node_property(&mut self, qn: &str, key: &str, value: &str) -> bool {
    if let Some(&idx) = self.node_by_qn.get(qn) {
        self.nodes[idx]
            .properties
            .insert(key.to_string(), value.to_string());
        true
    } else {
        false
    }
}
```

- [ ] **Step 8: Run tests to verify both pass**

Run: `cargo test -p tokkit-core set_node_property_works route_hint_default`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add crates/tokkit-core/src/types.rs crates/tokkit-core/src/graph/mod.rs
git commit -m "feat: add RouteHint type and set_node_property helper"
```

---

### Task 2: Route pattern parsing module

**Files:**
- Create: `crates/tokkit-core/src/extract/route_patterns.rs`
- Modify: `crates/tokkit-core/src/extract/mod.rs`

- [ ] **Step 1: Register the module**

In `extract/mod.rs`, add:

```rust
pub mod route_patterns;
```

- [ ] **Step 2: Write failing tests for Python decorator parsing**

Create `crates/tokkit-core/src/extract/route_patterns.rs`:

```rust
use regex::Regex;
use std::sync::LazyLock;

/// HTTP methods recognized as route indicators
const HTTP_METHODS: &[&str] = &["get", "post", "put", "delete", "patch", "head", "options", "all"];

/// Parse a Python route decorator text into (method, path) pairs.
///
/// Handles:
/// - `@app.get("/users")` (FastAPI, Flask shorthand, Starlette, aiohttp)
/// - `@app.route("/users", methods=["GET", "POST"])` (Flask, Bottle)
/// - `@app.route("/users")` (defaults to GET)
pub fn parse_python_route_decorator(_text: &str) -> Vec<(String, String)> {
    Vec::new() // stub
}

/// Parse a NestJS-style decorator into (method, path).
///
/// Handles:
/// - `@Get("/users")`, `@Post("/users")`, etc.
/// - `@Get()` (empty path → "/")
pub fn parse_nestjs_decorator(_text: &str) -> Option<(String, String)> {
    None // stub
}

/// Check if a call expression method name indicates an HTTP route.
/// e.g., "get", "post", "put", "delete", "patch", "all"
pub fn is_http_method(name: &str) -> bool {
    HTTP_METHODS.contains(&name.to_lowercase().as_str())
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- Python decorator tests ---

    #[test]
    fn fastapi_get_decorator() {
        let result = parse_python_route_decorator(r#"@app.get("/users")"#);
        assert_eq!(result, vec![("GET".to_string(), "/users".to_string())]);
    }

    #[test]
    fn fastapi_post_with_router() {
        let result = parse_python_route_decorator(r#"@router.post("/items")"#);
        assert_eq!(result, vec![("POST".to_string(), "/items".to_string())]);
    }

    #[test]
    fn flask_route_with_methods() {
        let result = parse_python_route_decorator(
            r#"@app.route("/users", methods=["GET", "POST"])"#
        );
        assert_eq!(result.len(), 2);
        assert!(result.contains(&("GET".to_string(), "/users".to_string())));
        assert!(result.contains(&("POST".to_string(), "/users".to_string())));
    }

    #[test]
    fn flask_route_default_get() {
        let result = parse_python_route_decorator(r#"@app.route("/health")"#);
        assert_eq!(result, vec![("GET".to_string(), "/health".to_string())]);
    }

    #[test]
    fn starlette_route_single_quotes() {
        let result = parse_python_route_decorator(r#"@app.get('/items/{item_id}')"#);
        assert_eq!(result, vec![("GET".to_string(), "/items/{item_id}".to_string())]);
    }

    #[test]
    fn non_route_decorator_returns_empty() {
        let result = parse_python_route_decorator(r#"@dataclass"#);
        assert!(result.is_empty());
    }

    #[test]
    fn aiohttp_routes_get() {
        let result = parse_python_route_decorator(r#"@routes.get("/ws")"#);
        assert_eq!(result, vec![("GET".to_string(), "/ws".to_string())]);
    }

    // --- NestJS decorator tests ---

    #[test]
    fn nestjs_get_with_path() {
        let result = parse_nestjs_decorator(r#"@Get("/users")"#);
        assert_eq!(result, Some(("GET".to_string(), "/users".to_string())));
    }

    #[test]
    fn nestjs_post_empty_path() {
        let result = parse_nestjs_decorator(r#"@Post()"#);
        assert_eq!(result, Some(("POST".to_string(), "/".to_string())));
    }

    #[test]
    fn nestjs_delete_with_param() {
        let result = parse_nestjs_decorator(r#"@Delete(":id")"#);
        assert_eq!(result, Some(("DELETE".to_string(), ":id".to_string())));
    }

    #[test]
    fn non_nestjs_decorator_returns_none() {
        let result = parse_nestjs_decorator(r#"@Injectable()"#);
        assert!(result.is_none());
    }

    // --- is_http_method tests ---

    #[test]
    fn recognizes_http_methods() {
        assert!(is_http_method("get"));
        assert!(is_http_method("POST"));
        assert!(is_http_method("Delete"));
        assert!(!is_http_method("route"));
        assert!(!is_http_method("middleware"));
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cargo test -p tokkit-core route_patterns`
Expected: FAIL — all parse functions return empty/None

- [ ] **Step 4: Implement parse_python_route_decorator**

Replace the stub:

```rust
static PYTHON_METHOD_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"\.(?i)(get|post|put|delete|patch|head|options|all)\s*\(\s*["']([^"']+)["']"#)
        .unwrap()
});

static PYTHON_ROUTE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"\.route\s*\(\s*["']([^"']+)["']"#).unwrap()
});

static PYTHON_METHODS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"methods\s*=\s*\[([^\]]+)\]"#).unwrap()
});

static PYTHON_METHOD_ITEM_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"["'](\w+)["']"#).unwrap()
});

pub fn parse_python_route_decorator(text: &str) -> Vec<(String, String)> {
    // Pattern 1: @xxx.METHOD("/path") — FastAPI, Flask shorthand, Starlette, aiohttp
    if let Some(caps) = PYTHON_METHOD_RE.captures(text) {
        let method = caps[1].to_uppercase();
        let path = caps[2].to_string();
        return vec![(method, path)];
    }

    // Pattern 2: @xxx.route("/path", methods=[...]) or @xxx.route("/path")
    if let Some(caps) = PYTHON_ROUTE_RE.captures(text) {
        let path = caps[1].to_string();

        if let Some(methods_caps) = PYTHON_METHODS_RE.captures(text) {
            let methods_str = &methods_caps[1];
            return PYTHON_METHOD_ITEM_RE
                .captures_iter(methods_str)
                .map(|m| (m[1].to_uppercase(), path.clone()))
                .collect();
        }

        return vec![("GET".to_string(), path)];
    }

    Vec::new()
}
```

- [ ] **Step 5: Implement parse_nestjs_decorator**

Replace the stub:

```rust
static NESTJS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"@(?i)(Get|Post|Put|Delete|Patch|Head|Options|All)\s*\(\s*(?:["']([^"']*?)["'])?\s*\)"#)
        .unwrap()
});

pub fn parse_nestjs_decorator(text: &str) -> Option<(String, String)> {
    let caps = NESTJS_RE.captures(text)?;
    let method = caps[1].to_uppercase();
    let path = caps.get(2).map_or("/", |m| m.as_str()).to_string();
    let path = if path.is_empty() { "/".to_string() } else { path };
    Some((method, path))
}
```

- [ ] **Step 6: Run all route_patterns tests**

Run: `cargo test -p tokkit-core route_patterns`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add crates/tokkit-core/src/extract/route_patterns.rs crates/tokkit-core/src/extract/mod.rs
git commit -m "feat: add route pattern parsing module with Python and NestJS support"
```

---

### Task 3: Walker integration — decorator and call-expression detection

**Files:**
- Modify: `crates/tokkit-core/src/extract/walker.rs`

This is the core task. The walker needs three additions:
1. Accumulate decorator text in a `pending_decorators` buffer
2. When processing a function/method, consume pending decorators and check for route patterns
3. When processing a call expression, check for Express-style `app.get("/path", handler)` patterns

- [ ] **Step 1: Write failing test for Python FastAPI route extraction**

Add to `walker.rs` tests:

```rust
#[test]
fn extracts_fastapi_route_hints() {
    let source = r#"
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
async def list_users():
    return []

@app.post("/users")
async def create_user():
    return {}
"#;
    let spec = spec_for_language(Language::Python);
    let result = extract_file(source, "routes/users.py", "proj", spec).unwrap();
    assert_eq!(result.route_hints.len(), 2);

    let get_hint = result.route_hints.iter().find(|h| h.route_method == "GET").unwrap();
    assert_eq!(get_hint.route_path, "/users");
    assert!(get_hint.def_qn.contains("list_users"));

    let post_hint = result.route_hints.iter().find(|h| h.route_method == "POST").unwrap();
    assert_eq!(post_hint.route_path, "/users");
    assert!(post_hint.def_qn.contains("create_user"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test -p tokkit-core extracts_fastapi_route_hints`
Expected: FAIL — `route_hints` is empty

- [ ] **Step 3: Write failing test for Flask route decorator**

```rust
#[test]
fn extracts_flask_route_hints() {
    let source = r#"
from flask import Flask
app = Flask(__name__)

@app.route("/users", methods=["GET", "POST"])
def users():
    pass
"#;
    let spec = spec_for_language(Language::Python);
    let result = extract_file(source, "views.py", "proj", spec).unwrap();
    assert_eq!(result.route_hints.len(), 2);
    assert!(result.route_hints.iter().any(|h| h.route_method == "GET" && h.route_path == "/users"));
    assert!(result.route_hints.iter().any(|h| h.route_method == "POST" && h.route_path == "/users"));
}
```

- [ ] **Step 4: Write failing test for Express call-expression route**

```rust
#[test]
fn extracts_express_route_hints() {
    let source = r#"
const express = require('express');
const app = express();

function getUsers(req, res) {
    res.json([]);
}

app.get("/users", getUsers);
app.post("/users", createUser);
"#;
    let spec = spec_for_language(Language::JavaScript);
    let result = extract_file(source, "routes.js", "proj", spec).unwrap();
    assert!(result.route_hints.len() >= 1);

    let get_hint = result.route_hints.iter().find(|h| h.route_method == "GET").unwrap();
    assert_eq!(get_hint.route_path, "/users");
    assert_eq!(get_hint.handler_name, "getUsers");
}
```

- [ ] **Step 5: Write failing test for NestJS decorator route**

```rust
#[test]
fn extracts_nestjs_route_hints() {
    let source = r#"
import { Controller, Get, Post } from '@nestjs/common';

@Controller('/cats')
export class CatsController {
    @Get('/findAll')
    findAll() {
        return [];
    }

    @Post()
    create() {
        return {};
    }
}
"#;
    let spec = spec_for_language(Language::TypeScript);
    let result = extract_file(source, "cats.controller.ts", "proj", spec).unwrap();
    assert!(result.route_hints.len() >= 1);

    let get_hint = result.route_hints.iter().find(|h| h.route_method == "GET").unwrap();
    assert_eq!(get_hint.route_path, "/findAll");
}
```

- [ ] **Step 6: Run all four tests to verify they all fail**

Run: `cargo test -p tokkit-core extracts_fastapi extracts_flask extracts_express extracts_nestjs`
Expected: ALL FAIL

- [ ] **Step 7: Implement decorator detection in walk_node**

Modify `walk_node` in `walker.rs`. Add `pending_decorators: &mut Vec<String>` parameter to both `walk_node` and `walk_children`. Update `extract_file` to initialize the buffer.

In `extract_file`, change:

```rust
let mut pending_decorators: Vec<String> = Vec::new();

walk_node(
    tree.root_node(),
    source_bytes,
    file_rel_path,
    project_name,
    spec,
    &mut scope_stack,
    &mut pending_decorators,
    &mut result,
);
```

In `walk_node`, add the `pending_decorators` parameter and add decorator detection at the top (before the existing `is_function` check):

```rust
fn walk_node(
    node: Node<'_>,
    source: &[u8],
    file_rel_path: &str,
    project_name: &str,
    spec: &dyn LanguageSpec,
    scope_stack: &mut Vec<String>,
    pending_decorators: &mut Vec<String>,
    result: &mut FileResult,
) {
    let kind = node.kind();
    let line_start = node.start_position().row as u32 + 1;
    let line_end = node.end_position().row as u32 + 1;

    let is_function = spec.function_types().contains(&kind);
    let is_class = spec.class_types().contains(&kind);
    let is_call = spec.call_types().contains(&kind);
    let is_import = spec.import_types().contains(&kind);
    let is_import_from = spec.import_from_types().contains(&kind);
    let is_decorator = spec.decorator_types().contains(&kind);

    // Accumulate decorator text for route detection
    if is_decorator {
        if let Some(text) = node_text(node, source) {
            // Only push to pending if this decorator is NOT a child of a function/method node.
            // If it IS a child (TypeScript pattern), check_child_decorators handles it instead.
            let parent_is_function = node
                .parent()
                .map(|p| spec.function_types().contains(&p.kind()))
                .unwrap_or(false);
            if !parent_is_function {
                pending_decorators.push(text.to_string());
            }
        }
        // Don't walk children — decorator calls (e.g., @app.get) aren't control-flow calls
        return;
    }

    if is_function && let Some(name) = extract_name(node, source) {
        let label = if in_class_scope(scope_stack, &result.definitions) {
            NodeLabel::Method
        } else {
            NodeLabel::Function
        };
        let qn = current_scope_qn(project_name, file_rel_path, scope_stack, name);

        // Check pending decorators for route patterns
        consume_route_decorators(pending_decorators, &qn, line_start, result);

        // Also check direct child decorators (TypeScript/NestJS pattern)
        check_child_decorators(node, source, &qn, line_start, result);

        result.definitions.push(Definition {
            name: name.to_string(),
            qualified_name: qn,
            label,
            line_start,
            line_end,
        });
        scope_stack.push(name.to_string());
        walk_children(node, source, file_rel_path, project_name, spec, scope_stack, pending_decorators, result);
        scope_stack.pop();
        return;
    }

    // ... rest of existing handlers (is_class, is_call, is_import, etc.)
    // Pass pending_decorators through to walk_children in every branch
```

- [ ] **Step 8: Implement consume_route_decorators helper**

Add to `walker.rs`:

```rust
use crate::extract::route_patterns::{parse_python_route_decorator, parse_nestjs_decorator};
use crate::types::RouteHint;

fn consume_route_decorators(
    pending_decorators: &mut Vec<String>,
    def_qn: &str,
    line: u32,
    result: &mut FileResult,
) {
    for dec_text in pending_decorators.drain(..) {
        // Try Python-style decorator
        let routes = parse_python_route_decorator(&dec_text);
        for (method, path) in routes {
            result.route_hints.push(RouteHint {
                def_qn: def_qn.to_string(),
                handler_name: String::new(),
                route_path: path,
                route_method: method,
                line,
            });
        }

        // Try NestJS-style decorator
        if let Some((method, path)) = parse_nestjs_decorator(&dec_text) {
            result.route_hints.push(RouteHint {
                def_qn: def_qn.to_string(),
                handler_name: String::new(),
                route_path: path,
                route_method: method,
                line,
            });
        }
    }
}
```

- [ ] **Step 9: Implement check_child_decorators for TypeScript**

Add to `walker.rs`:

```rust
fn check_child_decorators(
    node: Node<'_>,
    source: &[u8],
    def_qn: &str,
    line: u32,
    result: &mut FileResult,
) {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind() == "decorator" {
            if let Some(text) = node_text(child, source) {
                // Try NestJS-style
                if let Some((method, path)) = parse_nestjs_decorator(text) {
                    result.route_hints.push(RouteHint {
                        def_qn: def_qn.to_string(),
                        handler_name: String::new(),
                        route_path: path,
                        route_method: method,
                        line,
                    });
                }
                // Try Python-style (for completeness)
                for (method, path) in parse_python_route_decorator(text) {
                    result.route_hints.push(RouteHint {
                        def_qn: def_qn.to_string(),
                        handler_name: String::new(),
                        route_path: path,
                        route_method: method,
                        line,
                    });
                }
            }
        }
    }
}
```

- [ ] **Step 10: Implement Express-style call-expression route detection**

In the `is_call` branch of `walk_node`, after the existing `CallRef` creation, add:

```rust
if is_call && let Some(callee_text) = extract_call_callee(node, source) {
    let simple_name = callee_text
        .rsplit('.')
        .next()
        .unwrap_or(callee_text)
        .to_string();

    // Check for Express-style route: app.get("/path", handler)
    if callee_text.contains('.') && route_patterns::is_http_method(&simple_name) {
        if let Some((path, handler_name)) = extract_route_call_args(node, source) {
            let method = simple_name.to_uppercase();
            result.route_hints.push(RouteHint {
                def_qn: String::new(),
                handler_name,
                route_path: path,
                route_method: method,
                line: line_start,
            });
        }
    }

    let enclosing_qn = if scope_stack.is_empty() {
        None
    } else {
        Some(qualified_name(
            project_name,
            file_rel_path,
            &scope_stack.join("."),
        ))
    };
    result.calls.push(CallRef {
        callee_name: simple_name,
        line: line_start,
        enclosing_qn,
    });
}
```

- [ ] **Step 11: Implement extract_route_call_args helper**

Add to `walker.rs`:

```rust
/// Extract (route_path, handler_name) from a call expression like `app.get("/path", handler)`.
/// Returns None if the first argument isn't a string starting with "/".
fn extract_route_call_args(node: Node<'_>, source: &[u8]) -> Option<(String, String)> {
    let args_node = node.child_by_field_name("arguments")?;
    let mut string_arg: Option<String> = None;
    let mut handler_name = String::new();
    let mut arg_index = 0;

    let mut cursor = args_node.walk();
    for child in args_node.children(&mut cursor) {
        let ck = child.kind();
        // Skip punctuation: (, ), ,
        if ck == "(" || ck == ")" || ck == "," {
            continue;
        }

        if arg_index == 0 {
            // First argument should be a string literal
            if ck == "string" || ck == "string_fragment" || ck == "template_string" {
                let text = node_text(child, source)?;
                let path = text.trim_matches(|c| c == '"' || c == '\'' || c == '`');
                if path.starts_with('/') {
                    string_arg = Some(path.to_string());
                }
            }
        } else if arg_index == 1 {
            // Second argument: handler reference
            if ck == "identifier" {
                handler_name = node_text(child, source)?.to_string();
            } else if ck == "member_expression" {
                // e.g., controller.getUsers — take the property name
                if let Some(prop) = child.child_by_field_name("property") {
                    handler_name = node_text(prop, source)?.to_string();
                }
            }
            // arrow_function / function_expression → inline handler, handler_name stays empty
        }

        arg_index += 1;
    }

    let path = string_arg?;
    Some((path, handler_name))
}
```

- [ ] **Step 12: Update walk_children to pass pending_decorators**

```rust
fn walk_children(
    node: Node<'_>,
    source: &[u8],
    file_rel_path: &str,
    project_name: &str,
    spec: &dyn LanguageSpec,
    scope_stack: &mut Vec<String>,
    pending_decorators: &mut Vec<String>,
    result: &mut FileResult,
) {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        walk_node(child, source, file_rel_path, project_name, spec, scope_stack, pending_decorators, result);
    }
}
```

Update ALL existing call sites of `walk_children` and `walk_node` throughout the function to pass `pending_decorators`. There are multiple: the `is_function` branch (line 129), the `is_class` branch (line 145), and the final fallthrough (line 182).

- [ ] **Step 13: Run all four route extraction tests**

Run: `cargo test -p tokkit-core extracts_fastapi extracts_flask extracts_express extracts_nestjs`
Expected: PASS (or some may need debugging — see Step 14)

- [ ] **Step 14: Debug and fix any failing tests**

Common issues:
- Tree-sitter Python may use `decorated_definition` as a wrapper — verify decorators are visited before the function definition in `walk_children`
- TypeScript decorator node structure may differ — check `child.kind()` for exact node kinds with a debug print
- Express string argument may include quotes — ensure proper trimming
- NestJS test may need `tree_sitter_typescript::LANGUAGE_TYPESCRIPT` which doesn't support decorators in all positions — verify grammar support

Run: `cargo test -p tokkit-core -- --nocapture 2>&1 | head -100` to see debug output if needed.

- [ ] **Step 15: Run full test suite to check for regressions**

Run: `cargo test -p tokkit-core`
Expected: ALL PASS (no regressions in existing walker tests)

- [ ] **Step 16: Commit**

```bash
git add crates/tokkit-core/src/extract/walker.rs
git commit -m "feat: detect route decorators and call-expression routes in walker"
```

---

### Task 4: Wire route hints into pipeline

**Files:**
- Modify: `crates/tokkit-core/src/pipeline/mod.rs:77-104`

- [ ] **Step 1: Write failing integration test**

Add to `pipeline/mod.rs` tests:

```rust
#[test]
fn pipeline_detects_fastapi_routes() {
    let repo_dir = TempDir::new().unwrap();
    fs::create_dir_all(repo_dir.path().join("app")).unwrap();

    fs::write(
        repo_dir.path().join("app/main.py"),
        r#"from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
async def list_users():
    return []

@app.post("/users")
async def create_user():
    return {}
"#,
    )
    .unwrap();

    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    run(
        repo_dir.path().to_str().unwrap(),
        db_path.to_str().unwrap(),
        IndexMode::Full,
    )
    .unwrap();

    let store = Store::open(db_path.to_str().unwrap()).unwrap();
    let nodes = store.all_nodes().unwrap();

    let route_nodes: Vec<_> = nodes.iter().filter(|n| n.label == NodeLabel::Route).collect();
    assert!(
        route_nodes.len() >= 2,
        "Expected at least 2 Route nodes, got {}. Nodes: {:?}",
        route_nodes.len(),
        route_nodes.iter().map(|n| &n.name).collect::<Vec<_>>()
    );

    let edges = store.all_edges().unwrap();
    let handles_edges: Vec<_> = edges.iter().filter(|e| e.edge_type == EdgeType::Handles).collect();
    assert!(
        handles_edges.len() >= 2,
        "Expected at least 2 HANDLES edges, got {}",
        handles_edges.len()
    );
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test -p tokkit-core pipeline_detects_fastapi_routes`
Expected: FAIL — no Route nodes created (route_hints aren't wired to graph properties yet)

- [ ] **Step 3: Wire route hints into graph node properties**

In `pipeline/mod.rs`, after the definition-building loop (after line 104), add:

```rust
// Apply route hints to definition nodes
for (_file_info, file_result) in files.iter().zip(file_results.iter()) {
    for hint in &file_result.route_hints {
        let target_qn: Option<String> = if !hint.def_qn.is_empty() {
            Some(hint.def_qn.clone())
        } else if !hint.handler_name.is_empty() {
            // Express-style: find function by name across the project
            gbuf.nodes()
                .iter()
                .find(|n| {
                    n.name == hint.handler_name
                        && (n.label == NodeLabel::Function || n.label == NodeLabel::Method)
                })
                .map(|n| n.qualified_name.clone())
        } else {
            None
        };

        if let Some(qn) = target_qn {
            gbuf.set_node_property(&qn, "route_path", &hint.route_path);
            // Append method (comma-separated for multi-method routes)
            let existing_method = gbuf
                .find_by_qn(&qn)
                .and_then(|n| n.properties.get("route_method").cloned())
                .unwrap_or_default();
            let method = if existing_method.is_empty() {
                hint.route_method.clone()
            } else if existing_method.contains(&hint.route_method) {
                existing_method // already has this method
            } else {
                format!("{},{}", existing_method, hint.route_method)
            };
            gbuf.set_node_property(&qn, "route_method", &method);
        }
    }
}
```

- [ ] **Step 4: Run pipeline test**

Run: `cargo test -p tokkit-core pipeline_detects_fastapi_routes`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cargo test -p tokkit-core`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add crates/tokkit-core/src/pipeline/mod.rs
git commit -m "feat: wire route hints from extraction into graph node properties"
```

---

### Task 5: Enrichment updates — multi-method support and file-based routing

**Files:**
- Modify: `crates/tokkit-core/src/enrich/routes.rs`

- [ ] **Step 1: Write failing test for comma-separated methods**

Add to `routes.rs` tests:

```rust
#[test]
fn handles_comma_separated_methods() {
    let mut buf = GraphBuffer::new("proj", "/root");

    let func_id = buf.add_node(
        NodeLabel::Function,
        "users",
        "proj::views.py::users",
        Some("views.py".to_string()),
        1,
        10,
    );
    buf.set_node_property("proj::views.py::users", "route_path", "/users");
    buf.set_node_property("proj::views.py::users", "route_method", "GET,POST");

    find_routes(&mut buf);

    let route_nodes: Vec<_> = buf.nodes().iter().filter(|n| n.label == NodeLabel::Route).collect();
    assert_eq!(route_nodes.len(), 2, "Expected 2 Route nodes for GET,POST");

    let handles: Vec<_> = buf.edges().iter().filter(|e| {
        e.source_id == func_id && e.edge_type == EdgeType::Handles
    }).collect();
    assert_eq!(handles.len(), 2, "Expected 2 HANDLES edges");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test -p tokkit-core handles_comma_separated_methods`
Expected: FAIL — Branch A creates only one route, doesn't split on comma

- [ ] **Step 3: Update Branch A to split comma-separated methods**

In `routes.rs`, change the `prop_routes` processing (lines 28-30) from:

```rust
for (func_id, route_path, method) in prop_routes {
    route_edges.push((func_id, route_path, method));
}
```

to:

```rust
for (func_id, route_path, methods_str) in prop_routes {
    for method in methods_str.split(',') {
        let method = method.trim().to_string();
        if !method.is_empty() {
            route_edges.push((func_id, route_path.clone(), method));
        }
    }
}
```

- [ ] **Step 4: Run test**

Run: `cargo test -p tokkit-core handles_comma_separated_methods`
Expected: PASS

- [ ] **Step 5: Write failing test for file-based routing (Next.js)**

```rust
#[test]
fn detects_nextjs_file_route() {
    let mut buf = GraphBuffer::new("proj", "/root");

    buf.add_node(
        NodeLabel::File,
        "route.ts",
        "proj::app/users/route.ts::__file__",
        Some("app/users/route.ts".to_string()),
        0,
        0,
    );

    buf.add_node(
        NodeLabel::Function,
        "GET",
        "proj::app/users/route.ts::GET",
        Some("app/users/route.ts".to_string()),
        1,
        10,
    );

    buf.add_node(
        NodeLabel::Function,
        "POST",
        "proj::app/users/route.ts::POST",
        Some("app/users/route.ts".to_string()),
        12,
        20,
    );

    find_routes(&mut buf);

    let route_nodes: Vec<_> = buf.nodes().iter().filter(|n| n.label == NodeLabel::Route).collect();
    assert!(
        route_nodes.len() >= 2,
        "Expected at least 2 Route nodes for Next.js file routing, got {}",
        route_nodes.len()
    );
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cargo test -p tokkit-core detects_nextjs_file_route`
Expected: FAIL — no file-routing detection

- [ ] **Step 7: Add file-based routing detection**

In `routes.rs`, after the existing name-heuristic loop (after line 58), add a new detection branch:

```rust
// Branch C: File-based routing (Next.js, SvelteKit)
// Exported functions named GET/POST/PUT/DELETE/PATCH in route files
let file_route_patterns: &[&str] = &[
    "/route.ts", "/route.js", "/route.tsx", "/route.jsx",
    "/+server.ts", "/+server.js",
    "/+page.server.ts", "/+page.server.js",
];

for (func_id, func_name, file_path) in &func_nodes {
    if route_edges.iter().any(|(id, _, _)| id == func_id) {
        continue;
    }

    let fp = file_path.as_deref().unwrap_or("");
    let is_route_file = file_route_patterns.iter().any(|pat| fp.ends_with(pat));
    if !is_route_file {
        continue;
    }

    let upper_name = func_name.to_uppercase();
    if matches!(upper_name.as_str(), "GET" | "POST" | "PUT" | "DELETE" | "PATCH" | "HEAD" | "OPTIONS") {
        // Synthesize route path from directory structure
        // app/users/[id]/route.ts → /users/:id
        let route_path = synthesize_file_route_path(fp);
        route_edges.push((*func_id, route_path, upper_name));
    }
}
```

Add the path synthesis helper:

```rust
fn synthesize_file_route_path(file_path: &str) -> String {
    // Strip the filename to get the directory
    let dir = file_path
        .rsplit_once('/')
        .map(|(d, _)| d)
        .unwrap_or("");

    // Strip common prefixes: app/, src/app/, pages/api/
    let dir = dir
        .strip_prefix("src/app")
        .or_else(|| dir.strip_prefix("app"))
        .or_else(|| dir.strip_prefix("src/routes"))
        .or_else(|| dir.strip_prefix("pages/api"))
        .unwrap_or(dir);

    if dir.is_empty() {
        return "/".to_string();
    }

    // Convert [param] to :param and [...slug] to *slug
    let segments: Vec<String> = dir
        .split('/')
        .filter(|s| !s.is_empty())
        .map(|seg| {
            if seg.starts_with("[...") && seg.ends_with(']') {
                format!("*{}", &seg[4..seg.len() - 1])
            } else if seg.starts_with('[') && seg.ends_with(']') {
                format!(":{}", &seg[1..seg.len() - 1])
            } else if seg.starts_with("(") && seg.ends_with(")") {
                // Route groups like (auth) — skip
                String::new()
            } else {
                seg.to_string()
            }
        })
        .filter(|s| !s.is_empty())
        .collect();

    if segments.is_empty() {
        "/".to_string()
    } else {
        format!("/{}", segments.join("/"))
    }
}
```

- [ ] **Step 8: Run file-routing test**

Run: `cargo test -p tokkit-core detects_nextjs_file_route`
Expected: PASS

- [ ] **Step 9: Run full enrichment test suite**

Run: `cargo test -p tokkit-core enrich`
Expected: ALL PASS (no regressions)

- [ ] **Step 10: Commit**

```bash
git add crates/tokkit-core/src/enrich/routes.rs
git commit -m "feat: support comma-separated methods and file-based routing in enrichment"
```

---

### Task 6: Multi-framework integration test

**Files:**
- Modify: `crates/tokkit-core/src/pipeline/mod.rs` (test section)

- [ ] **Step 1: Write comprehensive integration test**

Add to `pipeline/mod.rs` tests:

```rust
#[test]
fn pipeline_detects_routes_across_frameworks() {
    let repo_dir = TempDir::new().unwrap();

    // FastAPI
    fs::create_dir_all(repo_dir.path().join("python_app")).unwrap();
    fs::write(
        repo_dir.path().join("python_app/main.py"),
        r#"from fastapi import FastAPI
app = FastAPI()

@app.get("/api/users")
async def list_users():
    return []

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int):
    pass
"#,
    )
    .unwrap();

    // Express
    fs::create_dir_all(repo_dir.path().join("js_app")).unwrap();
    fs::write(
        repo_dir.path().join("js_app/routes.js"),
        r#"const express = require('express');
const router = express.Router();

function getItems(req, res) {
    res.json([]);
}

router.get("/api/items", getItems);
"#,
    )
    .unwrap();

    // Next.js file routing
    fs::create_dir_all(repo_dir.path().join("app/products/[id]")).unwrap();
    fs::write(
        repo_dir.path().join("app/products/[id]/route.ts"),
        "export async function GET(request: Request) {\n    return Response.json({});\n}\n\nexport async function DELETE(request: Request) {\n    return Response.json({});\n}\n",
    )
    .unwrap();

    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    let result = run(
        repo_dir.path().to_str().unwrap(),
        db_path.to_str().unwrap(),
        IndexMode::Full,
    )
    .unwrap();

    let store = Store::open(db_path.to_str().unwrap()).unwrap();
    let nodes = store.all_nodes().unwrap();
    let edges = store.all_edges().unwrap();

    let route_nodes: Vec<_> = nodes.iter().filter(|n| n.label == NodeLabel::Route).collect();
    let handles_edges: Vec<_> = edges.iter().filter(|e| e.edge_type == EdgeType::Handles).collect();

    // FastAPI: 2 routes (GET /api/users, DELETE /api/users/{user_id})
    // Express: 1 route (GET /api/items) — if handler name matches
    // Next.js: 2 routes (GET /products/:id, DELETE /products/:id)
    // Total: at least 4 routes
    assert!(
        route_nodes.len() >= 4,
        "Expected at least 4 Route nodes, got {}. Routes: {:?}",
        route_nodes.len(),
        route_nodes.iter().map(|n| (&n.name, &n.qualified_name)).collect::<Vec<_>>()
    );

    assert!(
        handles_edges.len() >= 4,
        "Expected at least 4 HANDLES edges, got {}",
        handles_edges.len()
    );
}
```

- [ ] **Step 2: Run integration test**

Run: `cargo test -p tokkit-core pipeline_detects_routes_across_frameworks`
Expected: PASS (if all previous tasks were implemented correctly)

- [ ] **Step 3: If test fails, debug and fix**

Run with output: `cargo test -p tokkit-core pipeline_detects_routes_across_frameworks -- --nocapture`

Check:
- Are route_hints populated? Add temp debug prints in pipeline wiring
- Are properties set on nodes? Check `gbuf.find_by_qn(...).properties`
- Is enrichment picking them up? Check routes.rs Branch A output

- [ ] **Step 4: Run full cargo test suite**

Run: `cargo test --workspace`
Expected: ALL PASS

- [ ] **Step 5: Run Python tests for MCP layer**

Run: `pytest tests/ -v --ignore=tests/e2e/benchmark -x`
Expected: ALL PASS (MCP layer unchanged)

- [ ] **Step 6: Commit**

```bash
git add crates/tokkit-core/src/pipeline/mod.rs
git commit -m "test: add multi-framework route detection integration test"
```

---

### Task 7: Update documentation

**Files:**
- Modify: `skill/SKILL.md`

- [ ] **Step 1: Update SKILL.md route detection documentation**

In the Known Limitations section, remove the "Route detection is heuristic" bullet and replace with:

```markdown
- **Route detection** covers decorator-based frameworks (FastAPI, Flask, Starlette, NestJS) and call-expression frameworks (Express, Koa, Hono, Fastify). Django urlpatterns and Tornado class-based handlers are not yet detected.
```

- [ ] **Step 2: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs: update route detection limitations in SKILL.md"
```

---

## Framework Coverage Summary

| Framework | Language | Pattern | Detection |
|-----------|----------|---------|-----------|
| FastAPI | Python | `@app.get("/path")` | Decorator (walker) |
| Flask | Python | `@app.route("/path", methods=[...])` | Decorator (walker) |
| Starlette | Python | `@app.route("/path")` | Decorator (walker) |
| Bottle | Python | `@app.get("/path")` | Decorator (walker) |
| aiohttp | Python | `@routes.get("/path")` | Decorator (walker) |
| Express | JS | `app.get("/path", handler)` | Call expression (walker) |
| Koa | JS | `router.get("/path", handler)` | Call expression (walker) |
| Hono | JS/TS | `app.get("/path", handler)` | Call expression (walker) |
| Fastify | JS/TS | `fastify.get("/path", handler)` | Call expression (walker) |
| Elysia | TS | `app.get("/path", handler)` | Call expression (walker) |
| NestJS | TS | `@Get("/path")` | Decorator (walker) |
| Next.js | JS/TS | `export function GET()` in route files | File routing (enrichment) |
| SvelteKit | JS/TS | `export function GET()` in +server files | File routing (enrichment) |

**Not covered (future work):**
- Django urlpatterns (separate URL configuration file, no decorators)
- Tornado class-based handlers (method names on RequestHandler subclass)
- tRPC (procedure-based, not REST)
- NestJS `@Controller` prefix concatenation
