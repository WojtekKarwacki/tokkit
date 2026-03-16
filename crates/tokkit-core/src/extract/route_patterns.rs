use regex::Regex;
use std::sync::LazyLock;

/// HTTP methods recognized as route indicators
const HTTP_METHODS: &[&str] = &["get", "post", "put", "delete", "patch", "head", "options", "all"];

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

static NESTJS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"@(?i)(Get|Post|Put|Delete|Patch|Head|Options|All)\s*\(\s*(?:["']([^"']*?)["'])?\s*\)"#)
        .unwrap()
});

/// Parse a Python route decorator text into (method, path) pairs.
///
/// Handles:
/// - `@app.get("/users")` (FastAPI, Flask shorthand, Starlette, aiohttp)
/// - `@app.route("/users", methods=["GET", "POST"])` (Flask, Bottle)
/// - `@app.route("/users")` (defaults to GET)
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

/// Parse a NestJS-style decorator into (method, path).
///
/// Handles:
/// - `@Get("/users")`, `@Post("/users")`, etc.
/// - `@Get()` (empty path → "/")
pub fn parse_nestjs_decorator(text: &str) -> Option<(String, String)> {
    let caps = NESTJS_RE.captures(text)?;
    let method = caps[1].to_uppercase();
    let path = caps.get(2).map_or("/", |m| m.as_str()).to_string();
    let path = if path.is_empty() { "/".to_string() } else { path };
    Some((method, path))
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
