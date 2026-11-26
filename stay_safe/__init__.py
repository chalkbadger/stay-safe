import os
from pathlib import Path
import stat
import sys


FEEDBACK = "Report a problem or suggest an idea: https://github.com/chalkbadger/stay-safe/issues/new/choose\n"


def command(path):
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
        NEXT = "Select or install a supported Python: https://github.com/chalkbadger/stay-safe/blob/main/docs/usage.md#python-setup"
    sys.stderr.write("stay-safe needs Python 3.11 or newer; this is Python %s. %s\n" % (THIS, NEXT))
    sys.stderr.write(FEEDBACK)
    sys.exit(2)
