import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from stay_safe.cli import codex_home, main
from tests.support import INCOMPLETE
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
        self.assertEqual(run.stderr, INCOMPLETE if run.returncode == 2 else "")
        return run.returncode, json.loads(run.stdout)

    def in_process(self, env):
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(Path, 'home', side_effect=unknown_home), \
                redirect_stdout(output):
            status = main(['--format', 'json'])
        return status, json.loads(output.getvalue())

    def observations(self, report):
        return {e['id']: e['observations'] for e in report['catalog']}

    @unittest.skipUnless(os.supports_bytes_environ, 'Unix byte-valued environment')
    def test_non_unicode_override_reads_and_labels_the_default_codex_files(self):
        (self.home / '.codex' / 'config.toml').write_text(
            'approval_policy="never"\nsandbox_mode="read-only"\nshell_environment_policy.inherit="none"\n')
        invalid = os.fsdecode(os.fsencode(self.root) + b'/missing-\xff')
        existing = Path(os.fsdecode(os.fsencode(self.root) + b'/present-\xff'))
        for override in ({}, {'CODEX_HOME': invalid}, {'CODEX_HOME': str(existing)}):
            with self.subTest(override=override), patch.dict(os.environ, {'HOME': str(self.home), **override}, clear=True):
                if override.get('CODEX_HOME') == str(existing):
                    try:
                        existing.mkdir()
                    except OSError as error:
                        if error.errno == errno.EILSEQ:
                            self.skipTest('filesystem requires UTF-8 directory names')
                        raise
                    (existing / 'config.toml').write_text('approval_policy="on-request"\n')
                with redirect_stdout(io.StringIO()) as output:
                    status = main(['--agent', 'codex', '--format', 'json'])
                report = json.loads(output.getvalue())
                self.assertEqual((status, report['inspection_gaps']), (0, []))
                self.assertIn('commands_without_prompts', [risk['rule'] for risk in report['risks']])
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main(['--agent', 'codex', '--format', 'markdown']), 0)
                self.assertIn('**Config file `~/.codex/config.toml`**', output.getvalue())
                self.assertIn('**Rules file `~/.codex/rules/default.rules`**', output.getvalue())

    @unittest.skipUnless(os.supports_bytes_environ, 'Unix byte-valued environment')
    def test_non_unicode_override_does_not_select_codex_in_a_claude_only_home(self):
        home = self.root / 'claude-only'
        (home / '.claude').mkdir(parents=True)
        (home / '.claude' / 'settings.json').write_text('{"permissions":{"defaultMode":"default"}}')
        invalid = os.fsdecode(os.fsencode(self.root) + b'/missing-\xff')
        with patch.dict(os.environ, {'HOME': str(home), 'CODEX_HOME': invalid}, clear=True), \
                redirect_stdout(io.StringIO()) as output:
            status = main(['--format', 'json'])
        report = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(report['harness'], 'Claude Code')

    @unittest.skipUnless(os.supports_bytes_environ, 'Unix byte-valued environment')
    def test_valid_utf8_override_keeps_its_original_filesystem_path(self):
        override = Path(os.fsdecode(os.fsencode(self.root) + b'/home-\xc3\xa9'))
        override.mkdir()
        (override / 'config.toml').write_text('approval_policy="never"\n')
        run = subprocess.run(
            [sys.executable, '-B', '-m', 'stay_safe', '--agent', 'codex', '--format', 'json'], cwd=ROOT,
            env={'LC_ALL': 'C', 'PYTHONCOERCECLOCALE': '0', 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'utf-8',
                 'HOME': str(self.home), 'CODEX_HOME': str(override)},
            capture_output=True, encoding='utf-8', timeout=10)
        self.assertIn('commands_without_prompts', [risk['rule'] for risk in json.loads(run.stdout)['risks']])

    def test_windows_home_lookup_accepts_paired_surrogates_and_ignores_unpaired_ones(self):
        override = self.root / 'home-\U00010437'
        override.mkdir()
        default = self.home / '.codex'
        for suffix, selected in (('\ud801', default), ('\udc37', default),
                                 ('\ud801\udc37', override), ('\U00010437', override)):
            with self.subTest(suffix=ascii(suffix)), patch.object(sys, 'platform', 'win32'), \
                    patch.object(os, 'supports_bytes_environ', False), patch.object(Path, 'home', return_value=self.home), \
                    patch.object(os, 'environ', {'CODEX_HOME': str(self.root / ('home-' + suffix))}):
                self.assertEqual(codex_home(), (selected, None))

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
