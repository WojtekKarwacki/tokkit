use hashbrown::HashMap;
use crate::NodeLabel;

pub struct Registry {
    exact: HashMap<String, (NodeLabel, String)>,
    by_name: HashMap<String, Vec<String>>,
}

impl Default for Registry {
    fn default() -> Self {
        Self::new()
    }
}

impl Registry {
    pub fn new() -> Self {
        Self {
            exact: HashMap::new(),
            by_name: HashMap::new(),
        }
    }

    pub fn register(&mut self, qualified_name: &str, label: NodeLabel) {
        let sname = simple_name(qualified_name);
        self.exact.insert(
            qualified_name.to_string(),
            (label, sname.clone()),
        );
        self.by_name
            .entry(sname)
            .or_default()
            .push(qualified_name.to_string());
    }

    pub fn get_exact(&self, qn: &str) -> Option<&(NodeLabel, String)> {
        self.exact.get(qn)
    }

    pub fn get_by_name(&self, name: &str) -> Option<&Vec<String>> {
        self.by_name.get(name)
    }

    pub fn len(&self) -> usize {
        self.exact.len()
    }

    pub fn is_empty(&self) -> bool {
        self.exact.is_empty()
    }
}

pub fn simple_name(qn: &str) -> String {
    let dot_part = if let Some(pos) = qn.rfind('.') {
        &qn[pos + 1..]
    } else {
        qn
    };
    if let Some(pos) = dot_part.rfind("::") {
        dot_part[pos + 2..].to_string()
    } else {
        dot_part.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_lookup() {
        let mut r = Registry::new();
        r.register("proj::auth.py::authenticate", NodeLabel::Function);
        r.register("proj::user.py::User", NodeLabel::Class);

        assert!(r.get_exact("proj::auth.py::authenticate").is_some());
        assert!(r.get_exact("proj::user.py::User").is_some());
        assert!(r.get_exact("proj::missing").is_none());

        let by_name = r.get_by_name("authenticate").unwrap();
        assert_eq!(by_name.len(), 1);
        assert_eq!(by_name[0], "proj::auth.py::authenticate");

        assert_eq!(r.len(), 2);
    }

    #[test]
    fn multiple_candidates_same_name() {
        let mut r = Registry::new();
        r.register("proj::utils.py::process", NodeLabel::Function);
        r.register("proj::core.py::process", NodeLabel::Function);

        let candidates = r.get_by_name("process").unwrap();
        assert_eq!(candidates.len(), 2);
    }

    #[test]
    fn simple_name_extraction() {
        assert_eq!(simple_name("proj::file.py::Foo.bar"), "bar");
        assert_eq!(simple_name("proj::file.py::authenticate"), "authenticate");
        assert_eq!(simple_name("authenticate"), "authenticate");
        assert_eq!(simple_name("module::MyClass"), "MyClass");
        assert_eq!(simple_name("a.b.c"), "c");
    }
}
