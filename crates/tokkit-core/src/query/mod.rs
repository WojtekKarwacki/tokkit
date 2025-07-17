use std::collections::{HashSet, VecDeque};

use regex::Regex;

use crate::store::Store;
use crate::{
    ChangedFile, CodeSnippet, Confidence, EdgeType, FileInfo, Node, NodeLabel, PathStep,
    Result, SchemaResult, SearchFilters, StatusResult, TokkitError,
};

pub fn search_nodes(store: &Store, filters: &SearchFilters) -> Result<Vec<Node>> {
    let limit = filters.limit.unwrap_or(50) as usize;
    let all = store.all_nodes()?;
    let mut results: Vec<Node> = all
        .into_iter()
        .filter(|n| {
            if let Some(q) = &filters.query {
                let q_lower = q.to_lowercase();
                let name_match = n.name.to_lowercase().contains(&q_lower);
                let qn_match = n.qualified_name.to_lowercase().contains(&q_lower);
                if !name_match && !qn_match {
                    return false;
                }
            }
            if let Some(label) = &filters.label
                && n.label != *label
            {
                return false;
            }
            if let Some(fp) = &filters.file_path {
                match &n.file_path {
                    Some(nfp) => {
                        if !nfp.contains(fp.as_str()) {
                            return false;
                        }
                    }
                    None => return false,
                }
            }
            if let Some(pat) = &filters.name_pattern {
                if let Ok(re) = Regex::new(pat) {
                    if !re.is_match(&n.name) {
                        return false;
                    }
                }
            }
            if filters.exclude_entry_points == Some(true) {
                let dominated_names = ["main", "__main__", "__init__"];
                if dominated_names.iter().any(|&ep| n.name == ep) {
                    return false;
                }
                if n.name.starts_with("test_") || n.name.starts_with("Test") {
                    return false;
                }
                if n.label == NodeLabel::Route {
                    return false;
                }
            }
            true
        })
        .collect();

    if let Some(max_deg) = filters.max_degree {
        results.retain(|n| {
            let out_edges = store.get_edges_from(n.id).unwrap_or_default();
            let in_edges = store.get_edges_to(n.id).unwrap_or_default();
            let total_degree = out_edges.len() + in_edges.len();
            total_degree <= max_deg as usize
        });
    }

    if let Some(ref rel) = filters.relationship {
        results.retain(|n| {
            let out_edges = store.get_edges_from(n.id).unwrap_or_default();
            let in_edges = store.get_edges_to(n.id).unwrap_or_default();
            out_edges.iter().any(|e| e.edge_type.as_str() == rel)
                || in_edges.iter().any(|e| e.edge_type.as_str() == rel)
        });
    }

    results.truncate(limit);
    Ok(results)
}

pub fn trace_path(
    store: &Store,
    from_qn: &str,
    to_qn: &str,
    max_depth: u32,
) -> Result<Vec<PathStep>> {
    let from_node = match store.get_node(from_qn)? {
        Some(n) => n,
        None => return Ok(vec![]),
    };
    let to_node = match store.get_node(to_qn)? {
        Some(n) => n,
        None => return Ok(vec![]),
    };

    let target_id = to_node.id;

    // Each queue entry: (current_node_id, path_so_far as Vec<PathStep>)
    let mut queue: VecDeque<(u64, Vec<PathStep>)> = VecDeque::new();
    let initial_step = PathStep {
        node: from_node.clone(),
        edge: None,
        depth: 0,
        body: None,
    };
    queue.push_back((from_node.id, vec![initial_step]));

    let mut visited: HashSet<u64> = HashSet::new();
    visited.insert(from_node.id);

    while let Some((current_id, path)) = queue.pop_front() {
        let depth = path.len() as u32;
        if depth > max_depth {
            continue;
        }

        let edges = store.get_edges_from(current_id)?;
        for edge in edges {
            let next_id = edge.target_id;
            if next_id == target_id {
                let next_node = match store.get_node_by_id(next_id)? {
                    Some(n) => n,
                    None => continue,
                };
                let mut full_path = path.clone();
                full_path.push(PathStep {
                    node: next_node,
                    edge: Some(edge),
                    depth,
                    body: None,
                });
                return Ok(full_path);
            }
            if !visited.contains(&next_id) && depth < max_depth {
                visited.insert(next_id);
                let next_node = match store.get_node_by_id(next_id)? {
                    Some(n) => n,
                    None => continue,
                };
                let mut new_path = path.clone();
                new_path.push(PathStep {
                    node: next_node,
                    edge: Some(edge),
                    depth,
                    body: None,
                });
                queue.push_back((next_id, new_path));
            }
        }
    }
    Ok(vec![])
}

pub fn trace_fan(
    store: &Store,
    start_qn: &str,
    direction: &str, // "inbound", "outbound", "both"
    max_depth: u32,
) -> Result<Vec<PathStep>> {
    let start_node = match store.get_node(start_qn)? {
        Some(n) => n,
        None => return Ok(vec![]),
    };

    let mut results: Vec<PathStep> = Vec::new();
    let mut queue: VecDeque<(u64, u32)> = VecDeque::new();
    let mut visited: HashSet<u64> = HashSet::new();

    results.push(PathStep {
        node: start_node.clone(),
        edge: None,
        depth: 0,
        body: None,
    });
    visited.insert(start_node.id);
    queue.push_back((start_node.id, 0));

    while let Some((current_id, depth)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }

        let mut edges: Vec<crate::Edge> = Vec::new();
        if direction == "outbound" || direction == "both" {
            edges.extend(store.get_edges_from(current_id)?);
        }
        if direction == "inbound" || direction == "both" {
            edges.extend(store.get_edges_to(current_id)?);
        }

        for edge in edges {
            let next_id = if edge.source_id == current_id {
                edge.target_id
            } else {
                edge.source_id
            };

            if visited.contains(&next_id) {
                continue;
            }
            visited.insert(next_id);

            if let Some(next_node) = store.get_node_by_id(next_id)? {
                results.push(PathStep {
                    node: next_node,
                    edge: Some(edge),
                    depth: depth + 1,
                    body: None,
                });
                queue.push_back((next_id, depth + 1));
            }
        }
    }

    Ok(results)
}

pub fn get_callers(
    store: &Store,
    qn: &str,
) -> Result<Vec<(Node, Option<Confidence>)>> {
    let node = match store.get_node(qn)? {
        Some(n) => n,
        None => return Ok(vec![]),
    };
    let edges = store.get_edges_to(node.id)?;
    let mut result = Vec::new();
    for edge in edges {
        if edge.edge_type != EdgeType::Calls {
            continue;
        }
        if let Some(src_node) = store.get_node_by_id(edge.source_id)? {
            result.push((src_node, edge.confidence));
        }
    }
    Ok(result)
}

pub fn get_callees(
    store: &Store,
    qn: &str,
) -> Result<Vec<(Node, Option<Confidence>)>> {
    let node = match store.get_node(qn)? {
        Some(n) => n,
        None => return Ok(vec![]),
    };
    let edges = store.get_edges_from(node.id)?;
    let mut result = Vec::new();
    for edge in edges {
        if edge.edge_type != EdgeType::Calls {
            continue;
        }
        if let Some(tgt_node) = store.get_node_by_id(edge.target_id)? {
            result.push((tgt_node, edge.confidence));
        }
    }
    Ok(result)
}

/// Like trace_fan but resolves plain function names and optionally embeds code bodies.
pub fn trace_fan_with_body(
    store: &Store,
    name: &str,
    direction: &str,
    max_depth: u32,
    repo_path: &str,
    include_body: bool,
) -> Result<Vec<PathStep>> {
    // Resolve: if name contains "::", treat as qualified name; otherwise fuzzy-match
    let start_qn = if name.contains("::") {
        name.to_string()
    } else {
        let all = store.all_nodes()?;
        // Exact name match, prefer Function/Method
        let mut candidates: Vec<&Node> = all
            .iter()
            .filter(|n| n.name == name)
            .collect();
        if candidates.is_empty() {
            let lower = name.to_lowercase();
            candidates = all
                .iter()
                .filter(|n| n.name.to_lowercase().contains(&lower))
                .collect();
        }
        candidates.sort_by_key(|n| match n.label {
            NodeLabel::Function => 0,
            NodeLabel::Method => 1,
            NodeLabel::Class => 2,
            _ => 3,
        });
        match candidates.first() {
            Some(n) => n.qualified_name.clone(),
            None => return Ok(vec![]),
        }
    };

    let mut steps = trace_fan(store, &start_qn, direction, max_depth)?;

    if include_body {
        for step in &mut steps {
            if let Some(ref fp) = step.node.file_path {
                let full_path = std::path::Path::new(repo_path).join(fp);
                if let Ok(content) = std::fs::read_to_string(&full_path) {
                    let lines: Vec<&str> = content.lines().collect();
                    let start = step.node.line_start.saturating_sub(1) as usize;
                    let end = (step.node.line_end as usize).min(lines.len());
                    if start < end {
                        step.body = Some(lines[start..end].join("\n"));
                    }
                }
            }
        }
    }

    Ok(steps)
}

pub fn get_snippet(
    store: &Store,
    qn: &str,
    repo_path: &str,
    context_lines: u32,
) -> Result<Option<CodeSnippet>> {
    let node = match store.get_node(qn)? {
        Some(n) => n,
        None => return Ok(None),
    };
    let rel_path = match &node.file_path {
        Some(fp) => fp.clone(),
        None => return Ok(None),
    };
    let full_path = std::path::Path::new(repo_path).join(&rel_path);
    let content = std::fs::read_to_string(&full_path)
        .map_err(TokkitError::Io)?;
    let lines: Vec<&str> = content.lines().collect();
    let total = lines.len() as u32;

    let start = node.line_start.saturating_sub(1).saturating_sub(context_lines);
    let end = (node.line_end + context_lines).min(total);

    let snippet_lines = &lines[start as usize..end as usize];
    let snippet_content = snippet_lines.join("\n");

    let ext = full_path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_string();

    Ok(Some(CodeSnippet {
        qualified_name: qn.to_string(),
        file_path: rel_path,
        line_start: start + 1,
        line_end: end,
        content: snippet_content,
        language: ext,
    }))
}

pub fn detect_changes(
    store: &Store,
    project: &str,
    _repo_path: &str,
    files: &[FileInfo],
) -> Result<Vec<ChangedFile>> {
    let mut changed = Vec::new();
    let mut seen_paths: HashSet<String> = HashSet::new();

    for fi in files {
        seen_paths.insert(fi.rel_path.clone());
        let meta = std::fs::metadata(&fi.path).ok();
        let (mtime, size) = match meta {
            Some(m) => {
                let mt = m
                    .modified()
                    .ok()
                    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                    .map(|d| d.as_secs() as i64)
                    .unwrap_or(0);
                (mt, m.len() as i64)
            }
            None => {
                changed.push(ChangedFile {
                    path: fi.rel_path.clone(),
                    change_type: "deleted".to_string(),
                });
                continue;
            }
        };

        match store.get_file_hash(project, &fi.rel_path)? {
            None => changed.push(ChangedFile {
                path: fi.rel_path.clone(),
                change_type: "added".to_string(),
            }),
            Some((stored_mtime, stored_size)) => {
                if mtime != stored_mtime || size != stored_size {
                    changed.push(ChangedFile {
                        path: fi.rel_path.clone(),
                        change_type: "modified".to_string(),
                    });
                }
            }
        }
    }

    Ok(changed)
}

pub fn index_status(store: &Store) -> Result<StatusResult> {
    let node_count = store.node_count()?;
    let edge_count = store.edge_count()?;
    Ok(StatusResult {
        indexed: node_count > 0,
        project_name: None,
        node_count,
        edge_count,
    })
}

pub fn get_graph_schema(store: &Store) -> Result<SchemaResult> {
    let nodes = store.all_nodes()?;
    let edges = store.all_edges()?;

    let node_count = nodes.len();
    let edge_count = edges.len();

    let mut labels: HashSet<String> = HashSet::new();
    for n in &nodes {
        labels.insert(n.label.as_str().to_string());
    }

    let mut edge_types: HashSet<String> = HashSet::new();
    for e in &edges {
        edge_types.insert(e.edge_type.as_str().to_string());
    }

    let mut node_labels: Vec<String> = labels.into_iter().collect();
    node_labels.sort();
    let mut edge_type_vec: Vec<String> = edge_types.into_iter().collect();
    edge_type_vec.sort();

    Ok(SchemaResult {
        node_labels,
        edge_types: edge_type_vec,
        node_count,
        edge_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graph::GraphBuffer;
    use crate::store::Store;
    use crate::{Edge, EdgeType, Node, NodeLabel, SearchFilters, IMPORT_MAP};
    use std::collections::HashMap;

    fn make_test_store() -> Store {
        let store = Store::open_memory().expect("open_memory");
        let mut buf = GraphBuffer::new("proj", "/root");

        let auth_id = buf.add_node(
            NodeLabel::Function,
            "authenticate",
            "proj::authenticate",
            Some("src/auth.py".to_string()),
            10,
            30,
        );
        let get_user_id = buf.add_node(
            NodeLabel::Function,
            "get_user",
            "proj::get_user",
            Some("src/users.py".to_string()),
            1,
            15,
        );
        let _svc_id = buf.add_node(
            NodeLabel::Class,
            "UserService",
            "proj::UserService",
            Some("src/service.py".to_string()),
            1,
            50,
        );

        buf.add_edge(Edge {
            source_id: auth_id,
            target_id: get_user_id,
            edge_type: EdgeType::Calls,
            confidence: Some(IMPORT_MAP),
            properties: HashMap::new(),
        });

        store.write_graph(&buf).unwrap();
        store
    }

    #[test]
    fn search_by_name() {
        let store = make_test_store();
        let filters = SearchFilters {
            query: Some("auth".to_string()),
            label: None,
            file_path: None,
            limit: None,
            name_pattern: None,
            max_degree: None,
            exclude_entry_points: None,
            relationship: None,
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert!(!results.is_empty());
        assert!(results.iter().any(|n| n.name == "authenticate"));
    }

    #[test]
    fn search_by_label() {
        let store = make_test_store();
        let filters = SearchFilters {
            query: None,
            label: Some(NodeLabel::Class),
            file_path: None,
            limit: None,
            name_pattern: None,
            max_degree: None,
            exclude_entry_points: None,
            relationship: None,
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "UserService");
    }

    #[test]
    fn search_by_name_pattern() {
        let store = make_test_store();
        let filters = SearchFilters {
            query: None, label: None, file_path: None, limit: None,
            name_pattern: Some("auth.*".to_string()),
            max_degree: None, exclude_entry_points: None, relationship: None,
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "authenticate");
    }

    #[test]
    fn search_name_pattern_no_match() {
        let store = make_test_store();
        let filters = SearchFilters {
            query: None, label: None, file_path: None, limit: None,
            name_pattern: Some("^zzz.*".to_string()),
            max_degree: None, exclude_entry_points: None, relationship: None,
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert!(results.is_empty());
    }

    #[test]
    fn search_max_degree_zero_finds_isolated() {
        let store = make_test_store();
        let filters = SearchFilters {
            query: None, label: None, file_path: None, limit: None,
            name_pattern: None, max_degree: Some(0),
            exclude_entry_points: None, relationship: None,
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "UserService");
    }

    #[test]
    fn search_exclude_entry_points() {
        let store = Store::open_memory().expect("open_memory");
        let mut buf = GraphBuffer::new("proj", "/root");
        buf.add_node(NodeLabel::Function, "main", "proj::main", Some("main.py".to_string()), 1, 5);
        buf.add_node(NodeLabel::Function, "test_foo", "proj::test_foo", Some("test.py".to_string()), 1, 5);
        buf.add_node(NodeLabel::Function, "helper", "proj::helper", Some("lib.py".to_string()), 1, 5);
        store.write_graph(&buf).unwrap();
        let filters = SearchFilters {
            query: None, label: None, file_path: None, limit: None,
            name_pattern: None, max_degree: None,
            exclude_entry_points: Some(true), relationship: None,
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "helper");
    }

    #[test]
    fn search_by_relationship() {
        let store = make_test_store();
        let filters = SearchFilters {
            query: None, label: None, file_path: None, limit: None,
            name_pattern: None, max_degree: None,
            exclude_entry_points: None, relationship: Some("CALLS".to_string()),
        };
        let results = search_nodes(&store, &filters).unwrap();
        assert_eq!(results.len(), 2);
        let names: Vec<&str> = results.iter().map(|n| n.name.as_str()).collect();
        assert!(names.contains(&"authenticate"));
        assert!(names.contains(&"get_user"));
    }

    #[test]
    fn get_callers_works() {
        let store = make_test_store();
        let callers = get_callers(&store, "proj::get_user").unwrap();
        assert_eq!(callers.len(), 1);
        assert_eq!(callers[0].0.name, "authenticate");
    }

    #[test]
    fn get_callees_works() {
        let store = make_test_store();
        let callees = get_callees(&store, "proj::authenticate").unwrap();
        assert_eq!(callees.len(), 1);
        assert_eq!(callees[0].0.name, "get_user");
    }

    #[test]
    fn trace_path_finds_direct_connection() {
        let store = make_test_store();
        let path = trace_path(&store, "proj::authenticate", "proj::get_user", 5).unwrap();
        assert_eq!(path.len(), 2);
        assert_eq!(path[0].node.name, "authenticate");
        assert_eq!(path[1].node.name, "get_user");
    }

    #[test]
    fn trace_path_returns_empty_for_no_connection() {
        let store = make_test_store();
        let path = trace_path(&store, "proj::get_user", "proj::authenticate", 5).unwrap();
        assert!(path.is_empty());
    }

    #[test]
    fn schema_returns_used_labels_and_types() {
        let store = make_test_store();
        let schema = get_graph_schema(&store).unwrap();
        assert!(schema.node_labels.contains(&"Function".to_string()));
        assert!(schema.node_labels.contains(&"Class".to_string()));
        assert!(schema.edge_types.contains(&"CALLS".to_string()));
        assert_eq!(schema.node_count, 3);
        assert_eq!(schema.edge_count, 1);
    }

    #[test]
    fn trace_fan_outbound() {
        let store = make_test_store();
        let path = trace_fan(&store, "proj::authenticate", "outbound", 3).unwrap();
        assert_eq!(path.len(), 2);
        assert_eq!(path[0].node.name, "authenticate");
        assert_eq!(path[0].depth, 0);
        assert_eq!(path[1].node.name, "get_user");
        assert_eq!(path[1].depth, 1);
    }

    #[test]
    fn trace_fan_inbound() {
        let store = make_test_store();
        let path = trace_fan(&store, "proj::get_user", "inbound", 3).unwrap();
        assert_eq!(path.len(), 2);
        assert_eq!(path[0].node.name, "get_user");
        assert_eq!(path[1].node.name, "authenticate");
    }

    #[test]
    fn trace_fan_depth_zero() {
        let store = make_test_store();
        let path = trace_fan(&store, "proj::authenticate", "outbound", 0).unwrap();
        assert_eq!(path.len(), 1);
        assert_eq!(path[0].node.name, "authenticate");
    }
// rev-9
// rev-15
}
