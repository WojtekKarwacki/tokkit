use std::collections::HashMap;
use std::process::Command;
use crate::graph::GraphBuffer;
use crate::types::{NodeLabel, EdgeType, Edge};
use crate::error::Result;

pub fn compute_co_changes(buf: &mut GraphBuffer, repo_path: &str) -> Result<()> {
    let output = Command::new("git")
        .args([
            "log",
            "--name-only",
            "--pretty=format:COMMIT",
            "--since=1 year ago",
            "-n",
            "10000",
        ])
        .current_dir(repo_path)
        .output();

    let output = match output {
        Ok(o) => o,
        Err(_) => return Ok(()),
    };

    if !output.status.success() {
        return Ok(());
    }

    let text = match std::str::from_utf8(&output.stdout) {
        Ok(s) => s,
        Err(_) => return Ok(()),
    };

    // Parse commits: group files between COMMIT markers
    let mut commits: Vec<Vec<String>> = Vec::new();
    let mut current: Vec<String> = Vec::new();

    for line in text.lines() {
        let line = line.trim();
        if line == "COMMIT" {
            if !current.is_empty() {
                commits.push(std::mem::take(&mut current));
            }
        } else if !line.is_empty() {
            current.push(line.to_string());
        }
    }
    if !current.is_empty() {
        commits.push(current);
    }

    // Count individual file appearances and co-occurrences
    let mut file_counts: HashMap<String, u32> = HashMap::new();
    let mut pair_counts: HashMap<(String, String), u32> = HashMap::new();

    for commit_files in &commits {
        // Skip commits with >20 files (merge/refactor noise)
        if commit_files.len() > 20 {
            continue;
        }

        for f in commit_files {
            *file_counts.entry(f.clone()).or_insert(0) += 1;
        }

        // Count all pairs
        for i in 0..commit_files.len() {
            for j in (i + 1)..commit_files.len() {
                let a = &commit_files[i];
                let b = &commit_files[j];
                let key = if a <= b {
                    (a.clone(), b.clone())
                } else {
                    (b.clone(), a.clone())
                };
                *pair_counts.entry(key).or_insert(0) += 1;
            }
        }
    }

    // Build a map from file path to node id
    let path_to_id: HashMap<String, u64> = buf
        .nodes()
        .iter()
        .filter(|n| n.label == NodeLabel::File)
        .filter_map(|n| n.file_path.as_ref().map(|p| (p.clone(), n.id)))
        .collect();

    let mut edges_to_add: Vec<(u64, u64, u32, f64)> = Vec::new();

    for ((file_a, file_b), co_changes) in &pair_counts {
        if *co_changes < 3 {
            continue;
        }

        let count_a = *file_counts.get(file_a).unwrap_or(&0);
        let count_b = *file_counts.get(file_b).unwrap_or(&0);
        let min_count = count_a.min(count_b);

        if min_count == 0 {
            continue;
        }

        let coupling_score = *co_changes as f64 / min_count as f64;
        if coupling_score < 0.3 {
            continue;
        }

        let id_a = path_to_id.get(file_a).copied();
        let id_b = path_to_id.get(file_b).copied();

        if let (Some(a), Some(b)) = (id_a, id_b) {
            edges_to_add.push((a, b, *co_changes, coupling_score));
        }
    }

    for (a, b, co_changes, coupling_score) in edges_to_add {
        let mut props = HashMap::new();
        props.insert("co_changes".to_string(), co_changes.to_string());
        props.insert(
            "coupling_score".to_string(),
            format!("{:.2}", coupling_score),
        );

        buf.add_edge(Edge {
            source_id: a,
            target_id: b,
            edge_type: EdgeType::CoChanged,
            confidence: None,
            properties: props,
        });
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn git_history_skips_non_repo() {
        let dir = tempfile::tempdir().expect("tempdir");
        let mut buf = GraphBuffer::new("proj", "/root");

        let result = compute_co_changes(&mut buf, dir.path().to_str().unwrap());
        assert!(result.is_ok(), "Expected Ok for non-git directory");

        let co_changed_edges = buf
            .edges()
            .iter()
            .filter(|e| e.edge_type == EdgeType::CoChanged)
            .count();
        assert_eq!(co_changed_edges, 0, "Expected no CO_CHANGED edges for non-repo");
    }
}
