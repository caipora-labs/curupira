"""Thin Python wrapper around the compiled ``curupi._native`` extension."""

from curupi._native import rust_core_version as _rust_core_version


def rust_core_version() -> str:
    """Return the ``curupi-core`` crate version compiled into this install."""
    version = _rust_core_version()
    if version == "":
        message = "curupi._native.rust_core_version() returned an empty version"
        raise RuntimeError(message)
    return version


__all__ = ["rust_core_version"]
