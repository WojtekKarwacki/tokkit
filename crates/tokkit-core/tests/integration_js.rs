use tempfile::TempDir;
use tokkit_core::pipeline;
use tokkit_core::query;
use tokkit_core::store::Store;
use tokkit_core::types::*;

fn fixture_path(name: &str) -> String {
    format!("{}/tests/fixtures/{}", env!("CARGO_MANIFEST_DIR"), name)
}

#[test]
fn indexes_js_project() {
    let repo_path = fixture_path("js_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    let result = pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    assert!(
        result.node_count >= 8,
        "Expected node_count >= 8, got {}",
        result.node_count
    );
    assert!(
        result.edge_count >= 3,
        "Expected edge_count >= 3, got {}",
        result.edge_count
    );
}

#[test]
fn finds_js_functions() {
    let repo_path = fixture_path("js_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    let store = Store::open(db_path.to_str().unwrap()).unwrap();

    let results = query::search_nodes(
        &store,
        &SearchFilters {
            query: Some("login".to_string()),
            label: Some(NodeLabel::Function),
            file_path: None,
            limit: None,
            name_pattern: None,
            max_degree: None,
            exclude_entry_points: None,
            relationship: None,
        },
    )
    .unwrap();

    assert!(
        !results.is_empty(),
        "Expected to find 'login' function, got none"
    );
}
