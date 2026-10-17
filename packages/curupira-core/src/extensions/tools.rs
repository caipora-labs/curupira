//! Glob allow/deny filters for `[plugins.<alias>].tools`.

/// Return whether a local trigger name is selected by `tools` patterns.
///
/// - Empty `patterns` → allow all.
/// - `github-*` → include only names matching the glob.
/// - `!github-*` → exclude names matching the glob.
/// - Mix includes and excludes: must match an include (or any if none) and
///   must not match any exclude. `*` matches every name.
#[must_use]
pub fn tool_allowed(name: &str, patterns: &[String]) -> bool {
    if patterns.is_empty() {
        return true;
    }
    let mut includes: Vec<&str> = Vec::new();
    let mut excludes: Vec<&str> = Vec::new();
    for pattern in patterns {
        if let Some(rest) = pattern.strip_prefix('!') {
            excludes.push(rest);
        } else {
            includes.push(pattern.as_str());
        }
    }
    let included = if includes.is_empty() {
        true
    } else {
        includes.iter().any(|pattern| wildcard_match(pattern, name))
    };
    if !included {
        return false;
    }
    !excludes
        .iter()
        .any(|pattern| wildcard_match(pattern, name))
}

/// Simple glob: only `*` is special (matches any sequence, including empty).
#[must_use]
pub fn wildcard_match(pattern: &str, text: &str) -> bool {
    wildcard_match_bytes(pattern.as_bytes(), text.as_bytes())
}

fn wildcard_match_bytes(pattern: &[u8], text: &[u8]) -> bool {
    let mut pi = 0;
    let mut ti = 0;
    let mut star_pi: Option<usize> = None;
    let mut star_ti = 0;
    while ti < text.len() {
        if pi < pattern.len() && pattern[pi] == b'*' {
            star_pi = Some(pi);
            star_ti = ti;
            pi += 1;
            continue;
        }
        if pi < pattern.len() && pattern[pi] == text[ti] {
            pi += 1;
            ti += 1;
            continue;
        }
        if let Some(sp) = star_pi {
            pi = sp + 1;
            star_ti += 1;
            ti = star_ti;
            continue;
        }
        return false;
    }
    while pi < pattern.len() && pattern[pi] == b'*' {
        pi += 1;
    }
    pi == pattern.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn patterns(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| (*s).to_string()).collect()
    }

    #[test]
    fn empty_allows_all() {
        assert!(tool_allowed("github-issues", &[]));
        assert!(tool_allowed("monday-items", &[]));
    }

    #[test]
    fn include_prefix_filters_others() {
        let p = patterns(&["github-*"]);
        assert!(tool_allowed("github-issues", &p));
        assert!(tool_allowed("github-pull-requests", &p));
        assert!(!tool_allowed("monday-items", &p));
        assert!(!tool_allowed("trello-cli-cards", &p));
    }

    #[test]
    fn exclude_prefix_keeps_others() {
        let p = patterns(&["!github-*"]);
        assert!(!tool_allowed("github-issues", &p));
        assert!(!tool_allowed("github-pull-requests", &p));
        assert!(tool_allowed("monday-items", &p));
        assert!(tool_allowed("azure-cli-pull-requests", &p));
    }

    #[test]
    fn star_then_exclude() {
        let p = patterns(&["*", "!monday-*"]);
        assert!(tool_allowed("github-issues", &p));
        assert!(!tool_allowed("monday-items", &p));
    }

    #[test]
    fn include_then_narrow_exclude() {
        let p = patterns(&["github-*", "!github-pull-requests"]);
        assert!(tool_allowed("github-issues", &p));
        assert!(!tool_allowed("github-pull-requests", &p));
        assert!(!tool_allowed("trello-cli-cards", &p));
    }

    #[test]
    fn exact_and_star() {
        assert!(wildcard_match("*", "anything"));
        assert!(wildcard_match("github-issues", "github-issues"));
        assert!(!wildcard_match("github-issues", "github-pull-requests"));
        assert!(wildcard_match("*-issues", "github-issues"));
        assert!(wildcard_match("a*b*c", "aXbYc"));
    }
}
