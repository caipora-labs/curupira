"""Thin Python wrapper around the compiled ``opscli._native`` extension."""

from opscli._native import rust_core_version as _rust_core_version


def rust_core_version() -> str:
    """Return the ``opscli-core`` crate version compiled into this install."""
    version = _rust_core_version()
    if version == "":
        message = "opscli._native.rust_core_version() returned an empty version"
        raise RuntimeError(message)
    return version


__all__ = ["rust_core_version"]
