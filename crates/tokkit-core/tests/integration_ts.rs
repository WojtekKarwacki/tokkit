use tempfile::TempDir;
use tokkit_core::pipeline;
use tokkit_core::query;
use tokkit_core::store::Store;
use tokkit_core::types::*;

fn fixture_path(name: &str) -> String {
    format!("{}/tests/fixtures/{}", env!("CARGO_MANIFEST_DIR"), name)
}

#[test]
fn indexes_ts_project() {
    let repo_path = fixture_path("ts_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    let result = pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    assert!(
        result.node_count >= 10,
        "Expected node_count >= 10, got {}",
        result.node_count
    );
    assert!(
        result.edge_count >= 3,
        "Expected edge_count >= 3, got {}",
        result.edge_count
    );
}

#[test]
fn finds_interfaces_and_enums() {
    let repo_path = fixture_path("ts_project");
    let db_dir = TempDir::new().unwrap();
    let db_path = db_dir.path().join("test.redb");

    pipeline::run(&repo_path, db_path.to_str().unwrap(), IndexMode::Full).unwrap();

    let store = Store::open(db_path.to_str().unwrap()).unwrap();

    let interface_results = query::search_nodes(
        &store,
        &SearchFilters {
            query: Some("User".to_string()),
            label: Some(NodeLabel::Interface),
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
        !interface_results.is_empty(),
        "Expected to find 'User' interface, got none"
    );

    let enum_results = query::search_nodes(
        &store,
        &SearchFilters {
            query: Some("UserRole".to_string()),
            label: Some(NodeLabel::Enum),
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
        !enum_results.is_empty(),
        "Expected to find 'UserRole' enum, got none"
    );
// rev-8
}
