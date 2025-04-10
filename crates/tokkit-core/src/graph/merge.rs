use hashbrown::HashMap;
use super::GraphBuffer;

pub fn merge_into(main: &mut GraphBuffer, worker: GraphBuffer) {
    let mut id_remap: HashMap<u64, u64> = HashMap::new();

    for node in worker.nodes {
        let old_id = node.id;
        let new_id = main.upsert_node(node);
        id_remap.insert(old_id, new_id);
    }

    for mut edge in worker.edges {
        if let Some(&new_src) = id_remap.get(&edge.source_id) {
            edge.source_id = new_src;
        }
        if let Some(&new_tgt) = id_remap.get(&edge.target_id) {
            edge.target_id = new_tgt;
        }
        main.add_edge(edge);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{NodeLabel, EdgeType, Confidence, Edge};

    #[test]
    fn merge_remaps_ids_correctly() {
        let mut main = GraphBuffer::new("proj", "/root");
        let proj_id = main.add_node(NodeLabel::Project, "proj", "proj", None, 0, 0);

        let mut worker = GraphBuffer::with_shared_ids("proj", "/root", 100);
        let fn_a = worker.add_node(NodeLabel::Function, "foo", "proj::foo", None, 1, 5);
        let fn_b = worker.add_node(NodeLabel::Function, "bar", "proj::bar", None, 6, 10);

        let edge = Edge {
            source_id: fn_a,
            target_id: fn_b,
            edge_type: EdgeType::Calls,
            confidence: Some(Confidence::new(0.8)),
            properties: std::collections::HashMap::new(),
        };
        worker.add_edge(edge);

        merge_into(&mut main, worker);

        assert_eq!(main.node_count(), 3);
        assert_eq!(main.edge_count(), 1);

        let _ = proj_id;

        let foo_node = main.find_by_qn("proj::foo").expect("foo must exist");
        let bar_node = main.find_by_qn("proj::bar").expect("bar must exist");
        let foo_id = foo_node.id;
        let bar_id = bar_node.id;

        let e = &main.edges()[0];
        assert_eq!(e.source_id, foo_id);
        assert_eq!(e.target_id, bar_id);
        assert!(main.find_by_id(e.source_id).is_some());
        assert!(main.find_by_id(e.target_id).is_some());
    }
}
