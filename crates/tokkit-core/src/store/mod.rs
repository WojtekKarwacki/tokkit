pub mod tables;

use redb::{Database, ReadableTable, ReadableTableMetadata};
use std::collections::HashMap;

use crate::graph::GraphBuffer;
use crate::{Edge, Node, Result, TokkitError};
use tables::*;

pub struct Store {
    db: Database,
    path: String,
}

impl Store {
    pub fn open(path: &str) -> Result<Self> {
        let db = Database::create(path)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let store = Self { db, path: path.to_string() };
        store.init_tables()?;
        Ok(store)
    }

    #[cfg(test)]
    pub fn open_memory() -> Result<Self> {
        let tmp = tempfile::NamedTempFile::new()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let path = tmp.path().to_string_lossy().to_string();
        let db = Database::create(tmp.path())
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        std::mem::forget(tmp);
        let store = Self { db, path };
        store.init_tables()?;
        Ok(store)
    }

    pub fn path(&self) -> &str {
        &self.path
    }

    pub fn init_tables(&self) -> Result<()> {
        let tx = self.db.begin_write()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        {
            tx.open_table(NODES).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(NODE_BY_ID).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(NODES_BY_LABEL).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(NODES_BY_FILE).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(EDGES).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(EDGES_BY_SOURCE).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(EDGES_BY_TARGET).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(FILE_HASHES).map_err(|e| TokkitError::Store(e.to_string()))?;
            tx.open_table(PROJECTS).map_err(|e| TokkitError::Store(e.to_string()))?;
        }
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }

    pub fn write_graph(&self, buf: &GraphBuffer) -> Result<()> {
        let tx = self.db.begin_write()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        {
            let mut nodes_table = tx.open_table(NODES)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut node_by_id_table = tx.open_table(NODE_BY_ID)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut nodes_by_label_table = tx.open_table(NODES_BY_LABEL)
                .map_err(|e| TokkitError::Store(e.to_string()))?;

            // Build nodes_by_file map
            let mut file_index: HashMap<String, Vec<String>> = HashMap::new();

            for node in buf.nodes() {
                let qn = &node.qualified_name;
                let bytes = bincode::serialize(node)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                nodes_table
                    .insert(qn.as_str(), bytes.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                let id_key = node.id.to_string();
                node_by_id_table
                    .insert(id_key.as_str(), qn.as_str())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                let label_key = format!("{}::{}", node.label.as_str(), &node.name);
                nodes_by_label_table
                    .insert(label_key.as_str(), qn.as_str())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                if let Some(fp) = &node.file_path {
                    file_index
                        .entry(fp.clone())
                        .or_default()
                        .push(qn.clone());
                }
            }

            let mut nodes_by_file_table = tx.open_table(NODES_BY_FILE)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (fp, qns) in &file_index {
                let bytes = bincode::serialize(qns)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                nodes_by_file_table
                    .insert(fp.as_str(), bytes.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }

            let mut edges_table = tx.open_table(EDGES)
                .map_err(|e| TokkitError::Store(e.to_string()))?;

            // Build edge index maps
            let mut by_source: HashMap<String, Vec<String>> = HashMap::new();
            let mut by_target: HashMap<String, Vec<String>> = HashMap::new();

            for edge in buf.edges() {
                let edge_key = format!(
                    "{}:{}:{}",
                    edge.source_id,
                    edge.target_id,
                    edge.edge_type.as_str()
                );
                let bytes = bincode::serialize(edge)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                edges_table
                    .insert(edge_key.as_str(), bytes.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                by_source
                    .entry(edge.source_id.to_string())
                    .or_default()
                    .push(edge_key.clone());
                by_target
                    .entry(edge.target_id.to_string())
                    .or_default()
                    .push(edge_key);
            }

            let mut edges_by_source_table = tx.open_table(EDGES_BY_SOURCE)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (src_id, keys) in &by_source {
                let bytes = bincode::serialize(keys)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                edges_by_source_table
                    .insert(src_id.as_str(), bytes.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }

            let mut edges_by_target_table = tx.open_table(EDGES_BY_TARGET)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (tgt_id, keys) in &by_target {
                let bytes = bincode::serialize(keys)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                edges_by_target_table
                    .insert(tgt_id.as_str(), bytes.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }
        }
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }

    pub fn get_node(&self, qn: &str) -> Result<Option<Node>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(NODES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        match table.get(qn).map_err(|e| TokkitError::Store(e.to_string()))? {
            Some(v) => {
                let node: Node = bincode::deserialize(v.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                Ok(Some(node))
            }
            None => Ok(None),
        }
    }

    pub fn get_node_by_id(&self, id: u64) -> Result<Option<Node>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let id_table = tx.open_table(NODE_BY_ID)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let id_str = id.to_string();
        let qn = match id_table.get(id_str.as_str())
            .map_err(|e| TokkitError::Store(e.to_string()))?
        {
            Some(v) => v.value().to_string(),
            None => return Ok(None),
        };
        drop(id_table);
        drop(tx);
        self.get_node(&qn)
    }

    pub fn get_edges_from(&self, source_id: u64) -> Result<Vec<Edge>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let by_src = tx.open_table(EDGES_BY_SOURCE)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let src_str = source_id.to_string();
        let keys: Vec<String> = match by_src.get(src_str.as_str())
            .map_err(|e| TokkitError::Store(e.to_string()))?
        {
            Some(v) => bincode::deserialize(v.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?,
            None => return Ok(vec![]),
        };
        drop(by_src);

        let edges_table = tx.open_table(EDGES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let mut result = Vec::new();
        for key in &keys {
            if let Some(v) = edges_table.get(key.as_str())
                .map_err(|e| TokkitError::Store(e.to_string()))?
            {
                let edge: Edge = bincode::deserialize(v.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                result.push(edge);
            }
        }
        Ok(result)
    }

    pub fn get_edges_to(&self, target_id: u64) -> Result<Vec<Edge>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let by_tgt = tx.open_table(EDGES_BY_TARGET)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let tgt_str = target_id.to_string();
        let keys: Vec<String> = match by_tgt.get(tgt_str.as_str())
            .map_err(|e| TokkitError::Store(e.to_string()))?
        {
            Some(v) => bincode::deserialize(v.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?,
            None => return Ok(vec![]),
        };
        drop(by_tgt);

        let edges_table = tx.open_table(EDGES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let mut result = Vec::new();
        for key in &keys {
            if let Some(v) = edges_table.get(key.as_str())
                .map_err(|e| TokkitError::Store(e.to_string()))?
            {
                let edge: Edge = bincode::deserialize(v.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                result.push(edge);
            }
        }
        Ok(result)
    }

    pub fn node_count(&self) -> Result<usize> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(NODES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(table.len().map_err(|e| TokkitError::Store(e.to_string()))? as usize)
    }

    pub fn edge_count(&self) -> Result<usize> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(EDGES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(table.len().map_err(|e| TokkitError::Store(e.to_string()))? as usize)
    }

    pub fn write_file_hashes(
        &self,
        project: &str,
        hashes: &[(String, i64, i64)],
    ) -> Result<()> {
        let tx = self.db.begin_write()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        {
            let mut table = tx.open_table(FILE_HASHES)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (path, mtime, size) in hashes {
                let key = format!("{}::{}", project, path);
                let value: (i64, i64) = (*mtime, *size);
                let bytes = bincode::serialize(&value)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                table
                    .insert(key.as_str(), bytes.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }
        }
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }

    pub fn get_file_hash(&self, project: &str, path: &str) -> Result<Option<(i64, i64)>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(FILE_HASHES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let key = format!("{}::{}", project, path);
        match table.get(key.as_str()).map_err(|e| TokkitError::Store(e.to_string()))? {
            Some(v) => {
                let pair: (i64, i64) = bincode::deserialize(v.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                Ok(Some(pair))
            }
            None => Ok(None),
        }
    }

    pub fn all_nodes(&self) -> Result<Vec<Node>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(NODES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let mut result = Vec::new();
        for entry in table.iter().map_err(|e| TokkitError::Store(e.to_string()))? {
            let (_, v) = entry.map_err(|e| TokkitError::Store(e.to_string()))?;
            let node: Node = bincode::deserialize(v.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            result.push(node);
        }
        Ok(result)
    }

    pub fn all_edges(&self) -> Result<Vec<Edge>> {
        let tx = self.db.begin_read()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(EDGES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let mut result = Vec::new();
        for entry in table.iter().map_err(|e| TokkitError::Store(e.to_string()))? {
            let (_, v) = entry.map_err(|e| TokkitError::Store(e.to_string()))?;
            let edge: Edge = bincode::deserialize(v.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            result.push(edge);
        }
        Ok(result)
    }

    pub fn clear(&self) -> Result<()> {
        let tx = self.db.begin_write()
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        {
            let mut t = tx.open_table(NODES).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(NODE_BY_ID).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(NODES_BY_LABEL).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(NODES_BY_FILE).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(EDGES).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(EDGES_BY_SOURCE).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(EDGES_BY_TARGET).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(FILE_HASHES).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut t = tx.open_table(PROJECTS).map_err(|e| TokkitError::Store(e.to_string()))?;
            t.retain(|_, _| false).map_err(|e| TokkitError::Store(e.to_string()))?;
        }
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Confidence, Edge, EdgeType, Node, NodeLabel, IMPORT_MAP};
    use std::collections::HashMap;

    fn make_store() -> Store {
        Store::open_memory().expect("open_memory failed")
    }

    fn func_node(id: u64, name: &str, qn: &str) -> Node {
        Node {
            id,
            label: NodeLabel::Function,
            name: name.to_string(),
            qualified_name: qn.to_string(),
            file_path: Some("src/auth.py".to_string()),
            line_start: 10,
            line_end: 20,
            properties: HashMap::new(),
        }
    }

    fn make_buf_with_two_nodes() -> GraphBuffer {
        let mut buf = GraphBuffer::new("proj", "/root");
        buf.add_node(NodeLabel::Function, "foo", "proj::foo", Some("src/a.py".to_string()), 1, 5);
        buf.add_node(NodeLabel::Function, "bar", "proj::bar", Some("src/a.py".to_string()), 6, 10);
        buf
    }

    #[test]
    fn roundtrip_node() {
        let store = make_store();
        let buf = make_buf_with_two_nodes();
        store.write_graph(&buf).unwrap();

        let node = store.get_node("proj::foo").unwrap().expect("should exist");
        assert_eq!(node.name, "foo");
        assert_eq!(node.label, NodeLabel::Function);
        assert_eq!(node.line_start, 1);
        assert_eq!(node.line_end, 5);
    }

    #[test]
    fn node_not_found() {
        let store = make_store();
        let buf = make_buf_with_two_nodes();
        store.write_graph(&buf).unwrap();
        assert!(store.get_node("proj::nonexistent").unwrap().is_none());
    }

    #[test]
    fn roundtrip_edges() {
        let store = make_store();
        let mut buf = GraphBuffer::new("proj", "/root");
        let src = buf.add_node(NodeLabel::Function, "caller", "proj::caller", None, 1, 5);
        let tgt = buf.add_node(NodeLabel::Function, "callee", "proj::callee", None, 6, 10);
        buf.add_edge(Edge {
            source_id: src,
            target_id: tgt,
            edge_type: EdgeType::Calls,
            confidence: Some(IMPORT_MAP),
            properties: HashMap::new(),
        });
        store.write_graph(&buf).unwrap();

        let edges = store.get_edges_from(src).unwrap();
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].edge_type, EdgeType::Calls);
        assert!(edges[0].confidence.is_some());
        assert!((edges[0].confidence.unwrap().value() - 0.95).abs() < 1e-9);
    }

    #[test]
    fn reverse_edge_lookup() {
        let store = make_store();
        let mut buf = GraphBuffer::new("proj", "/root");
        let src = buf.add_node(NodeLabel::Function, "caller", "proj::caller", None, 1, 5);
        let tgt = buf.add_node(NodeLabel::Function, "callee", "proj::callee", None, 6, 10);
        buf.add_edge(Edge {
            source_id: src,
            target_id: tgt,
            edge_type: EdgeType::Calls,
            confidence: Some(IMPORT_MAP),
            properties: HashMap::new(),
        });
        store.write_graph(&buf).unwrap();

        let edges = store.get_edges_to(tgt).unwrap();
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].source_id, src);
        assert_eq!(edges[0].target_id, tgt);
    }

    #[test]
    fn counts() {
        let store = make_store();
        let mut buf = GraphBuffer::new("proj", "/root");
        let src = buf.add_node(NodeLabel::Function, "a", "proj::a", None, 1, 5);
        let tgt = buf.add_node(NodeLabel::Function, "b", "proj::b", None, 6, 10);
        buf.add_edge(Edge {
            source_id: src,
            target_id: tgt,
            edge_type: EdgeType::Calls,
            confidence: None,
            properties: HashMap::new(),
        });
        store.write_graph(&buf).unwrap();

        assert_eq!(store.node_count().unwrap(), 2);
        assert_eq!(store.edge_count().unwrap(), 1);
    }

    #[test]
    fn file_hash_roundtrip() {
        let store = make_store();
        let hashes = vec![("src/auth.py".to_string(), 1_700_000_000i64, 4096i64)];
        store.write_file_hashes("myproj", &hashes).unwrap();
        let result = store.get_file_hash("myproj", "src/auth.py").unwrap();
        assert_eq!(result, Some((1_700_000_000, 4096)));
        let missing = store.get_file_hash("myproj", "src/missing.py").unwrap();
        assert!(missing.is_none());
    }
}
