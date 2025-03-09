use std::collections::HashMap;
use serde::{Deserialize, Serialize};

// --- Language ---

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Language {
    Python,
    JavaScript,
    TypeScript,
    Tsx,
}

// --- NodeLabel ---

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum NodeLabel {
    Project,
    Folder,
    File,
    Function,
    Method,
    Class,
    Interface,
    Struct,
    Enum,
    Variable,
    Route,
    Test,
}

impl NodeLabel {
    pub fn as_str(&self) -> &'static str {
        match self {
            NodeLabel::Project => "Project",
            NodeLabel::Folder => "Folder",
            NodeLabel::File => "File",
            NodeLabel::Function => "Function",
            NodeLabel::Method => "Method",
            NodeLabel::Class => "Class",
            NodeLabel::Interface => "Interface",
            NodeLabel::Struct => "Struct",
            NodeLabel::Enum => "Enum",
            NodeLabel::Variable => "Variable",
            NodeLabel::Route => "Route",
            NodeLabel::Test => "Test",
        }
    }
}

// --- EdgeType ---

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EdgeType {
    ContainsFile,
    ContainsFolder,
    Calls,
    CalledBy,
    Uses,
    UsedBy,
    Imports,
    TypeRef,
    Tests,
    TestsFile,
    CoChanged,
    SimilarTo,
    Handles,
    Configures,
    DataFlows,
}

impl EdgeType {
    pub fn as_str(&self) -> &'static str {
        match self {
            EdgeType::ContainsFile => "CONTAINS_FILE",
            EdgeType::ContainsFolder => "CONTAINS_FOLDER",
            EdgeType::Calls => "CALLS",
            EdgeType::CalledBy => "CALLED_BY",
            EdgeType::Uses => "USES",
            EdgeType::UsedBy => "USED_BY",
            EdgeType::Imports => "IMPORTS",
            EdgeType::TypeRef => "TYPE_REF",
            EdgeType::Tests => "TESTS",
            EdgeType::TestsFile => "TESTS_FILE",
            EdgeType::CoChanged => "CO_CHANGED",
            EdgeType::SimilarTo => "SIMILAR_TO",
            EdgeType::Handles => "HANDLES",
            EdgeType::Configures => "CONFIGURES",
            EdgeType::DataFlows => "DATA_FLOWS",
        }
    }
}

// --- IndexMode ---

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndexMode {
    Full,
    Fast,
}

// --- Confidence ---

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Confidence(f64);

impl Confidence {
    pub fn new(value: f64) -> Self {
        Self(value.clamp(0.0, 1.0))
    }

    pub fn value(&self) -> f64 {
        self.0
    }

    pub fn band(&self) -> &'static str {
        if self.0 >= 0.7 {
            "high"
        } else if self.0 >= 0.45 {
            "medium"
        } else if self.0 >= 0.25 {
            "speculative"
        } else {
            "low"
        }
    }
}

pub const IMPORT_MAP: Confidence = Confidence(0.95);
pub const SAME_MODULE: Confidence = Confidence(0.90);
pub const UNIQUE_NAME: Confidence = Confidence(0.75);
pub const SUFFIX_MATCH: Confidence = Confidence(0.55);

// --- Graph entities ---

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    pub id: u64,
    pub label: NodeLabel,
    pub name: String,
    pub qualified_name: String,
    pub file_path: Option<String>,
    pub line_start: u32,
    pub line_end: u32,
    pub properties: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Edge {
    pub source_id: u64,
    pub target_id: u64,
    pub edge_type: EdgeType,
    pub confidence: Option<Confidence>,
    pub properties: HashMap<String, String>,
}

// --- File discovery ---

#[derive(Debug, Clone)]
pub struct FileInfo {
    pub path: String,
    pub rel_path: String,
    pub language: Language,
}

// --- Extraction output ---

#[derive(Debug, Clone)]
pub struct Definition {
    pub name: String,
    pub qualified_name: String,
    pub label: NodeLabel,
    pub line_start: u32,
    pub line_end: u32,
}

#[derive(Debug, Clone)]
pub struct CallRef {
    pub callee_name: String,
    pub line: u32,
    pub enclosing_qn: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ImportRef {
    pub module_path: String,
    pub alias: Option<String>,
    pub names: Vec<String>,
    pub line: u32,
}

#[derive(Debug, Clone)]
pub struct UsageRef {
    pub name: String,
    pub line: u32,
    pub enclosing_qn: Option<String>,
}

#[derive(Debug, Clone)]
pub struct TypeReference {
    pub name: String,
    pub line: u32,
    pub enclosing_qn: Option<String>,
}

#[derive(Debug, Clone)]
pub struct RouteHint {
    pub def_qn: String,        // qualified name of decorated function (empty for Express-style)
    pub handler_name: String,  // handler reference name for Express-style (empty for decorators)
    pub route_path: String,    // "/users", "/items/{id}"
    pub route_method: String,  // "GET", "POST", etc.
    pub line: u32,
}

#[derive(Debug, Clone, Default)]
pub struct FileResult {
    pub definitions: Vec<Definition>,
    pub calls: Vec<CallRef>,
    pub imports: Vec<ImportRef>,
    pub usages: Vec<UsageRef>,
    pub type_refs: Vec<TypeReference>,
    pub route_hints: Vec<RouteHint>,
}

// --- Query results ---

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexResult {
    pub project_name: String,
    pub node_count: usize,
    pub edge_count: usize,
    pub elapsed_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PathStep {
    pub node: Node,
    pub edge: Option<Edge>,
    pub depth: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub body: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeSnippet {
    pub qualified_name: String,
    pub file_path: String,
    pub line_start: u32,
    pub line_end: u32,
    pub content: String,
    pub language: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeMatch {
    pub file_path: String,
    pub line: u32,
    pub content: String,
    pub enclosing_function: Option<String>,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangedFile {
    pub path: String,
    pub change_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectInfo {
    pub name: String,
    pub db_path: String,
    pub node_count: usize,
    pub edge_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatusResult {
    pub indexed: bool,
    pub project_name: Option<String>,
    pub node_count: usize,
    pub edge_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArchSummary {
    pub project_name: String,
    pub languages: Vec<String>,
    pub top_files: Vec<String>,
    pub entry_points: Vec<String>,
    pub packages: Vec<String>,
    pub summary: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchFilters {
    pub query: Option<String>,
    pub label: Option<NodeLabel>,
    pub file_path: Option<String>,
    pub limit: Option<u32>,
    pub name_pattern: Option<String>,
    pub max_degree: Option<u32>,
    pub exclude_entry_points: Option<bool>,
    pub relationship: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaResult {
    pub node_labels: Vec<String>,
    pub edge_types: Vec<String>,
    pub node_count: usize,
    pub edge_count: usize,
}

// --- Tests ---

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn confidence_clamps_to_valid_range() {
        assert_eq!(Confidence::new(1.5).value(), 1.0);
        assert_eq!(Confidence::new(-0.5).value(), 0.0);
        assert_eq!(Confidence::new(0.75).value(), 0.75);
    }

    #[test]
    fn confidence_bands_are_correct() {
        assert_eq!(IMPORT_MAP.band(), "high");
        assert_eq!(SUFFIX_MATCH.band(), "medium");
        assert_eq!(Confidence::new(0.2).band(), "low");
    }

    #[test]
    fn node_label_roundtrip() {
        let label = NodeLabel::Function;
        let json = serde_json::to_string(&label).unwrap();
        let back: NodeLabel = serde_json::from_str(&json).unwrap();
        assert_eq!(label, back);
    }

    #[test]
    fn edge_type_roundtrip() {
        let et = EdgeType::ContainsFile;
        let json = serde_json::to_string(&et).unwrap();
        let back: EdgeType = serde_json::from_str(&json).unwrap();
        assert_eq!(et, back);
    }

    #[test]
    fn route_hint_default_in_file_result() {
        let fr = FileResult::default();
        assert!(fr.route_hints.is_empty());
    }
}
