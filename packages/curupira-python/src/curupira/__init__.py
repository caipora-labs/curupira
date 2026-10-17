"""Curupira Python distribution layer.

The CLI implementation is the Rust binary installed by this package. Only
``__version__`` is a supported programmatic export.
"""

from importlib.metadata import version

__all__ = ["__version__"]

# Read from the installed distribution, whose version comes from the release tag.
__version__ = version("curupira")
