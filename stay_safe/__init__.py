"""Deterministic configuration diagnostics.

The version check below runs before any module that needs Python 3.11 is imported (issue #48), so this file must
stay parseable by older Pythons, such as macOS's own Python 3.9.
"""
import os
from pathlib import Path
import stat
import sys


def command(path):
    """Whether `path` is a file with an execute bit set, read from its metadata only; stay-safe never starts it."""
    try:
        return path.is_file() and bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    except OSError:
        return False


if sys.version_info < (3, 11):
    THIS = "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    FOLDERS = [folder for folder in os.environ.get("PATH", "").split(os.pathsep) if folder]
    NEWER = [name for name in ("python3.13", "python3.12", "python3.11")
             if any(command(Path(folder, name)) for folder in FOLDERS)]
    if NEWER:
        NEXT = "Run: %s -m stay_safe" % NEWER[0]
    else:
        NEXT = "Install Python 3.11 or newer, then run: python3.11 -m stay_safe"
    # Like the "Invalid arguments" message, this goes to stderr with exit status 2.
    sys.stderr.write("stay-safe needs Python 3.11 or newer; this is Python %s. %s\n" % (THIS, NEXT))
    sys.exit(2)
