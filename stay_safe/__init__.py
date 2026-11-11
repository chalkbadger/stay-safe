"""Deterministic configuration diagnostics.

The version check below runs before any module that needs Python 3.11 is imported (issue #48), so this file must
stay parseable by older Pythons, such as macOS's own Python 3.9.
"""
import sys

if sys.version_info < (3, 11):
    import shutil

    THIS = "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    # Only checks that the command exists on the PATH; stay-safe doesn't start it.
    NEWER = [name for name in ("python3.13", "python3.12", "python3.11") if shutil.which(name)]
    if NEWER:
        NEXT = "Run: %s -m stay_safe" % NEWER[0]
    else:
        NEXT = "Install Python 3.11 or newer, then run: python3.11 -m stay_safe"
    # Like the "Invalid arguments" message, this goes to stderr with exit status 2.
    sys.stderr.write("stay-safe needs Python 3.11 or newer; this is Python %s. %s\n" % (THIS, NEXT))
    sys.exit(2)
