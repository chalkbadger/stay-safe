import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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

    def sentinel(self, folder, passing=False):
        path = self.root / 'tests' / folder / 'test_sentinel.py'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('import unittest\nclass Sentinel(unittest.TestCase):\n'
                        '    def test_sentinel(self):\n'
                        f'        self.assertTrue({passing!r}, "sentinel executed")\n')

    def test_missing_direct_and_intermediate_markers_stop_the_complete_check(self):
        for folder, missing in [('direct', 'direct'), ('outer/inner', 'outer')]:
            with self.subTest(folder=folder):
                self.sentinel(folder)
                if '/' in folder:
                    (self.root / 'tests' / folder / '__init__.py').touch()
                code, output = self.run_check()
                self.assertNotEqual(code, 0, output)
                self.assertIn(f'Missing package marker: tests/{missing}/__init__.py', output)
                self.assertNotIn('\nOK', output)
                self.assertNotIn('sentinel executed', output)
                shutil.rmtree(self.root / 'tests' / folder.split('/')[0])

    def test_restored_markers_run_the_failing_sentinel_then_allow_its_pass(self):
        self.sentinel('outer/inner')
        for folder in ['outer', 'outer/inner']:
            (self.root / 'tests' / folder / '__init__.py').touch()
        code, output = self.run_check()
        self.assertNotEqual(code, 0, output)
        self.assertIn('sentinel executed', output)
        self.assertIn('FAILED (failures=1)', output)
        self.sentinel('outer/inner', passing=True)
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
