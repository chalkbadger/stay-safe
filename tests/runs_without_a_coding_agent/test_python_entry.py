import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.support import ROOT

SAMPLE = ROOT / "tests" / "runs_without_a_coding_agent" / "sample.toml"
# Runs stay-safe the way `python3 -m stay_safe` (module) or `python3 stay_safe` (folder) does, after making the
# interpreter report itself as Python 3.9.6, macOS's own python3 (issue #48). It prints which stay-safe modules and
# whether tomllib (new in Python 3.11) were loaded when stay-safe stopped, then exits with stay-safe's status.
OLD_PYTHON = """import collections, json, runpy, sys
sys.version = "3.9.6 (default, simulated) [Clang 13.0.0]"
sys.version_info = collections.namedtuple("version_info", "major minor micro releaselevel serial")(3, 9, 6, "final", 0)
way = sys.argv.pop(1)
try:
    if way == "module":
        runpy.run_module("stay_safe", run_name="__main__", alter_sys=True)
    else:
        runpy.run_path("stay_safe", run_name="__main__")
    status = 0
except SystemExit as stop:
    status = stop.code
print(json.dumps(sorted(name for name in sys.modules if name == "tomllib" or name.startswith("stay_safe."))))
sys.exit(status)
"""
TOO_OLD = "stay-safe needs Python 3.11 or newer; this is Python 3.9.6. "
# A command that writes a marker file when started, so a run shows whether stay-safe started it.
FAKE = "#!/bin/sh\necho started > \"$(dirname \"$0\")/started-$(basename \"$0\")\"\n"


def run(*args, env=None):
    return subprocess.run([sys.executable, "-B", *args], cwd=ROOT, env=env or {}, text=True, capture_output=True,
                          timeout=20)


def old_python(way, path):
    """Run stay-safe under the simulated Python 3.9.6 with only `path` on the PATH."""
    return run("-c", OLD_PYTHON, way, "--config", str(SAMPLE), env={"PATH": path})


def commands(folder, executable, plain=()):
    folder = Path(folder)
    for name in executable:
        (folder / name).write_text(FAKE, encoding="utf-8")
        (folder / name).chmod(0o755)
    for name in plain:
        (folder / name).write_text(FAKE, encoding="utf-8")
        (folder / name).chmod(0o644)
    return str(folder)


class PythonEntryTests(unittest.TestCase):
    def test_running_the_folder_without_m_gives_the_same_report_and_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in (["--config", str(SAMPLE)], ["--config", str(SAMPLE), "--format", "json"],
                         ["--config", str(Path(tmp) / "missing.toml")], ["--unknown"]):
                with self.subTest(args=args):
                    module = run("-m", "stay_safe", *args)
                    folder = run("stay_safe", *args)
                    self.assertEqual((folder.returncode, folder.stdout, folder.stderr),
                                     (module.returncode, module.stdout, module.stderr))
        sample = run("stay_safe", "--config", str(SAMPLE))
        self.assertEqual((sample.returncode, sample.stderr), (0, ""))
        self.assertIn("/blob/", sample.stdout)

    def test_too_old_python_names_the_newest_python_on_the_path_and_exits_2(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            # python3.13 here can't be run, so it is not a command; python3.12 is the newest one found.
            path = (commands(first, ["python3", "python3.10", "python3.11"], plain=["python3.13"]) + ":"
                    + commands(second, ["python3.12", "python3.11"]))
            for way in ("module", "folder"):
                with self.subTest(way=way):
                    result = old_python(way, path)
                    self.assertEqual((result.returncode, result.stderr, result.stdout),
                                     (2, TOO_OLD + "Run: python3.12 -m stay_safe\n", "[]\n"))
            commands(second, ["python3.13"])
            result = old_python("module", path)
            self.assertEqual((result.returncode, result.stderr), (2, TOO_OLD + "Run: python3.13 -m stay_safe\n"))
            self.assertEqual(sorted(p.name for p in [*Path(first).iterdir(), *Path(second).iterdir()]
                                    if p.name.startswith("started-")), [])

    def test_too_old_python_without_a_newer_one_says_to_install_it_and_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            path = commands(folder, ["python3", "python3.9", "python3.10", "python3.14"])
            for way in ("module", "folder"):
                with self.subTest(way=way):
                    result = old_python(way, path)
                    self.assertEqual((result.returncode, result.stderr, result.stdout),
                                     (2, TOO_OLD + "Install Python 3.11 or newer, then run: python3.11 -m stay_safe\n",
                                      "[]\n"))

    def test_version_check_runs_before_any_module_needing_3_11_and_parses_as_python_3_9(self):
        with tempfile.TemporaryDirectory() as folder:
            for way in ("module", "folder"):
                with self.subTest(way=way):
                    result = old_python(way, folder)
                    self.assertEqual((result.returncode, result.stdout), (2, "[]\n"))
        # `python3 -m stay_safe` runs __init__.py first; `python3 stay_safe` compiles __main__.py first.
        for name in ("__init__.py", "__main__.py"):
            with self.subTest(name=name):
                ast.parse((ROOT / "stay_safe" / name).read_text(encoding="utf-8"), filename=name,
                          feature_version=(3, 9))
