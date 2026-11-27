from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import INCOMPLETE
from tests.support import ConfigCase, section, gap_items, run_home
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
ALLOW = 'prefix_rule(pattern=["curl"], decision="allow")\n'
OTHER = 'rules-1: Other rules files exist and were not inspected.'
UNKNOWN_TYPE = 'rules-1: A rules entry could not be checked to determine whether it is a file.'
UNLISTABLE = 'rules-1: The rules directory cannot be listed; other rules files may exist and were not inspected.'
UNREADABLE = 'rules-1: Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.'
DEFAULT_APPROVAL = ('rules-1:prefix_rule.1', ['program: curl', 'tokens: 1', 'broad: one-token prefix'])


class OtherRulesFileTests(ConfigCase):
    def home(self, name):
        self.codex_home = self.root / name
        self.codex_home.mkdir()
        (self.codex_home / 'config.toml').write_text(CONFIG)
        return self.codex_home / 'rules'

    def run_report(self, format_name='json', args=()):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.codex_home)}), redirect_stdout(out), redirect_stderr(err):
            code = main(['--format', format_name, *args])
        self.assertEqual(err.getvalue(), INCOMPLETE if code == 2 else "")
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
        for name in ['private-team.rules', '.private-team.rules', 'default.private-team.rules']:
            for default in [ALLOW, None]:
                with self.subTest(name=name, default=default):
                    self.another_file_gives_the_gap(name, default)
        with self.subTest(selected='--rules'):
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

    def test_rules_named_directory_adds_no_gap_and_the_saved_approval_stays_visible(self):
        for kind, expected in [('absent', []), ('directory', []), ('file', [OTHER])]:
            with self.subTest(kind=kind):
                rules = self.home(kind)
                rules.mkdir()
                (rules / 'default.rules').write_text(ALLOW)
                sibling = rules / 'private-team.rules'
                if kind == 'directory':
                    sibling.mkdir()
                elif kind == 'file':
                    sibling.touch()
                code, out = self.run_report()
                report = json.loads(out)
                self.assertEqual(self.approvals(report), [DEFAULT_APPROVAL])
                self.assertEqual([r['entry'] for r in report['risks'] if r['rule'] == 'saved_approval'],
                                 ['rules-1:prefix_rule.1'])
                self.assertEqual((code, report['inspection_gaps']), (2 if expected else 0, expected))
                self.assertNotIn(sibling.name, out)

    def test_symlinks_and_pipes_add_no_rules_gap_and_preserve_the_approval(self):
        rules = self.home('nonregular')
        rules.mkdir()
        default = rules / 'default.rules'
        default.write_text(ALLOW)
        sibling = rules / 'private-team.rules'

        def scan():

            return run_home(self.root, '--agent', 'codex', '--format', 'json', CODEX_HOME=str(self.codex_home))

        absent = scan()
        baseline = json.loads(absent.stdout)
        self.assertNotIn(OTHER, baseline['inspection_gaps'])
        self.assertEqual(self.approvals(baseline), [DEFAULT_APPROVAL])
        self.assertEqual([risk['entry'] for risk in baseline['risks'] if risk['rule'] == 'saved_approval'],
                         ['rules-1:prefix_rule.1'])
        for kind in ['file symlink', 'broken symlink', 'FIFO']:
            with self.subTest(kind=kind):
                if kind == 'FIFO':
                    os.mkfifo(sibling)
                else:
                    sibling.symlink_to(default if kind == 'file symlink' else rules / 'missing')
                run = scan()
                sibling.unlink()
                self.assertEqual((run.returncode, run.stderr), (absent.returncode, absent.stderr))
                self.assertEqual(json.loads(run.stdout), baseline)

    def test_an_uninspectable_sibling_reports_an_incomplete_check_and_preserves_the_approval(self):
        rules = self.home('vanishing-entry')
        rules.mkdir()
        (rules / 'default.rules').write_text(ALLOW)
        sibling = rules / 'private-team.rules'
        listdir = os.listdir

        def remove_after_listing(directory):
            names = listdir(directory)
            if directory == rules and sibling.name in names:
                sibling.unlink()
            return names

        extra = rules / 'other-team.rules'
        for include_extra in [False, True]:
            with self.subTest(include_extra=include_extra):
                sibling.touch()
                if include_extra:
                    extra.touch()
                with patch('os.listdir', side_effect=remove_after_listing):
                    code, out = self.run_report()
                report = json.loads(out)
                self.assertEqual(self.approvals(report), [DEFAULT_APPROVAL])
                self.assertEqual([r['entry'] for r in report['risks'] if r['rule'] == 'saved_approval'],
                                 ['rules-1:prefix_rule.1'])
                expected_gaps = [UNKNOWN_TYPE, OTHER] if include_extra else [UNKNOWN_TYPE]
                self.assertEqual((code, report['inspection_gaps']), (2, expected_gaps))
                self.assertNotIn(sibling.name, out)
                self.assertNotIn(extra.name, out)

    def test_only_a_rules_extension_adds_a_gap(self):
        ignored = ['default.rules.bak', 'team.rules~', 'team.RULES', 'team.rule', 'notes.txt', 'rules', '.rules']
        for index, name in enumerate([*ignored, 'team.rules']):
            with self.subTest(name=name):
                rules = self.home(f'home-{index}')
                rules.mkdir()
                (rules / 'default.rules').write_text(ALLOW)
                (rules / name).write_text(ALLOW)
                code, out = self.run_report()
                report = json.loads(out)
                expected = (2, [OTHER]) if name == 'team.rules' else (0, [])
                self.assertEqual((code, report['inspection_gaps']), expected)
                self.assertEqual(self.approvals(report), [DEFAULT_APPROVAL])

    def test_rules_directory_that_cannot_be_listed_is_a_gap(self):
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
        rules = self.home('home')
        rules.mkdir()
        (rules / 'default.rules').write_text(ALLOW)
        listdir = os.listdir

        def denied(path):
            if path == rules:
                raise PermissionError(13, 'Permission denied')
            return listdir(path)
        with patch('stay_safe.codex_rules.os.listdir', side_effect=denied):
            code, out = self.run_report()
        report = json.loads(out)
        self.assertEqual((code, self.approvals(report), report['inspection_gaps']),
                         (2, [DEFAULT_APPROVAL], [UNLISTABLE]))
