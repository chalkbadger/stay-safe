"""Run stay-safe on a real Python older than 3.11, both as `python -m stay_safe` and `python stay_safe` (issue #48).

The CI job in .github/workflows/checks.yml runs this with Python 3.9, and on macOS also with Apple's /usr/bin/python3.
Each run gets a PATH holding only a temporary folder: empty, so the message says to install Python 3.11 or newer, or
holding a runnable python3.12 (and a python3.13 that can't be run), so the message names python3.12. It checks the
exit status 2, the exact line on stderr, an empty stdout, and that the fake python3.12 was not started. On Python 3.11
or newer it has nothing to check, says so and exits 0. Not a unittest module: the test suite runs on Python 3.11+.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "runs_without_a_coding_agent" / "sample.toml"
FAKE = "#!/bin/sh\necho started > \"$(dirname \"$0\")/started-$(basename \"$0\")\"\n"


def main():
    this = "%d.%d.%d" % tuple(sys.version_info[:3])
    if sys.version_info >= (3, 11):
        print("Python %s at %s is 3.11 or newer; nothing to check." % (this, sys.executable))
        return 0
    start = "stay-safe needs Python 3.11 or newer; this is Python %s. " % this
    failures = 0
    with tempfile.TemporaryDirectory() as empty, tempfile.TemporaryDirectory() as newer:
        for name, mode in (("python3.12", 0o755), ("python3.13", 0o644)):
            (Path(newer) / name).write_text(FAKE, encoding="utf-8")
            (Path(newer) / name).chmod(mode)
        cases = ((empty, start + "Install Python 3.11 or newer, then run: python3.11 -m stay_safe\n"),
                 (newer, start + "Run: python3.12 -m stay_safe\n"))
        for path, expected in cases:
            for way in (["-m", "stay_safe"], ["stay_safe"]):
                command = [sys.executable, "-B"] + way + ["--config", str(SAMPLE)]
                run = subprocess.run(command, cwd=str(ROOT), env=dict(os.environ, PATH=path),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                     timeout=60)
                started = sorted(p.name for p in Path(path).iterdir() if p.name.startswith("started-"))
                ok = (run.returncode, run.stdout, run.stderr, started) == (2, "", expected, [])
                failures += not ok
                print("%s: %s with PATH=<%s>: exit %d, stdout %r, stderr %r, started %r" % (
                    "ok" if ok else "FAIL", " ".join(["python"] + way), "empty" if path == empty else "newer",
                    run.returncode, run.stdout, run.stderr, started))
                if not ok:
                    print("  expected: exit 2, stdout '', stderr %r, started []" % expected)
    print("Python %s at %s: %d failure(s)" % (this, sys.executable, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
