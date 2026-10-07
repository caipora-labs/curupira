"""Thin Python wrapper around the compiled ``curupira._native`` extension."""

from curupira._native import rust_core_version as _rust_core_version


def rust_core_version() -> str:
    """Return the ``curupira-core`` crate version compiled into this install."""
    version = _rust_core_version()
    if version == "":
        message = "curupira._native.rust_core_version() returned an empty version"
        raise RuntimeError(message)
    return version


__all__ = ["rust_core_version"]
