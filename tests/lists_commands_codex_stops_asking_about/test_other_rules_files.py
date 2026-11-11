"""Other rules files in the Codex home's rules/ directory, in a run with no file arguments.

Expected results follow openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a:
- core/src/exec_policy.rs `policy_files` (L688-L712) joins `rules` to each enabled layer's config folder;
  the User layer's folder is the parent of the Codex home's config.toml (config/src/state.rs
  `config_folder`, L218-L232; config/src/loader/mod.rs L293-L328).
- core/src/exec_policy.rs `collect_policy_files` (L1177-L1227) loads every regular file whose extension is
  exactly `rules` (L1209-L1215), returns nothing for a missing directory (L1181) and fails with `ReadDir` for
  any other listing error (L1182-L1187). The reader matches names only (archived issue #76): any other name ending in `.rules`
  adds the gap, and a name that does not end in `.rules` adds none.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase, section, gap_items
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
ALLOW = 'prefix_rule(pattern=["curl"], decision="allow")\n'
OTHER = 'rules-1: Other rules files exist and were not inspected.'
UNLISTABLE = 'rules-1: The rules directory cannot be listed; other rules files may exist and were not inspected.'
UNREADABLE = 'rules-1: Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.'
DEFAULT_APPROVAL = ('rules-1:prefix_rule.1', ['program: curl', 'tokens: 1', 'broad: one-token prefix'])


class OtherRulesFileTests(ConfigCase):
    def home(self, name):
        """Return a new Codex home holding config.toml, and its rules directory path."""
        self.codex_home = self.root / name
        self.codex_home.mkdir()
        (self.codex_home / 'config.toml').write_text(CONFIG)
        return self.codex_home / 'rules'

    def run_report(self, format_name='json', args=()):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.codex_home)}), redirect_stdout(out), redirect_stderr(err):
            code = main(['--format', format_name, *args])
        self.assertEqual(err.getvalue(), '')
        return code, out.getvalue()

    def approvals(self, report):
        return [(e['id'], e['observations']) for e in report['catalog'] if e['kind'] == 'saved approval']

    def another_file_gives_the_gap(self, name, default):
        rules = self.home(f'home-{name}-{default is None}')
        rules.mkdir()
        if default is not None:
            (rules / 'default.rules').write_text(default)
        (rules / name).write_text('prefix_rule(pattern=["curl"], decision="forbidden")\n')
        code, out = self.run_report()
        report = json.loads(out)
        self.assertEqual((code, report['file_inspection'], report['inspection_gaps']),
                         (2, 'incomplete', [OTHER]))
        code, markdown = self.run_report('markdown')
        self.assertEqual(code, 2)
        self.assertEqual(gap_items(markdown), [gap_text(OTHER, file='$CODEX_HOME/rules/default.rules')])
        self.assertNotIn('private-team', out + markdown)

    def test_another_rules_file_adds_a_gap_naming_no_file_and_exits_2(self):
        # Codex loads each of these names (exec_policy.rs L1209-L1215), hidden and `default.`-prefixed ones too.
        for name in ['private-team.rules', '.private-team.rules', 'default.private-team.rules']:
            for default in [ALLOW, None]:
                with self.subTest(name=name, default=default):
                    self.another_file_gives_the_gap(name, default)
        with self.subTest(selected='--rules'):
            # Runs with --rules inspect only the selected file (archived issue #76, Not included).
            rules = self.home('selected')
            rules.mkdir()
            (rules / 'default.rules').write_text(ALLOW)
            (rules / 'private-team.rules').write_text(ALLOW)
            code, out = self.run_report(args=['--rules', str(rules / 'default.rules')])
            self.assertEqual((code, json.loads(out)['inspection_gaps']), (0, []))

    def test_other_rules_file_is_not_read(self):
        rules = self.home('home')
        rules.mkdir()
        (rules / 'default.rules').write_text(ALLOW)
        (rules / 'team.rules').write_text(
            '\nprefix_rule(pattern=["git", "push"], decision="allow")\nunsupported line\n')
        code, out = self.run_report()
        report = json.loads(out)
        self.assertEqual(code, 2)
        self.assertEqual(self.approvals(report), [DEFAULT_APPROVAL])
        self.assertEqual([r['entry'] for r in report['risks'] if r['rule'] == 'saved_approval'],
                         ['rules-1:prefix_rule.1'])
        self.assertEqual(report['inspection_gaps'], [OTHER])

    def test_files_codex_does_not_load_add_no_gap(self):
        # A name that does not end in `.rules` adds no gap; Codex loads none of these (exec_policy.rs L1209-L1215).
        for index, name in enumerate(['default.rules.bak', 'team.rules~', 'team.RULES', 'team.rule',
                                      'notes.txt', 'rules']):
            with self.subTest(name=name):
                rules = self.home(f'home-{index}')
                rules.mkdir()
                (rules / 'default.rules').write_text(ALLOW)
                (rules / name).write_text(ALLOW)
                code, out = self.run_report()
                report = json.loads(out)
                self.assertEqual((code, report['inspection_gaps']), (0, []))
                self.assertEqual(self.approvals(report), [DEFAULT_APPROVAL])

    def test_rules_directory_that_cannot_be_listed_is_a_gap(self):
        # A regular file and a self-referencing link both fail `read_dir` with an error other than NotFound.
        for kind in ['regular file', 'self-referencing link']:
            with self.subTest(kind=kind):
                rules = self.home(kind.replace(' ', '-'))
                if kind == 'regular file':
                    rules.write_text(ALLOW)
                else:
                    rules.symlink_to(rules)
                code, out = self.run_report()
                report = json.loads(out)
                self.assertEqual((code, self.approvals(report), report['inspection_gaps']),
                                 (2, [], [UNREADABLE, UNLISTABLE]))

    def test_rules_directory_listing_denied_beside_a_readable_default_is_a_gap(self):
        # Permission denied is not NotFound, so Codex fails with ReadDir (exec_policy.rs L1181-L1187).
        rules = self.home('home')
        rules.mkdir()
        (rules / 'default.rules').write_text(ALLOW)
        listdir = os.listdir

        def denied(path):
            # Only this listing is denied; other listings in the Codex home run as usual.
            if path == rules:
                raise PermissionError(13, 'Permission denied')
            return listdir(path)
        with patch('stay_safe.codex_rules.os.listdir', side_effect=denied):
            code, out = self.run_report()
        report = json.loads(out)
        self.assertEqual((code, self.approvals(report), report['inspection_gaps']),
                         (2, [DEFAULT_APPROVAL], [UNLISTABLE]))
