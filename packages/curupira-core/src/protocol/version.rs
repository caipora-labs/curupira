//! Protocol version negotiation.

use serde::{Deserialize, Serialize};

/// Current protocol version implemented by this crate.
pub const CURRENT_PROTOCOL_VERSION: u32 = 1;

/// Oldest protocol version this host will accept.
pub const MIN_PROTOCOL_VERSION: u32 = 1;

/// Negotiated protocol version pair.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProtocolVersion {
    /// Version the peer speaks.
    pub version: u32,
}

/// Return whether `peer` is acceptable to this host.
#[must_use]
pub fn is_compatible(peer: u32) -> bool {
    (MIN_PROTOCOL_VERSION..=CURRENT_PROTOCOL_VERSION).contains(&peer)
}

/// Negotiate a version, returning the peer version when compatible.
pub fn negotiate(peer: u32) -> Result<ProtocolVersion, String> {
    if is_compatible(peer) {
        Ok(ProtocolVersion { version: peer })
    } else {
        Err(format!(
            "incompatible extension protocol version {peer} (host supports {MIN_PROTOCOL_VERSION}..={CURRENT_PROTOCOL_VERSION})"
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_current() {
        assert!(is_compatible(CURRENT_PROTOCOL_VERSION));
        assert!(negotiate(1).is_ok());
    }

    #[test]
    fn rejects_future() {
        assert!(!is_compatible(99));
        assert!(negotiate(99).is_err());
    }
}
