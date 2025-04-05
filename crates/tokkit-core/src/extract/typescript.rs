use crate::types::Language;
use super::spec::LanguageSpec;

pub struct TypeScriptSpec;

impl LanguageSpec for TypeScriptSpec {
    fn language_id(&self) -> Language {
        Language::TypeScript
    }

    fn ts_language(&self) -> tree_sitter::Language {
        tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into()
    }

    fn function_types(&self) -> &[&str] {
        &[
            "function_declaration",
            "generator_function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "function_signature",
        ]
    }

    fn class_types(&self) -> &[&str] {
        &[
            "class_declaration",
            "class",
            "abstract_class_declaration",
            "enum_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "internal_module",
        ]
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

    fn decorator_types(&self) -> &[&str] {
        &["decorator"]
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
    fn typescript_spec_parses_small_snippet() {
        let spec = TypeScriptSpec;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();
        let source = "const x: number = 1;\n";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        assert_eq!(root.kind(), "program");
    }

    #[test]
    fn typescript_spec_first_child_matches() {
        let spec = TypeScriptSpec;
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&spec.ts_language()).unwrap();
        let source = "function foo(): void {}\n";
        let tree = parser.parse(source, None).unwrap();
        let root = tree.root_node();
        assert_eq!(root.kind(), "program");
        let first_child = root.child(0).unwrap();
        assert_eq!(first_child.kind(), "function_declaration");
    }
}
