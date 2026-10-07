"""Smoke checks for the compiled curupi-core extension."""

import pytest


def test_rust_core_version_is_non_empty() -> None:
    native = pytest.importorskip("curupi._native")
    version = native.rust_core_version()
    assert isinstance(version, str)
    assert version.strip()


def test_python_wrapper_returns_the_crate_version() -> None:
    native = pytest.importorskip("curupi._native")
    from curupi.native import rust_core_version

    assert rust_core_version() == native.rust_core_version()
