//! Prompt templates for automations.
//!
//! A prompt is plain text with two kinds of markup, both optional:
//!
//! * `${name}` inserts a field. This is the simple form and covers most prompts. A name the
//!   trigger does not provide is left as written, so shell text such as `${HOME}` is safe.
//! * Jinja syntax (`{{ name }}`, `{% if %}`, `{% for %}`, filters) makes a prompt dynamic.
//!
//! Every field is a string, exactly as the trigger sent it. Lists and objects arrive as compact
//! JSON text; use `| fromjson` to loop over them. Field values are data: a title or body that
//! contains `{{` or `{%` is inserted as-is and never interpreted, because the template is
//! compiled once and rendered once with the fields as the context.

use std::collections::{BTreeMap, BTreeSet};

use minijinja::{
    syntax::SyntaxConfig, value::Serde, Environment, Error, ErrorKind, UndefinedBehavior, Value,
};

use crate::error::CurupiraError;
use crate::protocol::KeyValue;

/// Fields the host adds to every task, besides the ones the trigger returns.
pub const HOST_FIELDS: &[&str] = &["repository", "automation"];

/// Name of the map holding every field, used for `${name}` (so any key works, even `a-b`).
const RAW: &str = "_fields";

/// Host fields followed by the trigger's own, sorted, for messages and checks.
pub fn available_fields(trigger_fields: &[String]) -> Vec<String> {
    let mut names: BTreeSet<String> = HOST_FIELDS.iter().map(|s| (*s).to_string()).collect();
    names.extend(trigger_fields.iter().cloned());
    names.into_iter().collect()
}

/// Render `template` for one task. `automation_id` also labels errors.
pub fn render(
    template: &str,
    values: &[KeyValue],
    repository: &str,
    automation_id: &str,
) -> Result<String, CurupiraError> {
    let mut fields: BTreeMap<&str, &str> = BTreeMap::new();
    fields.insert("repository", repository);
    fields.insert("automation", automation_id);
    for pair in values {
        fields.insert(&pair.key, &pair.value);
    }
    let source = legacy_to_jinja(template, |name| fields.contains_key(name));
    let mut context = BTreeMap::new();
    for (name, value) in &fields {
        if is_identifier(name) {
            context.insert((*name).to_string(), Value::from(*value));
        }
    }
    context.insert(RAW.to_string(), Value::from(Serde(&fields)));
    let names: Vec<String> = fields.keys().map(|k| (*k).to_string()).collect();
    environment()
        .render_str(&source, Value::from(Serde(&context)))
        .map_err(|e| CurupiraError::Dispatch(describe(automation_id, template, &e, &names)))
}

/// Check a prompt at `validate` time: syntax, and that every field it uses exists.
///
/// `known` is `None` when the trigger does not declare its fields; only syntax is checked then.
pub fn check(label: &str, template: &str, known: Option<&[String]>) -> Result<(), CurupiraError> {
    let allowed: Vec<String> = available_fields(known.unwrap_or(&[]));
    let source = legacy_to_jinja(template, |name| allowed.iter().any(|a| a == name));
    let env = environment();
    let compiled = env
        .template_from_str(&source)
        .map_err(|e| CurupiraError::Config(describe(label, template, &e, &[])))?;
    if known.is_none() {
        return Ok(());
    }
    let mut unknown: BTreeSet<String> = compiled
        .undeclared_variables(false)
        .into_iter()
        .filter(|name| name != RAW && !allowed.contains(name))
        .collect();
    // `${name}` is left alone when unknown (it may be shell text), unless it looks like a typo.
    for name in legacy_names(template) {
        if !allowed.contains(&name) && closest(&name, &allowed).is_some() {
            unknown.insert(name);
        }
    }
    if unknown.is_empty() {
        return Ok(());
    }
    let hints: Vec<String> = unknown
        .iter()
        .map(|name| match closest(name, &allowed) {
            Some(near) => format!("{name:?} (did you mean {near:?}?)"),
            None => format!("{name:?}"),
        })
        .collect();
    Err(CurupiraError::Config(format!(
        "automation {label:?}: prompt uses unknown field(s) {}. Available fields: {}",
        hints.join(", "),
        allowed.join(", ")
    )))
}

fn environment() -> Environment<'static> {
    let mut env = Environment::new();
    // A typo should fail loudly instead of silently producing an empty string.
    env.set_undefined_behavior(UndefinedBehavior::Strict);
    // Indentation before a block tag is dropped, but the newline after it is kept, so text
    // that follows an inline `{% endif %}` never gets glued to the next line.
    env.set_syntax(
        SyntaxConfig::builder()
            .lstrip_blocks(true)
            .keep_trailing_newline(true)
            .build()
            .expect("valid built-in syntax configuration"),
    );
    // Prompts are plain text, not HTML.
    env.set_auto_escape_callback(|_| minijinja::AutoEscape::None);
    env.add_filter("fromjson", fromjson_filter);
    env
}

/// Parse a JSON string (for example `item_comments`) into a value the template can loop over.
fn fromjson_filter(text: String) -> Result<Value, Error> {
    let parsed: serde_json::Value = serde_json::from_str(&text).map_err(|e| {
        Error::new(
            ErrorKind::InvalidOperation,
            format!("fromjson: invalid JSON: {e}"),
        )
    })?;
    Ok(Value::from(Serde(&parsed)))
}

/// Rewrite `${name}` into a lookup of the raw field text, for names that exist.
///
/// Unknown names stay as written. Only the template is rewritten, never field values.
fn legacy_to_jinja(template: &str, exists: impl Fn(&str) -> bool) -> String {
    let mut out = String::with_capacity(template.len());
    let mut i = 0;
    while i < template.len() {
        if template.as_bytes()[i] == b'$' {
            if let Some((name, end)) = braced_name(template, i) {
                if exists(name) {
                    out.push_str(&format!("{{{{ {RAW}[{name:?}] }}}}"));
                    i = end;
                    continue;
                }
            }
            if let Some(end) = bare_automation(template, i) {
                out.push_str(&format!("{{{{ {RAW}[\"automation\"] }}}}"));
                i = end;
                continue;
            }
        }
        // Copy one UTF-8 character.
        let ch = template[i..].chars().next().unwrap_or(' ');
        out.push(ch);
        i += ch.len_utf8();
    }
    out
}

/// Every `${name}` in the template (names that are identifiers or other keys).
fn legacy_names(template: &str) -> Vec<String> {
    let mut names = Vec::new();
    let mut i = 0;
    while let Some(offset) = template[i..].find("${") {
        let start = i + offset;
        match braced_name(template, start) {
            Some((name, end)) => {
                names.push(name.to_string());
                i = end;
            }
            None => i = start + 2,
        }
    }
    names
}

fn braced_name(template: &str, start: usize) -> Option<(&str, usize)> {
    let rest = template.get(start..)?.strip_prefix("${")?;
    let close = rest.find('}')?;
    let name = &rest[..close];
    let usable = !name.is_empty() && !name.contains("${") && !name.contains(['\n', '"', '\\']);
    usable.then_some((name, start + 2 + close + 1))
}

fn bare_automation(template: &str, start: usize) -> Option<usize> {
    let rest = template.get(start..)?.strip_prefix("$automation")?;
    let next = rest.chars().next();
    next.is_none_or(|c| !(c.is_ascii_alphanumeric() || c == '_'))
        .then_some(start + "$automation".len())
}

fn is_identifier(name: &str) -> bool {
    let mut chars = name.chars();
    chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// Turn a template error into one message that says where and what to do.
fn describe(label: &str, template: &str, error: &Error, fields: &[String]) -> String {
    let mut message = format!(
        "automation {label:?}: prompt template error: {}",
        brief(error)
    );
    if let Some(line) = error.line() {
        // The legacy rewrite keeps line numbers, so this points at the user's own text.
        message.push_str(&format!(" (line {line}"));
        if let Some(text) = template.lines().nth(line.saturating_sub(1)) {
            message.push_str(&format!(": {:?}", text.trim()));
        }
        message.push(')');
    }
    if error.kind() == ErrorKind::UndefinedError && !fields.is_empty() {
        message.push_str(&format!(". Available fields: {}", fields.join(", ")));
    }
    message
}

fn brief(error: &Error) -> String {
    match error.kind() {
        ErrorKind::UndefinedError => {
            "a field used by the prompt has no value for this task (use {{ name | default(\"\") }} \
             for optional fields; if the braces are literal text, wrap it in {% raw %}...{% endraw %})"
                .to_string()
        }
        ErrorKind::SyntaxError => format!(
            "{}. Jinja blocks look like {{% if x %}}...{{% endif %}} and {{% for a in b %}}...{{% endfor %}}",
            error.detail().unwrap_or("syntax error")
        ),
        _ => error
            .detail()
            .map_or_else(|| error.to_string(), ToString::to_string),
    }
}

/// The known name closest to `name`, when it is near enough to be a likely typo.
fn closest(name: &str, known: &[String]) -> Option<String> {
    known
        .iter()
        .map(|candidate| (distance(name, candidate), candidate))
        .filter(|(d, candidate)| *d <= 2.max(candidate.len() / 4))
        .min_by_key(|(d, _)| *d)
        .map(|(_, candidate)| candidate.clone())
}

fn distance(a: &str, b: &str) -> usize {
    let b: Vec<char> = b.chars().collect();
    let mut row: Vec<usize> = (0..=b.len()).collect();
    for (i, ca) in a.chars().enumerate() {
        let mut prev = row[0];
        row[0] = i + 1;
        for (j, cb) in b.iter().enumerate() {
            let cost = usize::from(ca != *cb);
            let next = (row[j + 1] + 1).min(row[j] + 1).min(prev + cost);
            prev = row[j + 1];
            row[j + 1] = next;
        }
    }
    row[b.len()]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pair(key: &str, value: &str) -> KeyValue {
        KeyValue {
            key: key.into(),
            value: value.into(),
        }
    }

    fn values() -> Vec<KeyValue> {
        vec![
            pair("item_number", "7"),
            pair("item_title", "Crash {{ boom }} {% if x %}"),
            pair("item_labels", r#"["bug","security"]"#),
            pair("item_type", "issue"),
            pair("item_comments", r#"[{"author":"ana","body":"hi"}]"#),
            pair("flag", "true"),
            pair("issue-number", "42"),
            pair("project_fields", r#"{"Status":"Ready"}"#),
        ]
    }

    fn render_ok(template: &str) -> String {
        render(template, &values(), "acme/api", "fix").expect("render")
    }

    #[test]
    fn dollar_placeholders_still_work() {
        assert_eq!(
            render_ok("Fix ${item_number} in ${repository} by ${automation}"),
            "Fix 7 in acme/api by fix"
        );
    }

    #[test]
    fn dollar_placeholders_accept_any_key_and_keep_raw_text() {
        assert_eq!(
            render_ok("${issue-number} ${item_labels}"),
            r#"42 ["bug","security"]"#
        );
    }

    #[test]
    fn unknown_dollar_placeholders_and_shell_text_are_left_alone() {
        assert_eq!(
            render_ok("cost $5 and ${HOME} and ${not valid} and ${ and $"),
            "cost $5 and ${HOME} and ${not valid} and ${ and $"
        );
    }

    #[test]
    fn field_text_is_never_interpreted_as_a_template() {
        assert_eq!(render_ok("${item_title}"), "Crash {{ boom }} {% if x %}");
        assert_eq!(render_ok("{{ item_title }}"), "Crash {{ boom }} {% if x %}");
    }

    #[test]
    fn conditionals_and_lists_use_fromjson() {
        let template = "{% if 'security' in item_labels | fromjson %}\nSECURITY\n{% else %}\nplain\n{% endif %}\nend";
        assert_eq!(render_ok(template), "\nSECURITY\n\nend");
        assert_eq!(
            render_ok("{% for l in item_labels | fromjson %}- {{ l }}\n{% endfor %}"),
            "- bug\n- security\n"
        );
        assert_eq!(
            render_ok(
                "{% for c in item_comments | fromjson %}{{ c.author }}:{{ c.body }}{% endfor %}"
            ),
            "ana:hi"
        );
    }

    #[test]
    fn newline_after_a_block_tag_is_kept() {
        assert_eq!(
            render_ok("{% if flag == 'true' %}yes{% endif %}\nnext"),
            "yes\nnext"
        );
        assert_eq!(render_ok("a\n{%- if flag %}b{% endif -%}\nc"), "abc");
    }

    #[test]
    fn numbers_compare_after_int_filter() {
        assert_eq!(
            render_ok("{% if item_number | int > 5 %}big{% endif %}"),
            "big"
        );
    }

    #[test]
    fn missing_jinja_field_is_an_error_with_available_names() {
        let err = render("{{ nope }}", &values(), "acme/api", "fix")
            .unwrap_err()
            .to_string();
        assert!(err.contains("fix"), "{err}");
        assert!(err.contains("item_number"), "{err}");
        assert!(err.contains("raw"), "{err}");
    }

    #[test]
    fn default_filter_makes_optional_fields_safe() {
        assert_eq!(render_ok("[{{ nope | default('n/a') }}]"), "[n/a]");
        let fields = pair("project_fields", r#"{"Status":"Ready"}"#);
        let template = "{% set f = project_fields | fromjson %}{{ f.Priority | default('none') }}/{{ f.Status }}";
        assert_eq!(render(template, &[fields], "r", "a").unwrap(), "none/Ready");
    }

    #[test]
    fn raw_block_keeps_literal_braces() {
        assert_eq!(
            render_ok("{% raw %}${{ secrets.TOKEN }}{% endraw %}"),
            "${{ secrets.TOKEN }}"
        );
    }

    #[test]
    fn check_suggests_close_names_for_jinja_and_dollar() {
        let known = vec!["item_title".to_string(), "item_body".to_string()];
        for template in ["${item_titel}", "{{ item_titel }}"] {
            let err = check("a", template, Some(&known)).unwrap_err().to_string();
            assert!(err.contains("did you mean \"item_title\""), "{err}");
            assert!(err.contains("Available fields"), "{err}");
        }
    }

    #[test]
    fn check_ignores_unrelated_dollar_names_but_not_jinja_ones() {
        let known = vec!["item_title".to_string()];
        check("a", "${HOME} ${PATH}", Some(&known)).expect("shell text is fine");
        assert!(check("a", "{{ HOME }}", Some(&known)).is_err());
    }

    #[test]
    fn check_accepts_loop_variables_and_host_fields() {
        let known = vec!["item_labels".to_string()];
        check(
            "a",
            "{% for l in item_labels | fromjson %}{{ l }} {{ repository }} ${automation}{% endfor %}",
            Some(&known),
        )
        .expect("valid");
    }

    #[test]
    fn syntax_errors_name_the_line() {
        let err = check("a", "ok\n{% if x %}\nunclosed", None)
            .unwrap_err()
            .to_string();
        assert!(err.contains("line"), "{err}");
        assert!(err.contains("endif"), "{err}");
    }

    #[test]
    fn without_declared_fields_only_syntax_is_checked() {
        check("a", "${whatever} {{ anything }}", None).expect("syntax only");
    }
}
