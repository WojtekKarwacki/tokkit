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
    if std::path::Path::new(repo_path).join(".git").exists() {
        git_history::compute_co_changes(buf, repo_path)?;
    }
    Ok(())
}
