use redb::TableDefinition;

pub const NODES: TableDefinition<&str, &[u8]> = TableDefinition::new("nodes");
pub const NODE_BY_ID: TableDefinition<&str, &str> = TableDefinition::new("node_by_id");
pub const NODES_BY_LABEL: TableDefinition<&str, &str> = TableDefinition::new("nodes_by_label");
pub const NODES_BY_FILE: TableDefinition<&str, &[u8]> = TableDefinition::new("nodes_by_file");
pub const EDGES: TableDefinition<&str, &[u8]> = TableDefinition::new("edges");
pub const EDGES_BY_SOURCE: TableDefinition<&str, &[u8]> = TableDefinition::new("edges_by_source");
pub const EDGES_BY_TARGET: TableDefinition<&str, &[u8]> = TableDefinition::new("edges_by_target");
pub const FILE_HASHES: TableDefinition<&str, &[u8]> = TableDefinition::new("file_hashes");
pub const PROJECTS: TableDefinition<&str, &[u8]> = TableDefinition::new("projects");
