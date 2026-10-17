//! Language-independent Curupira extension protocol.
//!
//! Transport is JSON-RPC 2.0 over stdin/stdout with length-prefixed frames.
//! Stdout is reserved for protocol frames; diagnostics go to stderr.

mod error;
mod framing;
mod manifest;
mod methods;
mod version;

pub use error::{ErrorCode, ProtocolError, RpcError};
pub use framing::{read_frame, write_frame, FrameError, DEFAULT_MAX_FRAME_BYTES};
pub use manifest::{
    ExtensionCapability, ExtensionKind, ExtensionManifest, ExtensionRuntime, LaunchSpec,
    PackageRef, MANIFEST_FILE_NAME,
};
pub use methods::*;
pub use version::{
    is_compatible, negotiate, ProtocolVersion, CURRENT_PROTOCOL_VERSION, MIN_PROTOCOL_VERSION,
};
