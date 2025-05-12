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
    Ok(None)
}
