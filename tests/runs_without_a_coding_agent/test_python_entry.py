import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.support import ROOT

SAMPLE = ROOT / "tests" / "runs_without_a_coding_agent" / "sample.toml"
# Runs stay-safe the way `python3 -m stay_safe` (module) or `python3 stay_safe` (folder) does, after making the
# interpreter report itself as the version given, such as 3.9.6, macOS's own python3 (issue #48). It prints which
# stay-safe modules and whether tomllib (new in Python 3.11) were loaded when stay-safe stopped, then exits with
# stay-safe's status.
OLD_PYTHON = """import collections, json, runpy, sys
way, version = sys.argv.pop(1), sys.argv.pop(1)
sys.version = version + " (default, simulated) [Clang 13.0.0]"
sys.version_info = collections.namedtuple("version_info", "major minor micro releaselevel serial")(
    *map(int, version.split(".")), "final", 0)
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


def old_python(way, path, version="3.9.6"):
    """Run stay-safe under a simulated Python `version` with only `path` on the PATH."""
    return run("-c", OLD_PYTHON, way, version, "--config", str(SAMPLE), env={"PATH": path})


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
                         ["--config", str(Path(tmp) / "missing.toml")], ["--unknown"], ["--help"]):
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
        install = "Install Python 3.11 or newer, then run: python3.11 -m stay_safe\n"
        with tempfile.TemporaryDirectory() as folder:
            path = commands(folder, ["python3", "python3.9", "python3.10", "python3.14"])
            for way in ("module", "folder"):
                with self.subTest(way=way):
                    result = old_python(way, path)
                    self.assertEqual((result.returncode, result.stderr, result.stdout), (2, TOO_OLD + install, "[]\n"))
                # The edges of "older than 3.11": the last 3.10 release is too old; 3.11.0 runs the report.
                with self.subTest(way=way, version="3.10.19"):
                    result = old_python(way, path, "3.10.19")
                    self.assertEqual((result.returncode, result.stderr, result.stdout),
                                     (2, "stay-safe needs Python 3.11 or newer; this is Python 3.10.19. " + install,
                                      "[]\n"))
                with self.subTest(way=way, version="3.11.0"):
                    result = old_python(way, path, "3.11.0")
                    report = run("-m", "stay_safe", "--config", str(SAMPLE))
                    self.assertEqual((result.returncode, result.stderr), (0, ""))
                    self.assertTrue(result.stdout.startswith(report.stdout), result.stdout[:300])

    def test_version_check_runs_before_any_module_needing_3_11_and_parses_as_python_3_9(self):
        with tempfile.TemporaryDirectory() as folder:
            for way in ("module", "folder"):
                with self.subTest(way=way):
                    result = old_python(way, folder)
                    self.assertEqual((result.returncode, result.stdout), (2, "[]\n"))
        # `python3 -m stay_safe` runs __init__.py first; `python3 stay_safe` compiles __main__.py first.
        # ast's feature_version is best-effort: it rejects newer statements such as `match`, but accepts f-strings
        # written as only Python 3.12 allows, and annotations such as `str | None`, which Python 3.9 evaluates and
        # fails on. So these two files must also hold no f-string and no annotation.
        for name in ("__init__.py", "__main__.py"):
            with self.subTest(name=name):
                tree = ast.parse((ROOT / "stay_safe" / name).read_text(encoding="utf-8"), filename=name,
                                 feature_version=(3, 9))
                newer = [type(node).__name__ for node in ast.walk(tree)
                         if isinstance(node, (ast.JoinedStr, ast.AnnAssign))
                         or isinstance(node, ast.arg) and node.annotation is not None
                         or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None]
                self.assertEqual(newer, [])
