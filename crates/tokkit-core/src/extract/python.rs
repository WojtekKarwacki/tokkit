use crate::types::Language;
use super::spec::LanguageSpec;

pub struct PythonSpec;

impl LanguageSpec for PythonSpec {
    fn language_id(&self) -> Language {
        Language::Python
    }

    fn ts_language(&self) -> tree_sitter::Language {
        tree_sitter_python::LANGUAGE.into()
    }

    fn function_types(&self) -> &[&str] {
        &["function_definition"]
    }

    fn class_types(&self) -> &[&str] {
        &["class_definition"]
    }

    fn module_types(&self) -> &[&str] {
        &["module"]
    }

    fn call_types(&self) -> &[&str] {
        &["call"]
    }

    fn import_types(&self) -> &[&str] {
        &["import_statement"]
    }

    fn import_from_types(&self) -> &[&str] {
        &["import_from_statement"]
    }

    fn var_types(&self) -> &[&str] {
        &["assignment", "augmented_assignment"]
    }

    fn throw_types(&self) -> &[&str] {
        &["raise_statement"]
    }

    fn decorator_types(&self) -> &[&str] {
        &["decorator"]
    }

    fn branch_types(&self) -> &[&str] {
        &[
            "if_statement",
            "for_statement",
            "while_statement",
            "try_statement",
            "except_clause",
            "with_statement",
            "elif_clause",
        ]
    }

    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[("os", "environ"), ("os", "getenv")]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn python_spec_parses_small_snippet() {
        let spec = PythonSpec;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();
        let source = "x = 1\n";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        assert_eq!(root.kind(), "module");
    }

    #[test]
    fn python_spec_first_child_matches() {
        let spec = PythonSpec;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();
        let source = "def foo(): pass\n";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        assert_eq!(root.kind(), "module");
        let first_child = root.child(0).unwrap();
        assert_eq!(first_child.kind(), "function_definition");
    }
// rev-5
}
