"""Default discovery selects the directory Codex selects, as in the pinned `find_codex_home`:
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/utils/home-dir/src/lib.rs
An empty CODEX_HOME counts as unset; a set one must exist and be a directory, or Codex refuses to start;
the home directory is looked up only when CODEX_HOME is unset ("Could not find home directory" otherwise).
Python's Path.home raises RuntimeError when the home directory cannot be resolved:
https://docs.python.org/3/library/pathlib.html#pathlib.Path.home
An empty HOME is reported as an undetermined home (owner decision, archived PR #67), not resolved further.
"""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase, ROOT

POLICY = 'approval_policy="on-request"\nsandbox_mode="read-only"\n[shell_environment_policy]\ninherit="{}"\n'
SET_GAP = ('Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; '
           'Codex would not start, so no default files were inspected.')
UNKNOWN_GAP = ('Codex home: CODEX_HOME is unset and the home directory cannot be determined; '
               'no default files were inspected.')


def unknown_home():
    raise RuntimeError("Could not determine home directory.")


class CodexHomeTests(ConfigCase):
    def setUp(self):
        super().setUp()
        # A populated ~/.codex and a decoy configuration in the working directory.
        self.home, self.work = self.root / 'home', self.root / 'work'
        (self.home / '.codex' / 'rules').mkdir(parents=True)
        (self.home / '.codex' / 'config.toml').write_text(POLICY.format('core'))
        (self.home / '.codex' / 'rules' / 'default.rules').write_text('\nprefix_rule(pattern=["git", "status"], decision="allow")\n')
        (self.work / 'rules').mkdir(parents=True)
        (self.work / 'config.toml').write_text(POLICY.format('all'))
        (self.work / 'rules' / 'default.rules').write_text('prefix_rule(pattern=["curl"], decision="allow")\n')

    def cli(self, **env):
        run = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--format', 'json'], cwd=self.work,
                             env={'HOME': str(self.home), 'PYTHONPATH': str(ROOT), **env},
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(run.stderr, '')
        return run.returncode, json.loads(run.stdout)

    def in_process(self, env):
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(Path, 'home', side_effect=unknown_home), \
                redirect_stdout(output):
            status = main(['--format', 'json'])
        return status, json.loads(output.getvalue())

    def observations(self, report):
        return {e['id']: e['observations'] for e in report['catalog']}

    def test_empty_or_unset_codex_home_reads_home_dot_codex_not_the_working_directory(self):
        for name, env in [('empty', {'CODEX_HOME': ''}), ('unset', {})]:
            with self.subTest(codex_home=name):
                self.require_no_system_folder()
                status, report = self.cli(**env)
                self.assertEqual((status, report['inspection_gaps']), (0, []))
                found = self.observations(report)
                self.assertEqual(found['config-1:shell_environment_policy'],
                                 ['inherit: core (explicit)', 'ignore_default_excludes: true (default)'])
                self.assertEqual(found['rules-1:prefix_rule.2'], ['program: git', 'tokens: 2'])
                self.assertEqual([r['rule'] for r in report['risks']], ['saved_approval'])

    def test_set_codex_home_is_read_when_the_home_lookup_fails(self):
        status, report = self.in_process({'CODEX_HOME': str(self.home / '.codex')})
        self.assertEqual((status, report['inspection_gaps']), (0, []))
        self.assertEqual(self.observations(report)['config-1:shell_environment_policy'],
                         ['inherit: core (explicit)', 'ignore_default_excludes: true (default)'])

    def test_missing_or_file_codex_home_is_a_gap_without_defaults(self):
        (self.root / 'file-home').write_text(POLICY.format('all'))
        for name in ('missing-home', 'file-home'):
            with self.subTest(codex_home=name):
                status, report = self.cli(CODEX_HOME=str(self.root / name))
                self.assertEqual((status, report['inspection_gaps']), (2, [SET_GAP]))
                self.assertEqual((report['file_inspection'], report['catalog'], report['risks']),
                                 ('incomplete', [], []))
        # Python 3.11-3.13 Path.is_dir propagates PermissionError for a path under an unsearchable directory.
        with self.subTest(codex_home='unreadable'), \
                patch.object(Path, 'is_dir', side_effect=PermissionError(13, 'Permission denied')):
            status, report = self.in_process({'CODEX_HOME': str(self.home / '.codex')})
            self.assertEqual((status, report['inspection_gaps']), (2, [SET_GAP]))
            self.assertEqual((report['file_inspection'], report['catalog'], report['risks']), ('incomplete', [], []))

    def test_unknown_home_with_unset_codex_home_is_a_gap_without_defaults(self):
        for name, run in [('unset', lambda: self.in_process({})), ('empty', lambda: self.in_process({'CODEX_HOME': ''})),
                          ('unset, HOME empty', lambda: self.cli(HOME=''))]:
            with self.subTest(codex_home=name):
                status, report = run()
                self.assertEqual((status, report['inspection_gaps']), (2, [UNKNOWN_GAP]))
                self.assertEqual((report['catalog'], report['risks']), ([], []))
