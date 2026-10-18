//! Prompt templates for automations.
//!
//! A prompt is plain text with two kinds of markup, both optional:
//!
//! * `${name}` inserts a field. This is the simple form and covers most prompts.
//! * Jinja syntax (`{{ name }}`, `{% if %}`, `{% for %}`, filters) makes a prompt dynamic.
//!
//! Item fields come from the trigger. Their values are data: a title or body that contains
//! `{{` or `{%` is inserted as-is and never interpreted, because the template is compiled
//! once and rendered once with the item as the context.

use std::collections::BTreeSet;

use minijinja::{Environment, Error, ErrorKind, UndefinedBehavior, Value};
use serde_json::{Map, Value as Json};

use crate::error::CurupiraError;

/// Names the host provides for every automation, in addition to the trigger's item fields.
pub const COMMON_FIELDS: &[&str] = &[
    "repo",
    "repository",
    "automation",
    "automation_id",
    "task_type",
    "task_number",
    "task_title",
    "task_body",
    "task_url",
];

/// Common fields followed by the trigger's own, for error messages and checks.
pub fn available_fields(trigger_fields: &[String]) -> Vec<String> {
    let mut names: BTreeSet<String> = COMMON_FIELDS.iter().map(|s| (*s).to_string()).collect();
    names.extend(trigger_fields.iter().cloned());
    names.into_iter().collect()
}

/// Render `template` with `vars` (a JSON object). `label` names the automation in errors.
pub fn render(label: &str, template: &str, vars: &Json) -> Result<String, CurupiraError> {
    let source = legacy_to_jinja(template);
    let env = environment();
    env.render_str(&source, Value::from_serialize(vars))
        .map_err(|e| {
            let names: Vec<String> = vars
                .as_object()
                .map(|o| o.keys().cloned().collect())
                .unwrap_or_default();
            CurupiraError::Dispatch(describe(label, template, &e, &names))
        })
}

/// Check a prompt at `validate` time: syntax, and that every field it uses exists.
///
/// `known` is `None` when the trigger does not declare its fields; only syntax is checked then.
pub fn check(label: &str, template: &str, known: Option<&[String]>) -> Result<(), CurupiraError> {
    let source = legacy_to_jinja(template);
    let env = environment();
    let compiled = env
        .template_from_str(&source)
        .map_err(|e| CurupiraError::Config(describe(label, template, &e, &[])))?;
    let Some(known) = known else {
        return Ok(());
    };
    let allowed = available_fields(known);
    let mut unknown: Vec<String> = compiled
        .undeclared_variables(false)
        .into_iter()
        .filter(|name| !allowed.contains(name))
        .collect();
    unknown.sort();
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

/// Build the variables for one task: common fields first, then the item (which wins).
pub fn task_vars(common: &[(&str, String)], item: &Json) -> Json {
    let mut map = Map::new();
    for (name, value) in common {
        map.insert((*name).to_string(), Json::String(value.clone()));
    }
    if let Some(object) = item.as_object() {
        for (name, value) in object {
            map.insert(name.clone(), value.clone());
        }
    }
    Json::Object(map)
}

fn environment() -> Environment<'static> {
    let mut env = Environment::new();
    // A typo should fail loudly instead of silently producing an empty string.
    env.set_undefined_behavior(UndefinedBehavior::Strict);
    // Indentation before a block tag is dropped, but the newline after it is kept, so text
    // that follows an inline `{% endif %}` never gets glued to the next line.
    env.set_lstrip_blocks(true);
    env.set_keep_trailing_newline(true);
    // Prompts are plain text, not HTML.
    env.set_auto_escape_callback(|_| minijinja::AutoEscape::None);
    env.add_filter("legacy", legacy_filter);
    env.add_filter("fromjson", fromjson_filter);
    env
}

/// `${name}` rendering: strings as-is, everything else as compact JSON.
fn legacy_filter(value: Value) -> Result<Value, Error> {
    if let Some(text) = value.as_str() {
        return Ok(Value::from(text.to_string()));
    }
    let json = serde_json::to_string(&value).map_err(|e| {
        Error::new(
            ErrorKind::InvalidOperation,
            format!("cannot render value: {e}"),
        )
    })?;
    Ok(Value::from(json))
}

/// Parse a JSON string (for example `item_comments`) into a value the template can loop over.
fn fromjson_filter(text: String) -> Result<Value, Error> {
    let parsed: Json = serde_json::from_str(&text).map_err(|e| {
        Error::new(
            ErrorKind::InvalidOperation,
            format!("fromjson: invalid JSON: {e}"),
        )
    })?;
    Ok(Value::from_serialize(&parsed))
}

/// Rewrite `${name}` (and the old bare `$automation`) into `{{ name | legacy }}`.
///
/// Only the template is rewritten, never item values.
fn legacy_to_jinja(template: &str) -> String {
    let mut out = String::with_capacity(template.len());
    let bytes = template.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'$' {
            if let Some((name, end)) = braced_name(template, i) {
                out.push_str(&format!("{{{{ {name} | legacy }}}}"));
                i = end;
                continue;
            }
            if let Some(end) = bare_automation(template, i) {
                out.push_str("{{ automation | legacy }}");
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

fn braced_name(template: &str, start: usize) -> Option<(&str, usize)> {
    let rest = template.get(start..)?.strip_prefix("${")?;
    let close = rest.find('}')?;
    let name = &rest[..close];
    is_identifier(name).then_some((name, start + 2 + close + 1))
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
            "a field used by the prompt has no value for this item (use {{ name | default(\"\") }} \
             for optional fields)"
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
    use serde_json::json;

    fn vars() -> Json {
        task_vars(
            &[
                ("automation", "fix".to_string()),
                ("repo", "acme/api".to_string()),
            ],
            &json!({
                "item_number": 7,
                "item_title": "Crash {{ boom }} {% if x %}",
                "item_labels": ["bug", "security"],
                "item_type": "issue",
                "item_comments": "[{\"author\":\"ana\",\"body\":\"hi\"}]",
                "flag": true,
            }),
        )
    }

    fn render_ok(template: &str) -> String {
        render("t", template, &vars()).expect("render")
    }

    #[test]
    fn dollar_placeholders_still_work() {
        assert_eq!(
            render_ok("Fix ${item_number} in ${repo} by $automation / ${automation}"),
            "Fix 7 in acme/api by fix / fix"
        );
    }

    #[test]
    fn dollar_renders_lists_and_bools_as_json() {
        assert_eq!(
            render_ok("${item_labels} ${flag}"),
            r#"["bug","security"] true"#
        );
    }

    #[test]
    fn item_text_is_never_interpreted_as_a_template() {
        assert_eq!(render_ok("${item_title}"), "Crash {{ boom }} {% if x %}");
        assert_eq!(render_ok("{{ item_title }}"), "Crash {{ boom }} {% if x %}");
    }

    #[test]
    fn conditionals_and_lists() {
        let template =
            "{% if 'security' in item_labels %}\nSECURITY\n{% else %}\nplain\n{% endif %}\nend";
        assert_eq!(render_ok(template), "\nSECURITY\n\nend");
        assert_eq!(
            render_ok("{% if flag %}yes{% endif %}\nnext"),
            "yes\nnext",
            "the newline after a block tag is kept"
        );
        assert_eq!(render_ok("a\n{%- if flag %}b{% endif -%}\nc"), "abc");
        assert_eq!(
            render_ok("{% for l in item_labels %}- {{ l }}\n{% endfor %}"),
            "- bug\n- security\n"
        );
    }

    #[test]
    fn fromjson_filter_unpacks_comment_json() {
        assert_eq!(
            render_ok(
                "{% for c in item_comments | fromjson %}{{ c.author }}:{{ c.body }}{% endfor %}"
            ),
            "ana:hi"
        );
    }

    #[test]
    fn missing_field_is_an_error_with_available_names() {
        let err = render("fix", "{{ nope }}", &vars())
            .unwrap_err()
            .to_string();
        assert!(err.contains("fix"), "{err}");
        assert!(err.contains("item_number"), "{err}");
    }

    #[test]
    fn default_filter_makes_optional_fields_safe() {
        assert_eq!(render_ok("[{{ nope | default('n/a') }}]"), "[n/a]");
    }

    #[test]
    fn check_suggests_close_names() {
        let known = vec!["item_title".to_string(), "item_body".to_string()];
        let err = check("a", "${item_titel}", Some(&known))
            .unwrap_err()
            .to_string();
        assert!(err.contains("did you mean \"item_title\""), "{err}");
        assert!(err.contains("Available fields"), "{err}");
    }

    #[test]
    fn check_accepts_loop_variables_and_common_fields() {
        let known = vec!["item_labels".to_string()];
        check(
            "a",
            "{% for l in item_labels %}{{ l }} {{ repo }}{% endfor %}",
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
        check("a", "${whatever}", None).expect("syntax only");
    }

    #[test]
    fn missing_map_key_can_be_defaulted() {
        let vars = task_vars(&[], &json!({"project_fields": "{\"Status\":\"Ready\"}"}));
        let template = "{% set f = project_fields | fromjson %}{{ f.Priority | default('none') }}/{{ f.Status }}";
        check("t", template, Some(&["project_fields".to_string()])).expect("valid");
        assert_eq!(render("t", template, &vars).unwrap(), "none/Ready");
    }

    #[test]
    fn plain_dollar_text_is_untouched() {
        assert_eq!(
            render_ok("cost $5 and ${not valid} and $"),
            "cost $5 and ${not valid} and $"
        );
    }
}
