"""Static check: the diagnostic's source has no way to run programs, connect or evaluate input, and only its save
step, stay_safe/save.py, can write files.

Python documents audit hooks as unsuitable for sandboxing (https://github.com/python/cpython/issues/87604),
so this reads the source instead of trapping a run. Which file the save step writes is shown by running it, in
tests/nothing_in_my_setup_changes/test_save.py.
"""
import argparse
import ast
import pathlib
import unittest

from tests.support import ROOT

MODULES = {"argparse", "dataclasses", "hashlib", "html", "ipaddress", "json", "os", "pathlib", "re",
           "stat", "sys", "tomllib", "urllib.parse"}
OS_NAMES = {"open", "fdopen", "fstat", "environ", "listdir", "O_RDONLY", "O_NONBLOCK", "O_NOFOLLOW"}
OS_READ_FLAGS = {"O_RDONLY", "O_NONBLOCK", "O_NOFOLLOW"}
BANNED_NAMES = {"exec", "eval", "compile", "__import__", "open", "getattr", "importlib",
                "__builtins__", "globals", "vars"}
PATHLIB_ARGPARSE = set(dir(pathlib.Path)) | set(dir(argparse)) | set(dir(argparse.ArgumentParser))
# The pathlib and argparse names the package uses; any other name of theirs is reported.
USED_NAMES = {"Path", "home", "resolve", "parents", "is_dir", "is_file", "read_text", "read_bytes", "as_uri",
              "ArgumentParser", "add_argument", "parse_args", "error", "exit"}
# The save step may also create a temporary file beside the report, write it, move it into place or remove it.
WRITER = "stay_safe/save.py"
WRITER_MODULES = {"tempfile"}
WRITER_OS_NAMES = {"replace", "unlink"}


def is_os(node):
    return isinstance(node, ast.Name) and node.id == "os"


def read_only_flags(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return read_only_flags(node.left) and read_only_flags(node.right)
    return isinstance(node, ast.Attribute) and is_os(node.value) and node.attr in OS_READ_FLAGS


def argument(call, position, keyword):
    if len(call.args) > position:
        return call.args[position]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def violations(source, filename):
    """Return 'file:line: problem' for each construct outside the allow-lists."""
    writer = filename == WRITER
    modules = MODULES | WRITER_MODULES if writer else MODULES
    os_names = OS_NAMES | WRITER_OS_NAMES if writer else OS_NAMES
    tree = ast.parse(source, filename)
    found = []
    # Allowed: str.replace(old, new); Path.replace(target) takes one argument.
    exempt = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "replace" and len(n.args) >= 2}

    def report(node, message):
        found.append(f"{filename}:{node.lineno}: {message}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                exempt.add(id(alias))  # a module name, checked against MODULES
                if alias.name not in modules:
                    report(node, f"import {alias.name} is outside the allowed modules")
                elif alias.name == "os" and alias.asname not in (None, "os"):
                    report(node, "os may not be renamed")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module not in modules:
                report(node, f"import from {node.module} is outside the allowed modules")
            elif node.level > 1:
                report(node, "import from outside the package")
            elif node.module == "os":
                report(node, "from os import is not allowed; use os.<name>")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            report(node, f"{node.id} is not allowed")
        elif isinstance(node, ast.Attribute) and is_os(node.value):
            if node.attr not in os_names:
                report(node, f"os.{node.attr} is outside the allowed os names")
        elif isinstance(node, ast.Attribute) and node.attr in {"__builtins__", "importlib"}:
            report(node, f"{node.attr} is not allowed")
        elif isinstance(node, (ast.Attribute, ast.alias)) and id(node) not in exempt:
            name = node.attr if isinstance(node, ast.Attribute) else node.name
            if name in PATHLIB_ARGPARSE and name not in USED_NAMES:
                report(node, f"{name} is outside the allowed pathlib and argparse names")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and is_os(node.func.value):
            if node.func.attr == "open" and not read_only_flags(argument(node, 1, "flags")):
                report(node, "os.open flags must be read-only")
            elif node.func.attr == "fdopen" and not writer:
                mode = argument(node, 1, "mode")
                if mode is not None and not (isinstance(mode, ast.Constant) and mode.value in {"r", "rb"}):
                    report(node, "os.fdopen mode must be read-only")
    return sorted(found, key=lambda line: (int(line.split(":")[1]), line))


class ReadOnlySourceTests(unittest.TestCase):
    def test_package_source_uses_only_allowed_imports_calls_and_os_names(self):
        sources = sorted((ROOT / "stay_safe").rglob("*.py"))
        self.assertIn(ROOT / "stay_safe" / "codex.py", sources)
        found = [line for path in sources
                 for line in violations(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix())]
        self.assertEqual(found, [])

    def test_each_planted_violation_is_reported_with_file_and_line(self):
        cases = {
            "import subprocess": ["import subprocess is outside the allowed modules"],
            "from urllib import request": ["import from urllib is outside the allowed modules"],
            "import os as o": ["os may not be renamed"],
            "from os import system": ["from os import is not allowed; use os.<name>"],
            "exec(text)": ["exec is not allowed"],
            "eval(text)": ["eval is not allowed"],
            "compile(text, 'x', 'exec')": ["compile is not allowed"],
            "__import__('socket')": ["__import__ is not allowed"],
            "open(p, 'w')": ["open is not allowed"],
            "with open(p) as f: pass": ["open is not allowed"],
            "os.posix_spawn(p, [], {})": ["os.posix_spawn is outside the allowed os names"],
            "os.system('git')": ["os.system is outside the allowed os names"],
            "os.open(p, 1)": ["os.open flags must be read-only"],
            "os.open(p, os.O_RDONLY | os.O_CREAT)": ["os.O_CREAT is outside the allowed os names",
                                                    "os.open flags must be read-only"],
            "os.fdopen(fd, 'w')": ["os.fdopen mode must be read-only"],
            "os.fdopen(fd, mode=m)": ["os.fdopen mode must be read-only"],
            "Path(p).write_text('x')": ["write_text is outside the allowed pathlib and argparse names"],
            "Path(p).open('w')": ["open is outside the allowed pathlib and argparse names"],
            "Path(p).unlink()": ["unlink is outside the allowed pathlib and argparse names"],
            "Path(p).replace(q)": ["replace is outside the allowed pathlib and argparse names"],
            "getattr(os, name)": ["getattr is not allowed"],
            "lookup = getattr": ["getattr is not allowed"],
            "import importlib": ["import importlib is outside the allowed modules"],
            "__builtins__['eval'](text)": ["__builtins__ is not allowed"],
            "globals()['x']": ["globals is not allowed"],
            "vars(os)['system']": ["vars is not allowed"],
            "import tempfile": ["import tempfile is outside the allowed modules"],
            "os.replace(p, q)": ["os.replace is outside the allowed os names"],
            "os.unlink(p)": ["os.unlink is outside the allowed os names"],
        }
        for source, messages in cases.items():
            with self.subTest(source=source):
                self.assertEqual(violations("\n" + source + "\n", "stay_safe/planted.py"),
                                 [f"stay_safe/planted.py:2: {m}" for m in messages])

    def test_the_save_step_may_write_but_still_cannot_run_programs_connect_or_evaluate_input(self):
        allowed = ["import tempfile", "tempfile.mkstemp(dir=d)", "os.fdopen(fd, 'w', encoding='utf-8')",
                   "os.replace(p, q)", "os.unlink(p)"]
        for source in allowed:
            with self.subTest(source=source):
                self.assertEqual(violations("\n" + source + "\n", WRITER), [])
        cases = {
            "import subprocess": ["import subprocess is outside the allowed modules"],
            "import socket": ["import socket is outside the allowed modules"],
            "os.system('git')": ["os.system is outside the allowed os names"],
            "os.remove(p)": ["os.remove is outside the allowed os names"],
            "os.rename(p, q)": ["os.rename is outside the allowed os names"],
            "eval(text)": ["eval is not allowed"],
            "open(p, 'w')": ["open is not allowed"],
            "Path(p).write_text('x')": ["write_text is outside the allowed pathlib and argparse names"],
        }
        for source, messages in cases.items():
            with self.subTest(source=source):
                self.assertEqual(violations("\n" + source + "\n", WRITER), [f"{WRITER}:2: {m}" for m in messages])
