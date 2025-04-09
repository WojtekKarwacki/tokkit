use std::sync::atomic::{AtomicU64, Ordering};
use std::collections::HashMap as StdHashMap;
use hashbrown::{HashMap, HashSet};
use crate::{Node, NodeLabel, Edge, EdgeType};

pub mod merge;

pub struct GraphBuffer {
    project: String,
    root_path: String,
    next_id: AtomicU64,
    nodes: Vec<Node>,
    node_by_qn: HashMap<String, usize>,
    node_by_id: HashMap<u64, usize>,
    edges: Vec<Edge>,
    edge_dedup: HashSet<(u64, u64, EdgeType)>,
}

impl GraphBuffer {
    pub fn new(project: &str, root_path: &str) -> Self {
        Self::with_shared_ids(project, root_path, 1)
    }

    pub fn with_shared_ids(project: &str, root_path: &str, start_id: u64) -> Self {
        Self {
            project: project.to_string(),
            root_path: root_path.to_string(),
            next_id: AtomicU64::new(start_id),
            nodes: Vec::new(),
            node_by_qn: HashMap::new(),
            node_by_id: HashMap::new(),
            edges: Vec::new(),
            edge_dedup: HashSet::new(),
        }
    }

    pub fn upsert_node(&mut self, mut node: Node) -> u64 {
        if let Some(&idx) = self.node_by_qn.get(&node.qualified_name) {
            let existing = &mut self.nodes[idx];
            let id = existing.id;
            existing.label = node.label;
            existing.name = node.name;
            existing.file_path = node.file_path;
            existing.line_start = node.line_start;
            existing.line_end = node.line_end;
            existing.properties.extend(node.properties);
            return id;
        }

        let id = if node.id != 0 {
            node.id
        } else {
            self.next_id.fetch_add(1, Ordering::Relaxed)
        };
        node.id = id;

        let idx = self.nodes.len();
        self.node_by_qn.insert(node.qualified_name.clone(), idx);
        self.node_by_id.insert(id, idx);
        self.nodes.push(node);
        id
    }

    pub fn add_node(
        &mut self,
        label: NodeLabel,
        name: &str,
        qualified_name: &str,
        file_path: Option<String>,
        line_start: u32,
        line_end: u32,
    ) -> u64 {
        let node = Node {
            id: 0,
            label,
            name: name.to_string(),
            qualified_name: qualified_name.to_string(),
            file_path,
            line_start,
            line_end,
            properties: StdHashMap::new(),
        };
        self.upsert_node(node)
    }

    pub fn add_edge(&mut self, edge: Edge) -> bool {
        let key = (edge.source_id, edge.target_id, edge.edge_type);
        if self.edge_dedup.contains(&key) {
            if let Some(existing) = self.edges.iter_mut().find(|e| {
                e.source_id == edge.source_id
                    && e.target_id == edge.target_id
                    && e.edge_type == edge.edge_type
            }) {
                match (existing.confidence, edge.confidence) {
                    (Some(ec), Some(nc)) if nc.value() > ec.value() => {
                        existing.confidence = Some(nc);
                    }
                    (None, Some(_)) => {
                        existing.confidence = edge.confidence;
                    }
                    _ => {}
                }
                existing.properties.extend(edge.properties);
            }
            return false;
        }
        self.edge_dedup.insert(key);
        self.edges.push(edge);
        true
    }

    pub fn find_by_qn(&self, qn: &str) -> Option<&Node> {
        self.node_by_qn.get(qn).map(|&idx| &self.nodes[idx])
    }

    pub fn find_by_id(&self, id: u64) -> Option<&Node> {
        self.node_by_id.get(&id).map(|&idx| &self.nodes[idx])
    }

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

    pub fn nodes(&self) -> &[Node] {
        &self.nodes
    }

    pub fn edges(&self) -> &[Edge] {
        &self.edges
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    pub fn next_id_value(&self) -> u64 {
        self.next_id.load(Ordering::Relaxed)
    }

    pub fn project(&self) -> &str {
        &self.project
    }

    pub fn root_path(&self) -> &str {
        &self.root_path
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Confidence;

    fn make_edge(src: u64, tgt: u64, et: EdgeType, conf: Option<f64>) -> Edge {
        Edge {
            source_id: src,
            target_id: tgt,
            edge_type: et,
            confidence: conf.map(Confidence::new),
            properties: StdHashMap::new(),
        }
    }

    #[test]
    fn add_node_assigns_unique_ids() {
        let mut g = GraphBuffer::new("proj", "/root");
        let a = g.add_node(NodeLabel::Function, "foo", "proj::foo", None, 1, 5);
        let b = g.add_node(NodeLabel::Function, "bar", "proj::bar", None, 6, 10);
        assert_ne!(a, b);
        assert_eq!(g.node_count(), 2);
    }

    #[test]
    fn upsert_deduplicates_by_qn() {
        let mut g = GraphBuffer::new("proj", "/root");
        let id1 = g.add_node(NodeLabel::Function, "foo", "proj::foo", None, 1, 5);
        let id2 = g.add_node(NodeLabel::Function, "foo_updated", "proj::foo", None, 1, 10);
        assert_eq!(id1, id2);
        assert_eq!(g.node_count(), 1);
        assert_eq!(g.find_by_id(id1).unwrap().name, "foo_updated");
        assert_eq!(g.find_by_id(id1).unwrap().line_end, 10);
    }

    #[test]
    fn edge_dedup_on_triple() {
        let mut g = GraphBuffer::new("proj", "/root");
        let a = g.add_node(NodeLabel::Function, "foo", "proj::foo", None, 1, 5);
        let b = g.add_node(NodeLabel::Function, "bar", "proj::bar", None, 6, 10);

        let e1 = make_edge(a, b, EdgeType::Calls, Some(0.5));
        let e2 = make_edge(a, b, EdgeType::Calls, Some(0.9));

        assert!(g.add_edge(e1));
        assert!(!g.add_edge(e2));
        assert_eq!(g.edge_count(), 1);
        assert_eq!(g.edges()[0].confidence.unwrap().value(), 0.9);
    }

    #[test]
    fn find_by_qn_and_id() {
        let mut g = GraphBuffer::new("proj", "/root");
        let id = g.add_node(NodeLabel::Class, "MyClass", "proj::MyClass", None, 1, 20);
        assert!(g.find_by_qn("proj::MyClass").is_some());
        assert!(g.find_by_id(id).is_some());
        assert!(g.find_by_qn("proj::Missing").is_none());
        assert!(g.find_by_id(9999).is_none());
    }

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
}
