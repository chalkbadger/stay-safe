"""Save the report page: the only code in stay-safe that writes a file (archived issue #106)."""

import os
import tempfile
from pathlib import Path

from .provenance import ROOT, INSTALLED

NAME = "stay-safe-report.html"


def save(text, root=None):
    """Replace NAME in the checkout with text; return its path, or None if it could not be written.

    The page is written to a new temporary file beside it and moved into place, so a reader never sees a partial
    page and an existing symlink or hard link at NAME is replaced rather than written through.
    """
    try:
        root = root if root is not None else Path(".").resolve() if INSTALLED else ROOT
        handle, temporary = tempfile.mkstemp(dir=root, prefix=".stay-safe-report.", suffix=".tmp")
    except OSError:
        return None
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, root / NAME)
    except (OSError, ValueError):
        try:
            os.unlink(temporary)
        except OSError:
            pass
        return None
    return root / NAME
