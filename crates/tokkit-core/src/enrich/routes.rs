use std::collections::HashMap;
use crate::graph::GraphBuffer;
use crate::types::{NodeLabel, EdgeType, Edge};

pub fn find_routes(buf: &mut GraphBuffer) {
    let func_nodes: Vec<(u64, String, Option<String>)> = buf
        .nodes()
        .iter()
        .filter(|n| n.label == NodeLabel::Function || n.label == NodeLabel::Method)
        .map(|n| (n.id, n.name.clone(), n.file_path.clone()))
        .collect();

    // Also check properties for explicit route metadata
    let prop_routes: Vec<(u64, String, String)> = buf
        .nodes()
        .iter()
        .filter(|n| n.label == NodeLabel::Function || n.label == NodeLabel::Method)
        .filter_map(|n| {
            let path = n.properties.get("route_path")?.clone();
            let method = n.properties.get("route_method").cloned().unwrap_or_else(|| "GET".to_string());
            Some((n.id, path, method))
        })
        .collect();

    let mut route_edges: Vec<(u64, String, String)> = Vec::new();

    // Process explicit route properties (supports comma-separated methods)
    for (func_id, route_path, methods_str) in prop_routes {
        for method in methods_str.split(',') {
            let method = method.trim().to_string();
            if !method.is_empty() {
                route_edges.push((func_id, route_path.clone(), method));
            }
        }
    }

    // Process name-based route detection in route files
    let http_prefixes = ["get_", "post_", "put_", "delete_", "patch_"];
    for (func_id, func_name, file_path) in &func_nodes {
        // Skip if already handled via properties
        if route_edges.iter().any(|(id, _, _)| id == func_id) {
            continue;
        }

        let fp = file_path.as_deref().unwrap_or("");
        let is_route_file = fp.contains("route")
            || fp.contains("controller")
            || fp.contains("handler")
            || fp.contains("view");

        if !is_route_file {
            continue;
        }

        for prefix in &http_prefixes {
            if let Some(resource) = func_name.strip_prefix(prefix) {
                let method = prefix.trim_end_matches('_').to_uppercase();
                let route_path = format!("/{}", resource.replace('_', "/"));
                route_edges.push((*func_id, route_path, method));
                break;
            }
        }
    }

    // Branch C: File-based routing (Next.js, SvelteKit)
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
            let route_path = synthesize_file_route_path(fp);
            route_edges.push((*func_id, route_path, upper_name));
        }
    }

    // Create Route nodes and HANDLES edges
    let mut new_items: Vec<(u64, String, String)> = Vec::new();
    for (func_id, route_path, method) in route_edges {
        new_items.push((func_id, route_path, method));
    }

    for (func_id, route_path, method) in new_items {
        let route_qn = format!("route:{}:{}", method, route_path);
        let route_id = buf.add_node(
            NodeLabel::Route,
            &route_path,
            &route_qn,
            None,
            0,
            0,
        );

        // Set method property on the route node
        if let Some(node) = buf.nodes().iter().find(|n| n.id == route_id) {
            let _ = node; // just verify it exists
        }

        buf.add_edge(Edge {
            source_id: func_id,
            target_id: route_id,
            edge_type: EdgeType::Handles,
            confidence: None,
            properties: {
                let mut p = HashMap::new();
                p.insert("method".to_string(), method);
                p
            },
        });
    }
}

fn synthesize_file_route_path(file_path: &str) -> String {
    let dir = file_path
        .rsplit_once('/')
        .map(|(d, _)| d)
        .unwrap_or("");

    let dir = dir
        .strip_prefix("src/app")
        .or_else(|| dir.strip_prefix("app"))
        .or_else(|| dir.strip_prefix("src/routes"))
        .or_else(|| dir.strip_prefix("pages/api"))
        .unwrap_or(dir);

    if dir.is_empty() {
        return "/".to_string();
    }

    let segments: Vec<String> = dir
        .split('/')
        .filter(|s| !s.is_empty())
        .map(|seg| {
            if seg.starts_with("[...") && seg.ends_with(']') {
                format!("*{}", &seg[4..seg.len() - 1])
            } else if seg.starts_with('[') && seg.ends_with(']') {
                format!(":{}", &seg[1..seg.len() - 1])
            } else if seg.starts_with('(') && seg.ends_with(')') {
                String::new() // route groups — skip
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_route_handler() {
        let mut buf = GraphBuffer::new("proj", "/root");

        let _file_id = buf.add_node(
            NodeLabel::File,
            "users.py",
            "routes/users.py",
            Some("routes/users.py".to_string()),
            0,
            0,
        );

        let func_id = buf.add_node(
            NodeLabel::Function,
            "get_users",
            "routes/users.py::get_users",
            Some("routes/users.py".to_string()),
            1,
            10,
        );

        find_routes(&mut buf);

        let route_exists = buf
            .nodes()
            .iter()
            .any(|n| n.label == NodeLabel::Route);
        assert!(route_exists, "Expected a Route node to be created");

        let handles_edge = buf.edges().iter().any(|e| {
            e.source_id == func_id && e.edge_type == EdgeType::Handles
        });
        assert!(handles_edge, "Expected a HANDLES edge from get_users to the route");
    }

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
}
