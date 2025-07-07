use std::collections::HashMap;
use crate::graph::GraphBuffer;
use crate::types::{NodeLabel, EdgeType, Edge};

pub fn compute_similarity(buf: &mut GraphBuffer) {
    let func_nodes: Vec<(u64, String, Option<String>)> = buf
        .nodes()
        .iter()
        .filter(|n| n.label == NodeLabel::Function || n.label == NodeLabel::Method)
        .map(|n| (n.id, n.name.clone(), n.file_path.clone()))
        .collect();

    // Normalize names by stripping common test prefixes/suffixes
    let normalized: Vec<(u64, String, Option<String>)> = func_nodes
        .iter()
        .map(|(id, name, path)| {
            let norm = normalize_name(name);
            (*id, norm, path.clone())
        })
        .collect();

    // Group by normalized name
    let mut groups: HashMap<String, Vec<(u64, Option<String>)>> = HashMap::new();
    for (id, norm_name, path) in &normalized {
        groups
            .entry(norm_name.clone())
            .or_default()
            .push((*id, path.clone()));
    }

    let mut edges_to_add: Vec<(u64, u64)> = Vec::new();

    for members in groups.values() {
        if members.len() < 2 {
            continue;
        }

        // Create SIMILAR_TO edges between functions with the same normalized name
        // in different files
        for i in 0..members.len() {
            for j in (i + 1)..members.len() {
                let (id_a, path_a) = &members[i];
                let (id_b, path_b) = &members[j];

                // Only link if in different files
                if path_a != path_b {
                    edges_to_add.push((*id_a, *id_b));
                }
            }
        }
    }

    for (a, b) in edges_to_add {
        buf.add_edge(Edge {
            source_id: a,
            target_id: b,
            edge_type: EdgeType::SimilarTo,
            confidence: None,
            properties: HashMap::new(),
        });
    }
}

fn normalize_name(name: &str) -> String {
    let name = name.strip_prefix("test_").unwrap_or(name);
    let name = name.strip_suffix("_test").unwrap_or(name);
    name.to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_similar_functions() {
        let mut buf = GraphBuffer::new("proj", "/root");

        let id_a = buf.add_node(
            NodeLabel::Function,
            "process_data",
            "file_a.py::process_data",
            Some("file_a.py".to_string()),
            1,
            10,
        );
        let id_b = buf.add_node(
            NodeLabel::Function,
            "process_data",
            "file_b.py::process_data",
            Some("file_b.py".to_string()),
            1,
            10,
        );

        compute_similarity(&mut buf);

        let has_edge = buf.edges().iter().any(|e| {
            ((e.source_id == id_a && e.target_id == id_b)
                || (e.source_id == id_b && e.target_id == id_a))
                && e.edge_type == EdgeType::SimilarTo
        });
        assert!(has_edge, "Expected SIMILAR_TO edge between process_data in file_a and file_b");
    }
// rev-14
}
