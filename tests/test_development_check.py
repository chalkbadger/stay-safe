import ast
import io
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTED = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def comments_and_docstrings(root):
    names = subprocess.run(['git', 'ls-files', '-z', '--', '*.py'], cwd=root, check=True, capture_output=True,
                           text=True).stdout.split('\0')
    found = []
    for name in filter(None, names):
        path = root / name
        if not path.is_file():
            continue
        source = path.read_text(encoding='utf-8')
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                found.append(f'{name}:{token.start[0]}: comment')
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, DOCUMENTED) and ast.get_docstring(node, clean=False) is not None:
                found.append(f'{name}:{node.body[0].lineno}: docstring')
    return sorted(found)


class NoCommentsTests(unittest.TestCase):
    def test_code_has_no_comments_or_docstrings(self):
        self.assertEqual(comments_and_docstrings(ROOT), [])

    def test_each_comment_and_docstring_is_named_with_its_file_and_line(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'stay_safe').mkdir()
            (root / 'tests' / 'nested').mkdir(parents=True)
            (root / 'setup.py').write_text('x = 1  # inline\n')
            (root / 'check_tests.py').write_text("'''Module.'''\n")
            (root / 'stay_safe' / 'code.py').write_text(
                'text = "# not a comment"\n\n\nclass Thing:\n    """Class."""\n\n    def run(self):\n'
                '        # full line\n        return text\n')
            (root / 'tests' / 'nested' / 'test_thing.py').write_text(
                'async def check():\n    """Function."""\n    """Not a docstring."""\n')
            (root / 'tools').mkdir()
            (root / 'tools' / 'script.py').write_text('# tracked anywhere\n')
            (root / 'untracked.py').write_text('# not committed\n')
            (root / 'docs.md').write_text('# Heading\n')
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            subprocess.run(['git', 'add', '--', '*.py', 'docs.md', ':!untracked.py'], cwd=root, check=True)
            self.assertEqual(comments_and_docstrings(root), [
                'check_tests.py:1: docstring',
                'setup.py:1: comment',
                'stay_safe/code.py:5: docstring',
                'stay_safe/code.py:8: comment',
                'tests/nested/test_thing.py:2: docstring',
                'tools/script.py:1: comment',
            ])


class LayoutCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'tests').mkdir()
        (self.root / 'tests' / 'test_baseline.py').write_text(
            'import unittest\nclass Baseline(unittest.TestCase):\n'
            '    def test_baseline(self):\n        self.assertTrue(True)\n')
        script = ROOT / 'check_tests.py'
        if script.exists():
            shutil.copyfile(script, self.root / script.name)
        develop = (ROOT / 'README.md').read_text().split('## Develop\n', 1)[1].split('\n## ', 1)[0]
        command = re.search(r'`(python3 [^`]+)`', develop).group(1)
        self.command = [sys.executable, *shlex.split(command)[1:]]

    def run_check(self):
        result = subprocess.run(self.command, cwd=self.root, capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout + result.stderr

    def sentinel(self, folder, passing=False, filename='test_sentinel.py'):
        path = self.root / 'tests' / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('import unittest\nclass Sentinel(unittest.TestCase):\n'
                        '    def test_sentinel(self):\n'
                        f'        self.assertTrue({passing!r}, "sentinel executed")\n')

    def test_missing_direct_and_intermediate_markers_stop_the_complete_check(self):
        for folder, missing, filename in [('direct', 'direct', 'test_sentinel.py'),
                                           ('direct', 'direct', 'test.py'),
                                           ('outer/inner', 'outer', 'testplain.py')]:
            with self.subTest(folder=folder, filename=filename):
                self.sentinel(folder, filename=filename)
                if '/' in folder:
                    (self.root / 'tests' / folder / '__init__.py').touch()
                code, output = self.run_check()
                self.assertNotEqual(code, 0, output)
                self.assertIn(f'Missing package marker: tests/{missing}/__init__.py', output)
                self.assertNotIn('\nOK', output)
                self.assertNotIn('sentinel executed', output)
                shutil.rmtree(self.root / 'tests' / folder.split('/')[0])

    def test_restored_markers_run_the_failing_sentinel_then_allow_its_pass(self):
        self.sentinel('outer/inner', filename='testplain.py')
        for folder in ['outer', 'outer/inner']:
            (self.root / 'tests' / folder / '__init__.py').touch()
        code, output = self.run_check()
        self.assertNotEqual(code, 0, output)
        self.assertIn('sentinel executed', output)
        self.assertIn('FAILED (failures=1)', output)
        self.sentinel('outer/inner', passing=True, filename='testplain.py')
        code, output = self.run_check()
        self.assertEqual(code, 0, output)
        self.assertIn('Ran 2 tests', output)
        self.assertIn('\nOK', output)

    def test_folders_without_matching_tests_do_not_need_markers(self):
        (self.root / 'tests' / 'helpers' / 'nested').mkdir(parents=True)
        (self.root / 'tests' / 'helpers' / 'nested' / 'helper.py').write_text('')
        self.sentinel('real', passing=True)
        (self.root / 'tests' / 'real' / '__init__.py').touch()
        code, output = self.run_check()
        self.assertEqual(code, 0, output)
        self.assertIn('Ran 2 tests', output)


if __name__ == '__main__':
    unittest.main()
