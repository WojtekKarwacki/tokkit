pub mod incremental;

use std::collections::HashSet;
use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

use rayon::prelude::*;

use crate::discover;
use crate::enrich;
use crate::extract;
use crate::graph::GraphBuffer;
use crate::resolve::{Registry, resolve};
use crate::store::Store;
use crate::error::{Result, TokkitError};
use crate::types::*;

static PIPELINE_BUSY: AtomicBool = AtomicBool::new(false);

pub fn try_lock() -> bool {
    PIPELINE_BUSY
        .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
        .is_ok()
}

pub fn unlock() {
    PIPELINE_BUSY.store(false, Ordering::Release);
}

pub fn run(repo_path: &str, db_path: &str, mode: IndexMode) -> Result<IndexResult> {
    let start = Instant::now();

    let project_name = project_name_from_path(repo_path);

    // Discover files
    let files = discover::discover(repo_path, mode)?;

    if files.is_empty() {
        return Ok(IndexResult {
            project_name,
            node_count: 0,
            edge_count: 0,
            elapsed_ms: start.elapsed().as_millis() as u64,
        });
    }

    // Incremental check
    if Path::new(db_path).exists() {
        let store = Store::open(db_path)?;
        match incremental::try_incremental(&store, &project_name, repo_path, &files, mode)? {
            Some((node_count, edge_count)) => {
                return Ok(IndexResult {
                    project_name,
                    node_count,
                    edge_count,
                    elapsed_ms: start.elapsed().as_millis() as u64,
                });
            }
            None => {
                drop(store);
                std::fs::remove_file(db_path).map_err(TokkitError::Io)?;
            }
        }
    }

    // Build main graph buffer
    let mut gbuf = GraphBuffer::new(&project_name, repo_path);

    // Structure pass: Project/Folder/File nodes
    build_structure(&mut gbuf, &project_name, &files);

    // Parallel extraction
    let file_results = extract_parallel(&files, &project_name)?;

    // Build registry from all definitions
    let mut registry = Registry::new();
    for (file_info, file_result) in files.iter().zip(file_results.iter()) {
        for def in &file_result.definitions {
            registry.register(&def.qualified_name, def.label);

            // Add definition node to graph buffer
            let file_qn = format!("{}::{}::__file__", project_name, file_info.rel_path);
            let def_id = gbuf.add_node(
                def.label,
                &def.name,
                &def.qualified_name,
                Some(file_info.rel_path.clone()),
                def.line_start,
                def.line_end,
            );
            let file_node_id = gbuf.find_by_qn(&file_qn).map(|n| n.id);
            if let Some(file_id) = file_node_id {
                gbuf.add_edge(Edge {
                    source_id: file_id,
                    target_id: def_id,
                    edge_type: EdgeType::ContainsFile,
                    confidence: None,
                    properties: HashMap::new(),
                });
            }
        }
    }

    // Apply route hints to definition nodes
    for (_file_info, file_result) in files.iter().zip(file_results.iter()) {
        for hint in &file_result.route_hints {
            let target_qn: Option<String> = if !hint.def_qn.is_empty() {
                Some(hint.def_qn.clone())
            } else if !hint.handler_name.is_empty() {
                // Express-style: find function by name across the project
                gbuf.nodes()
                    .iter()
                    .find(|n| {
                        n.name == hint.handler_name
                            && (n.label == NodeLabel::Function || n.label == NodeLabel::Method)
                    })
                    .map(|n| n.qualified_name.clone())
            } else {
                None
            };

            if let Some(qn) = target_qn {
                gbuf.set_node_property(&qn, "route_path", &hint.route_path);
                // Append method (comma-separated for multi-method routes like Flask)
                let existing_method = gbuf
                    .find_by_qn(&qn)
                    .and_then(|n| n.properties.get("route_method").cloned())
                    .unwrap_or_default();
                let method = if existing_method.is_empty() {
                    hint.route_method.clone()
                } else if existing_method.contains(&hint.route_method) {
                    existing_method // already has this method
                } else {
                    format!("{},{}", existing_method, hint.route_method)
                };
                gbuf.set_node_property(&qn, "route_method", &method);
            }
        }
    }

    // Resolve references and create CALLS edges
    for (file_info, file_result) in files.iter().zip(file_results.iter()) {
        for call in &file_result.calls {
            let caller_qn = match &call.enclosing_qn {
                Some(qn) => qn.clone(),
                None => format!("{}::{}::__file__", project_name, file_info.rel_path),
            };

            let resolution = resolve(
                &call.callee_name,
                &file_info.rel_path,
                &caller_qn,
                &project_name,
                &file_result.imports,
                &registry,
            );

            if let Some(res) = resolution {
                let src_id = gbuf.find_by_qn(&caller_qn).map(|n| n.id);
                let tgt_id = gbuf.find_by_qn(&res.target_qn).map(|n| n.id);

                if let (Some(src), Some(tgt)) = (src_id, tgt_id) {
                    gbuf.add_edge(Edge {
                        source_id: src,
                        target_id: tgt,
                        edge_type: EdgeType::Calls,
                        confidence: Some(res.confidence),
                        properties: HashMap::new(),
                    });
                }
            }
        }
    }

    // Enrichment
    enrich::run_enrichment(&mut gbuf, repo_path)?;

    // Persist
    let store = Store::open(db_path)?;
    store.write_graph(&gbuf)?;

    // File hashes
    let mut hashes: Vec<(String, i64, i64)> = Vec::new();
    for file_info in &files {
        if let Ok(meta) = std::fs::metadata(&file_info.path) {
            let mtime = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs() as i64)
                .unwrap_or(0);
            let size = meta.len() as i64;
            hashes.push((file_info.rel_path.clone(), mtime, size));
        }
    }
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

pub fn project_name_from_path(path: &str) -> String {
    Path::new(path)
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string())
}

fn build_structure(gbuf: &mut GraphBuffer, project_name: &str, files: &[FileInfo]) {
    let project_qn = project_name.to_string();
    gbuf.add_node(NodeLabel::Project, project_name, &project_qn, None, 0, 0);

    let mut seen_dirs: HashSet<String> = HashSet::new();

    for file_info in files {
        let file_qn = format!("{}::{}::__file__", project_name, file_info.rel_path);
        let basename = Path::new(&file_info.rel_path)
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_else(|| file_info.rel_path.clone());

        let file_id = gbuf.add_node(
            NodeLabel::File,
            &basename,
            &file_qn,
            Some(file_info.path.clone()),
            0,
            0,
        );

        // Get the parent directory
        let parent_dir = Path::new(&file_info.rel_path)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();

        let folder_qn = create_folder_chain(gbuf, project_name, &parent_dir, &mut seen_dirs);

        if let Some(folder_node) = gbuf.find_by_qn(&folder_qn) {
            let folder_id = folder_node.id;
            gbuf.add_edge(Edge {
                source_id: folder_id,
                target_id: file_id,
                edge_type: EdgeType::ContainsFile,
                confidence: None,
                properties: HashMap::new(),
            });
        }
    }
}

fn create_folder_chain(
    gbuf: &mut GraphBuffer,
    project_name: &str,
    dir: &str,
    seen_dirs: &mut HashSet<String>,
) -> String {
    if dir.is_empty() {
        // Root folder — represented by the project node
        return project_name.to_string();
    }

    let folder_qn = format!("{}::__folder__::{}", project_name, dir);

    if seen_dirs.contains(&folder_qn) {
        return folder_qn;
    }

    let folder_name = Path::new(dir)
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| dir.to_string());

    let folder_id = gbuf.add_node(NodeLabel::Folder, &folder_name, &folder_qn, None, 0, 0);
    seen_dirs.insert(folder_qn.clone());

    // Create parent chain
    let parent_dir = Path::new(dir)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();

    let parent_qn = create_folder_chain(gbuf, project_name, &parent_dir, seen_dirs);

    if let Some(parent_node) = gbuf.find_by_qn(&parent_qn) {
        let parent_id = parent_node.id;
        gbuf.add_edge(Edge {
            source_id: parent_id,
            target_id: folder_id,
            edge_type: EdgeType::ContainsFolder,
            confidence: None,
            properties: HashMap::new(),
        });
    }

    folder_qn
}

fn extract_parallel(files: &[FileInfo], project_name: &str) -> Result<Vec<FileResult>> {
    let results: Vec<Result<FileResult>> = files
        .par_iter()
        .map(|file_info| {
            let source = std::fs::read_to_string(&file_info.path)?;
            let spec = extract::spec_for_language(file_info.language);
            let file_result =
                extract::extract_file(&source, &file_info.rel_path, project_name, spec)?;

            // Merge worker buffer into file result
            Ok(file_result)
        })
        .collect();

    results.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn create_test_repo(dir: &TempDir) {
        fs::create_dir_all(dir.path().join("src")).unwrap();

        fs::write(
            dir.path().join("src/utils.py"),
            "def helper():\n    return 42\n",
        )
        .unwrap();

        fs::write(
            dir.path().join("src/main.py"),
            "from src.utils import helper\n\ndef main():\n    result = helper()\n    return result\n",
        )
        .unwrap();
    }

    #[test]
    fn pipeline_indexes_small_repo() {
        let repo_dir = TempDir::new().unwrap();
        create_test_repo(&repo_dir);

        let db_dir = TempDir::new().unwrap();
        let db_path = db_dir.path().join("test.redb");

        let result = run(
            repo_dir.path().to_str().unwrap(),
            db_path.to_str().unwrap(),
            IndexMode::Full,
        )
        .unwrap();

        assert!(result.node_count > 0, "Expected node_count > 0");
        assert!(result.edge_count > 0, "Expected edge_count > 0");
        assert!(
            result.elapsed_ms < 30000,
            "Expected elapsed_ms < 30000, got {}",
            result.elapsed_ms
        );
    }

    #[test]
    fn pipeline_detects_fastapi_routes() {
        let repo_dir = TempDir::new().unwrap();
        fs::create_dir_all(repo_dir.path().join("app")).unwrap();

        fs::write(
            repo_dir.path().join("app/main.py"),
            r#"from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
async def list_users():
    return []

@app.post("/users")
async def create_user():
    return {}
"#,
        )
        .unwrap();

        let db_dir = TempDir::new().unwrap();
        let db_path = db_dir.path().join("test.redb");

        run(
            repo_dir.path().to_str().unwrap(),
            db_path.to_str().unwrap(),
            IndexMode::Full,
        )
        .unwrap();

        let store = Store::open(db_path.to_str().unwrap()).unwrap();
        let nodes = store.all_nodes().unwrap();

        let route_nodes: Vec<_> = nodes.iter().filter(|n| n.label == NodeLabel::Route).collect();
        assert!(
            route_nodes.len() >= 2,
            "Expected at least 2 Route nodes, got {}. Nodes: {:?}",
            route_nodes.len(),
            route_nodes.iter().map(|n| &n.name).collect::<Vec<_>>()
        );

        let edges = store.all_edges().unwrap();
        let handles_edges: Vec<_> = edges.iter().filter(|e| e.edge_type == EdgeType::Handles).collect();
        assert!(
            handles_edges.len() >= 2,
            "Expected at least 2 HANDLES edges, got {}",
            handles_edges.len()
        );
    }

    #[test]
    fn pipeline_creates_structure_nodes() {
        let repo_dir = TempDir::new().unwrap();
        create_test_repo(&repo_dir);

        let db_dir = TempDir::new().unwrap();
        let db_path = db_dir.path().join("test.redb");

        run(
            repo_dir.path().to_str().unwrap(),
            db_path.to_str().unwrap(),
            IndexMode::Full,
        )
        .unwrap();

        let store = Store::open(db_path.to_str().unwrap()).unwrap();
        let nodes = store.all_nodes().unwrap();

        let labels: HashSet<String> = nodes.iter().map(|n| n.label.as_str().to_string()).collect();

        assert!(
            labels.contains("Project"),
            "Expected Project node, got: {:?}",
            labels
        );
        assert!(
            labels.contains("Folder"),
            "Expected Folder node, got: {:?}",
            labels
        );
        assert!(
            labels.contains("File"),
            "Expected File node, got: {:?}",
            labels
        );
        assert!(
            labels.contains("Function"),
            "Expected Function node, got: {:?}",
            labels
        );
    }

    #[test]
    fn pipeline_detects_routes_across_frameworks() {
        let repo_dir = TempDir::new().unwrap();

        // FastAPI
        fs::create_dir_all(repo_dir.path().join("python_app")).unwrap();
        fs::write(
            repo_dir.path().join("python_app/main.py"),
            r#"from fastapi import FastAPI
app = FastAPI()

@app.get("/api/users")
async def list_users():
    return []

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int):
    pass
"#,
        )
        .unwrap();

        // Express
        fs::create_dir_all(repo_dir.path().join("js_app")).unwrap();
        fs::write(
            repo_dir.path().join("js_app/routes.js"),
            r#"const express = require('express');
const router = express.Router();

function getItems(req, res) {
    res.json([]);
}

router.get("/api/items", getItems);
"#,
        )
        .unwrap();

        // Next.js file routing
        fs::create_dir_all(repo_dir.path().join("app/products/[id]")).unwrap();
        fs::write(
            repo_dir.path().join("app/products/[id]/route.ts"),
            "export async function GET(request: Request) {\n    return Response.json({});\n}\n\nexport async function DELETE(request: Request) {\n    return Response.json({});\n}\n",
        )
        .unwrap();

        let db_dir = TempDir::new().unwrap();
        let db_path = db_dir.path().join("test.redb");

        let result = run(
            repo_dir.path().to_str().unwrap(),
            db_path.to_str().unwrap(),
            IndexMode::Full,
        )
        .unwrap();

        let store = Store::open(db_path.to_str().unwrap()).unwrap();
        let nodes = store.all_nodes().unwrap();
        let edges = store.all_edges().unwrap();

        let route_nodes: Vec<_> = nodes.iter().filter(|n| n.label == NodeLabel::Route).collect();
        let handles_edges: Vec<_> = edges.iter().filter(|e| e.edge_type == EdgeType::Handles).collect();

        // FastAPI: 2 routes (GET /api/users, DELETE /api/users/{user_id})
        // Express: 1 route (GET /api/items) — if handler name matches
        // Next.js: 2 routes (GET /products/:id, DELETE /products/:id)
        // Total: at least 4 routes
        assert!(
            route_nodes.len() >= 4,
            "Expected at least 4 Route nodes, got {}. Routes: {:?}",
            route_nodes.len(),
            route_nodes.iter().map(|n| (&n.name, &n.qualified_name)).collect::<Vec<_>>()
        );

        assert!(
            handles_edges.len() >= 4,
            "Expected at least 4 HANDLES edges, got {}",
            handles_edges.len()
        );

        let _ = result;
    }
}
