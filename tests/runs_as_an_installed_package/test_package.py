"""Build and run the artifacts outside the source tree, with no network access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

from tests.support import ROOT


def run(*args, cwd, **kwargs):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60, **kwargs)


class PackageTests(unittest.TestCase):
    def test_wheel_and_sdist_keep_report_resources_revision_and_safe_current_directory_save(self):
        self.assertTrue((ROOT / 'pyproject.toml').is_file(), 'The published package needs build metadata')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'source'
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('.git', '__pycache__', 'build', 'dist', '*.egg-info'))
            for args in [('init',), ('add', '.'), ('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'source')]:
                self.assertEqual(run('git', *args, cwd=source).returncode, 0)
            revision = run('git', 'rev-parse', 'HEAD', cwd=source).stdout.strip()
            built = run(sys.executable, '-m', 'build', '--no-isolation', cwd=source)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            wheel = next((source / 'dist').glob('*.whl'))
            install = base / 'installed'
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(install)
                metadata = archive.read(next(n for n in archive.namelist() if n.endswith('/METADATA'))).decode()
                self.assertIn('Requires-Python: >=3.11', metadata)
                entry = archive.read(next(n for n in archive.namelist() if n.endswith('/entry_points.txt'))).decode()
                self.assertIn('stay-safe = stay_safe.cli:main', entry)
            work = base / 'working directory'
            work.mkdir()
            config = work / 'config.toml'
            config.write_text('approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n[mcp_servers.sample]\nurl = "https://private.invalid"\n')
            env = dict(os.environ, PYTHONPATH=str(install), PYTHONDONTWRITEBYTECODE='1')
            args = ('-m', 'stay_safe', '--config', str(config))
            installed = run(sys.executable, *args, '--format', 'json', cwd=work, env=env)
            clone = run(sys.executable, *args, '--format', 'json', cwd=source)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            result, expected = json.loads(installed.stdout), json.loads(clone.stdout)
            self.assertEqual(result['inspection_gaps'], [])
            self.assertEqual(result['provenance']['source_revision'], revision)
            self.assertEqual(result['provenance']['source_status'], 'installed package commit')
            result['provenance']['source_status'] = expected['provenance']['source_status']
            self.assertEqual(result, expected)
            self.assertTrue(result['incident_links'])
            self.assertTrue(all('/' + revision + '/' in link for link in result['incident_links'].values()))
            target = work / 'keep.txt'
            target.write_text('untouched')
            saved = work / 'stay-safe-report.html'
            saved.symlink_to(target)
            plain = run(sys.executable, *args, cwd=work, env=env)
            clone_plain = run(sys.executable, *args, cwd=source)
            self.assertEqual(plain.stdout, clone_plain.stdout)
            self.assertEqual(plain.returncode, clone_plain.returncode)
            missing_args = ('-m', 'stay_safe', '--config', str(work / 'missing-private.toml'))
            missing = run(sys.executable, *missing_args, '--format', 'json', cwd=work, env=env)
            self.assertEqual(missing.returncode, 2)
            self.assertIn('Inspection incomplete (exit 2)', missing.stderr)
            missing_report = json.loads(missing.stdout)
            self.assertEqual(missing_report['file_inspection'], 'incomplete')
            self.assertTrue(any('Selected config file is missing.' in gap for gap in missing_report['inspection_gaps']))
            self.assertNotIn('missing-private', missing.stdout + missing.stderr)
            page = run(sys.executable, *args, '--save', cwd=work, env=env)
            self.assertEqual(page.returncode, plain.returncode)
            self.assertTrue(page.stdout.startswith(plain.stdout))
            self.assertIn(str(saved), page.stdout)
            self.assertIn('<!doctype html>', saved.read_text().lower())
            self.assertFalse(saved.is_symlink())
            self.assertEqual(target.read_text(), 'untouched')
            self.assertNotIn('private.invalid', page.stdout + saved.read_text())
            self.assertFalse((install / 'stay-safe-report.html').exists())
            saved.unlink()
            saved.mkdir()
            failed = run(sys.executable, *args, '--save', cwd=work, env=env)
            self.assertEqual(failed.returncode, 0)
            self.assertEqual(failed.stdout, plain.stdout)
            self.assertIn('Could not save', failed.stderr)
            self.assertNotIn('Saved the formatted report', failed.stdout)
            (install / 'stay_safe/package.txt').write_text('private-invalid-stamp')
            corrupt = run(sys.executable, *args, '--format', 'json', cwd=work, env=env)
            corrupt_result = json.loads(corrupt.stdout)
            self.assertEqual(corrupt.returncode, 2)
            self.assertIsNone(corrupt_result['provenance']['source_revision'])
            self.assertEqual(corrupt_result['provenance']['source_status'], 'revision unknown')
            self.assertEqual(corrupt_result['incident_links'], {})
            self.assertEqual([r['rule'] for r in corrupt_result['risks']], [r['rule'] for r in expected['risks']])
            self.assertTrue(all(r['rule_source'] is None for r in corrupt_result['risks']))
            self.assertNotIn('private-invalid-stamp', corrupt.stdout + corrupt.stderr)
            # `build` builds its wheel from the sdist by default: this also checks the source distribution.
            with tarfile.open(next((source / 'dist').glob('*.tar.gz'))) as archive:
                names = archive.getnames()
                self.assertTrue(any(n.endswith('/incidents.md') for n in names))
                stamp = archive.extractfile(next(n for n in names if n.endswith('/stay_safe/release.txt'))).read().decode().strip()
                self.assertEqual(stamp, revision)
