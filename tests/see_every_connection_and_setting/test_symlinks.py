"""Symlinked inputs (archived issue #62), run with the platform's real os.O_NOFOLLOW.

open(2) with O_NOFOLLOW fails when the final path component is a symbolic link:
https://pubs.opengroup.org/onlinepubs/9799919799/functions/open.html
"""

from contextlib import redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
ALLOW = 'prefix_rule(pattern=["curl"], decision="allow")\n'
CONFIG_GAP = 'config-1: Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.'
CONFIG_IDS = ['config-1:approval_policy', 'config-1:features.apps', 'config-1:sandbox_mode', 'config-1:shell_environment_policy']
RULES_GAP = 'rules-1: Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.'
RULES_IDS = ['rules-1:prefix_rule.1']


class SymlinkPolicyTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.home = self.root / 'home'
        (self.home / 'rules').mkdir(parents=True)
        self.targets = self.root / 'targets'
        self.targets.mkdir()
        (self.targets / 'config.toml').write_text(CONFIG)
        (self.targets / 'default.rules').write_text(ALLOW)

    def report(self, *args):
        output = io.StringIO()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.home)}, clear=True), redirect_stdout(output):
            status = main([*args, '--format', 'json'])
        report = json.loads(output.getvalue())
        return status, report['inspection_gaps'], sorted(e['id'] for e in report['catalog'])

    def test_symlinked_explicit_inputs_are_gaps(self):
        config = self.root / 'link.toml'
        config.symlink_to(self.targets / 'config.toml')
        rules = self.root / 'link.rules'
        rules.symlink_to(self.targets / 'default.rules')
        for option, path, gap in [('--config', config, CONFIG_GAP), ('--rules', rules, RULES_GAP)]:
            with self.subTest(option=option):
                self.assertEqual(self.report(option, str(path)), (2, [gap], []))

    def test_symlinked_default_files_are_gaps(self):
        config, rules = self.home / 'config.toml', self.home / 'rules' / 'default.rules'
        for link, regular, text, gap, ids in [(config, rules, ALLOW, CONFIG_GAP, RULES_IDS),
                                              (rules, config, CONFIG, RULES_GAP, CONFIG_IDS)]:
            with self.subTest(link=link.name):
                link.unlink(missing_ok=True)
                link.symlink_to(self.targets / link.name)
                regular.unlink(missing_ok=True)
                regular.write_text(text)
                self.assertEqual(self.report(), (2, [gap], ids))

    def test_regular_explicit_and_default_files_are_still_read(self):
        read = (0, [], [*CONFIG_IDS, *RULES_IDS])
        explicit = ('--config', str(self.targets / 'config.toml'), '--rules', str(self.targets / 'default.rules'))
        self.assertEqual(self.report(*explicit), read)
        (self.home / 'config.toml').write_text(CONFIG)
        (self.home / 'rules' / 'default.rules').write_text(ALLOW)
        self.assertEqual(self.report(), read)
