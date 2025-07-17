use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use serde::Serialize;
use tokkit_core::error::TokkitError;
use tokkit_core::types::{
    ArchSummary, IndexMode, NodeLabel, SearchFilters, StatusResult,
};
use tokkit_core::{discover, pipeline, query, store::Store};

// --- Helpers ---

fn to_py_err(e: TokkitError) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

fn to_json<T: Serialize>(val: &T) -> PyResult<String> {
    serde_json::to_string(val).map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

fn parse_label(s: &str) -> Option<NodeLabel> {
    match s {
        "Project" => Some(NodeLabel::Project),
        "Folder" => Some(NodeLabel::Folder),
        "File" => Some(NodeLabel::File),
        "Function" => Some(NodeLabel::Function),
        "Method" => Some(NodeLabel::Method),
        "Class" => Some(NodeLabel::Class),
        "Interface" => Some(NodeLabel::Interface),
        "Struct" => Some(NodeLabel::Struct),
        "Enum" => Some(NodeLabel::Enum),
        "Variable" => Some(NodeLabel::Variable),
        "Route" => Some(NodeLabel::Route),
        "Test" => Some(NodeLabel::Test),
        _ => None,
    }
}

// --- Functions ---

#[pyfunction]
#[pyo3(signature = (path, mode = "full"))]
fn index_repository(path: &str, mode: &str) -> PyResult<String> {
    let index_mode = match mode {
        "fast" => IndexMode::Fast,
        _ => IndexMode::Full,
    };

    let project_name = pipeline::project_name_from_path(path);
    let db_dir = format!("/tmp/tokkit");
    std::fs::create_dir_all(&db_dir)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    let db_path = format!("{}/{}.redb", db_dir, project_name);

    if !pipeline::try_lock() {
        return Err(to_py_err(TokkitError::PipelineBusy));
    }
    let result = pipeline::run(path, &db_path, index_mode);
    pipeline::unlock();

    let result = result.map_err(to_py_err)?;
    to_json(&result)
}

#[pyfunction]
#[pyo3(signature = (db_path, query, label = None, limit = None, name_pattern = None, max_degree = None, exclude_entry_points = None, relationship = None))]
fn search_nodes(
    db_path: &str,
    query: &str,
    label: Option<&str>,
    limit: Option<u32>,
    name_pattern: Option<String>,
    max_degree: Option<u32>,
    exclude_entry_points: Option<bool>,
    relationship: Option<String>,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let filters = SearchFilters {
        query: Some(query.to_string()),
        label: label.and_then(parse_label),
        file_path: None,
        limit,
        name_pattern,
        max_degree,
        exclude_entry_points,
        relationship,
    };
    let nodes = query::search_nodes(&store, &filters).map_err(to_py_err)?;
    to_json(&nodes)
}

#[pyfunction]
#[pyo3(signature = (db_path, from_qn, to_qn, max_depth = None))]
fn trace_path(
    db_path: &str,
    from_qn: &str,
    to_qn: &str,
    max_depth: Option<u32>,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let depth = max_depth.unwrap_or(5);
    let path = query::trace_path(&store, from_qn, to_qn, depth).map_err(to_py_err)?;
    to_json(&path)
}

#[pyfunction]
#[pyo3(signature = (db_path, function_name, direction = "both", depth = 3))]
fn trace_fan(
    db_path: &str,
    function_name: &str,
    direction: &str,
    depth: u32,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let path = query::trace_fan(&store, function_name, direction, depth).map_err(to_py_err)?;
    to_json(&path)
}

#[pyfunction]
#[pyo3(signature = (db_path, function_name, repo_path, direction = "both", depth = 3, include_body = false))]
fn trace_fan_with_body(
    db_path: &str,
    function_name: &str,
    repo_path: &str,
    direction: &str,
    depth: u32,
    include_body: bool,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let steps = query::trace_fan_with_body(&store, function_name, direction, depth, repo_path, include_body)
        .map_err(to_py_err)?;
    to_json(&steps)
}

#[pyfunction]
#[pyo3(signature = (db_path, qualified_name, repo_path, context_lines = None))]
fn get_snippet(
    db_path: &str,
    qualified_name: &str,
    repo_path: &str,
    context_lines: Option<u32>,
) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let ctx = context_lines.unwrap_or(3);
    let snippet = query::get_snippet(&store, qualified_name, repo_path, ctx).map_err(to_py_err)?;
    to_json(&snippet)
}

#[pyfunction]
fn get_architecture(db_path: &str, project: &str) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let nodes = store.all_nodes().map_err(to_py_err)?;
    let edges = store.all_edges().map_err(to_py_err)?;

    let mut languages: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut top_files: Vec<String> = Vec::new();
    let mut packages: std::collections::HashSet<String> = std::collections::HashSet::new();

    for node in &nodes {
        if let Some(fp) = &node.file_path {
            if let Some(ext) = std::path::Path::new(fp).extension() {
                let lang = match ext.to_str().unwrap_or("") {
                    "py" => "Python",
                    "js" => "JavaScript",
                    "ts" | "tsx" => "TypeScript",
                    _ => "",
                };
                if !lang.is_empty() {
                    languages.insert(lang.to_string());
                }
            }
            if node.label == tokkit_core::types::NodeLabel::File {
                top_files.push(fp.clone());
            }
            if let Some(dir) = std::path::Path::new(fp).parent() {
                let dir_str = dir.to_string_lossy().to_string();
                if !dir_str.is_empty() {
                    packages.insert(dir_str);
                }
            }
        }
    }

    top_files.sort();
    top_files.dedup();
    top_files.truncate(20);

    let mut lang_vec: Vec<String> = languages.into_iter().collect();
    lang_vec.sort();

    let mut pkg_vec: Vec<String> = packages.into_iter().collect();
    pkg_vec.sort();

    let summary = ArchSummary {
        project_name: project.to_string(),
        languages: lang_vec,
        top_files,
        entry_points: Vec::new(),
        packages: pkg_vec,
        summary: format!(
            "{} nodes, {} edges",
            nodes.len(),
            edges.len()
        ),
    };
    to_json(&summary)
}

#[pyfunction]
#[pyo3(signature = (db_path, repo_path, pattern, limit = None))]
fn search_code(
    db_path: &str,
    repo_path: &str,
    pattern: &str,
    limit: Option<u32>,
) -> PyResult<String> {
    let _ = (db_path, repo_path, pattern, limit);
    let results: Vec<tokkit_core::types::CodeMatch> = Vec::new();
    to_json(&results)
}

#[pyfunction]
fn detect_changes(db_path: &str, repo_path: &str) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let project_name = pipeline::project_name_from_path(repo_path);
    let files = discover::discover(repo_path, IndexMode::Full).map_err(to_py_err)?;
    let changed =
        query::detect_changes(&store, &project_name, repo_path, &files).map_err(to_py_err)?;
    to_json(&changed)
}

#[pyfunction]
fn index_status(db_path: &str) -> PyResult<String> {
    if !std::path::Path::new(db_path).exists() {
        let status = StatusResult {
            indexed: false,
            project_name: None,
            node_count: 0,
            edge_count: 0,
        };
        return to_json(&status);
    }
    let store = Store::open(db_path).map_err(to_py_err)?;
    let status = query::index_status(&store).map_err(to_py_err)?;
    to_json(&status)
}

#[pyfunction]
fn delete_project(db_path: &str) -> PyResult<bool> {
    let path = std::path::Path::new(db_path);
    if path.exists() {
        std::fs::remove_file(path).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        Ok(true)
    } else {
        Ok(false)
    }
}

#[pyfunction]
fn list_projects(cache_dir: &str) -> PyResult<String> {
    let dir = std::path::Path::new(cache_dir);
    let mut projects: Vec<tokkit_core::types::ProjectInfo> = Vec::new();

    if !dir.exists() {
        return to_json(&projects);
    }

    let entries = std::fs::read_dir(dir)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    for entry in entries {
        let entry = entry.map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("redb") {
            continue;
        }
        let db_path = path.to_string_lossy().to_string();
        let name = path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| db_path.clone());

        let (node_count, edge_count) = if let Ok(store) = Store::open(&db_path) {
            let nc = store.node_count().unwrap_or(0);
            let ec = store.edge_count().unwrap_or(0);
            (nc, ec)
        } else {
            (0, 0)
        };

        projects.push(tokkit_core::types::ProjectInfo {
            name,
            db_path,
            node_count,
            edge_count,
        });
    }

    to_json(&projects)
}

#[pyfunction]
fn get_graph_schema(db_path: &str) -> PyResult<String> {
    let store = Store::open(db_path).map_err(to_py_err)?;
    let schema = query::get_graph_schema(&store).map_err(to_py_err)?;
    to_json(&schema)
}

#[pyfunction]
fn manage_adr(db_path: &str, action: &str, args: &str) -> PyResult<String> {
    let _ = (db_path, action, args);
    Ok("{}".to_string())
}

// --- Module ---

#[pymodule]
fn tokkit_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(index_repository, m)?)?;
    m.add_function(wrap_pyfunction!(search_nodes, m)?)?;
    m.add_function(wrap_pyfunction!(trace_path, m)?)?;
    m.add_function(wrap_pyfunction!(trace_fan, m)?)?;
    m.add_function(wrap_pyfunction!(trace_fan_with_body, m)?)?;
    m.add_function(wrap_pyfunction!(get_snippet, m)?)?;
    m.add_function(wrap_pyfunction!(get_architecture, m)?)?;
    m.add_function(wrap_pyfunction!(search_code, m)?)?;
    m.add_function(wrap_pyfunction!(detect_changes, m)?)?;
    m.add_function(wrap_pyfunction!(index_status, m)?)?;
    m.add_function(wrap_pyfunction!(delete_project, m)?)?;
    m.add_function(wrap_pyfunction!(list_projects, m)?)?;
    m.add_function(wrap_pyfunction!(get_graph_schema, m)?)?;
    m.add_function(wrap_pyfunction!(manage_adr, m)?)?;
    Ok(())
// rev-16
}
