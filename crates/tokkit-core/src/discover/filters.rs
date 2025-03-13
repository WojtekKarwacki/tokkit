use std::path::Path;
use crate::types::IndexMode;

static ALWAYS_SKIP_DIRS: &[&str] = &[
    ".git", ".hg", ".svn", ".worktrees", ".idea", ".vs", ".vscode", ".eclipse",
    ".claude", ".cache", ".eggs", ".env", ".mypy_cache", ".nox", ".pytest_cache",
    ".ruff_cache", ".tox", ".venv", "__pycache__", "env", "htmlcov", "site-packages",
    "venv", ".npm", ".nyc_output", ".pnpm-store", ".yarn", "bower_components",
    "coverage", "node_modules", ".next", ".nuxt", ".svelte-kit", ".angular", ".turbo",
    ".parcel-cache", ".docusaurus", ".expo", "dist", "obj", "Pods", "target", "temp",
    "tmp", ".terraform", ".serverless", "bazel-bin", "bazel-out", "bazel-testlogs",
    ".cargo", ".stack-work", ".dart_tool", "zig-cache", "zig-out", ".metals", ".bloop",
    ".bsp", ".ccls-cache", ".clangd", "elm-stuff", "_opam", ".cpcache", ".shadow-cljs",
    ".vercel", ".netlify", ".qdrant_code_embeddings", ".tmp", "vendor",
];

static FAST_SKIP_DIRS: &[&str] = &[
    "generated", "gen", "auto-generated", "fixtures", "testdata", "test_data",
    "__tests__", "__mocks__", "__snapshots__", "__fixtures__", "__test__", "docs", "doc",
    "documentation", "examples", "example", "samples", "sample", "assets", "static",
    "public", "media", "third_party", "thirdparty", "3rdparty", "external", "migrations",
    "seeds", "e2e", "integration", "locale", "locales", "i18n", "l10n", "scripts",
    "tools", "hack", "bin", "build", "out",
];

static ALWAYS_IGNORED_SUFFIXES: &[&str] = &[
    ".tmp", "~", ".pyc", ".pyo", ".o", ".a", ".so", ".dll", ".class",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".tiff", ".webp", ".svg",
    ".wasm", ".node", ".exe", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
];

static FAST_IGNORED_SUFFIXES: &[&str] = &[
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z", ".jar", ".war", ".ear",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".ogg", ".mkv", ".webm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods",
    ".map", ".min.js", ".min.css", ".pem", ".crt", ".key", ".cer", ".p12",
    ".pb", ".avro", ".parquet", ".beam", ".elc", ".rlib", ".coverage", ".prof",
    ".out", ".patch", ".diff",
];

static FAST_SKIP_FILENAMES: &[&str] = &[
    "LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE-MIT", "LICENSE-APACHE",
    "LICENCE", "LICENCE.txt", "LICENCE.md", "CHANGELOG", "CHANGELOG.md",
    "CHANGES.md", "HISTORY", "HISTORY.md", "AUTHORS", "AUTHORS.md",
    "CONTRIBUTORS", "CONTRIBUTORS.md", "CODEOWNERS", "go.sum", "yarn.lock",
    "pnpm-lock.yaml", "Pipfile.lock", "poetry.lock", "Gemfile.lock", "Cargo.lock",
    "mix.lock", "flake.lock", "pubspec.lock", "composer.lock", "package-lock.json",
    "configure", "Makefile.in", "config.guess", "config.sub",
];

static FAST_PATTERNS: &[&str] = &[
    ".d.ts", ".bundle.", ".chunk.", ".generated.", ".pb.go", "_pb2.py", ".pb2.py",
    "_grpc.pb.go", "_string.go", "mock_", "_mock.", "_test_helpers.", ".stories.",
    ".spec.", ".test.",
];

pub fn should_skip_dir(name: &str, mode: IndexMode) -> bool {
    if ALWAYS_SKIP_DIRS.contains(&name) {
        return true;
    }
    if mode == IndexMode::Fast && FAST_SKIP_DIRS.contains(&name) {
        return true;
    }
    false
}

pub fn should_skip_file(path: &Path, mode: IndexMode) -> bool {
    let file_name = match path.file_name().and_then(|n| n.to_str()) {
        Some(n) => n,
        None => return false,
    };

    for suffix in ALWAYS_IGNORED_SUFFIXES {
        if file_name.ends_with(suffix) {
            return true;
        }
    }

    if mode == IndexMode::Fast {
        for suffix in FAST_IGNORED_SUFFIXES {
            if file_name.ends_with(suffix) {
                return true;
            }
        }
        if FAST_SKIP_FILENAMES.contains(&file_name) {
            return true;
        }
        for pattern in FAST_PATTERNS {
            if file_name.contains(pattern) {
                return true;
            }
        }
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn always_skips_git_and_node_modules() {
        assert!(should_skip_dir(".git", IndexMode::Full));
        assert!(should_skip_dir(".git", IndexMode::Fast));
        assert!(should_skip_dir("node_modules", IndexMode::Full));
        assert!(should_skip_dir("node_modules", IndexMode::Fast));
    }

    #[test]
    fn fast_mode_skips_extra_dirs() {
        assert!(!should_skip_dir("docs", IndexMode::Full));
        assert!(should_skip_dir("docs", IndexMode::Fast));
    }

    #[test]
    fn skips_binary_suffixes() {
        assert!(should_skip_file(Path::new("icon.png"), IndexMode::Full));
        assert!(should_skip_file(Path::new("module.wasm"), IndexMode::Full));
    }

    #[test]
    fn fast_mode_skips_extra_files() {
        assert!(!should_skip_file(Path::new("LICENSE"), IndexMode::Full));
        assert!(should_skip_file(Path::new("LICENSE"), IndexMode::Fast));
        assert!(!should_skip_file(Path::new("types.d.ts"), IndexMode::Full));
        assert!(should_skip_file(Path::new("types.d.ts"), IndexMode::Fast));
        assert!(!should_skip_file(Path::new("Button.stories.tsx"), IndexMode::Full));
        assert!(should_skip_file(Path::new("Button.stories.tsx"), IndexMode::Fast));
    }

    #[test]
    fn does_not_skip_source_files() {
        assert!(!should_skip_file(Path::new("app.py"), IndexMode::Full));
        assert!(!should_skip_file(Path::new("app.py"), IndexMode::Fast));
        assert!(!should_skip_file(Path::new("app.ts"), IndexMode::Full));
        assert!(!should_skip_file(Path::new("app.ts"), IndexMode::Fast));
        assert!(!should_skip_file(Path::new("app.js"), IndexMode::Full));
        assert!(!should_skip_file(Path::new("app.js"), IndexMode::Fast));
    }
}
