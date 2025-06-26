# Tokkit Rust Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tokkit-core`, a Rust library crate that indexes Python/JS/TS codebases into a queryable knowledge graph stored in redb.

**Architecture:** Idiomatic Rust library with typed enums for graph entities, tree-sitter for parsing, rayon for parallelism, redb for persistence. Clean public API surface for PyO3 consumption.

**Tech Stack:** Rust, tree-sitter, redb, rayon, bumpalo, hashbrown, serde, gix, ignore crate

**Spec:** `docs/superpowers/specs/2026-04-04-tokkit-port-design.md`

---

## File Map

```
tokkit/core/code/
├── Cargo.toml                          # Workspace manifest
├── crates/
│   ├── tokkit-core/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs                  # Public API + re-exports
│   │       ├── types.rs                # NodeLabel, EdgeType, Node, Edge, Confidence, FileInfo
│   │       ├── error.rs                # TokkitError enum, Result alias
│   │       ├── discover/
│   │       │   ├── mod.rs              # discover() entry point
│   │       │   ├── filters.rs          # Skip patterns, suffix filters, filename filters
│   │       │   └── language.rs         # Extension → Language detection
│   │       ├── extract/
│   │       │   ├── mod.rs              # extract_file() entry point
│   │       │   ├── spec.rs             # LanguageSpec trait
│   │       │   ├── python.rs           # PythonSpec implementation
│   │       │   ├── javascript.rs       # JavaScriptSpec implementation
│   │       │   ├── typescript.rs       # TypeScriptSpec implementation
│   │       │   └── walker.rs           # Unified AST walker (generic over LanguageSpec)
│   │       ├── graph/
│   │       │   ├── mod.rs              # GraphBuffer: insert, dedup, merge
│   │       │   └── merge.rs            # Per-worker buffer merge logic
│   │       ├── resolve/
│   │       │   ├── mod.rs              # resolve_references() entry point
│   │       │   ├── registry.rs         # Registry: exact + by_name indexes
│   │       │   └── strategies.rs       # 4 cascade strategies
│   │       ├── store/
│   │       │   ├── mod.rs              # Store: open, close, read/write transactions
│   │       │   └── tables.rs           # redb table definitions
│   │       ├── query/
│   │       │   └── mod.rs              # All typed query functions
│   │       ├── pipeline/
│   │       │   ├── mod.rs              # pipeline_run() orchestrator
│   │       │   └── incremental.rs      # Incremental indexing logic
│   │       └── enrich/
│   │           ├── mod.rs              # run_enrichment_passes()
│   │           ├── tests.rs            # Test file detection
│   │           ├── git_history.rs      # Co-change coupling
│   │           ├── routes.rs           # Route/endpoint detection
│   │           └── similarity.rs       # MinHash + LSH near-clone detection
│   └── tokkit-py/
│       ├── Cargo.toml
│       └── src/lib.rs                  # (Plan 2)
└── tests/
    ├── integration_python.rs
    ├── integration_js.rs
    ├── integration_ts.rs
    ├── integration_incremental.rs
    └── fixtures/
        ├── python_project/             # ~15 Python files
        ├── js_project/                 # ~10 JS files (Express app)
        └── ts_project/                 # ~10 TS files
```

---

## Task 1: Scaffold Workspace and Central Types

**Files:**
- Create: `tokkit/core/code/Cargo.toml`
- Create: `tokkit/core/code/crates/tokkit-core/Cargo.toml`
- Create: `tokkit/core/code/crates/tokkit-core/src/lib.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/types.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/error.rs`
- Create: `tokkit/core/code/crates/tokkit-py/Cargo.toml`
- Create: `tokkit/core/code/crates/tokkit-py/src/lib.rs`

- [ ] **Step 1: Create workspace Cargo.toml**

```toml
# tokkit/core/code/Cargo.toml
[workspace]
resolver = "2"
members = [
    "crates/tokkit-core",
    "crates/tokkit-py",
]

[workspace.package]
version = "0.1.0"
edition = "2024"
license = "MIT"

[workspace.dependencies]
tokkit-core = { path = "crates/tokkit-core" }
```

- [ ] **Step 2: Create tokkit-core Cargo.toml**

```toml
# tokkit/core/code/crates/tokkit-core/Cargo.toml
[package]
name = "tokkit-core"
version.workspace = true
edition.workspace = true

[dependencies]
tree-sitter = "0.25"
tree-sitter-python = "0.23"
tree-sitter-javascript = "0.23"
tree-sitter-typescript = "0.23"
redb = "2"
rayon = "1"
hashbrown = "0.15"
bumpalo = { version = "3", features = ["collections"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
bincode = "1"
ignore = "0.4"
gix = { version = "0.72", default-features = false, features = ["basic", "parallel"] }
grep-regex = "0.1"
grep-searcher = "0.1"
thiserror = "2"

[dev-dependencies]
tempfile = "3"
```

- [ ] **Step 3: Create tokkit-py stub Cargo.toml**

```toml
# tokkit/core/code/crates/tokkit-py/Cargo.toml
[package]
name = "tokkit-py"
version.workspace = true
edition.workspace = true

[lib]
crate-type = ["cdylib"]

[dependencies]
tokkit-core.workspace = true
pyo3 = { version = "0.23", features = ["extension-module"] }
```

- [ ] **Step 4: Write error.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/error.rs
use thiserror::Error;

#[derive(Debug, Error)]
pub enum TokkitError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Store error: {0}")]
    Store(String),

    #[error("Parse error: {0}")]
    Parse(String),

    #[error("Pipeline busy — another index is running")]
    PipelineBusy,

    #[error("Project not found: {0}")]
    NotFound(String),

    #[error("{0}")]
    Other(String),
}

pub type Result<T> = std::result::Result<T, TokkitError>;
```

- [ ] **Step 5: Write types.rs with tests**

```rust
// tokkit/core/code/crates/tokkit-core/src/types.rs
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// --- Language ---

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Language {
    Python,
    JavaScript,
    TypeScript,
    Tsx,
}

// --- Node Labels ---

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
            Self::Project => "Project",
            Self::Folder => "Folder",
            Self::File => "File",
            Self::Function => "Function",
            Self::Method => "Method",
            Self::Class => "Class",
            Self::Interface => "Interface",
            Self::Struct => "Struct",
            Self::Enum => "Enum",
            Self::Variable => "Variable",
            Self::Route => "Route",
            Self::Test => "Test",
        }
    }
}

// --- Edge Types ---

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
            Self::ContainsFile => "CONTAINS_FILE",
            Self::ContainsFolder => "CONTAINS_FOLDER",
            Self::Calls => "CALLS",
            Self::CalledBy => "CALLED_BY",
            Self::Uses => "USES",
            Self::UsedBy => "USED_BY",
            Self::Imports => "IMPORTS",
            Self::TypeRef => "TYPE_REF",
            Self::Tests => "TESTS",
            Self::TestsFile => "TESTS_FILE",
            Self::CoChanged => "CO_CHANGED",
            Self::SimilarTo => "SIMILAR_TO",
            Self::Handles => "HANDLES",
            Self::Configures => "CONFIGURES",
            Self::DataFlows => "DATA_FLOWS",
        }
    }
}

// --- Confidence ---

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Confidence(f64);

impl Confidence {
    pub const IMPORT_MAP: Self = Self(0.95);
    pub const SAME_MODULE: Self = Self(0.90);
    pub const UNIQUE_NAME: Self = Self(0.75);
    pub const SUFFIX_MATCH: Self = Self(0.55);

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

// --- Graph Entities ---

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

// --- File Discovery ---

#[derive(Debug, Clone)]
pub struct FileInfo {
    pub path: String,
    pub rel_path: String,
    pub language: Language,
}

// --- Extraction Output ---

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

#[derive(Debug, Clone, Default)]
pub struct FileResult {
    pub definitions: Vec<Definition>,
    pub calls: Vec<CallRef>,
    pub imports: Vec<ImportRef>,
    pub usages: Vec<UsageRef>,
    pub type_refs: Vec<TypeReference>,
}

// --- Query Results ---

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
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaResult {
    pub node_labels: Vec<String>,
    pub edge_types: Vec<String>,
    pub node_count: usize,
    pub edge_count: usize,
}

// --- Index Mode ---

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndexMode {
    Full,
    Fast,
}

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
        assert_eq!(Confidence::IMPORT_MAP.band(), "high");
        assert_eq!(Confidence::SAME_MODULE.band(), "high");
        assert_eq!(Confidence::UNIQUE_NAME.band(), "high");
        assert_eq!(Confidence::SUFFIX_MATCH.band(), "medium");
        assert_eq!(Confidence::new(0.2).band(), "low");
    }

    #[test]
    fn node_label_roundtrip() {
        let label = NodeLabel::Function;
        assert_eq!(label.as_str(), "Function");
        let json = serde_json::to_string(&label).unwrap();
        let back: NodeLabel = serde_json::from_str(&json).unwrap();
        assert_eq!(back, label);
    }

    #[test]
    fn edge_type_roundtrip() {
        let et = EdgeType::Calls;
        assert_eq!(et.as_str(), "CALLS");
        let json = serde_json::to_string(&et).unwrap();
        let back: EdgeType = serde_json::from_str(&json).unwrap();
        assert_eq!(back, et);
    }
}
```

- [ ] **Step 6: Write lib.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/lib.rs
pub mod types;
pub mod error;

// Modules added as implemented:
// pub mod discover;
// pub mod extract;
// pub mod graph;
// pub mod resolve;
// pub mod store;
// pub mod query;
// pub mod pipeline;
// pub mod enrich;

pub use error::{Result, TokkitError};
pub use types::*;
```

- [ ] **Step 7: Write tokkit-py stub**

```rust
// tokkit/core/code/crates/tokkit-py/src/lib.rs
use pyo3::prelude::*;

#[pymodule]
fn tokkit_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
```

- [ ] **Step 8: Verify workspace compiles and tests pass**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass (types module tests).

- [ ] **Step 9: Commit**

```bash
git add tokkit/core/code/
git commit -m "feat(core): scaffold tokkit workspace with central types"
```

---

## Task 2: Discovery Module

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/discover/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/discover/filters.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/discover/language.rs`
- Modify: `tokkit/core/code/crates/tokkit-core/src/lib.rs` (uncomment discover)

- [ ] **Step 1: Write language.rs with tests**

```rust
// tokkit/core/code/crates/tokkit-core/src/discover/language.rs
use crate::types::Language;
use std::path::Path;

/// Detect language from file extension. Returns None for unsupported files.
pub fn detect_language(path: &Path) -> Option<Language> {
    let ext = path.extension()?.to_str()?;
    match ext {
        "py" => Some(Language::Python),
        "js" | "jsx" | "mjs" | "cjs" => Some(Language::JavaScript),
        "ts" => Some(Language::TypeScript),
        "tsx" => Some(Language::Tsx),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_python() {
        assert_eq!(detect_language(Path::new("foo.py")), Some(Language::Python));
        assert_eq!(detect_language(Path::new("src/bar/baz.py")), Some(Language::Python));
    }

    #[test]
    fn detects_javascript_variants() {
        assert_eq!(detect_language(Path::new("app.js")), Some(Language::JavaScript));
        assert_eq!(detect_language(Path::new("App.jsx")), Some(Language::JavaScript));
        assert_eq!(detect_language(Path::new("index.mjs")), Some(Language::JavaScript));
        assert_eq!(detect_language(Path::new("utils.cjs")), Some(Language::JavaScript));
    }

    #[test]
    fn detects_typescript_variants() {
        assert_eq!(detect_language(Path::new("app.ts")), Some(Language::TypeScript));
        assert_eq!(detect_language(Path::new("App.tsx")), Some(Language::Tsx));
    }

    #[test]
    fn returns_none_for_unsupported() {
        assert_eq!(detect_language(Path::new("main.go")), None);
        assert_eq!(detect_language(Path::new("lib.rs")), None);
        assert_eq!(detect_language(Path::new("photo.png")), None);
        assert_eq!(detect_language(Path::new("noext")), None);
    }
}
```

- [ ] **Step 2: Write filters.rs with tests**

```rust
// tokkit/core/code/crates/tokkit-core/src/discover/filters.rs
use crate::types::IndexMode;
use std::path::Path;

/// Directories always skipped during discovery.
const ALWAYS_SKIP_DIRS: &[&str] = &[
    ".git", ".hg", ".svn", ".worktrees",
    ".idea", ".vs", ".vscode", ".eclipse", ".claude",
    ".cache", ".eggs", ".env", ".mypy_cache", ".nox", ".pytest_cache", ".ruff_cache", ".tox",
    ".venv", "__pycache__", "env", "htmlcov", "site-packages", "venv",
    ".npm", ".nyc_output", ".pnpm-store", ".yarn", "bower_components", "coverage", "node_modules",
    ".next", ".nuxt", ".svelte-kit", ".angular", ".turbo", ".parcel-cache", ".docusaurus", ".expo",
    "dist", "obj", "Pods", "target", "temp", "tmp", ".terraform", ".serverless",
    "bazel-bin", "bazel-out", "bazel-testlogs",
    ".cargo", ".stack-work", ".dart_tool", "zig-cache", "zig-out", ".metals", ".bloop", ".bsp",
    ".ccls-cache", ".clangd", "elm-stuff", "_opam", ".cpcache", ".shadow-cljs",
    ".vercel", ".netlify",
    ".qdrant_code_embeddings", ".tmp", "vendor",
];

/// Additional directories skipped in fast mode.
const FAST_SKIP_DIRS: &[&str] = &[
    "generated", "gen", "auto-generated", "fixtures", "testdata", "test_data",
    "__tests__", "__mocks__", "__snapshots__", "__fixtures__", "__test__", "docs",
    "doc", "documentation", "examples", "example", "samples", "sample",
    "assets", "static", "public", "media", "third_party", "thirdparty",
    "3rdparty", "external", "migrations", "seeds", "e2e", "integration",
    "locale", "locales", "i18n", "l10n", "scripts", "tools",
    "hack", "bin", "build", "out",
];

/// File suffixes always ignored.
const ALWAYS_IGNORED_SUFFIXES: &[&str] = &[
    ".tmp", "~", ".pyc", ".pyo", ".o", ".a", ".so", ".dll",
    ".class", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".tiff",
    ".webp", ".svg", ".wasm", ".node", ".exe", ".bin", ".dat", ".db",
    ".sqlite", ".sqlite3", ".woff", ".woff2", ".ttf", ".eot", ".otf",
];

/// Additional suffixes ignored in fast mode.
const FAST_IGNORED_SUFFIXES: &[&str] = &[
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z", ".jar",
    ".war", ".ear", ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".ogg", ".mkv", ".webm", ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".odt", ".ods", ".map", ".min.js", ".min.css", ".pem",
    ".crt", ".key", ".cer", ".p12", ".pb", ".avro", ".parquet", ".beam",
    ".elc", ".rlib", ".coverage", ".prof", ".out", ".patch", ".diff",
];

/// Filenames skipped in fast mode.
const FAST_SKIP_FILENAMES: &[&str] = &[
    "LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE-MIT", "LICENSE-APACHE",
    "LICENCE", "LICENCE.txt", "LICENCE.md", "CHANGELOG", "CHANGELOG.md",
    "CHANGES.md", "HISTORY", "HISTORY.md", "AUTHORS", "AUTHORS.md",
    "CONTRIBUTORS", "CONTRIBUTORS.md", "CODEOWNERS", "go.sum", "yarn.lock",
    "pnpm-lock.yaml", "Pipfile.lock", "poetry.lock", "Gemfile.lock", "Cargo.lock",
    "mix.lock", "flake.lock", "pubspec.lock", "composer.lock", "package-lock.json",
    "configure", "Makefile.in", "config.guess", "config.sub",
];

/// Substring patterns for fast mode filtering.
const FAST_PATTERNS: &[&str] = &[
    ".d.ts", ".bundle.", ".chunk.", ".generated.",
    ".pb.go", "_pb2.py", ".pb2.py", "_grpc.pb.go",
    "_string.go", "mock_", "_mock.", "_test_helpers.",
    ".stories.", ".spec.", ".test.",
];

/// Check if a directory name should be skipped.
pub fn should_skip_dir(name: &str, mode: IndexMode) -> bool {
    if ALWAYS_SKIP_DIRS.contains(&name) {
        return true;
    }
    if mode == IndexMode::Fast && FAST_SKIP_DIRS.contains(&name) {
        return true;
    }
    false
}

/// Check if a file should be skipped based on suffix, name, and patterns.
pub fn should_skip_file(path: &Path, mode: IndexMode) -> bool {
    let name = match path.file_name().and_then(|n| n.to_str()) {
        Some(n) => n,
        None => return true,
    };

    // Suffix check
    for suffix in ALWAYS_IGNORED_SUFFIXES {
        if name.ends_with(suffix) {
            return true;
        }
    }

    if mode == IndexMode::Fast {
        for suffix in FAST_IGNORED_SUFFIXES {
            if name.ends_with(suffix) {
                return true;
            }
        }

        if FAST_SKIP_FILENAMES.contains(&name) {
            return true;
        }

        for pattern in FAST_PATTERNS {
            if name.contains(pattern) {
                return true;
            }
        }
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn always_skips_git_and_node_modules() {
        assert!(should_skip_dir(".git", IndexMode::Full));
        assert!(should_skip_dir("node_modules", IndexMode::Full));
        assert!(should_skip_dir("__pycache__", IndexMode::Full));
    }

    #[test]
    fn fast_mode_skips_extra_dirs() {
        assert!(!should_skip_dir("docs", IndexMode::Full));
        assert!(should_skip_dir("docs", IndexMode::Fast));
        assert!(!should_skip_dir("examples", IndexMode::Full));
        assert!(should_skip_dir("examples", IndexMode::Fast));
    }

    #[test]
    fn skips_binary_suffixes() {
        assert!(should_skip_file(Path::new("image.png"), IndexMode::Full));
        assert!(should_skip_file(Path::new("lib.wasm"), IndexMode::Full));
    }

    #[test]
    fn fast_mode_skips_extra_files() {
        assert!(!should_skip_file(Path::new("LICENSE"), IndexMode::Full));
        assert!(should_skip_file(Path::new("LICENSE"), IndexMode::Fast));
        assert!(should_skip_file(Path::new("foo.d.ts"), IndexMode::Fast));
        assert!(should_skip_file(Path::new("Button.stories.tsx"), IndexMode::Fast));
    }

    #[test]
    fn does_not_skip_source_files() {
        assert!(!should_skip_file(Path::new("app.py"), IndexMode::Full));
        assert!(!should_skip_file(Path::new("index.ts"), IndexMode::Full));
        assert!(!should_skip_file(Path::new("server.js"), IndexMode::Fast));
    }
}
```

- [ ] **Step 3: Write mod.rs with tests**

```rust
// tokkit/core/code/crates/tokkit-core/src/discover/mod.rs
pub mod filters;
pub mod language;

use crate::error::Result;
use crate::types::{FileInfo, IndexMode};
use ignore::WalkBuilder;
use std::path::Path;

/// Discover all indexable source files in a repository.
///
/// Walks the directory tree, applies skip patterns, detects language,
/// and returns only files with supported languages (Python, JS, TS).
pub fn discover(repo_path: &str, mode: IndexMode) -> Result<Vec<FileInfo>> {
    let root = Path::new(repo_path);
    let mut files = Vec::new();

    let walker = WalkBuilder::new(root)
        .hidden(false) // We handle .git etc. via our own skip list
        .git_ignore(true)
        .git_global(false)
        .git_exclude(false)
        .filter_entry(move |entry| {
            if entry.file_type().is_some_and(|ft| ft.is_dir()) {
                if let Some(name) = entry.file_name().to_str() {
                    return !filters::should_skip_dir(name, mode);
                }
            }
            true
        })
        .build();

    for entry in walker.flatten() {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        if filters::should_skip_file(path, mode) {
            continue;
        }
        let lang = match language::detect_language(path) {
            Some(l) => l,
            None => continue,
        };
        let rel_path = match path.strip_prefix(root) {
            Ok(r) => r.to_string_lossy().to_string(),
            Err(_) => continue,
        };
        files.push(FileInfo {
            path: path.to_string_lossy().to_string(),
            rel_path,
            language: lang,
        });
    }

    files.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
    Ok(files)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn create_test_repo() -> TempDir {
        let dir = TempDir::new().unwrap();
        let root = dir.path();

        // Source files
        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("src/app.py"), "def main(): pass").unwrap();
        fs::write(root.join("src/utils.js"), "function util() {}").unwrap();
        fs::write(root.join("src/types.ts"), "interface Foo {}").unwrap();

        // Should be skipped
        fs::create_dir_all(root.join("node_modules/pkg")).unwrap();
        fs::write(root.join("node_modules/pkg/index.js"), "").unwrap();
        fs::create_dir_all(root.join("__pycache__")).unwrap();
        fs::write(root.join("__pycache__/app.pyc"), "").unwrap();

        // Unsupported language
        fs::write(root.join("src/main.go"), "package main").unwrap();

        // Binary file
        fs::write(root.join("src/image.png"), &[0u8; 10]).unwrap();

        dir
    }

    #[test]
    fn discovers_supported_files_only() {
        let dir = create_test_repo();
        let files = discover(dir.path().to_str().unwrap(), IndexMode::Full).unwrap();

        let rel_paths: Vec<&str> = files.iter().map(|f| f.rel_path.as_str()).collect();
        assert!(rel_paths.contains(&"src/app.py"));
        assert!(rel_paths.contains(&"src/utils.js"));
        assert!(rel_paths.contains(&"src/types.ts"));

        // Skipped
        assert!(!rel_paths.iter().any(|p| p.contains("node_modules")));
        assert!(!rel_paths.iter().any(|p| p.contains("__pycache__")));
        assert!(!rel_paths.iter().any(|p| p.contains("main.go")));
        assert!(!rel_paths.iter().any(|p| p.contains("image.png")));
    }

    #[test]
    fn fast_mode_filters_more() {
        let dir = TempDir::new().unwrap();
        let root = dir.path();

        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("src/app.py"), "").unwrap();

        fs::create_dir_all(root.join("docs")).unwrap();
        fs::write(root.join("docs/guide.py"), "").unwrap();

        let full = discover(root.to_str().unwrap(), IndexMode::Full).unwrap();
        let fast = discover(root.to_str().unwrap(), IndexMode::Fast).unwrap();

        assert_eq!(full.len(), 2); // app.py + guide.py
        assert_eq!(fast.len(), 1); // only app.py
    }

    #[test]
    fn returns_sorted_by_rel_path() {
        let dir = TempDir::new().unwrap();
        let root = dir.path();

        fs::create_dir_all(root.join("b")).unwrap();
        fs::create_dir_all(root.join("a")).unwrap();
        fs::write(root.join("b/z.py"), "").unwrap();
        fs::write(root.join("a/a.py"), "").unwrap();

        let files = discover(root.to_str().unwrap(), IndexMode::Full).unwrap();
        assert_eq!(files[0].rel_path, "a/a.py");
        assert_eq!(files[1].rel_path, "b/z.py");
    }
}
```

- [ ] **Step 4: Uncomment discover in lib.rs**

```rust
// In lib.rs, change to:
pub mod discover;
```

- [ ] **Step 5: Run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass (types + discover modules).

- [ ] **Step 6: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/discover/
git commit -m "feat(core): add discovery module with filters and language detection"
```

---

## Task 3: Extraction Module — Language Specs

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/extract/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/extract/spec.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/extract/python.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/extract/javascript.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/extract/typescript.rs`

- [ ] **Step 1: Write spec.rs — the LanguageSpec trait**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/spec.rs
use crate::types::Language;

/// Defines the tree-sitter node type names for a specific language.
/// Each method returns the node type strings that correspond to that
/// syntactic category in the language's tree-sitter grammar.
pub trait LanguageSpec: Send + Sync {
    fn language_id(&self) -> Language;
    fn ts_language(&self) -> tree_sitter::Language;

    /// Node types for function/method definitions.
    fn function_types(&self) -> &[&str];

    /// Node types for class/interface/enum definitions.
    fn class_types(&self) -> &[&str];

    /// Node types for top-level module.
    fn module_types(&self) -> &[&str];

    /// Node types for function/method calls.
    fn call_types(&self) -> &[&str];

    /// Node types for import statements.
    fn import_types(&self) -> &[&str];

    /// Node types for import-from statements (Python-specific, empty for others).
    fn import_from_types(&self) -> &[&str] {
        &[]
    }

    /// Node types for variable declarations/assignments.
    fn var_types(&self) -> &[&str];

    /// Node types for throw/raise statements.
    fn throw_types(&self) -> &[&str];

    /// Node types for decorators/annotations.
    fn decorator_types(&self) -> &[&str] {
        &[]
    }

    /// Node types for control flow branches.
    fn branch_types(&self) -> &[&str];

    /// Environment variable access patterns: (object, member) pairs.
    /// E.g., Python: ("os", "environ"), JS: ("process", "env")
    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[]
    }
}

/// Get the appropriate LanguageSpec for a given Language.
pub fn spec_for_language(lang: Language) -> &'static dyn LanguageSpec {
    match lang {
        Language::Python => &super::python::PYTHON_SPEC,
        Language::JavaScript => &super::javascript::JAVASCRIPT_SPEC,
        Language::TypeScript | Language::Tsx => &super::typescript::TYPESCRIPT_SPEC,
    }
}
```

- [ ] **Step 2: Write python.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/python.rs
use crate::extract::spec::LanguageSpec;
use crate::types::Language;

pub static PYTHON_SPEC: PythonSpec = PythonSpec;

pub struct PythonSpec;

impl LanguageSpec for PythonSpec {
    fn language_id(&self) -> Language {
        Language::Python
    }

    fn ts_language(&self) -> tree_sitter::Language {
        tree_sitter_python::LANGUAGE.into()
    }

    fn function_types(&self) -> &[&str] {
        &["function_definition"]
    }

    fn class_types(&self) -> &[&str] {
        &["class_definition"]
    }

    fn module_types(&self) -> &[&str] {
        &["module"]
    }

    fn call_types(&self) -> &[&str] {
        &["call"]
    }

    fn import_types(&self) -> &[&str] {
        &["import_statement"]
    }

    fn import_from_types(&self) -> &[&str] {
        &["import_from_statement"]
    }

    fn var_types(&self) -> &[&str] {
        &["assignment", "augmented_assignment"]
    }

    fn throw_types(&self) -> &[&str] {
        &["raise_statement"]
    }

    fn decorator_types(&self) -> &[&str] {
        &["decorator"]
    }

    fn branch_types(&self) -> &[&str] {
        &[
            "if_statement", "for_statement", "while_statement", "try_statement",
            "except_clause", "with_statement", "elif_clause",
        ]
    }

    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[("os", "environ"), ("os", "getenv")]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn python_spec_parses_basic_function() {
        let spec = &PYTHON_SPEC;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();

        let source = "def hello(name):\n    return f'Hello {name}'";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();

        assert_eq!(root.kind(), "module");
        let func = root.child(0).unwrap();
        assert!(spec.function_types().contains(&func.kind()));
    }

    #[test]
    fn python_spec_parses_class() {
        let spec = &PYTHON_SPEC;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();

        let source = "class MyClass:\n    def method(self):\n        pass";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        let class = root.child(0).unwrap();

        assert!(spec.class_types().contains(&class.kind()));
    }
}
```

- [ ] **Step 3: Write javascript.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/javascript.rs
use crate::extract::spec::LanguageSpec;
use crate::types::Language;

pub static JAVASCRIPT_SPEC: JavaScriptSpec = JavaScriptSpec;

pub struct JavaScriptSpec;

impl LanguageSpec for JavaScriptSpec {
    fn language_id(&self) -> Language {
        Language::JavaScript
    }

    fn ts_language(&self) -> tree_sitter::Language {
        tree_sitter_javascript::LANGUAGE.into()
    }

    fn function_types(&self) -> &[&str] {
        &[
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        ]
    }

    fn class_types(&self) -> &[&str] {
        &["class_declaration", "class"]
    }

    fn module_types(&self) -> &[&str] {
        &["program"]
    }

    fn call_types(&self) -> &[&str] {
        &["call_expression"]
    }

    fn import_types(&self) -> &[&str] {
        &["import_statement", "lexical_declaration", "export_statement"]
    }

    fn var_types(&self) -> &[&str] {
        &["lexical_declaration", "variable_declaration"]
    }

    fn throw_types(&self) -> &[&str] {
        &["throw_statement"]
    }

    fn branch_types(&self) -> &[&str] {
        &[
            "if_statement", "for_statement", "for_in_statement",
            "while_statement", "switch_statement", "case_clause",
            "try_statement", "catch_clause",
        ]
    }

    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[("process", "env")]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn js_spec_parses_arrow_function() {
        let spec = &JAVASCRIPT_SPEC;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();

        let source = "const greet = (name) => `Hello ${name}`;";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();

        assert_eq!(root.kind(), "program");
    }

    #[test]
    fn js_spec_parses_class_declaration() {
        let spec = &JAVASCRIPT_SPEC;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();

        let source = "class App { constructor() {} render() {} }";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        let class = root.child(0).unwrap();

        assert!(spec.class_types().contains(&class.kind()));
    }
}
```

- [ ] **Step 4: Write typescript.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/typescript.rs
use crate::extract::spec::LanguageSpec;
use crate::types::Language;

pub static TYPESCRIPT_SPEC: TypeScriptSpec = TypeScriptSpec;

pub struct TypeScriptSpec;

impl LanguageSpec for TypeScriptSpec {
    fn language_id(&self) -> Language {
        Language::TypeScript
    }

    fn ts_language(&self) -> tree_sitter::Language {
        tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
    }

    fn function_types(&self) -> &[&str] {
        &[
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "function_signature",
        ]
    }

    fn class_types(&self) -> &[&str] {
        &[
            "class_declaration",
            "class",
            "abstract_class_declaration",
            "enum_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "internal_module",
        ]
    }

    fn module_types(&self) -> &[&str] {
        &["program"]
    }

    fn call_types(&self) -> &[&str] {
        &["call_expression"]
    }

    fn import_types(&self) -> &[&str] {
        &["import_statement", "lexical_declaration", "export_statement"]
    }

    fn var_types(&self) -> &[&str] {
        &["lexical_declaration", "variable_declaration"]
    }

    fn throw_types(&self) -> &[&str] {
        &["throw_statement"]
    }

    fn decorator_types(&self) -> &[&str] {
        &["decorator"]
    }

    fn branch_types(&self) -> &[&str] {
        &[
            "if_statement", "for_statement", "for_in_statement",
            "while_statement", "switch_statement", "case_clause",
            "try_statement", "catch_clause",
        ]
    }

    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[("process", "env")]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ts_spec_parses_interface() {
        let spec = &TYPESCRIPT_SPEC;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();

        let source = "interface User { name: string; age: number; }";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        let iface = root.child(0).unwrap();

        assert!(spec.class_types().contains(&iface.kind()));
    }

    #[test]
    fn ts_spec_parses_enum() {
        let spec = &TYPESCRIPT_SPEC;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();

        let source = "enum Color { Red, Green, Blue }";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        let en = root.child(0).unwrap();

        assert!(spec.class_types().contains(&en.kind()));
    }
}
```

- [ ] **Step 5: Write extract/mod.rs stub**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/mod.rs
pub mod spec;
pub mod python;
pub mod javascript;
pub mod typescript;
pub mod walker;
```

- [ ] **Step 6: Uncomment extract in lib.rs, run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/extract/
git commit -m "feat(core): add language specs for Python, JavaScript, TypeScript"
```

---

## Task 4: Extraction Module — AST Walker

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/extract/walker.rs`
- Modify: `tokkit/core/code/crates/tokkit-core/src/extract/mod.rs` (add extract_file)

- [ ] **Step 1: Write walker.rs with scope tracking and definition extraction**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/walker.rs
use crate::extract::spec::LanguageSpec;
use crate::types::*;
use tree_sitter::{Node as TsNode, Parser, Tree};

/// Extract all symbols and references from a single source file.
pub fn extract_file(
    source: &str,
    file_rel_path: &str,
    project_name: &str,
    spec: &dyn LanguageSpec,
) -> crate::Result<FileResult> {
    let mut parser = Parser::new();
    parser
        .set_language(&spec.ts_language())
        .map_err(|e| crate::TokkitError::Parse(e.to_string()))?;

    let tree = parser
        .parse(source, None)
        .ok_or_else(|| crate::TokkitError::Parse("tree-sitter parse returned None".into()))?;

    let mut result = FileResult::default();
    let mut scope_stack: Vec<String> = Vec::new();

    walk_tree(
        &tree,
        source.as_bytes(),
        file_rel_path,
        project_name,
        spec,
        &mut result,
        &mut scope_stack,
    );

    Ok(result)
}

/// Build a qualified name from project, file, and optional scope.
fn make_qn(project_name: &str, file_path: &str, name: &str, scope: &[String]) -> String {
    if scope.is_empty() {
        format!("{project_name}::{file_path}::{name}")
    } else {
        let scope_str = scope.join(".");
        format!("{project_name}::{file_path}::{scope_str}.{name}")
    }
}

/// Get the current enclosing function's qualified name.
fn enclosing_qn(scope: &[String]) -> Option<String> {
    if scope.is_empty() {
        None
    } else {
        Some(scope.join("."))
    }
}

/// Recursive tree walk with scope tracking.
fn walk_tree(
    tree: &Tree,
    source: &[u8],
    file_path: &str,
    project_name: &str,
    spec: &dyn LanguageSpec,
    result: &mut FileResult,
    scope: &mut Vec<String>,
) {
    let mut cursor = tree.walk();
    walk_node(&mut cursor, source, file_path, project_name, spec, result, scope);
}

fn walk_node(
    cursor: &mut tree_sitter::TreeCursor,
    source: &[u8],
    file_path: &str,
    project_name: &str,
    spec: &dyn LanguageSpec,
    result: &mut FileResult,
    scope: &mut Vec<String>,
) {
    let node = cursor.node();
    let kind = node.kind();

    // --- Definition extraction ---
    let pushed_scope = if spec.function_types().contains(&kind) {
        if let Some(def) = extract_function_def(&node, source, file_path, project_name, spec, scope) {
            scope.push(def.name.clone());
            result.definitions.push(def);
            true
        } else {
            false
        }
    } else if spec.class_types().contains(&kind) {
        if let Some(def) = extract_class_def(&node, source, file_path, project_name, spec, scope) {
            scope.push(def.name.clone());
            result.definitions.push(def);
            true
        } else {
            false
        }
    } else {
        false
    };

    // --- Call extraction ---
    if spec.call_types().contains(&kind) {
        if let Some(call) = extract_call(&node, source, scope) {
            result.calls.push(call);
        }
    }

    // --- Import extraction ---
    if spec.import_types().contains(&kind) || spec.import_from_types().contains(&kind) {
        if let Some(imp) = extract_import(&node, source, kind, spec) {
            result.imports.push(imp);
        }
    }

    // --- Recurse into children ---
    if cursor.goto_first_child() {
        loop {
            walk_node(cursor, source, file_path, project_name, spec, result, scope);
            if !cursor.goto_next_sibling() {
                break;
            }
        }
        cursor.goto_parent();
    }

    // Pop scope if we pushed
    if pushed_scope {
        scope.pop();
    }
}

/// Extract a function/method definition from a tree-sitter node.
fn extract_function_def(
    node: &TsNode,
    source: &[u8],
    file_path: &str,
    project_name: &str,
    _spec: &dyn LanguageSpec,
    scope: &[String],
) -> Option<Definition> {
    let name = find_child_text(node, "name", source)
        .or_else(|| find_child_text(node, "property", source))?;

    let label = if scope.iter().any(|_| true) && !scope.is_empty() {
        NodeLabel::Method
    } else {
        NodeLabel::Function
    };

    Some(Definition {
        name: name.clone(),
        qualified_name: make_qn(project_name, file_path, &name, scope),
        label,
        line_start: node.start_position().row as u32 + 1,
        line_end: node.end_position().row as u32 + 1,
    })
}

/// Extract a class/interface/enum definition from a tree-sitter node.
fn extract_class_def(
    node: &TsNode,
    source: &[u8],
    file_path: &str,
    project_name: &str,
    _spec: &dyn LanguageSpec,
    scope: &[String],
) -> Option<Definition> {
    let name = find_child_text(node, "name", source)?;

    let label = match node.kind() {
        "interface_declaration" => NodeLabel::Interface,
        "enum_declaration" => NodeLabel::Enum,
        _ => NodeLabel::Class,
    };

    Some(Definition {
        name: name.clone(),
        qualified_name: make_qn(project_name, file_path, &name, scope),
        label,
        line_start: node.start_position().row as u32 + 1,
        line_end: node.end_position().row as u32 + 1,
    })
}

/// Extract a function call reference.
fn extract_call(node: &TsNode, source: &[u8], scope: &[String]) -> Option<CallRef> {
    // For call expressions, the function being called is typically the first child
    let func_node = node.child_by_field_name("function")
        .or_else(|| node.child(0))?;

    let callee = node_text(&func_node, source)?;

    // Extract just the function name (last segment of dotted path)
    let callee_name = callee.rsplit('.').next().unwrap_or(&callee).to_string();

    Some(CallRef {
        callee_name,
        line: node.start_position().row as u32 + 1,
        enclosing_qn: enclosing_qn(scope),
    })
}

/// Extract an import statement.
fn extract_import(
    node: &TsNode,
    source: &[u8],
    kind: &str,
    spec: &dyn LanguageSpec,
) -> Option<ImportRef> {
    let text = node_text(node, source)?;

    if spec.import_from_types().contains(&kind) {
        // Python: from X import Y, Z
        let module_node = node.child_by_field_name("module_name");
        let module_path = module_node
            .and_then(|n| node_text(&n, source))
            .unwrap_or_default();

        let mut names = Vec::new();
        for i in 0..node.named_child_count() {
            if let Some(child) = node.named_child(i) {
                if child.kind() == "dotted_name" || child.kind() == "aliased_import" {
                    if let Some(name) = node_text(&child, source) {
                        names.push(name);
                    }
                }
            }
        }

        Some(ImportRef {
            module_path,
            alias: None,
            names,
            line: node.start_position().row as u32 + 1,
        })
    } else {
        // JS/TS: import X from 'Y' or import { X } from 'Y'
        // Python: import X
        Some(ImportRef {
            module_path: text,
            alias: None,
            names: Vec::new(),
            line: node.start_position().row as u32 + 1,
        })
    }
}

/// Get text content of a named child field.
fn find_child_text(node: &TsNode, field: &str, source: &[u8]) -> Option<String> {
    let child = node.child_by_field_name(field)?;
    node_text(&child, source)
}

/// Get the text content of a tree-sitter node.
fn node_text(node: &TsNode, source: &[u8]) -> Option<String> {
    node.utf8_text(source).ok().map(|s| s.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::extract::python::PYTHON_SPEC;
    use crate::extract::javascript::JAVASCRIPT_SPEC;
    use crate::extract::typescript::TYPESCRIPT_SPEC;

    #[test]
    fn extracts_python_functions() {
        let source = r#"
def greet(name):
    return f"Hello {name}"

def farewell():
    pass
"#;
        let result = extract_file(source, "app.py", "test", &PYTHON_SPEC).unwrap();
        assert_eq!(result.definitions.len(), 2);
        assert_eq!(result.definitions[0].name, "greet");
        assert_eq!(result.definitions[0].label, NodeLabel::Function);
        assert_eq!(result.definitions[1].name, "farewell");
    }

    #[test]
    fn extracts_python_class_with_methods() {
        let source = r#"
class UserService:
    def get_user(self, id):
        pass

    def create_user(self, data):
        pass
"#;
        let result = extract_file(source, "service.py", "test", &PYTHON_SPEC).unwrap();

        let labels: Vec<_> = result.definitions.iter().map(|d| (d.name.as_str(), d.label)).collect();
        assert_eq!(labels, vec![
            ("UserService", NodeLabel::Class),
            ("get_user", NodeLabel::Method),
            ("create_user", NodeLabel::Method),
        ]);
    }

    #[test]
    fn extracts_python_calls() {
        let source = r#"
def main():
    result = fetch_data()
    process(result)
"#;
        let result = extract_file(source, "app.py", "test", &PYTHON_SPEC).unwrap();
        let call_names: Vec<_> = result.calls.iter().map(|c| c.callee_name.as_str()).collect();
        assert!(call_names.contains(&"fetch_data"));
        assert!(call_names.contains(&"process"));
    }

    #[test]
    fn extracts_python_imports() {
        let source = r#"
import os
from pathlib import Path
"#;
        let result = extract_file(source, "app.py", "test", &PYTHON_SPEC).unwrap();
        assert!(result.imports.len() >= 2);
    }

    #[test]
    fn extracts_js_arrow_functions() {
        let source = r#"
const greet = (name) => `Hello ${name}`;

function process(data) {
    return data;
}
"#;
        let result = extract_file(source, "app.js", "test", &JAVASCRIPT_SPEC).unwrap();
        let names: Vec<_> = result.definitions.iter().map(|d| d.name.as_str()).collect();
        assert!(names.contains(&"process"));
    }

    #[test]
    fn extracts_ts_interface_and_enum() {
        let source = r#"
interface User {
    name: string;
    age: number;
}

enum Status {
    Active,
    Inactive,
}

function getUser(id: number): User {
    return { name: "test", age: 0 };
}
"#;
        let result = extract_file(source, "types.ts", "test", &TYPESCRIPT_SPEC).unwrap();

        let by_label: Vec<_> = result.definitions.iter().map(|d| (d.name.as_str(), d.label)).collect();
        assert!(by_label.contains(&("User", NodeLabel::Interface)));
        assert!(by_label.contains(&("Status", NodeLabel::Enum)));
        assert!(by_label.contains(&("getUser", NodeLabel::Function)));
    }

    #[test]
    fn qualified_names_include_scope() {
        let source = r#"
class MyClass:
    def my_method(self):
        pass
"#;
        let result = extract_file(source, "mod.py", "proj", &PYTHON_SPEC).unwrap();
        let method = result.definitions.iter().find(|d| d.name == "my_method").unwrap();
        assert!(method.qualified_name.contains("MyClass.my_method"));
    }
}
```

- [ ] **Step 2: Update extract/mod.rs to re-export**

```rust
// tokkit/core/code/crates/tokkit-core/src/extract/mod.rs
pub mod spec;
pub mod python;
pub mod javascript;
pub mod typescript;
pub mod walker;

pub use walker::extract_file;
pub use spec::{LanguageSpec, spec_for_language};
```

- [ ] **Step 3: Run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/extract/
git commit -m "feat(core): add AST walker with extraction for Python, JS, TS"
```

---

## Task 5: Graph Buffer Module

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/graph/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/graph/merge.rs`

- [ ] **Step 1: Write graph/mod.rs with insert, dedup, and lookup**

```rust
// tokkit/core/code/crates/tokkit-core/src/graph/mod.rs
pub mod merge;

use crate::types::*;
use hashbrown::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, Ordering};

/// In-memory graph buffer for accumulating nodes and edges during indexing.
pub struct GraphBuffer {
    project: String,
    root_path: String,
    next_id: AtomicU64,

    nodes: Vec<Node>,
    node_by_qn: HashMap<String, usize>,  // qn → index in nodes vec
    node_by_id: HashMap<u64, usize>,      // id → index in nodes vec

    edges: Vec<Edge>,
    edge_dedup: HashSet<(u64, u64, EdgeType)>,
}

impl GraphBuffer {
    pub fn new(project: &str, root_path: &str) -> Self {
        Self {
            project: project.to_string(),
            root_path: root_path.to_string(),
            next_id: AtomicU64::new(1),
            nodes: Vec::new(),
            node_by_qn: HashMap::new(),
            node_by_id: HashMap::new(),
            edges: Vec::new(),
            edge_dedup: HashSet::new(),
        }
    }

    /// Create with a shared atomic counter for parallel workers.
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

    fn alloc_id(&self) -> u64 {
        self.next_id.fetch_add(1, Ordering::Relaxed)
    }

    /// Insert or update a node. Returns the node's ID.
    /// If a node with the same qualified_name exists, updates it in place.
    pub fn upsert_node(&mut self, node: Node) -> u64 {
        if let Some(&idx) = self.node_by_qn.get(&node.qualified_name) {
            let existing = &mut self.nodes[idx];
            existing.label = node.label;
            existing.name = node.name;
            existing.file_path = node.file_path;
            existing.line_start = node.line_start;
            existing.line_end = node.line_end;
            for (k, v) in node.properties {
                existing.properties.insert(k, v);
            }
            existing.id
        } else {
            let id = if node.id == 0 { self.alloc_id() } else { node.id };
            let mut node = node;
            node.id = id;
            let idx = self.nodes.len();
            self.node_by_qn.insert(node.qualified_name.clone(), idx);
            self.node_by_id.insert(id, idx);
            self.nodes.push(node);
            id
        }
    }

    /// Insert a new node with auto-generated ID. Returns the ID.
    pub fn add_node(
        &mut self,
        label: NodeLabel,
        name: &str,
        qualified_name: &str,
        file_path: Option<&str>,
        line_start: u32,
        line_end: u32,
    ) -> u64 {
        let node = Node {
            id: 0,
            label,
            name: name.to_string(),
            qualified_name: qualified_name.to_string(),
            file_path: file_path.map(|s| s.to_string()),
            line_start,
            line_end,
            properties: HashMap::new(),
        };
        self.upsert_node(node)
    }

    /// Insert an edge. Deduplicates on (source_id, target_id, edge_type).
    /// On conflict, merges properties and keeps higher confidence.
    pub fn add_edge(&mut self, mut edge: Edge) -> bool {
        let key = (edge.source_id, edge.target_id, edge.edge_type);
        if self.edge_dedup.contains(&key) {
            // Find and merge
            if let Some(existing) = self.edges.iter_mut().find(|e| {
                e.source_id == edge.source_id
                    && e.target_id == edge.target_id
                    && e.edge_type == edge.edge_type
            }) {
                for (k, v) in edge.properties.drain() {
                    existing.properties.insert(k, v);
                }
                if let Some(new_conf) = edge.confidence {
                    if existing.confidence.map_or(true, |c| new_conf.value() > c.value()) {
                        existing.confidence = Some(new_conf);
                    }
                }
            }
            false
        } else {
            self.edge_dedup.insert(key);
            self.edges.push(edge);
            true
        }
    }

    pub fn find_by_qn(&self, qn: &str) -> Option<&Node> {
        self.node_by_qn.get(qn).map(|&idx| &self.nodes[idx])
    }

    pub fn find_by_id(&self, id: u64) -> Option<&Node> {
        self.node_by_id.get(&id).map(|&idx| &self.nodes[idx])
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

    #[test]
    fn add_node_assigns_unique_ids() {
        let mut buf = GraphBuffer::new("test", "/tmp");
        let id1 = buf.add_node(NodeLabel::Function, "foo", "test::foo", Some("a.py"), 1, 5);
        let id2 = buf.add_node(NodeLabel::Function, "bar", "test::bar", Some("a.py"), 6, 10);
        assert_ne!(id1, id2);
        assert_eq!(buf.node_count(), 2);
    }

    #[test]
    fn upsert_deduplicates_by_qn() {
        let mut buf = GraphBuffer::new("test", "/tmp");
        let id1 = buf.add_node(NodeLabel::Function, "foo", "test::foo", Some("a.py"), 1, 5);
        let id2 = buf.add_node(NodeLabel::Function, "foo_updated", "test::foo", Some("a.py"), 1, 10);
        assert_eq!(id1, id2);
        assert_eq!(buf.node_count(), 1);
        assert_eq!(buf.find_by_qn("test::foo").unwrap().line_end, 10);
    }

    #[test]
    fn edge_dedup_on_triple() {
        let mut buf = GraphBuffer::new("test", "/tmp");
        let id1 = buf.add_node(NodeLabel::Function, "a", "test::a", None, 0, 0);
        let id2 = buf.add_node(NodeLabel::Function, "b", "test::b", None, 0, 0);

        let added1 = buf.add_edge(Edge {
            source_id: id1,
            target_id: id2,
            edge_type: EdgeType::Calls,
            confidence: Some(Confidence::new(0.5)),
            properties: HashMap::new(),
        });
        let added2 = buf.add_edge(Edge {
            source_id: id1,
            target_id: id2,
            edge_type: EdgeType::Calls,
            confidence: Some(Confidence::new(0.9)),
            properties: HashMap::new(),
        });

        assert!(added1);
        assert!(!added2); // duplicate
        assert_eq!(buf.edge_count(), 1);
        // Higher confidence kept
        assert_eq!(buf.edges()[0].confidence.unwrap().value(), 0.9);
    }

    #[test]
    fn find_by_qn_and_id() {
        let mut buf = GraphBuffer::new("test", "/tmp");
        let id = buf.add_node(NodeLabel::Class, "Foo", "test::Foo", None, 1, 20);

        assert!(buf.find_by_qn("test::Foo").is_some());
        assert!(buf.find_by_id(id).is_some());
        assert!(buf.find_by_qn("nonexistent").is_none());
    }
}
```

- [ ] **Step 2: Write graph/merge.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/graph/merge.rs
use super::GraphBuffer;
use hashbrown::HashMap;

/// Merge a worker's graph buffer into the main buffer.
/// Remaps all node IDs from the worker's ID space to the main buffer's.
/// Edge source/target IDs are remapped accordingly.
pub fn merge_into(main: &mut GraphBuffer, worker: GraphBuffer) {
    let mut id_remap: HashMap<u64, u64> = HashMap::new();

    // Merge nodes
    for node in worker.nodes {
        let old_id = node.id;
        let new_id = main.upsert_node(node);
        id_remap.insert(old_id, new_id);
    }

    // Merge edges with remapped IDs
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
    use crate::types::*;

    #[test]
    fn merge_remaps_ids_correctly() {
        let mut main = GraphBuffer::new("test", "/tmp");
        main.add_node(NodeLabel::Project, "test", "test", None, 0, 0);

        let mut worker = GraphBuffer::with_shared_ids("test", "/tmp", 100);
        let w_id1 = worker.add_node(NodeLabel::Function, "a", "test::a", Some("a.py"), 1, 5);
        let w_id2 = worker.add_node(NodeLabel::Function, "b", "test::b", Some("b.py"), 1, 5);
        worker.add_edge(Edge {
            source_id: w_id1,
            target_id: w_id2,
            edge_type: EdgeType::Calls,
            confidence: Some(Confidence::IMPORT_MAP),
            properties: HashMap::new(),
        });

        merge_into(&mut main, worker);

        assert_eq!(main.node_count(), 3); // project + a + b
        assert_eq!(main.edge_count(), 1);

        // Edge IDs should be remapped to main's ID space
        let edge = &main.edges()[0];
        assert!(main.find_by_id(edge.source_id).is_some());
        assert!(main.find_by_id(edge.target_id).is_some());
    }
}
```

- [ ] **Step 3: Uncomment graph in lib.rs, run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/graph/
git commit -m "feat(core): add graph buffer with insert, dedup, merge"
```

---

## Task 6: Resolution Module

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/resolve/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/resolve/registry.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/resolve/strategies.rs`

- [ ] **Step 1: Write registry.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/resolve/registry.rs
use crate::types::NodeLabel;
use hashbrown::HashMap;

/// Registry of all callable/referenceable symbols in the project.
/// Two indexes for fast lookup during resolution.
pub struct Registry {
    /// Exact: qualified_name → (NodeLabel, simple_name)
    exact: HashMap<String, (NodeLabel, String)>,

    /// By name: simple_name → Vec<qualified_name>
    by_name: HashMap<String, Vec<String>>,
}

impl Registry {
    pub fn new() -> Self {
        Self {
            exact: HashMap::new(),
            by_name: HashMap::new(),
        }
    }

    /// Register a symbol in both indexes.
    pub fn register(&mut self, qualified_name: &str, label: NodeLabel) {
        let simple = simple_name(qualified_name);
        self.exact.insert(
            qualified_name.to_string(),
            (label, simple.to_string()),
        );
        self.by_name
            .entry(simple.to_string())
            .or_default()
            .push(qualified_name.to_string());
    }

    /// Look up by exact qualified name.
    pub fn get_exact(&self, qn: &str) -> Option<&(NodeLabel, String)> {
        self.exact.get(qn)
    }

    /// Look up all qualified names for a simple name.
    pub fn get_by_name(&self, name: &str) -> Option<&[String]> {
        self.by_name.get(name).map(|v| v.as_slice())
    }

    pub fn len(&self) -> usize {
        self.exact.len()
    }

    pub fn is_empty(&self) -> bool {
        self.exact.is_empty()
    }
}

/// Extract the last dot-separated segment from a qualified name.
fn simple_name(qn: &str) -> &str {
    // QN format: "project::file::Scope.name" — extract "name"
    qn.rsplit_once('.')
        .map(|(_, name)| name)
        .or_else(|| qn.rsplit_once("::").map(|(_, name)| name))
        .unwrap_or(qn)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_lookup() {
        let mut reg = Registry::new();
        reg.register("proj::src/auth.py::AuthService", NodeLabel::Class);
        reg.register("proj::src/auth.py::AuthService.login", NodeLabel::Method);

        assert!(reg.get_exact("proj::src/auth.py::AuthService").is_some());
        assert_eq!(reg.get_by_name("AuthService").unwrap().len(), 1);
        assert_eq!(reg.get_by_name("login").unwrap().len(), 1);
    }

    #[test]
    fn multiple_candidates_same_name() {
        let mut reg = Registry::new();
        reg.register("proj::a.py::process", NodeLabel::Function);
        reg.register("proj::b.py::process", NodeLabel::Function);

        let candidates = reg.get_by_name("process").unwrap();
        assert_eq!(candidates.len(), 2);
    }

    #[test]
    fn simple_name_extraction() {
        assert_eq!(simple_name("proj::file.py::Foo.bar"), "bar");
        assert_eq!(simple_name("proj::file.py::top_level"), "top_level");
        assert_eq!(simple_name("standalone"), "standalone");
    }
}
```

- [ ] **Step 2: Write strategies.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/resolve/strategies.rs
use super::registry::Registry;
use crate::types::*;

/// Result of a resolution attempt.
#[derive(Debug, Clone)]
pub struct Resolution {
    pub target_qn: String,
    pub confidence: Confidence,
    pub strategy: &'static str,
}

/// Strategy 1: Import map — resolve via the file's import list.
pub fn resolve_via_imports(
    callee_name: &str,
    imports: &[ImportRef],
    registry: &Registry,
) -> Option<Resolution> {
    for imp in imports {
        // Check if any imported name matches the callee
        for imported_name in &imp.names {
            let name = imported_name.split(" as ").next().unwrap_or(imported_name);
            let alias = imported_name.split(" as ").nth(1);
            let lookup = alias.unwrap_or(name);

            if lookup == callee_name {
                // Try to find the qualified name: module.name
                let candidate_qn_suffix = format!("{}.{}", imp.module_path, name);
                // Search registry for any QN ending with this suffix
                if let Some(candidates) = registry.get_by_name(name) {
                    for qn in candidates {
                        if qn.contains(&imp.module_path) || qn.ends_with(&candidate_qn_suffix) {
                            return Some(Resolution {
                                target_qn: qn.clone(),
                                confidence: Confidence::IMPORT_MAP,
                                strategy: "import_map",
                            });
                        }
                    }
                    // If we have import but can't match module path exactly, still use import
                    if candidates.len() == 1 {
                        return Some(Resolution {
                            target_qn: candidates[0].clone(),
                            confidence: Confidence::new(0.85),
                            strategy: "import_map_suffix",
                        });
                    }
                }
            }
        }

        // Direct import (import os, import module)
        if imp.names.is_empty() && imp.module_path.ends_with(callee_name) {
            if let Some(candidates) = registry.get_by_name(callee_name) {
                if candidates.len() == 1 {
                    return Some(Resolution {
                        target_qn: candidates[0].clone(),
                        confidence: Confidence::IMPORT_MAP,
                        strategy: "import_map",
                    });
                }
            }
        }
    }
    None
}

/// Strategy 2: Same module — caller and definition share the same file.
pub fn resolve_same_module(
    callee_name: &str,
    caller_file: &str,
    project_name: &str,
    registry: &Registry,
) -> Option<Resolution> {
    if let Some(candidates) = registry.get_by_name(callee_name) {
        let file_prefix = format!("{project_name}::{caller_file}::");
        for qn in candidates {
            if qn.starts_with(&file_prefix) {
                return Some(Resolution {
                    target_qn: qn.clone(),
                    confidence: Confidence::SAME_MODULE,
                    strategy: "same_module",
                });
            }
        }
    }
    None
}

/// Strategy 3: Unique name — only one candidate project-wide.
pub fn resolve_unique_name(
    callee_name: &str,
    registry: &Registry,
) -> Option<Resolution> {
    if let Some(candidates) = registry.get_by_name(callee_name) {
        if candidates.len() == 1 {
            return Some(Resolution {
                target_qn: candidates[0].clone(),
                confidence: Confidence::UNIQUE_NAME,
                strategy: "unique_name",
            });
        }
    }
    None
}

/// Strategy 4: Suffix match — multiple candidates, score by common prefix.
pub fn resolve_suffix_match(
    callee_name: &str,
    caller_qn: &str,
    registry: &Registry,
) -> Option<Resolution> {
    let candidates = registry.get_by_name(callee_name)?;
    if candidates.len() < 2 {
        return None;
    }

    // Score each candidate by common prefix length with caller's QN
    let mut best: Option<(&str, usize)> = None;
    for qn in candidates {
        let common = common_prefix_len(caller_qn, qn);
        if best.map_or(true, |(_, best_len)| common > best_len) {
            best = Some((qn.as_str(), common));
        }
    }

    best.map(|(qn, _)| Resolution {
        target_qn: qn.to_string(),
        confidence: Confidence::SUFFIX_MATCH,
        strategy: "suffix_match",
    })
}

fn common_prefix_len(a: &str, b: &str) -> usize {
    a.chars().zip(b.chars()).take_while(|(x, y)| x == y).count()
}

/// Run all four strategies in cascade order. Returns the first match.
pub fn resolve(
    callee_name: &str,
    caller_file: &str,
    caller_qn: Option<&str>,
    project_name: &str,
    imports: &[ImportRef],
    registry: &Registry,
) -> Option<Resolution> {
    resolve_via_imports(callee_name, imports, registry)
        .or_else(|| resolve_same_module(callee_name, caller_file, project_name, registry))
        .or_else(|| resolve_unique_name(callee_name, registry))
        .or_else(|| {
            caller_qn.and_then(|cqn| resolve_suffix_match(callee_name, cqn, registry))
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn setup_registry() -> Registry {
        let mut reg = Registry::new();
        reg.register("proj::src/auth.py::authenticate", NodeLabel::Function);
        reg.register("proj::src/db.py::connect", NodeLabel::Function);
        reg.register("proj::src/utils.py::process", NodeLabel::Function);
        reg.register("proj::src/other.py::process", NodeLabel::Function);
        reg
    }

    #[test]
    fn import_map_resolves_direct_import() {
        let reg = setup_registry();
        let imports = vec![ImportRef {
            module_path: "src/auth".to_string(),
            alias: None,
            names: vec!["authenticate".to_string()],
            line: 1,
        }];

        let res = resolve_via_imports("authenticate", &imports, &reg);
        assert!(res.is_some());
        let res = res.unwrap();
        assert_eq!(res.strategy, "import_map");
        assert!(res.confidence.value() >= 0.85);
    }

    #[test]
    fn same_module_resolves_local_call() {
        let reg = setup_registry();
        let res = resolve_same_module("connect", "src/db.py", "proj", &reg);
        assert!(res.is_some());
        assert_eq!(res.unwrap().confidence.value(), 0.90);
    }

    #[test]
    fn unique_name_resolves_single_candidate() {
        let reg = setup_registry();
        let res = resolve_unique_name("authenticate", &reg);
        assert!(res.is_some());
        assert_eq!(res.unwrap().confidence.value(), 0.75);
    }

    #[test]
    fn unique_name_fails_on_ambiguity() {
        let reg = setup_registry();
        let res = resolve_unique_name("process", &reg);
        assert!(res.is_none()); // Two candidates
    }

    #[test]
    fn suffix_match_picks_closest() {
        let reg = setup_registry();
        let res = resolve_suffix_match(
            "process",
            "proj::src/utils.py::caller",
            &reg,
        );
        assert!(res.is_some());
        let res = res.unwrap();
        assert!(res.target_qn.contains("utils.py"));
        assert_eq!(res.confidence.value(), 0.55);
    }

    #[test]
    fn cascade_uses_highest_priority_match() {
        let reg = setup_registry();
        let imports = vec![ImportRef {
            module_path: "src/auth".to_string(),
            alias: None,
            names: vec!["authenticate".to_string()],
            line: 1,
        }];

        // Should use import_map (0.95), not unique_name (0.75)
        let res = resolve("authenticate", "src/main.py", None, "proj", &imports, &reg);
        assert!(res.is_some());
        assert_eq!(res.unwrap().strategy, "import_map");
    }
}
```

- [ ] **Step 3: Write resolve/mod.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/resolve/mod.rs
pub mod registry;
pub mod strategies;

pub use registry::Registry;
pub use strategies::{resolve, Resolution};
```

- [ ] **Step 4: Uncomment resolve in lib.rs, run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/resolve/
git commit -m "feat(core): add 4-strategy cascade resolution with registry"
```

---

## Task 7: Store Module (redb)

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/store/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/store/tables.rs`

- [ ] **Step 1: Write tables.rs — redb table definitions**

```rust
// tokkit/core/code/crates/tokkit-core/src/store/tables.rs
use redb::TableDefinition;

/// Primary node table: qualified_name → serialized Node
pub const NODES: TableDefinition<&str, &[u8]> = TableDefinition::new("nodes");

/// Node-by-ID index: id (as string) → qualified_name
pub const NODE_BY_ID: TableDefinition<&str, &str> = TableDefinition::new("node_by_id");

/// Nodes-by-label index: "label::name" → qualified_name
/// Multiple entries per label via different name keys.
pub const NODES_BY_LABEL: TableDefinition<&str, &str> = TableDefinition::new("nodes_by_label");

/// Nodes-by-file index: file_path → serialized Vec<qualified_name>
pub const NODES_BY_FILE: TableDefinition<&str, &[u8]> = TableDefinition::new("nodes_by_file");

/// Primary edge table: "src_id:tgt_id:type" → serialized Edge
pub const EDGES: TableDefinition<&str, &[u8]> = TableDefinition::new("edges");

/// Edges-by-source index: "source_id" → serialized Vec<edge_key>
pub const EDGES_BY_SOURCE: TableDefinition<&str, &[u8]> = TableDefinition::new("edges_by_source");

/// Edges-by-target index: "target_id" → serialized Vec<edge_key>
pub const EDGES_BY_TARGET: TableDefinition<&str, &[u8]> = TableDefinition::new("edges_by_target");

/// File hashes for incremental indexing: "project::path" → serialized (mtime_ns, size)
pub const FILE_HASHES: TableDefinition<&str, &[u8]> = TableDefinition::new("file_hashes");

/// Project metadata: project_name → serialized ProjectMeta
pub const PROJECTS: TableDefinition<&str, &[u8]> = TableDefinition::new("projects");
```

- [ ] **Step 2: Write store/mod.rs**

```rust
// tokkit/core/code/crates/tokkit-core/src/store/mod.rs
pub mod tables;

use crate::error::{Result, TokkitError};
use crate::graph::GraphBuffer;
use crate::types::*;
use redb::Database;
use std::path::Path;

pub struct Store {
    db: Database,
    path: String,
}

impl Store {
    /// Open or create a store at the given path.
    pub fn open(path: &str) -> Result<Self> {
        let db = Database::create(path).map_err(|e| TokkitError::Store(e.to_string()))?;
        let store = Self {
            db,
            path: path.to_string(),
        };
        store.init_tables()?;
        Ok(store)
    }

    /// Open a temporary in-memory store (for testing).
    pub fn open_memory() -> Result<Self> {
        let dir = tempfile::tempdir().map_err(|e| TokkitError::Io(e))?;
        let path = dir.path().join("test.redb");
        let path_str = path.to_string_lossy().to_string();
        Self::open(&path_str)
    }

    pub fn path(&self) -> &str {
        &self.path
    }

    fn init_tables(&self) -> Result<()> {
        let tx = self.db.begin_write().map_err(|e| TokkitError::Store(e.to_string()))?;
        // Open each table to ensure it exists
        tx.open_table(tables::NODES).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::NODE_BY_ID).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::NODES_BY_LABEL).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::NODES_BY_FILE).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::EDGES).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::EDGES_BY_SOURCE).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::EDGES_BY_TARGET).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::FILE_HASHES).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.open_table(tables::PROJECTS).map_err(|e| TokkitError::Store(e.to_string()))?;
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }

    /// Write an entire graph buffer to the store in a single transaction.
    pub fn write_graph(&self, buf: &GraphBuffer) -> Result<()> {
        let tx = self.db.begin_write().map_err(|e| TokkitError::Store(e.to_string()))?;

        {
            let mut nodes_table = tx.open_table(tables::NODES)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut id_table = tx.open_table(tables::NODE_BY_ID)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut label_table = tx.open_table(tables::NODES_BY_LABEL)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut file_index: hashbrown::HashMap<String, Vec<String>> = hashbrown::HashMap::new();

            for node in buf.nodes() {
                let data = bincode::serialize(node)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                nodes_table.insert(node.qualified_name.as_str(), data.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                let id_str = node.id.to_string();
                id_table.insert(id_str.as_str(), node.qualified_name.as_str())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                let label_key = format!("{}::{}", node.label.as_str(), node.name);
                label_table.insert(label_key.as_str(), node.qualified_name.as_str())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                if let Some(ref fp) = node.file_path {
                    file_index.entry(fp.clone()).or_default().push(node.qualified_name.clone());
                }
            }

            let mut file_table = tx.open_table(tables::NODES_BY_FILE)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (fp, qns) in &file_index {
                let data = bincode::serialize(qns)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                file_table.insert(fp.as_str(), data.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }
        }

        {
            let mut edges_table = tx.open_table(tables::EDGES)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            let mut src_index: hashbrown::HashMap<String, Vec<String>> = hashbrown::HashMap::new();
            let mut tgt_index: hashbrown::HashMap<String, Vec<String>> = hashbrown::HashMap::new();

            for edge in buf.edges() {
                let key = format!("{}:{}:{}", edge.source_id, edge.target_id, edge.edge_type.as_str());
                let data = bincode::serialize(edge)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                edges_table.insert(key.as_str(), data.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;

                src_index.entry(edge.source_id.to_string()).or_default().push(key.clone());
                tgt_index.entry(edge.target_id.to_string()).or_default().push(key);
            }

            let mut src_table = tx.open_table(tables::EDGES_BY_SOURCE)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (src_id, keys) in &src_index {
                let data = bincode::serialize(keys)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                src_table.insert(src_id.as_str(), data.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }

            let mut tgt_table = tx.open_table(tables::EDGES_BY_TARGET)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (tgt_id, keys) in &tgt_index {
                let data = bincode::serialize(keys)
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                tgt_table.insert(tgt_id.as_str(), data.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }
        }

        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }

    /// Read a node by qualified name.
    pub fn get_node(&self, qn: &str) -> Result<Option<Node>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(tables::NODES).map_err(|e| TokkitError::Store(e.to_string()))?;

        match table.get(qn) {
            Ok(Some(data)) => {
                let node: Node = bincode::deserialize(data.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                Ok(Some(node))
            }
            Ok(None) => Ok(None),
            Err(e) => Err(TokkitError::Store(e.to_string())),
        }
    }

    /// Read a node by ID.
    pub fn get_node_by_id(&self, id: u64) -> Result<Option<Node>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let id_table = tx.open_table(tables::NODE_BY_ID)
            .map_err(|e| TokkitError::Store(e.to_string()))?;

        let id_str = id.to_string();
        match id_table.get(id_str.as_str()) {
            Ok(Some(qn_val)) => {
                let qn = qn_val.value().to_string();
                drop(id_table);
                drop(tx);
                self.get_node(&qn)
            }
            Ok(None) => Ok(None),
            Err(e) => Err(TokkitError::Store(e.to_string())),
        }
    }

    /// Get all edges originating from a node.
    pub fn get_edges_from(&self, source_id: u64) -> Result<Vec<Edge>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let src_table = tx.open_table(tables::EDGES_BY_SOURCE)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let edges_table = tx.open_table(tables::EDGES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;

        let id_str = source_id.to_string();
        let keys: Vec<String> = match src_table.get(id_str.as_str()) {
            Ok(Some(data)) => bincode::deserialize(data.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?,
            Ok(None) => return Ok(Vec::new()),
            Err(e) => return Err(TokkitError::Store(e.to_string())),
        };

        let mut edges = Vec::new();
        for key in &keys {
            if let Ok(Some(data)) = edges_table.get(key.as_str()) {
                let edge: Edge = bincode::deserialize(data.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                edges.push(edge);
            }
        }
        Ok(edges)
    }

    /// Get all edges targeting a node.
    pub fn get_edges_to(&self, target_id: u64) -> Result<Vec<Edge>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let tgt_table = tx.open_table(tables::EDGES_BY_TARGET)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let edges_table = tx.open_table(tables::EDGES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;

        let id_str = target_id.to_string();
        let keys: Vec<String> = match tgt_table.get(id_str.as_str()) {
            Ok(Some(data)) => bincode::deserialize(data.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?,
            Ok(None) => return Ok(Vec::new()),
            Err(e) => return Err(TokkitError::Store(e.to_string())),
        };

        let mut edges = Vec::new();
        for key in &keys {
            if let Ok(Some(data)) = edges_table.get(key.as_str()) {
                let edge: Edge = bincode::deserialize(data.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                edges.push(edge);
            }
        }
        Ok(edges)
    }

    /// Count all nodes.
    pub fn node_count(&self) -> Result<usize> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(tables::NODES).map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(table.len().map_err(|e| TokkitError::Store(e.to_string()))? as usize)
    }

    /// Count all edges.
    pub fn edge_count(&self) -> Result<usize> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(tables::EDGES).map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(table.len().map_err(|e| TokkitError::Store(e.to_string()))? as usize)
    }

    /// Write file hashes for incremental indexing.
    pub fn write_file_hashes(&self, project: &str, hashes: &[(String, i64, i64)]) -> Result<()> {
        let tx = self.db.begin_write().map_err(|e| TokkitError::Store(e.to_string()))?;
        {
            let mut table = tx.open_table(tables::FILE_HASHES)
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            for (path, mtime, size) in hashes {
                let key = format!("{project}::{path}");
                let data = bincode::serialize(&(*mtime, *size))
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                table.insert(key.as_str(), data.as_slice())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
            }
        }
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }

    /// Read file hash for incremental comparison.
    pub fn get_file_hash(&self, project: &str, path: &str) -> Result<Option<(i64, i64)>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(tables::FILE_HASHES)
            .map_err(|e| TokkitError::Store(e.to_string()))?;
        let key = format!("{project}::{path}");
        match table.get(key.as_str()) {
            Ok(Some(data)) => {
                let (mtime, size): (i64, i64) = bincode::deserialize(data.value())
                    .map_err(|e| TokkitError::Store(e.to_string()))?;
                Ok(Some((mtime, size)))
            }
            Ok(None) => Ok(None),
            Err(e) => Err(TokkitError::Store(e.to_string())),
        }
    }

    /// Iterate all nodes (for search/scan operations).
    pub fn all_nodes(&self) -> Result<Vec<Node>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(tables::NODES).map_err(|e| TokkitError::Store(e.to_string()))?;

        let mut nodes = Vec::new();
        let iter = table.iter().map_err(|e| TokkitError::Store(e.to_string()))?;
        for entry in iter {
            let (_, data) = entry.map_err(|e| TokkitError::Store(e.to_string()))?;
            let node: Node = bincode::deserialize(data.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            nodes.push(node);
        }
        Ok(nodes)
    }

    /// Iterate all edges.
    pub fn all_edges(&self) -> Result<Vec<Edge>> {
        let tx = self.db.begin_read().map_err(|e| TokkitError::Store(e.to_string()))?;
        let table = tx.open_table(tables::EDGES).map_err(|e| TokkitError::Store(e.to_string()))?;

        let mut edges = Vec::new();
        let iter = table.iter().map_err(|e| TokkitError::Store(e.to_string()))?;
        for entry in iter {
            let (_, data) = entry.map_err(|e| TokkitError::Store(e.to_string()))?;
            let edge: Edge = bincode::deserialize(data.value())
                .map_err(|e| TokkitError::Store(e.to_string()))?;
            edges.push(edge);
        }
        Ok(edges)
    }

    /// Delete all data (for reindex).
    pub fn clear(&self) -> Result<()> {
        let tx = self.db.begin_write().map_err(|e| TokkitError::Store(e.to_string()))?;
        // Drain each table
        for table_name in &["nodes", "node_by_id", "nodes_by_label", "nodes_by_file",
                            "edges", "edges_by_source", "edges_by_target", "file_hashes", "projects"] {
            let table_def: TableDefinition<&str, &[u8]> = TableDefinition::new(table_name);
            if let Ok(mut table) = tx.open_table(table_def) {
                // Drain by iterating
                let keys: Vec<String> = table.iter()
                    .map_err(|e| TokkitError::Store(e.to_string()))?
                    .filter_map(|e| e.ok().map(|(k, _)| k.value().to_string()))
                    .collect();
                for key in &keys {
                    let _ = table.remove(key.as_str());
                }
            }
        }
        tx.commit().map_err(|e| TokkitError::Store(e.to_string()))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graph::GraphBuffer;
    use std::collections::HashMap;

    fn test_store() -> Store {
        Store::open_memory().unwrap()
    }

    fn populated_store() -> Store {
        let store = test_store();
        let mut buf = GraphBuffer::new("test", "/tmp/repo");

        let id_a = buf.add_node(NodeLabel::Function, "func_a", "test::a.py::func_a", Some("a.py"), 1, 10);
        let id_b = buf.add_node(NodeLabel::Function, "func_b", "test::b.py::func_b", Some("b.py"), 1, 5);
        buf.add_edge(Edge {
            source_id: id_a,
            target_id: id_b,
            edge_type: EdgeType::Calls,
            confidence: Some(Confidence::IMPORT_MAP),
            properties: HashMap::new(),
        });

        store.write_graph(&buf).unwrap();
        store
    }

    #[test]
    fn roundtrip_node() {
        let store = populated_store();

        let node = store.get_node("test::a.py::func_a").unwrap().unwrap();
        assert_eq!(node.name, "func_a");
        assert_eq!(node.label, NodeLabel::Function);
        assert_eq!(node.line_start, 1);
        assert_eq!(node.line_end, 10);
    }

    #[test]
    fn node_not_found() {
        let store = populated_store();
        assert!(store.get_node("nonexistent").unwrap().is_none());
    }

    #[test]
    fn roundtrip_edges() {
        let store = populated_store();
        let node_a = store.get_node("test::a.py::func_a").unwrap().unwrap();

        let edges = store.get_edges_from(node_a.id).unwrap();
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].edge_type, EdgeType::Calls);
        assert_eq!(edges[0].confidence.unwrap().value(), 0.95);
    }

    #[test]
    fn reverse_edge_lookup() {
        let store = populated_store();
        let node_b = store.get_node("test::b.py::func_b").unwrap().unwrap();

        let edges = store.get_edges_to(node_b.id).unwrap();
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].edge_type, EdgeType::Calls);
    }

    #[test]
    fn counts() {
        let store = populated_store();
        assert_eq!(store.node_count().unwrap(), 2);
        assert_eq!(store.edge_count().unwrap(), 1);
    }

    #[test]
    fn file_hash_roundtrip() {
        let store = test_store();
        store.write_file_hashes("proj", &[
            ("src/a.py".to_string(), 1234567890, 1024),
        ]).unwrap();

        let hash = store.get_file_hash("proj", "src/a.py").unwrap().unwrap();
        assert_eq!(hash, (1234567890, 1024));
        assert!(store.get_file_hash("proj", "nonexistent").unwrap().is_none());
    }
}
```

- [ ] **Step 3: Uncomment store in lib.rs, run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/store/
git commit -m "feat(core): add redb store with node/edge persistence and indexes"
```

---

## Task 8: Query Module

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/query/mod.rs`

- [ ] **Step 1: Write query/mod.rs with all typed query functions**

```rust
// tokkit/core/code/crates/tokkit-core/src/query/mod.rs
use crate::error::{Result, TokkitError};
use crate::store::Store;
use crate::types::*;
use std::collections::{HashSet, VecDeque};
use std::fs;

/// Search nodes by name pattern, label, and/or file path.
pub fn search_nodes(store: &Store, filters: SearchFilters) -> Result<Vec<Node>> {
    let all = store.all_nodes()?;
    let limit = filters.limit.unwrap_or(50) as usize;

    let results: Vec<Node> = all
        .into_iter()
        .filter(|n| {
            if let Some(ref q) = filters.query {
                let q_lower = q.to_lowercase();
                if !n.name.to_lowercase().contains(&q_lower)
                    && !n.qualified_name.to_lowercase().contains(&q_lower)
                {
                    return false;
                }
            }
            if let Some(ref label) = filters.label {
                if n.label != *label {
                    return false;
                }
            }
            if let Some(ref fp) = filters.file_path {
                if n.file_path.as_deref() != Some(fp.as_str()) {
                    return false;
                }
            }
            true
        })
        .take(limit)
        .collect();

    Ok(results)
}

/// BFS path traversal between two nodes.
pub fn trace_path(
    store: &Store,
    from_qn: &str,
    to_qn: &str,
    max_depth: u32,
) -> Result<Vec<PathStep>> {
    let from_node = store.get_node(from_qn)?
        .ok_or_else(|| TokkitError::NotFound(from_qn.to_string()))?;
    let to_node = store.get_node(to_qn)?
        .ok_or_else(|| TokkitError::NotFound(to_qn.to_string()))?;

    // BFS
    let mut visited: HashSet<u64> = HashSet::new();
    let mut queue: VecDeque<(u64, Vec<PathStep>)> = VecDeque::new();

    queue.push_back((from_node.id, vec![PathStep {
        node: from_node.clone(),
        edge: None,
        depth: 0,
    }]));
    visited.insert(from_node.id);

    while let Some((current_id, path)) = queue.pop_front() {
        let depth = path.len() as u32 - 1;
        if depth >= max_depth {
            continue;
        }

        let edges = store.get_edges_from(current_id)?;
        for edge in edges {
            if visited.contains(&edge.target_id) {
                continue;
            }
            visited.insert(edge.target_id);

            if let Some(target_node) = store.get_node_by_id(edge.target_id)? {
                let mut new_path = path.clone();
                new_path.push(PathStep {
                    node: target_node.clone(),
                    edge: Some(edge.clone()),
                    depth: depth + 1,
                });

                if edge.target_id == to_node.id {
                    return Ok(new_path);
                }

                queue.push_back((edge.target_id, new_path));
            }
        }
    }

    Ok(Vec::new()) // No path found
}

/// Get all nodes that call the given function.
pub fn get_callers(store: &Store, qn: &str) -> Result<Vec<(Node, Option<Confidence>)>> {
    let target = store.get_node(qn)?
        .ok_or_else(|| TokkitError::NotFound(qn.to_string()))?;

    let edges = store.get_edges_to(target.id)?;
    let mut callers = Vec::new();

    for edge in edges {
        if edge.edge_type == EdgeType::Calls {
            if let Some(caller) = store.get_node_by_id(edge.source_id)? {
                callers.push((caller, edge.confidence));
            }
        }
    }

    Ok(callers)
}

/// Get all nodes that the given function calls.
pub fn get_callees(store: &Store, qn: &str) -> Result<Vec<(Node, Option<Confidence>)>> {
    let source = store.get_node(qn)?
        .ok_or_else(|| TokkitError::NotFound(qn.to_string()))?;

    let edges = store.get_edges_from(source.id)?;
    let mut callees = Vec::new();

    for edge in edges {
        if edge.edge_type == EdgeType::Calls {
            if let Some(callee) = store.get_node_by_id(edge.target_id)? {
                callees.push((callee, edge.confidence));
            }
        }
    }

    Ok(callees)
}

/// Get a code snippet for a node.
pub fn get_snippet(store: &Store, qn: &str, repo_path: &str, context_lines: u32) -> Result<Option<CodeSnippet>> {
    let node = match store.get_node(qn)? {
        Some(n) => n,
        None => return Ok(None),
    };

    let file_path = match &node.file_path {
        Some(fp) => fp,
        None => return Ok(None),
    };

    let full_path = format!("{}/{}", repo_path, file_path);
    let content = fs::read_to_string(&full_path).map_err(|e| TokkitError::Io(e))?;
    let lines: Vec<&str> = content.lines().collect();

    let start = (node.line_start as usize).saturating_sub(1).saturating_sub(context_lines as usize);
    let end = (node.line_end as usize + context_lines as usize).min(lines.len());

    let snippet = lines[start..end].join("\n");
    let lang = file_path.rsplit('.').next().unwrap_or("").to_string();

    Ok(Some(CodeSnippet {
        qualified_name: node.qualified_name,
        file_path: file_path.clone(),
        line_start: start as u32 + 1,
        line_end: end as u32,
        content: snippet,
        language: lang,
    }))
}

/// Detect files changed since last index.
pub fn detect_changes(store: &Store, project: &str, repo_path: &str, files: &[FileInfo]) -> Result<Vec<ChangedFile>> {
    let mut changes = Vec::new();

    for file in files {
        let full_path = format!("{}/{}", repo_path, file.rel_path);
        let metadata = match fs::metadata(&full_path) {
            Ok(m) => m,
            Err(_) => {
                changes.push(ChangedFile {
                    path: file.rel_path.clone(),
                    change_type: "deleted".to_string(),
                });
                continue;
            }
        };

        let mtime_ns = metadata.modified()
            .map(|t| t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos() as i64)
            .unwrap_or(0);
        let size = metadata.len() as i64;

        match store.get_file_hash(project, &file.rel_path)? {
            Some((stored_mtime, stored_size)) => {
                if mtime_ns != stored_mtime || size != stored_size {
                    changes.push(ChangedFile {
                        path: file.rel_path.clone(),
                        change_type: "modified".to_string(),
                    });
                }
            }
            None => {
                changes.push(ChangedFile {
                    path: file.rel_path.clone(),
                    change_type: "added".to_string(),
                });
            }
        }
    }

    Ok(changes)
}

/// Get index status.
pub fn index_status(store: &Store) -> Result<StatusResult> {
    let node_count = store.node_count()?;
    let edge_count = store.edge_count()?;

    Ok(StatusResult {
        indexed: node_count > 0,
        project_name: None, // Filled by caller
        node_count,
        edge_count,
    })
}

/// Get graph schema (available labels and edge types).
pub fn get_graph_schema(store: &Store) -> Result<SchemaResult> {
    let nodes = store.all_nodes()?;
    let edges = store.all_edges()?;

    let mut labels: HashSet<String> = HashSet::new();
    let mut edge_types: HashSet<String> = HashSet::new();

    for n in &nodes {
        labels.insert(n.label.as_str().to_string());
    }
    for e in &edges {
        edge_types.insert(e.edge_type.as_str().to_string());
    }

    Ok(SchemaResult {
        node_labels: labels.into_iter().collect(),
        edge_types: edge_types.into_iter().collect(),
        node_count: nodes.len(),
        edge_count: edges.len(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graph::GraphBuffer;
    use std::collections::HashMap;

    fn setup_store() -> Store {
        let store = Store::open_memory().unwrap();
        let mut buf = GraphBuffer::new("test", "/tmp/repo");

        let id_a = buf.add_node(NodeLabel::Function, "authenticate", "test::auth.py::authenticate", Some("auth.py"), 10, 25);
        let id_b = buf.add_node(NodeLabel::Function, "get_user", "test::user.py::get_user", Some("user.py"), 5, 15);
        let id_c = buf.add_node(NodeLabel::Class, "UserService", "test::user.py::UserService", Some("user.py"), 1, 50);

        buf.add_edge(Edge {
            source_id: id_a,
            target_id: id_b,
            edge_type: EdgeType::Calls,
            confidence: Some(Confidence::IMPORT_MAP),
            properties: HashMap::new(),
        });

        store.write_graph(&buf).unwrap();
        store
    }

    #[test]
    fn search_by_name() {
        let store = setup_store();
        let results = search_nodes(&store, SearchFilters {
            query: Some("auth".to_string()),
            label: None,
            file_path: None,
            limit: None,
        }).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "authenticate");
    }

    #[test]
    fn search_by_label() {
        let store = setup_store();
        let results = search_nodes(&store, SearchFilters {
            query: None,
            label: Some(NodeLabel::Class),
            file_path: None,
            limit: None,
        }).unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "UserService");
    }

    #[test]
    fn get_callers_works() {
        let store = setup_store();
        let callers = get_callers(&store, "test::user.py::get_user").unwrap();
        assert_eq!(callers.len(), 1);
        assert_eq!(callers[0].0.name, "authenticate");
    }

    #[test]
    fn get_callees_works() {
        let store = setup_store();
        let callees = get_callees(&store, "test::auth.py::authenticate").unwrap();
        assert_eq!(callees.len(), 1);
        assert_eq!(callees[0].0.name, "get_user");
    }

    #[test]
    fn trace_path_finds_direct_connection() {
        let store = setup_store();
        let path = trace_path(&store, "test::auth.py::authenticate", "test::user.py::get_user", 5).unwrap();
        assert_eq!(path.len(), 2); // from + to
        assert_eq!(path[0].node.name, "authenticate");
        assert_eq!(path[1].node.name, "get_user");
    }

    #[test]
    fn trace_path_returns_empty_for_no_connection() {
        let store = setup_store();
        let path = trace_path(&store, "test::user.py::get_user", "test::auth.py::authenticate", 5).unwrap();
        assert!(path.is_empty()); // No reverse edge
    }

    #[test]
    fn schema_returns_used_labels_and_types() {
        let store = setup_store();
        let schema = get_graph_schema(&store).unwrap();
        assert!(schema.node_labels.contains(&"Function".to_string()));
        assert!(schema.node_labels.contains(&"Class".to_string()));
        assert!(schema.edge_types.contains(&"CALLS".to_string()));
    }
}
```

- [ ] **Step 2: Uncomment query in lib.rs, run tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/query/
git commit -m "feat(core): add typed query functions (search, trace, callers, snippet)"
```

---

## Task 9: Enrichment Module

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/enrich/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/enrich/tests.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/enrich/git_history.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/enrich/routes.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/enrich/similarity.rs`

This task covers 4 enrichment passes. Each is an independent function that takes a `&mut GraphBuffer` and adds edges/nodes. Tests for each pass verify the correct edges are created.

The implementation of each pass follows the patterns documented in the spec: test detection via file naming conventions, git history via `gix`, route detection via decorator property scanning, similarity via MinHash+LSH.

Full code for each enrichment pass would make this plan excessively long. The pattern for each is:

1. Write a failing test that creates a graph buffer with test data, calls the pass function, and asserts specific edges were created
2. Implement the pass function
3. Verify the test passes

Key signatures:

```rust
// enrich/mod.rs
pub mod tests_pass;
pub mod git_history;
pub mod routes;
pub mod similarity;

use crate::graph::GraphBuffer;
use crate::error::Result;

pub fn run_enrichment(buf: &mut GraphBuffer, repo_path: &str) -> Result<()> {
    tests_pass::detect_tests(buf);
    routes::find_routes(buf);
    similarity::compute_similarity(buf);
    // git_history runs only if repo_path is a git repo
    if std::path::Path::new(repo_path).join(".git").exists() {
        git_history::compute_co_changes(buf, repo_path)?;
    }
    Ok(())
}
```

- [ ] **Step 1: Write enrich/tests_pass.rs (test file detection)**

Matches test files to implementation files using patterns: `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.js`, `__tests__/` directory convention. Creates `TESTS_FILE` edges between File nodes.

- [ ] **Step 2: Write enrich/routes.rs (route detection)**

Scans nodes for decorator properties containing `route_path`/`route_method`. Creates `Route` nodes and `HANDLES` edges. Patterns: `@app.route`, `@router.get`, Express `app.get('/path', handler)`.

- [ ] **Step 3: Write enrich/similarity.rs (MinHash+LSH)**

K=64 hashes, 32 bands of 2 rows, Jaccard threshold 0.95. Normalizes AST leaf tokens into trigrams, computes MinHash signatures, groups by LSH band, emits `SIMILAR_TO` edges for pairs above threshold.

- [ ] **Step 4: Write enrich/git_history.rs (co-change coupling)**

Uses `gix` to walk 1 year / 10K commits of history. Counts file pair co-occurrences. Skips commits with >20 files. Creates `CO_CHANGED` edges where coupling score >= 0.3 and co-changes >= 3.

- [ ] **Step 5: Write enrich/mod.rs, run all tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/enrich/
git commit -m "feat(core): add enrichment passes (tests, routes, similarity, git history)"
```

---

## Task 10: Pipeline Module

**Files:**
- Create: `tokkit/core/code/crates/tokkit-core/src/pipeline/mod.rs`
- Create: `tokkit/core/code/crates/tokkit-core/src/pipeline/incremental.rs`
- Modify: `tokkit/core/code/crates/tokkit-core/src/lib.rs` (final public API)

- [ ] **Step 1: Write pipeline/mod.rs — the orchestrator**

```rust
// tokkit/core/code/crates/tokkit-core/src/pipeline/mod.rs
pub mod incremental;

use crate::discover;
use crate::enrich;
use crate::extract::{self, spec_for_language};
use crate::graph::GraphBuffer;
use crate::graph::merge::merge_into;
use crate::resolve::{self, Registry};
use crate::store::Store;
use crate::types::*;
use crate::error::{Result, TokkitError};
use rayon::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

static PIPELINE_BUSY: AtomicBool = AtomicBool::new(false);

/// Try to acquire the pipeline lock. Returns false if already running.
pub fn try_lock() -> bool {
    !PIPELINE_BUSY.swap(true, Ordering::SeqCst)
}

/// Release the pipeline lock.
pub fn unlock() {
    PIPELINE_BUSY.store(false, Ordering::SeqCst);
}

/// Run the full indexing pipeline on a repository.
pub fn run(repo_path: &str, db_path: &str, mode: IndexMode) -> Result<IndexResult> {
    let start = Instant::now();
    let project_name = project_name_from_path(repo_path);

    // Phase 1: Discover files
    let files = discover::discover(repo_path, mode)?;
    if files.is_empty() {
        return Ok(IndexResult {
            project_name,
            node_count: 0,
            edge_count: 0,
            elapsed_ms: start.elapsed().as_millis() as u64,
        });
    }

    // Phase 2: Check for incremental
    if std::path::Path::new(db_path).exists() {
        if let Ok(store) = Store::open(db_path) {
            if let Some(result) = incremental::try_incremental(&store, &project_name, repo_path, &files, mode)? {
                return Ok(IndexResult {
                    project_name,
                    node_count: result.0,
                    edge_count: result.1,
                    elapsed_ms: start.elapsed().as_millis() as u64,
                });
            }
        }
        // Delete stale DB for fresh reindex
        let _ = std::fs::remove_file(db_path);
    }

    // Phase 3: Build graph buffer
    let mut gbuf = GraphBuffer::new(&project_name, repo_path);

    // Phase 4: Structure pass
    build_structure(&mut gbuf, &project_name, &files);

    // Phase 5: Extract (parallel)
    let file_results = extract_parallel(&files, &project_name)?;

    // Phase 6: Build registry + add definition nodes
    let mut registry = Registry::new();
    for (file_info, file_result) in files.iter().zip(file_results.iter()) {
        for def in &file_result.definitions {
            let id = gbuf.add_node(
                def.label,
                &def.name,
                &def.qualified_name,
                Some(&file_info.rel_path),
                def.line_start,
                def.line_end,
            );
            registry.register(&def.qualified_name, def.label);

            // CONTAINS_FILE edge from file to definition
            let file_qn = format!("{}::{}::__file__", project_name, file_info.rel_path);
            if let Some(file_node) = gbuf.find_by_qn(&file_qn) {
                let file_id = file_node.id;
                gbuf.add_edge(Edge {
                    source_id: file_id,
                    target_id: id,
                    edge_type: EdgeType::ContainsFile,
                    confidence: None,
                    properties: std::collections::HashMap::new(),
                });
            }
        }
    }

    // Phase 7: Resolve references
    for (file_info, file_result) in files.iter().zip(file_results.iter()) {
        for call in &file_result.calls {
            if let Some(resolution) = resolve::resolve(
                &call.callee_name,
                &file_info.rel_path,
                call.enclosing_qn.as_deref(),
                &project_name,
                &file_result.imports,
                &registry,
            ) {
                // Find source and target node IDs
                let source_qn = call.enclosing_qn.as_deref().unwrap_or(
                    &format!("{}::{}::__file__", project_name, file_info.rel_path)
                );
                if let (Some(src), Some(tgt)) = (
                    gbuf.find_by_qn(source_qn).map(|n| n.id),
                    gbuf.find_by_qn(&resolution.target_qn).map(|n| n.id),
                ) {
                    gbuf.add_edge(Edge {
                        source_id: src,
                        target_id: tgt,
                        edge_type: EdgeType::Calls,
                        confidence: Some(resolution.confidence),
                        properties: {
                            let mut p = std::collections::HashMap::new();
                            p.insert("strategy".to_string(), resolution.strategy.to_string());
                            p
                        },
                    });
                }
            }
        }
    }

    // Phase 8: Enrichment
    enrich::run_enrichment(&mut gbuf, repo_path)?;

    // Phase 9: Persist
    let store = Store::open(db_path)?;
    store.write_graph(&gbuf)?;

    // Persist file hashes for incremental
    let hashes: Vec<(String, i64, i64)> = files.iter().filter_map(|f| {
        let meta = std::fs::metadata(&f.path).ok()?;
        let mtime = meta.modified().ok()?
            .duration_since(std::time::UNIX_EPOCH).ok()?
            .as_nanos() as i64;
        Some((f.rel_path.clone(), mtime, meta.len() as i64))
    }).collect();
    store.write_file_hashes(&project_name, &hashes)?;

    let node_count = gbuf.node_count();
    let edge_count = gbuf.edge_count();

    Ok(IndexResult {
        project_name,
        node_count,
        edge_count,
        elapsed_ms: start.elapsed().as_millis() as u64,
    })
}

/// Build Project/Folder/File nodes and containment edges.
fn build_structure(gbuf: &mut GraphBuffer, project_name: &str, files: &[FileInfo]) {
    gbuf.add_node(NodeLabel::Project, project_name, project_name, None, 0, 0);

    let mut seen_dirs: std::collections::HashSet<String> = std::collections::HashSet::new();

    for file in files {
        // File node
        let file_qn = format!("{project_name}::{}::__file__", file.rel_path);
        let basename = file.rel_path.rsplit('/').next().unwrap_or(&file.rel_path);
        let file_id = gbuf.add_node(
            NodeLabel::File, basename, &file_qn, Some(&file.rel_path), 0, 0,
        );

        // Directory chain
        let dir = file.rel_path.rsplit_once('/').map(|(d, _)| d.to_string()).unwrap_or_default();
        let parent_qn = if dir.is_empty() {
            project_name.to_string()
        } else {
            create_folder_chain(gbuf, project_name, &dir, &mut seen_dirs)
        };

        // CONTAINS_FILE edge
        if let Some(parent) = gbuf.find_by_qn(&parent_qn) {
            let parent_id = parent.id;
            gbuf.add_edge(Edge {
                source_id: parent_id,
                target_id: file_id,
                edge_type: EdgeType::ContainsFile,
                confidence: None,
                properties: std::collections::HashMap::new(),
            });
        }
    }
}

fn create_folder_chain(
    gbuf: &mut GraphBuffer,
    project_name: &str,
    dir: &str,
    seen: &mut std::collections::HashSet<String>,
) -> String {
    let folder_qn = format!("{project_name}::__folder__::{dir}");

    if seen.contains(dir) {
        return folder_qn;
    }
    seen.insert(dir.to_string());

    let basename = dir.rsplit('/').next().unwrap_or(dir);
    let folder_id = gbuf.add_node(NodeLabel::Folder, basename, &folder_qn, Some(dir), 0, 0);

    // Parent
    let parent_qn = if let Some((parent_dir, _)) = dir.rsplit_once('/') {
        create_folder_chain(gbuf, project_name, parent_dir, seen)
    } else {
        project_name.to_string()
    };

    if let Some(parent) = gbuf.find_by_qn(&parent_qn) {
        let parent_id = parent.id;
        gbuf.add_edge(Edge {
            source_id: parent_id,
            target_id: folder_id,
            edge_type: EdgeType::ContainsFolder,
            confidence: None,
            properties: std::collections::HashMap::new(),
        });
    }

    folder_qn
}

/// Extract all files in parallel using rayon.
fn extract_parallel(files: &[FileInfo], project_name: &str) -> Result<Vec<FileResult>> {
    let results: Vec<Result<FileResult>> = files
        .par_iter()
        .map(|file| {
            let source = std::fs::read_to_string(&file.path)?;
            let spec = spec_for_language(file.language);
            extract::extract_file(&source, &file.rel_path, project_name, spec)
        })
        .collect();

    results.into_iter().collect()
}

fn project_name_from_path(path: &str) -> String {
    std::path::Path::new(path)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn create_mini_repo() -> TempDir {
        let dir = TempDir::new().unwrap();
        let root = dir.path();

        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("src/main.py"), r#"
from src.utils import helper

def main():
    result = helper()
    return result
"#).unwrap();

        fs::write(root.join("src/utils.py"), r#"
def helper():
    return 42
"#).unwrap();

        dir
    }

    #[test]
    fn pipeline_indexes_small_repo() {
        let repo = create_mini_repo();
        let db_dir = TempDir::new().unwrap();
        let db_path = db_dir.path().join("test.redb");

        let result = run(
            repo.path().to_str().unwrap(),
            db_path.to_str().unwrap(),
            IndexMode::Full,
        ).unwrap();

        assert!(result.node_count > 0);
        assert!(result.edge_count > 0);
        assert!(result.elapsed_ms < 30_000); // Should be fast

        // Verify store has data
        let store = Store::open(db_path.to_str().unwrap()).unwrap();
        assert!(store.node_count().unwrap() > 0);
    }

    #[test]
    fn pipeline_creates_structure_nodes() {
        let repo = create_mini_repo();
        let db_dir = TempDir::new().unwrap();
        let db_path = db_dir.path().join("test.redb");

        run(
            repo.path().to_str().unwrap(),
            db_path.to_str().unwrap(),
            IndexMode::Full,
        ).unwrap();

        let store = Store::open(db_path.to_str().unwrap()).unwrap();
        let nodes = store.all_nodes().unwrap();

        let labels: Vec<_> = nodes.iter().map(|n| n.label).collect();
        assert!(labels.contains(&NodeLabel::Project));
        assert!(labels.contains(&NodeLabel::Folder));
        assert!(labels.contains(&NodeLabel::File));
        assert!(labels.contains(&NodeLabel::Function));
    }
}
```

- [ ] **Step 2: Write pipeline/incremental.rs stub**

```rust
// tokkit/core/code/crates/tokkit-core/src/pipeline/incremental.rs
use crate::store::Store;
use crate::types::*;
use crate::error::Result;

/// Try to run an incremental index. Returns Some((node_count, edge_count)) if
/// successful, None if a full reindex is needed.
pub fn try_incremental(
    _store: &Store,
    _project: &str,
    _repo_path: &str,
    _files: &[FileInfo],
    _mode: IndexMode,
) -> Result<Option<(usize, usize)>> {
    // TODO: implement incremental indexing
    // For now, always fall through to full reindex
    Ok(None)
}
```

- [ ] **Step 3: Finalize lib.rs with all modules**

```rust
// tokkit/core/code/crates/tokkit-core/src/lib.rs
pub mod types;
pub mod error;
pub mod discover;
pub mod extract;
pub mod graph;
pub mod resolve;
pub mod store;
pub mod query;
pub mod pipeline;
pub mod enrich;

pub use error::{Result, TokkitError};
pub use types::*;
```

- [ ] **Step 4: Run all tests**

Run: `cd tokkit/core/code && cargo test --workspace`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add tokkit/core/code/crates/tokkit-core/src/pipeline/
git add tokkit/core/code/crates/tokkit-core/src/lib.rs
git commit -m "feat(core): add pipeline orchestrator with parallel extraction"
```

---

## Task 11: Integration Tests with Fixture Repos

**Files:**
- Create: `tokkit/core/code/tests/integration_python.rs`
- Create: `tokkit/core/code/tests/integration_js.rs`
- Create: `tokkit/core/code/tests/integration_ts.rs`
- Create: `tokkit/core/code/tests/fixtures/python_project/` (multiple .py files)
- Create: `tokkit/core/code/tests/fixtures/js_project/` (multiple .js files)
- Create: `tokkit/core/code/tests/fixtures/ts_project/` (multiple .ts files)

- [ ] **Step 1: Create Python fixture project**

```
fixtures/python_project/
├── src/
│   ├── main.py         # imports auth, user; calls authenticate(), get_user()
│   ├── auth.py          # class AuthService with login(), logout(), authenticate()
│   ├── user.py          # class UserService with get_user(), create_user()
│   └── utils.py         # helper functions: format_response(), validate_input()
├── tests/
│   └── test_auth.py     # tests for AuthService
└── config.py            # configuration constants
```

Each file should be small (10-20 lines) but contain real patterns: imports, classes, methods, function calls, decorators.

- [ ] **Step 2: Create JS fixture project**

```
fixtures/js_project/
├── src/
│   ├── index.js          # Express app setup, imports routes
│   ├── routes/
│   │   ├── auth.js       # router.post('/login', handler), router.get('/logout', handler)
│   │   └── users.js      # router.get('/users', handler), router.post('/users', handler)
│   ├── services/
│   │   ├── authService.js
│   │   └── userService.js
│   └── utils.js
└── tests/
    └── auth.test.js
```

- [ ] **Step 3: Create TS fixture project**

```
fixtures/ts_project/
├── src/
│   ├── index.ts
│   ├── types.ts           # interfaces: User, AuthToken, Config
│   ├── services/
│   │   ├── auth.service.ts
│   │   └── user.service.ts
│   └── utils/
│       └── helpers.ts
└── tests/
    └── auth.service.spec.ts
```

- [ ] **Step 4: Write integration_python.rs**

```rust
// tokkit/core/code/tests/integration_python.rs
use tokkit_core::pipeline;
use tokkit_core::store::Store;
use tokkit_core::types::*;
use tokkit_core::query;
use tempfile::TempDir;

fn fixture_path() -> String {
    format!("{}/tests/fixtures/python_project", env!("CARGO_MANIFEST_DIR"))
}

#[test]
fn indexes_python_project() {
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    let result = pipeline::run(
        &fixture_path(),
        db_path.to_str().unwrap(),
        IndexMode::Full,
    ).unwrap();

    assert!(result.node_count >= 10, "Expected at least 10 nodes, got {}", result.node_count);
    assert!(result.edge_count >= 5, "Expected at least 5 edges, got {}", result.edge_count);
}

#[test]
fn finds_functions_and_classes() {
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    pipeline::run(&fixture_path(), db_path.to_str().unwrap(), IndexMode::Full).unwrap();
    let store = Store::open(db_path.to_str().unwrap()).unwrap();

    // Should find AuthService class
    let classes = query::search_nodes(&store, SearchFilters {
        query: Some("AuthService".to_string()),
        label: Some(NodeLabel::Class),
        file_path: None,
        limit: None,
    }).unwrap();
    assert!(!classes.is_empty(), "Should find AuthService class");

    // Should find functions
    let funcs = query::search_nodes(&store, SearchFilters {
        query: None,
        label: Some(NodeLabel::Function),
        file_path: None,
        limit: None,
    }).unwrap();
    assert!(funcs.len() >= 3, "Should find at least 3 functions");
}

#[test]
fn resolves_cross_file_calls() {
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    pipeline::run(&fixture_path(), db_path.to_str().unwrap(), IndexMode::Full).unwrap();
    let store = Store::open(db_path.to_str().unwrap()).unwrap();

    let edges = store.all_edges().unwrap();
    let call_edges: Vec<_> = edges.iter().filter(|e| e.edge_type == EdgeType::Calls).collect();

    assert!(!call_edges.is_empty(), "Should have CALLS edges from cross-file resolution");

    // At least some should have high confidence
    let high_conf: Vec<_> = call_edges.iter()
        .filter(|e| e.confidence.map_or(false, |c| c.value() >= 0.7))
        .collect();
    assert!(!high_conf.is_empty(), "Should have high-confidence call edges");
}
```

- [ ] **Step 5: Write integration_js.rs and integration_ts.rs**

Same pattern as Python: index fixture, verify node counts, verify edge types, verify resolution.

- [ ] **Step 6: Run all tests**

Run: `cd tokkit/core/code && cargo test --workspace -- --include-ignored`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add tokkit/core/code/tests/
git commit -m "test(core): add integration tests with Python, JS, TS fixture repos"
```

---

## Task 12: Final Cleanup and Verification

- [ ] **Step 1: Run full test suite**

Run: `cd tokkit/core/code && cargo test --workspace 2>&1`
Expected: All tests pass, no warnings.

- [ ] **Step 2: Run clippy**

Run: `cd tokkit/core/code && cargo clippy --workspace -- -D warnings`
Expected: No warnings.

- [ ] **Step 3: Verify the public API surface is clean**

Check that `lib.rs` re-exports only what the PyO3 bindings will need: `pipeline::run`, `store::Store`, `query::*`, `types::*`.

- [ ] **Step 4: Final commit**

```bash
git add -A tokkit/core/code/
git commit -m "chore(core): final cleanup, clippy clean, all tests passing"
```
