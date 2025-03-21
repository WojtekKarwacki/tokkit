use tree_sitter::{Node, Parser};

use crate::error::Result;
use crate::extract::route_patterns::{is_http_method, parse_nestjs_decorator, parse_python_route_decorator};
use crate::types::{CallRef, Definition, FileResult, ImportRef, NodeLabel, RouteHint};

use super::spec::LanguageSpec;

pub fn extract_file(
    source: &str,
    file_rel_path: &str,
    project_name: &str,
    spec: &dyn LanguageSpec,
) -> Result<FileResult> {
    let mut parser = Parser::new();
    parser
        .set_language(&spec.ts_language())
        .map_err(|e| crate::error::TokkitError::Parse(e.to_string()))?;

    let tree = parser
        .parse(source, None)
        .ok_or_else(|| crate::error::TokkitError::Parse("tree-sitter returned None".into()))?;

    let source_bytes = source.as_bytes();
    let mut result = FileResult::default();
    let mut scope_stack: Vec<String> = Vec::new();
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

    Ok(result)
}

fn qualified_name(project_name: &str, file_rel_path: &str, name: &str) -> String {
    format!("{}::{}::{}", project_name, file_rel_path, name)
}

fn current_scope_qn(
    project_name: &str,
    file_rel_path: &str,
    scope_stack: &[String],
    name: &str,
) -> String {
    if scope_stack.is_empty() {
        qualified_name(project_name, file_rel_path, name)
    } else {
        let scope_path = scope_stack.join(".");
        qualified_name(project_name, file_rel_path, &format!("{}.{}", scope_path, name))
    }
}

fn node_text<'a>(node: Node<'_>, source: &'a [u8]) -> Option<&'a str> {
    node.utf8_text(source).ok()
}

fn extract_name<'a>(node: Node<'_>, source: &'a [u8]) -> Option<&'a str> {
    if let Some(name_node) = node.child_by_field_name("name") {
        return node_text(name_node, source);
    }
    if let Some(prop_node) = node.child_by_field_name("property") {
        return node_text(prop_node, source);
    }
    None
}

fn label_for_class_node(kind: &str) -> NodeLabel {
    match kind {
        "interface_declaration" => NodeLabel::Interface,
        "enum_declaration" => NodeLabel::Enum,
        _ => NodeLabel::Class,
    }
}

fn in_class_scope(scope_stack: &[String], definitions: &[Definition]) -> bool {
    if let Some(enclosing) = scope_stack.last() {
        for def in definitions {
            if def.name == *enclosing
                && (def.label == NodeLabel::Class
                    || def.label == NodeLabel::Interface
                    || def.label == NodeLabel::Enum)
            {
                return true;
            }
        }
    }
    false
}

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

    let is_decorator = spec.decorator_types().contains(&kind);
    let is_function = spec.function_types().contains(&kind);
    let is_class = spec.class_types().contains(&kind);
    let is_call = spec.call_types().contains(&kind);
    let is_import = spec.import_types().contains(&kind);
    let is_import_from = spec.import_from_types().contains(&kind);

    // Buffer decorators for consumption by the next function/method node
    if is_decorator {
        if let Some(text) = node_text(node, source) {
            // Only push to pending if not a child of a function/method node
            let parent_is_function = node
                .parent()
                .map(|p| spec.function_types().contains(&p.kind()))
                .unwrap_or(false);
            if !parent_is_function {
                pending_decorators.push(text.to_string());
            }
        }
        return; // Don't walk children
    }

    if is_function && let Some(name) = extract_name(node, source) {
        let label = if in_class_scope(scope_stack, &result.definitions) {
            NodeLabel::Method
        } else {
            NodeLabel::Function
        };
        let qn = current_scope_qn(project_name, file_rel_path, scope_stack, name);

        // Consume pending decorators for route patterns
        consume_route_decorators(pending_decorators, &qn, line_start, result);
        // Also check direct child decorators (TypeScript pattern)
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

    if is_class && let Some(name) = extract_name(node, source) {
        let label = label_for_class_node(kind);
        let qn = current_scope_qn(project_name, file_rel_path, scope_stack, name);
        // Clear any class-level decorators (e.g. @Controller) — don't treat as route
        pending_decorators.clear();
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

    if is_call && let Some(callee_text) = extract_call_callee(node, source) {
        let simple_name = callee_text
            .rsplit('.')
            .next()
            .unwrap_or(callee_text)
            .to_string();

        // Express-style route detection: app.get("/path", handler)
        if callee_text.contains('.') && is_http_method(&simple_name) {
            if let Some((path, handler_name)) = extract_route_call_args(node, source) {
                result.route_hints.push(RouteHint {
                    def_qn: String::new(),
                    handler_name,
                    route_path: path,
                    route_method: simple_name.to_uppercase(),
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

    if is_import {
        let import_ref = extract_import(node, source, line_start);
        result.imports.push(import_ref);
    }

    if is_import_from {
        let import_ref = extract_import_from(node, source, line_start);
        result.imports.push(import_ref);
    }

    walk_children(node, source, file_rel_path, project_name, spec, scope_stack, pending_decorators, result);
}

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

fn consume_route_decorators(
    pending_decorators: &mut Vec<String>,
    def_qn: &str,
    line: u32,
    result: &mut FileResult,
) {
    for dec_text in pending_decorators.drain(..) {
        for (method, path) in parse_python_route_decorator(&dec_text) {
            result.route_hints.push(RouteHint {
                def_qn: def_qn.to_string(),
                handler_name: String::new(),
                route_path: path,
                route_method: method,
                line,
            });
        }
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
                if let Some((method, path)) = parse_nestjs_decorator(text) {
                    result.route_hints.push(RouteHint {
                        def_qn: def_qn.to_string(),
                        handler_name: String::new(),
                        route_path: path,
                        route_method: method,
                        line,
                    });
                }
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

/// Extract (route_path, handler_name) from a call like `app.get("/path", handler)`.
fn extract_route_call_args(node: Node<'_>, source: &[u8]) -> Option<(String, String)> {
    let args_node = node.child_by_field_name("arguments")?;
    let mut string_arg: Option<String> = None;
    let mut handler_name = String::new();
    let mut arg_index = 0;

    let mut cursor = args_node.walk();
    for child in args_node.children(&mut cursor) {
        let ck = child.kind();
        if ck == "(" || ck == ")" || ck == "," {
            continue;
        }
        if arg_index == 0 {
            // First argument should be a string path starting with "/"
            if ck == "string" || ck == "string_fragment" || ck == "template_string" {
                let text = node_text(child, source)?;
                let path = text.trim_matches(|c| c == '"' || c == '\'' || c == '`');
                if path.starts_with('/') {
                    string_arg = Some(path.to_string());
                }
            }
        } else if arg_index == 1 {
            // Second argument is the handler
            if ck == "identifier" {
                handler_name = node_text(child, source)?.to_string();
            } else if ck == "member_expression" {
                if let Some(prop) = child.child_by_field_name("property") {
                    handler_name = node_text(prop, source)?.to_string();
                }
            }
        }
        arg_index += 1;
    }

    Some((string_arg?, handler_name))
}

fn extract_call_callee<'a>(node: Node<'_>, source: &'a [u8]) -> Option<&'a str> {
    if let Some(func_node) = node.child_by_field_name("function") {
        return node_text(func_node, source);
    }
    if let Some(first) = node.child(0) {
        return node_text(first, source);
    }
    None
}

fn extract_import(node: Node<'_>, source: &[u8], line: u32) -> ImportRef {
    let full_text = node_text(node, source).unwrap_or("").to_string();
    ImportRef {
        module_path: full_text,
        alias: None,
        names: Vec::new(),
        line,
    }
}

fn extract_import_from(node: Node<'_>, source: &[u8], line: u32) -> ImportRef {
    let module_path = node
        .child_by_field_name("module_name")
        .and_then(|n| node_text(n, source))
        .unwrap_or("")
        .to_string();

    let mut names = Vec::new();
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        let child_kind = child.kind();
        if (child_kind == "dotted_name" || child_kind == "identifier" || child_kind == "aliased_import")
            && let Some(text) = node_text(child, source)
            && text != module_path
        {
            names.push(text.to_string());
        }
    }

    ImportRef {
        module_path,
        alias: None,
        names,
        line,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::extract::spec::spec_for_language;
    use crate::types::{Language, NodeLabel};

    #[test]
    fn extracts_python_functions() {
        let source = "def foo():\n    pass\n\ndef bar():\n    pass\n";
        let spec = spec_for_language(Language::Python);
        let result = extract_file(source, "src/mod.py", "proj", spec).unwrap();
        let fns: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Function)
            .collect();
        assert_eq!(fns.len(), 2);
        let names: Vec<&str> = fns.iter().map(|d| d.name.as_str()).collect();
        assert!(names.contains(&"foo"));
        assert!(names.contains(&"bar"));
    }

    #[test]
    fn extracts_python_class_with_methods() {
        let source = "class MyClass:\n    def method_a(self):\n        pass\n\n    def method_b(self):\n        pass\n";
        let spec = spec_for_language(Language::Python);
        let result = extract_file(source, "src/cls.py", "proj", spec).unwrap();

        let classes: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Class)
            .collect();
        assert_eq!(classes.len(), 1);
        assert_eq!(classes[0].name, "MyClass");

        let methods: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Method)
            .collect();
        assert_eq!(methods.len(), 2);
        let method_names: Vec<&str> = methods.iter().map(|d| d.name.as_str()).collect();
        assert!(method_names.contains(&"method_a"));
        assert!(method_names.contains(&"method_b"));
    }

    #[test]
    fn extracts_python_calls() {
        let source = "def run():\n    foo()\n    bar()\n";
        let spec = spec_for_language(Language::Python);
        let result = extract_file(source, "src/run.py", "proj", spec).unwrap();
        assert!(result.calls.len() >= 2);
        let callee_names: Vec<&str> = result.calls.iter().map(|c| c.callee_name.as_str()).collect();
        assert!(callee_names.contains(&"foo"));
        assert!(callee_names.contains(&"bar"));
    }

    #[test]
    fn extracts_python_imports() {
        let source = "import os\nfrom pathlib import Path\n";
        let spec = spec_for_language(Language::Python);
        let result = extract_file(source, "src/imports.py", "proj", spec).unwrap();
        assert!(result.imports.len() >= 2);
    }

    #[test]
    fn extracts_js_arrow_functions() {
        let source = "const greet = (name) => name;\nfunction hello() { return 1; }\n";
        let spec = spec_for_language(Language::JavaScript);
        let result = extract_file(source, "src/app.js", "proj", spec).unwrap();
        let fn_defs: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Function)
            .collect();
        assert!(fn_defs.len() >= 1);
        let names: Vec<&str> = fn_defs.iter().map(|d| d.name.as_str()).collect();
        assert!(names.contains(&"hello"));
    }

    #[test]
    fn extracts_ts_interface_and_enum() {
        let source = "interface IFoo { x: number; }\nenum Color { Red, Green }\nfunction doThing(): void {}\n";
        let spec = spec_for_language(Language::TypeScript);
        let result = extract_file(source, "src/types.ts", "proj", spec).unwrap();

        let interfaces: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Interface)
            .collect();
        assert_eq!(interfaces.len(), 1);
        assert_eq!(interfaces[0].name, "IFoo");

        let enums: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Enum)
            .collect();
        assert_eq!(enums.len(), 1);
        assert_eq!(enums[0].name, "Color");

        let functions: Vec<_> = result
            .definitions
            .iter()
            .filter(|d| d.label == NodeLabel::Function)
            .collect();
        assert_eq!(functions.len(), 1);
        assert_eq!(functions[0].name, "doThing");
    }

    #[test]
    fn qualified_names_include_scope() {
        let source = "class AuthService:\n    def login(self):\n        pass\n";
        let spec = spec_for_language(Language::Python);
        let result = extract_file(source, "src/auth.py", "proj", spec).unwrap();

        let method = result
            .definitions
            .iter()
            .find(|d| d.name == "login")
            .unwrap();
        assert!(
            method.qualified_name.contains("AuthService.login"),
            "Expected QN to contain 'AuthService.login', got: {}",
            method.qualified_name
        );
    }

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
}
