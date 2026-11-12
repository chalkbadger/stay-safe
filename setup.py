"""Bundle committed references and stamp artifacts at build time, never during diagnostics."""
from pathlib import Path
import re
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

ROOT = Path(__file__).resolve().parent


def revision():
    if (ROOT / '.git').exists():
        if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip():
            raise RuntimeError('Build from a clean committed checkout or a release archive.')
        value = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    else:
        value = (ROOT / 'stay_safe/release.txt').read_text().strip()
    if not re.fullmatch(r'(?!0{40})[0-9a-f]{40}', value):
        raise RuntimeError('Build needs a full source commit in stay_safe/release.txt.')
    return value


class Package(build_py):
    def run(self):
        commit = revision()
        super().run()
        target = Path(self.build_lib) / 'stay_safe'
        for name in ('incidents.md', 'harnesses/codex.md'):
            dest = target / 'data' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / name).read_bytes())
        (target / 'package.txt').write_text(commit + '\n')


class Source(sdist):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        # Replace the copy rather than writing through setuptools' possible hard link.
        stamp = Path(base_dir) / 'stay_safe/release.txt'
        stamp.unlink(missing_ok=True)
        stamp.write_text(revision() + '\n')


setup(cmdclass={'build_py': Package, 'sdist': Source})
