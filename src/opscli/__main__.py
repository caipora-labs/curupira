"""Compatibility entry point for ``python -m opscli`` in source checkouts."""

from curupira.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
