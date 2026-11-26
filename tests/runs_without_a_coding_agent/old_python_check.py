import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "runs_without_a_coding_agent" / "sample.toml"
FAKE = "#!/bin/sh\necho started > \"$(dirname \"$0\")/started-$(basename \"$0\")\"\n"


FEEDBACK = "Report a problem or suggest an idea: https://github.com/chalkbadger/stay-safe/issues/new/choose\n"

def main():
    this = "%d.%d.%d" % tuple(sys.version_info[:3])
    if sys.version_info >= (3, 11):
        print("FAIL: Python %s at %s is 3.11 or newer, so nothing was checked." % (this, sys.executable))
        return 1
    start = "stay-safe needs Python 3.11 or newer; this is Python %s. " % this
    failures = 0
    with tempfile.TemporaryDirectory() as empty, tempfile.TemporaryDirectory() as newer:
        for name, mode in (("python3.12", 0o755), ("python3.13", 0o644)):
            (Path(newer) / name).write_text(FAKE, encoding="utf-8")
            (Path(newer) / name).chmod(mode)
        cases = ((empty, start + "Select or install a supported Python: https://github.com/chalkbadger/stay-safe/blob/main/docs/usage.md#python-setup\n" + FEEDBACK),
                 (newer, start + "Run: python3.12 -m stay_safe\n" + FEEDBACK))
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
