use crate::{Confidence, IMPORT_MAP, SAME_MODULE, UNIQUE_NAME, SUFFIX_MATCH, ImportRef};
use super::registry::Registry;

pub struct Resolution {
    pub target_qn: String,
    pub confidence: Confidence,
    pub strategy: &'static str,
}

pub fn resolve_via_imports(
    callee_name: &str,
    imports: &[ImportRef],
    registry: &Registry,
) -> Option<Resolution> {
    for import in imports {
        let matched = import.names.iter().any(|n| n == callee_name)
            || import.alias.as_deref() == Some(callee_name);

        if matched && let Some(candidates) = registry.get_by_name(callee_name) {
            for qn in candidates {
                if qn.contains(&import.module_path) {
                    return Some(Resolution {
                        target_qn: qn.clone(),
                        confidence: IMPORT_MAP,
                        strategy: "import_map",
                    });
                }
            }
        }
    }
    None
}

pub fn resolve_same_module(
    callee_name: &str,
    caller_file: &str,
    project_name: &str,
    registry: &Registry,
) -> Option<Resolution> {
    let prefix = format!("{}::{}", project_name, caller_file);
    if let Some(candidates) = registry.get_by_name(callee_name) {
        for qn in candidates {
            if qn.starts_with(&prefix) {
                return Some(Resolution {
                    target_qn: qn.clone(),
                    confidence: SAME_MODULE,
                    strategy: "same_module",
                });
            }
        }
    }
    None
}

pub fn resolve_unique_name(callee_name: &str, registry: &Registry) -> Option<Resolution> {
    if let Some(candidates) = registry.get_by_name(callee_name)
        && candidates.len() == 1
    {
        return Some(Resolution {
            target_qn: candidates[0].clone(),
            confidence: UNIQUE_NAME,
            strategy: "unique_name",
        });
    }
    None
}

pub fn resolve_suffix_match(
    callee_name: &str,
    caller_qn: &str,
    registry: &Registry,
) -> Option<Resolution> {
    let candidates = registry.get_by_name(callee_name)?;
    if candidates.is_empty() {
        return None;
    }

    let best = candidates.iter().max_by_key(|qn| {
        common_prefix_len(qn, caller_qn)
    })?;

    Some(Resolution {
        target_qn: best.clone(),
        confidence: SUFFIX_MATCH,
        strategy: "suffix_match",
    })
}

fn common_prefix_len(a: &str, b: &str) -> usize {
    a.chars().zip(b.chars()).take_while(|(x, y)| x == y).count()
}

pub fn resolve(
    callee_name: &str,
    caller_file: &str,
    caller_qn: &str,
    project_name: &str,
    imports: &[ImportRef],
    registry: &Registry,
) -> Option<Resolution> {
    resolve_via_imports(callee_name, imports, registry)
        .or_else(|| resolve_same_module(callee_name, caller_file, project_name, registry))
        .or_else(|| resolve_unique_name(callee_name, registry))
        .or_else(|| resolve_suffix_match(callee_name, caller_qn, registry))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{NodeLabel, ImportRef};
    use super::super::registry::Registry;

    fn make_registry() -> Registry {
        let mut r = Registry::new();
        r.register("proj::auth.py::authenticate", NodeLabel::Function);
        r.register("proj::utils.py::process", NodeLabel::Function);
        r.register("proj::core.py::process", NodeLabel::Function);
        r
    }

    fn make_import(module_path: &str, names: &[&str]) -> ImportRef {
        ImportRef {
            module_path: module_path.to_string(),
            alias: None,
            names: names.iter().map(|s| s.to_string()).collect(),
            line: 1,
        }
    }

    #[test]
    fn import_map_resolves_direct_import() {
        let r = make_registry();
        let imports = vec![make_import("auth.py", &["authenticate"])];
        let res = resolve_via_imports("authenticate", &imports, &r).unwrap();
        assert!(res.confidence.value() >= 0.85);
        assert_eq!(res.strategy, "import_map");
        assert!(res.target_qn.contains("authenticate"));
    }

    #[test]
    fn same_module_resolves_local_call() {
        let r = make_registry();
        let res = resolve_same_module("authenticate", "auth.py", "proj", &r).unwrap();
        assert_eq!(res.confidence.value(), 0.90);
        assert_eq!(res.strategy, "same_module");
    }

    #[test]
    fn unique_name_resolves_single_candidate() {
        let r = make_registry();
        let res = resolve_unique_name("authenticate", &r).unwrap();
        assert_eq!(res.confidence.value(), 0.75);
        assert_eq!(res.strategy, "unique_name");
    }

    #[test]
    fn unique_name_fails_on_ambiguity() {
        let r = make_registry();
        let res = resolve_unique_name("process", &r);
        assert!(res.is_none());
    }

    #[test]
    fn suffix_match_picks_closest() {
        let r = make_registry();
        let res = resolve_suffix_match("process", "proj::utils.py::helper", &r).unwrap();
        assert_eq!(res.strategy, "suffix_match");
        assert!(res.target_qn.contains("utils.py"));
    }

    #[test]
    fn cascade_uses_highest_priority_match() {
        let r = make_registry();
        let imports = vec![make_import("auth.py", &["authenticate"])];
        let res = resolve(
            "authenticate",
            "main.py",
            "proj::main.py::run",
            "proj",
            &imports,
            &r,
        )
        .unwrap();
        assert_eq!(res.strategy, "import_map");
    }
}
