// Version strings from release tags. Shared by build.rs (through `include!`) and the crate's
// tests, so it uses only the standard library.

/// Prefix of the tags that release the CLI, e.g. `publish/curupira-cli/0.3.1`.
const TAG_PREFIX: &str = "publish/curupira-cli/";

/// The binary's version from `git describe --tags --long --match 'publish/curupira-cli/*'`
/// output: the tag's version on a tagged commit, else `<version>+<commits>.g<sha>`.
fn version_from_describe(describe: &str) -> Option<String> {
    let rest = describe.trim().strip_prefix(TAG_PREFIX)?;
    let mut parts = rest.rsplitn(3, '-');
    let sha = parts.next()?;
    let commits: u32 = parts.next()?.parse().ok()?;
    let version = cargo_version(parts.next()?)?;
    if !sha.starts_with('g') {
        return None;
    }
    Some(if commits == 0 {
        version
    } else {
        format!("{version}+{commits}.{sha}")
    })
}

/// The SemVer form Cargo uses for a PEP 440 release tag, as the release workflow stamps it:
/// `0.3.0.dev0` becomes `0.3.0-dev0` and `0.3.0rc1` becomes `0.3.0-rc.1`.
fn cargo_version(tag: &str) -> Option<String> {
    let (release, dev) = match tag.split_once(".dev") {
        Some((release, dev)) => (release, Some(dev)),
        None => (tag, None),
    };
    let split = release
        .find(|c: char| c.is_ascii_alphabetic())
        .unwrap_or(release.len());
    let (numbers, pre) = release.split_at(split);
    let parts: Vec<&str> = numbers.split('.').collect();
    if parts.is_empty() || parts.iter().any(|p| p.is_empty() || !p.chars().all(|c| c.is_ascii_digit())) {
        return None;
    }
    let numbers = parts.join(".");
    if !pre.is_empty() {
        for (letter, name) in [("rc", "rc"), ("a", "alpha"), ("b", "beta")] {
            if let Some(number) = pre.strip_prefix(letter) {
                if !number.is_empty() && number.chars().all(|c| c.is_ascii_digit()) {
                    return Some(format!("{numbers}-{name}.{number}"));
                }
            }
        }
        return None;
    }
    match dev {
        Some(dev) if !dev.is_empty() && dev.chars().all(|c| c.is_ascii_digit()) => {
            Some(format!("{numbers}-dev{dev}"))
        }
        Some(_) => None,
        None => Some(numbers),
    }
}
