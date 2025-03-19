use crate::types::Language;

pub trait LanguageSpec: Send + Sync {
    fn language_id(&self) -> Language;
    fn ts_language(&self) -> tree_sitter::Language;
    fn function_types(&self) -> &[&str];
    fn class_types(&self) -> &[&str];
    fn module_types(&self) -> &[&str];
    fn call_types(&self) -> &[&str];
    fn import_types(&self) -> &[&str];
    fn import_from_types(&self) -> &[&str] {
        &[]
    }
    fn var_types(&self) -> &[&str];
    fn throw_types(&self) -> &[&str];
    fn decorator_types(&self) -> &[&str] {
        &[]
    }
    fn branch_types(&self) -> &[&str];
    fn env_access_patterns(&self) -> &[(&str, &str)] {
        &[]
    }
}

pub fn spec_for_language(lang: Language) -> &'static dyn LanguageSpec {
    match lang {
        Language::Python => &crate::extract::python::PythonSpec,
        Language::JavaScript => &crate::extract::javascript::JavaScriptSpec,
        Language::TypeScript | Language::Tsx => &crate::extract::typescript::TypeScriptSpec,
    }
}
