from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import INCOMPLETE
from tests.support import ConfigCase

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
PRIVATE = 'private-system-value'
GAP = 'System config folder: /etc/codex holds Codex configuration that was not inspected.'
FILES = ['config.toml', 'hooks.json', 'managed_config.toml', 'requirements.toml', 'rules/company.rules']


class SystemFolderTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.codex_home = self.root / 'home' / '.codex'
        self.codex_home.mkdir(parents=True)
        (self.codex_home / 'config.toml').write_text(CONFIG)

    def system(self, name, files=()):
        folder = self.root / name
        for file in files:
            (folder / file).parent.mkdir(parents=True, exist_ok=True)
            (folder / file).write_text(PRIVATE)
        return folder

    def run_report(self, folder, args=(), env=None):
        out, err = io.StringIO(), io.StringIO()
        env = {'CODEX_HOME': str(self.codex_home)} if env is None else env
        with patch('stay_safe.cli.SYSTEM', folder), patch.dict(os.environ, env, clear=True), \
                redirect_stdout(out), redirect_stderr(err):
            code = main(['--format', 'json', *args])
        self.assertEqual(err.getvalue(), INCOMPLETE if code == 2 else "")
        self.assertNotIn(PRIVATE, out.getvalue())
        report = json.loads(out.getvalue())
        return code, report['inspection_gaps']

    def test_each_codex_file_in_the_system_folder_gives_the_gap_and_exits_2(self):
        for file in FILES:
            with self.subTest(file=file):
                self.assertEqual(self.run_report(self.system(file.replace('/', '-'), [file])), (2, [GAP]))
        home = {'HOME': str(self.codex_home.parent)}
        for kind, env in [('CODEX_HOME unset', home), ('CODEX_HOME empty', {**home, 'CODEX_HOME': ''})]:
            with self.subTest(kind=kind):
                self.assertEqual(self.run_report(self.system(kind, ['config.toml']), env=env), (2, [GAP]))
        with self.subTest(file='all of them'):
            self.assertEqual(self.run_report(self.system('all', FILES)), (2, [GAP]))

    def test_system_folder_without_codex_files_gives_no_gap(self):
        cases = [('missing', []), ('empty', []), ('other names', ['README', 'config.toml.bak', 'rules/default.rules.bak'])]
        for kind, files in cases:
            with self.subTest(kind=kind):
                folder = self.system(kind, files)
                if kind == 'empty':
                    folder.mkdir()
                self.assertEqual(self.run_report(folder), (0, []))

    def test_unlistable_rules_folder_gives_the_gap_and_exits_2(self):
        folder = self.system('rules-file', ['rules'])
        self.assertEqual(self.run_report(folder), (2, [GAP]))
        folder = self.system('rules-denied')
        (folder / 'rules').mkdir(parents=True)
        listdir = os.listdir

        def denied(path):
            if path == folder / 'rules':
                raise PermissionError(13, 'Permission denied')
            return listdir(path)
        with patch('stay_safe.cli.os.listdir', side_effect=denied):
            self.assertEqual(self.run_report(folder), (2, [GAP]))

    def test_runs_with_file_arguments_give_no_system_folder_gap(self):
        config = self.config(CONFIG)
        rules = self.config('prefix_rule(pattern=["git", "status"], decision="allow")\n', 'default.rules')
        for args in [['--config', str(config)], ['--rules', str(rules)], ['--config', str(config), '--rules', str(rules)]]:
            with self.subTest(args=args[0::2]):
                self.assertEqual(self.run_report(self.system('all', FILES), args),
                                 self.run_report(self.root / 'missing', args))
