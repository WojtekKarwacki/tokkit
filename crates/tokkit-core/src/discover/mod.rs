pub mod filters;
pub mod language;

use std::path::Path;
use ignore::WalkBuilder;
use crate::error::Result;
use crate::types::{FileInfo, IndexMode};
use filters::{should_skip_dir, should_skip_file};
use language::detect_language;

pub fn discover(repo_path: &str, mode: IndexMode) -> Result<Vec<FileInfo>> {
    let root = Path::new(repo_path);

    let walker = WalkBuilder::new(root)
        .hidden(false)
        .git_ignore(true)
        .filter_entry(move |entry| {
            if entry.file_type().map(|ft| ft.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy();
                !should_skip_dir(&name, mode)
            } else {
                true
            }
        })
        .build();

    let mut files: Vec<FileInfo> = Vec::new();

    for result in walker {
        let entry = result.map_err(|e| crate::error::TokkitError::Other(e.to_string()))?;

        if !entry.file_type().map(|ft| ft.is_file()).unwrap_or(false) {
            continue;
        }

        let path = entry.path();

        if should_skip_file(path, mode) {
            continue;
        }

        let language = match detect_language(path) {
            Some(lang) => lang,
            None => continue,
        };

        let abs_path = path.to_string_lossy().to_string();
        let rel_path = path
            .strip_prefix(root)
            .unwrap_or(path)
            .to_string_lossy()
            .to_string();

        files.push(FileInfo {
            path: abs_path,
            rel_path,
            language,
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

    fn create_file(dir: &TempDir, rel: &str) {
        let full = dir.path().join(rel);
        if let Some(parent) = full.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(full, "").unwrap();
    }

    #[test]
    fn discovers_supported_files_only() {
        let dir = TempDir::new().unwrap();
        create_file(&dir, "src/app.py");
        create_file(&dir, "src/utils.js");
        create_file(&dir, "src/types.ts");
        create_file(&dir, "node_modules/pkg/index.js");
        create_file(&dir, "__pycache__/app.pyc");
        create_file(&dir, "src/main.go");
        create_file(&dir, "src/image.png");

        let files = discover(dir.path().to_str().unwrap(), IndexMode::Full).unwrap();
        assert_eq!(files.len(), 3);
        let rel_paths: Vec<&str> = files.iter().map(|f| f.rel_path.as_str()).collect();
        assert!(rel_paths.contains(&"src/app.py"));
        assert!(rel_paths.contains(&"src/utils.js"));
        assert!(rel_paths.contains(&"src/types.ts"));
    }

    #[test]
    fn fast_mode_filters_more() {
        let dir = TempDir::new().unwrap();
        create_file(&dir, "src/app.py");
        create_file(&dir, "docs/guide.py");

        let full_files = discover(dir.path().to_str().unwrap(), IndexMode::Full).unwrap();
        let fast_files = discover(dir.path().to_str().unwrap(), IndexMode::Fast).unwrap();

        assert_eq!(full_files.len(), 2);
        assert_eq!(fast_files.len(), 1);
        assert_eq!(fast_files[0].rel_path, "src/app.py");
    }

    #[test]
    fn returns_sorted_by_rel_path() {
        let dir = TempDir::new().unwrap();
        create_file(&dir, "b/z.py");
        create_file(&dir, "a/a.py");

        let files = discover(dir.path().to_str().unwrap(), IndexMode::Full).unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(files[0].rel_path, "a/a.py");
        assert_eq!(files[1].rel_path, "b/z.py");
    }
}
