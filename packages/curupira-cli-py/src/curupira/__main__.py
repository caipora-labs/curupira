"""``python -m curupira`` delegates to the installed ``curupira`` binary."""

from __future__ import annotations

import os
import shutil
import sys


def main() -> None:
    """Exec the Rust CLI with the same argv."""
    binary = shutil.which("curupira")
    if binary is None:
        print(
            "curupira binary not found on PATH; reinstall the curupira package",
            file=sys.stderr,
        )
        raise SystemExit(1)
    os.execvp(binary, [binary, *sys.argv[1:]])


if __name__ == "__main__":
    main()
