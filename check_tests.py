"""Check test package markers, then run the repository's unittest suite."""

from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    tests = root / 'tests'
    missing = set()
    for test in tests.rglob('test*.py'):
        if not test.is_file():
            continue
        folder = test.parent
        while folder != tests:
            if not (folder / '__init__.py').is_file():
                missing.add((folder / '__init__.py').relative_to(root).as_posix())
            folder = folder.parent
    if missing:
        for marker in sorted(missing):
            print(f'Missing package marker: {marker}', file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                          cwd=root).returncode


if __name__ == '__main__':
    sys.exit(main())
