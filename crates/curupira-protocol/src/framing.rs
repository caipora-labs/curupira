//! Length-prefixed JSON frames on a byte stream.
//!
//! Each frame is: 8 ASCII hex digits (big-endian length) + UTF-8 JSON body.
//! Newline-delimited JSON is intentionally not used.

use std::io::{Read, Write};

use thiserror::Error;

/// Default maximum accepted frame payload (16 MiB).
pub const DEFAULT_MAX_FRAME_BYTES: u32 = 16 * 1024 * 1024;

/// Framing failures.
#[derive(Debug, Error)]
pub enum FrameError {
    #[error("unexpected EOF while reading frame header")]
    UnexpectedEof,
    #[error("invalid frame header")]
    InvalidHeader,
    #[error("frame length {length} exceeds limit {limit}")]
    TooLarge { length: u32, limit: u32 },
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}

/// Write one length-prefixed JSON frame.
pub fn write_frame<W: Write>(writer: &mut W, payload: &[u8]) -> Result<(), FrameError> {
    let len = u32::try_from(payload.len()).map_err(|_| FrameError::TooLarge {
        length: u32::MAX,
        limit: DEFAULT_MAX_FRAME_BYTES,
    })?;
    write!(writer, "{len:08x}")?;
    writer.write_all(payload)?;
    writer.flush()?;
    Ok(())
}

/// Read one length-prefixed JSON frame.
pub fn read_frame<R: Read>(reader: &mut R, max_bytes: u32) -> Result<Vec<u8>, FrameError> {
    let mut header = [0_u8; 8];
    if let Err(error) = reader.read_exact(&mut header) {
        if error.kind() == std::io::ErrorKind::UnexpectedEof {
            return Err(FrameError::UnexpectedEof);
        }
        return Err(FrameError::Io(error));
    }
    let header_str = std::str::from_utf8(&header).map_err(|_| FrameError::InvalidHeader)?;
    let length = u32::from_str_radix(header_str, 16).map_err(|_| FrameError::InvalidHeader)?;
    if length > max_bytes {
        return Err(FrameError::TooLarge {
            length,
            limit: max_bytes,
        });
    }
    let mut body = vec![0_u8; length as usize];
    reader.read_exact(&mut body)?;
    Ok(body)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn round_trip() {
        let mut buf = Vec::new();
        write_frame(&mut buf, br#"{"ok":true}"#).unwrap();
        let mut cursor = Cursor::new(buf);
        let body = read_frame(&mut cursor, DEFAULT_MAX_FRAME_BYTES).unwrap();
        assert_eq!(body, br#"{"ok":true}"#);
    }

    #[test]
    fn rejects_oversized() {
        let mut buf = Vec::new();
        write_frame(&mut buf, b"hello").unwrap();
        let mut cursor = Cursor::new(buf);
        let err = read_frame(&mut cursor, 2).unwrap_err();
        assert!(matches!(err, FrameError::TooLarge { .. }));
    }
}
