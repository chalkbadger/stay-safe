"""Codex configuration in the system config folder, /etc/codex, in a run with no file arguments (archived issue #110).

Expected results follow openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a:
- config.toml: the System layer reads /etc/codex/config.toml (config/src/loader/mod.rs L80-L81, L275-L290).
- hooks.json: hooks are loaded from each layer's config folder (hooks/src/engine/discovery.rs L176-L181;
  config/src/state.rs L219-L243), which for the System layer is /etc/codex.
- managed_config.toml: read from /etc/codex on Unix (config/src/loader/layer_io.rs L21-L22, L222-L232).
- requirements.toml: read from /etc/codex on Unix (config/src/loader/mod.rs L109-L118, L734-L737).
- rules/: every `*.rules` file in each layer's rules folder is loaded; a missing folder gives none and any
  other listing error fails (core/src/exec_policy.rs L688-L711, L1177-L1215).
The gap text follows the issue: it names /etc/codex as not inspected; the files' contents are not read.
Tests replace the folder's path with a temporary directory; the real /etc is not touched.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
PRIVATE = 'private-system-value'
GAP = 'System config folder: /etc/codex holds Codex configuration that was not inspected.'
FILES = ['config.toml', 'hooks.json', 'managed_config.toml', 'requirements.toml', 'rules/company.rules']


class SystemFolderTests(ConfigCase):
    def setUp(self):
        super().setUp()
        # A clean Codex home: with no system folder the run has no gaps and exits 0.
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
        self.assertEqual(err.getvalue(), '')
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
        # A rules entry that is a file cannot be listed as a directory; this holds even for uid 0.
        folder = self.system('rules-file', ['rules'])
        self.assertEqual(self.run_report(folder), (2, [GAP]))
        # A rules/ directory whose listing is denied: not NotFound, so Codex fails with ReadDir (exec_policy.rs
        # L1179-L1187). Only this listing is denied; the Codex home's own rules listing runs as usual.
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
                # The same as with no system folder.
                self.assertEqual(self.run_report(self.system('all', FILES), args),
                                 self.run_report(self.root / 'missing', args))
