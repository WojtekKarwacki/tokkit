use std::path::Path;
use crate::types::Language;

pub fn detect_language(path: &Path) -> Option<Language> {
    let ext = path.extension()?.to_str()?;
    match ext {
        "py" => Some(Language::Python),
        "js" | "jsx" | "mjs" | "cjs" => Some(Language::JavaScript),
        "ts" => Some(Language::TypeScript),
        "tsx" => Some(Language::Tsx),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn detects_python() {
        assert_eq!(detect_language(Path::new("foo.py")), Some(Language::Python));
        assert_eq!(detect_language(Path::new("src/bar/baz.py")), Some(Language::Python));
    }

    #[test]
    fn detects_javascript_variants() {
        assert_eq!(detect_language(Path::new("app.js")), Some(Language::JavaScript));
        assert_eq!(detect_language(Path::new("app.jsx")), Some(Language::JavaScript));
        assert_eq!(detect_language(Path::new("app.mjs")), Some(Language::JavaScript));
        assert_eq!(detect_language(Path::new("app.cjs")), Some(Language::JavaScript));
    }

    #[test]
    fn detects_typescript_variants() {
        assert_eq!(detect_language(Path::new("app.ts")), Some(Language::TypeScript));
        assert_eq!(detect_language(Path::new("app.tsx")), Some(Language::Tsx));
    }

    #[test]
    fn returns_none_for_unsupported() {
        assert_eq!(detect_language(Path::new("main.go")), None);
        assert_eq!(detect_language(Path::new("lib.rs")), None);
        assert_eq!(detect_language(Path::new("icon.png")), None);
        assert_eq!(detect_language(Path::new("Makefile")), None);
    }
}
