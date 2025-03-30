use crate::types::Language;
use super::spec::LanguageSpec;

pub struct JavaScriptSpec;

impl LanguageSpec for JavaScriptSpec {
    fn language_id(&self) -> Language {
        Language::JavaScript
    }

    fn ts_language(&self) -> tree_sitter::Language {
        tree_sitter_javascript::LANGUAGE.into()
    }

    fn function_types(&self) -> &[&str] {
        &[
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        ]
    }

    fn class_types(&self) -> &[&str] {
        &["class_declaration", "class"]
    }

    fn module_types(&self) -> &[&str] {
        &["program"]
    }

    fn call_types(&self) -> &[&str] {
        &["call_expression"]
    }

    fn import_types(&self) -> &[&str] {
        &["import_statement", "lexical_declaration", "export_statement"]
    }

    fn var_types(&self) -> &[&str] {
        &["lexical_declaration", "variable_declaration"]
    }

    fn throw_types(&self) -> &[&str] {
        &["throw_statement"]
    }

    fn branch_types(&self) -> &[&str] {
        &[
            "if_statement",
            "for_statement",
            "for_in_statement",
            "while_statement",
            "switch_statement",
            "case_clause",
            "try_statement",
            "catch_clause",
        ]
    }

    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[("process", "env")]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn javascript_spec_parses_small_snippet() {
        let spec = JavaScriptSpec;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();
        let source = "var x = 1;\n";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        assert_eq!(root.kind(), "program");
    }

    #[test]
    fn javascript_spec_first_child_matches() {
        let spec = JavaScriptSpec;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();
        let source = "function foo() {}\n";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        assert_eq!(root.kind(), "program");
        let first_child = root.child(0).unwrap();
        assert_eq!(first_child.kind(), "function_declaration");
    }
}
