//! Package version shared with the Python distribution layer.

/// Version reported by `--version` and shown in the TUI. In a git checkout it is the latest
/// `publish/curupira-cli` tag (with the commits since); otherwise the Cargo.toml version, which
/// releases stamp from the tag. See build.rs.
pub const VERSION: &str = env!("CURUPIRA_VERSION");

/// [`VERSION`] without the commit hash, for tight spaces: `0.3.1+4` instead of
/// `0.3.1+4.g1a2b3c4`.
#[must_use]
pub fn short_version() -> &'static str {
    VERSION.split(".g").next().unwrap_or(VERSION)
}

#[cfg(test)]
mod tests {
    include!("version_describe.rs");

    #[test]
    fn tagged_commit_reports_the_tag() {
        assert_eq!(
            version_from_describe("publish/curupira-cli/0.3.1-0-g1a2b3c4").as_deref(),
            Some("0.3.1")
        );
    }

    #[test]
    fn later_commits_add_build_metadata() {
        assert_eq!(
            version_from_describe("publish/curupira-cli/0.3.1-12-g1a2b3c4\n").as_deref(),
            Some("0.3.1+12.g1a2b3c4")
        );
        assert_eq!(
            version_from_describe("publish/curupira-cli/0.4.0rc1-3-gabcdef0").as_deref(),
            Some("0.4.0-rc.1+3.gabcdef0")
        );
    }

    #[test]
    fn other_tags_and_malformed_output_are_ignored() {
        for describe in [
            "publish/curupira-sdk-py/0.1.0-0-g1a2b3c4",
            "publish/curupira-cli/0.3.1",
            "publish/curupira-cli/0.3.1-x-g1a2b3c4",
            "publish/curupira-cli/0.3.1-2-1a2b3c4",
            "publish/curupira-cli/latest-0-g1a2b3c4",
            "",
        ] {
            assert_eq!(version_from_describe(describe), None, "{describe:?}");
        }
    }

    #[test]
    fn tags_convert_like_the_release_stamp() {
        // Same table as cargo_version in packages/curupira-cli-py/scripts/publish_tag.py.
        for (tag, cargo) in [
            ("0.3.1", Some("0.3.1")),
            ("1.2", Some("1.2")),
            ("0.3.0.dev0", Some("0.3.0-dev0")),
            ("0.3.0rc1", Some("0.3.0-rc.1")),
            ("1.2.0a2", Some("1.2.0-alpha.2")),
            ("1.2.0b1", Some("1.2.0-beta.1")),
            ("1.2.0c1", None),
            ("1.2.0rc", None),
            ("1..2", None),
            ("v1.2.0", None),
        ] {
            assert_eq!(cargo_version(tag).as_deref(), cargo, "{tag}");
        }
    }

    #[test]
    fn short_version_drops_only_the_commit_hash() {
        let short = super::short_version();
        assert!(super::VERSION.starts_with(short));
        assert!(!short.contains(".g"), "{short}");
    }

    #[test]
    fn version_is_a_release_number() {
        assert!(
            super::VERSION.starts_with(|c: char| c.is_ascii_digit()),
            "{}",
            super::VERSION
        );
        assert!(super::VERSION
            .split(['-', '+'])
            .next()
            .unwrap()
            .split('.')
            .all(|p| p.parse::<u32>().is_ok()));
    }
}
