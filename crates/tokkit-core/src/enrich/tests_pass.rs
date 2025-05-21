use std::collections::HashMap;
use crate::graph::GraphBuffer;
use crate::types::{NodeLabel, EdgeType, Edge};

pub fn detect_tests(buf: &mut GraphBuffer) {
    let file_nodes: Vec<(u64, String)> = buf
        .nodes()
        .iter()
        .filter(|n| n.label == NodeLabel::File)
        .map(|n| (n.id, n.name.clone()))
        .collect();

    // Build a map from file name to node id for quick lookup
    let name_to_id: HashMap<String, u64> = file_nodes
        .iter()
        .map(|(id, name)| (name.clone(), *id))
        .collect();

    // Also build a map from path components for directory-based matching
    let path_to_id: HashMap<String, u64> = buf
        .nodes()
        .iter()
        .filter(|n| n.label == NodeLabel::File)
        .filter_map(|n| n.file_path.as_ref().map(|p| (p.clone(), n.id)))
        .collect();

    let mut edges_to_add: Vec<(u64, u64)> = Vec::new();

    for (test_id, test_name) in &file_nodes {
        // Check directory-based: file under __tests__/, tests/, test/, spec/
        let test_file_path = buf
            .find_by_id(*test_id)
            .and_then(|n| n.file_path.clone())
            .unwrap_or_default();

        let in_test_dir = is_in_test_directory(&test_file_path);

        if let Some(impl_name) = derive_impl_name(test_name) {
            // Try to find the implementation file by name
            if let Some(&impl_id) = name_to_id.get(&impl_name)
                && impl_id != *test_id
            {
                edges_to_add.push((*test_id, impl_id));
                continue;
            }

            // Try to find by matching the impl filename in paths
            for (path, impl_id) in &path_to_id {
                if *impl_id == *test_id {
                    continue;
                }
                let path_filename = std::path::Path::new(path)
                    .file_name()
                    .and_then(|f| f.to_str())
                    .unwrap_or("");
                if path_filename == impl_name {
                    edges_to_add.push((*test_id, *impl_id));
                    break;
                }
            }
        } else if in_test_dir {
            // In a test directory but name doesn't follow prefix/suffix pattern
            // Try to find a matching impl by the same filename in non-test dirs
            for (path, impl_id) in &path_to_id {
                if *impl_id == *test_id {
                    continue;
                }
                if is_in_test_directory(path) {
                    continue;
                }
                let path_filename = std::path::Path::new(path)
                    .file_name()
                    .and_then(|f| f.to_str())
                    .unwrap_or("");
                if path_filename == test_name.as_str() {
                    edges_to_add.push((*test_id, *impl_id));
                    break;
                }
            }
        }
    }

    for (test_id, impl_id) in edges_to_add {
        buf.add_edge(Edge {
            source_id: test_id,
            target_id: impl_id,
            edge_type: EdgeType::TestsFile,
            confidence: None,
            properties: HashMap::new(),
        });
    }
}

fn is_in_test_directory(path: &str) -> bool {
    let components: Vec<&str> = path.split('/').collect();
    for component in &components[..components.len().saturating_sub(1)] {
        if matches!(*component, "__tests__" | "tests" | "test" | "spec") {
            return true;
        }
    }
    false
}

fn derive_impl_name(filename: &str) -> Option<String> {
    // Python: test_foo.py -> foo.py
    if let Some(rest) = filename.strip_prefix("test_")
        && rest.ends_with(".py")
    {
        return Some(rest.to_string());
    }

    // Python: foo_test.py -> foo.py
    if let Some(base) = filename.strip_suffix("_test.py") {
        return Some(format!("{}.py", base));
    }

    // JS/TS: foo.test.js -> foo.js, foo.test.ts -> foo.ts, foo.test.tsx -> foo.tsx
    for ext in &["js", "ts", "tsx"] {
        let test_suffix = format!(".test.{}", ext);
        let spec_suffix = format!(".spec.{}", ext);
        if filename.ends_with(&test_suffix) {
            let base = &filename[..filename.len() - test_suffix.len()];
            return Some(format!("{}.{}", base, ext));
        }
        if filename.ends_with(&spec_suffix) {
            let base = &filename[..filename.len() - spec_suffix.len()];
            return Some(format!("{}.{}", base, ext));
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_buf() -> GraphBuffer {
        GraphBuffer::new("proj", "/root")
    }

    #[test]
    fn detects_python_test_files() {
        let mut buf = make_buf();
        let impl_id = buf.add_node(
            NodeLabel::File,
            "auth.py",
            "src/auth.py",
            Some("src/auth.py".to_string()),
            0,
            0,
        );
        let test_id = buf.add_node(
            NodeLabel::File,
            "test_auth.py",
            "tests/test_auth.py",
            Some("tests/test_auth.py".to_string()),
            0,
            0,
        );

        detect_tests(&mut buf);

        let has_edge = buf.edges().iter().any(|e| {
            e.source_id == test_id
                && e.target_id == impl_id
                && e.edge_type == EdgeType::TestsFile
        });
        assert!(has_edge, "Expected TESTS_FILE edge from test_auth.py to auth.py");
    }

    #[test]
    fn detects_js_spec_files() {
        let mut buf = make_buf();
        let impl_id = buf.add_node(
            NodeLabel::File,
            "app.js",
            "src/app.js",
            Some("src/app.js".to_string()),
            0,
            0,
        );
        let test_id = buf.add_node(
            NodeLabel::File,
            "app.spec.js",
            "src/app.spec.js",
            Some("src/app.spec.js".to_string()),
            0,
            0,
        );

        detect_tests(&mut buf);

        let has_edge = buf.edges().iter().any(|e| {
            e.source_id == test_id
                && e.target_id == impl_id
                && e.edge_type == EdgeType::TestsFile
        });
        assert!(has_edge, "Expected TESTS_FILE edge from app.spec.js to app.js");
    }
}
