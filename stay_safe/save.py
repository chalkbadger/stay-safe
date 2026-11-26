import os
import tempfile
from pathlib import Path

from .provenance import ROOT, INSTALLED

NAME = "stay-safe-report.html"


def save(text, root=None):
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
