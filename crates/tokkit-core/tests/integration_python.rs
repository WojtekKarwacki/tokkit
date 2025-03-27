use tempfile::TempDir;
use tokkit_core::pipeline;
use tokkit_core::query;
use tokkit_core::store::Store;
use tokkit_core::types::*;

fn fixture_path(name: &str) -> String {
    format!("{}/tests/fixtures/{}", env!("CARGO_MANIFEST_DIR"), name)
}

#[test]
fn indexes_python_project() {
    let repo_path = fixture_path("python_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    let result = pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    assert!(
        result.node_count >= 10,
        "Expected node_count >= 10, got {}",
        result.node_count
    );
    assert!(
        result.edge_count >= 5,
        "Expected edge_count >= 5, got {}",
        result.edge_count
    );
}

#[test]
fn finds_functions_and_classes() {
    let repo_path = fixture_path("python_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    let store = Store::open(db_path.to_str().unwrap()).unwrap();

    let class_results = query::search_nodes(
        &store,
        &SearchFilters {
            query: Some("AuthService".to_string()),
            label: Some(NodeLabel::Class),
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
        !class_results.is_empty(),
        "Expected to find AuthService class, got none"
    );

    let fn_results = query::search_nodes(
        &store,
        &SearchFilters {
            query: None,
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
        fn_results.len() >= 3,
        "Expected >= 3 functions, got {}",
        fn_results.len()
    );
}

#[test]
fn resolves_cross_file_calls() {
    let repo_path = fixture_path("python_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    let store = Store::open(db_path.to_str().unwrap()).unwrap();
    let all_edges = store.all_edges().unwrap();

    let calls_edges: Vec<_> = all_edges
        .iter()
        .filter(|e| e.edge_type == EdgeType::Calls)
        .collect();

    assert!(
        !calls_edges.is_empty(),
        "Expected at least one CALLS edge, found none"
    );

    let high_confidence = calls_edges.iter().any(|e| {
        e.confidence
            .as_ref()
            .map(|c| c.value() >= 0.7)
            .unwrap_or(false)
    });

    assert!(
        high_confidence,
        "Expected at least one CALLS edge with confidence >= 0.7"
    );
}
