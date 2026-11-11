"""Default values are independently expected from the pinned Codex conversion:
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/shell_environment_policy.rs#L133-L169
Selection and absence behavior are specified in stay-safe issue #7.
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
from tests.support import CHATGPT_APPS, ConfigCase, ROOT, items, section, gap_items
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text


NOTICE = 'No default Codex configuration file was found; documented shell-environment defaults assessed.'
DEFAULTS = ['inherit: all (default)', 'ignore_default_excludes: true (default)']
GAPS = [
    'config-1: approval_policy is absent; the reader does not infer its effective value.',
    'config-1: sandbox_mode is absent; the reader does not infer its effective value.',
]
READ_GAP = 'config-1: Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.'
BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
ALLOW = 'prefix_rule(pattern=["curl"], decision="allow")\n'
EXPLANATION = ('The selected configuration starts shell command environments from the parent process environment, '
               'apart from a few Codex launch variables. '
               'Inherited credentials could be misused, even with automatic name filtering enabled.')


class DefaultConfigTests(ConfigCase):
    def report(self, args=(), home=None):
        output = io.StringIO()
        with patch.dict(os.environ, {'CODEX_HOME': str(home or self.root)}, clear=True), redirect_stdout(output):
            status = main([*args, '--format', 'json'])
        return status, json.loads(output.getvalue())

    def cli(self, *args, home=None):
        return subprocess.run([sys.executable, '-B', '-m', 'stay_safe', *args], cwd=ROOT,
                              env={'CODEX_HOME': str(home or self.root)},
                              text=True, capture_output=True, timeout=10)

    def test_both_formats_report_cited_defaults_and_retained_gaps(self):
        self.require_no_system_folder()
        expected_entry = {'id': 'config-1:shell_environment_policy', 'source': 'config-1',
                          'name': 'shell_environment_policy', 'kind': 'permission', 'observations': DEFAULTS}
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=10).strip()
        prefix = f'https://github.com/chalkbadger/stay-safe/blob/{revision}/'
        for format_name in ('markdown', 'json'):
            with self.subTest(format=format_name):
                run = self.cli('--format', format_name)
                self.assertEqual((run.returncode, run.stderr), (2, ''))
                self.assertNotIn('Input is missing', run.stdout)
                if format_name == 'json':
                    self.assertIn(NOTICE, run.stdout)
                    self.assertIn('effective permissions are not tested', run.stdout)
                    report = json.loads(run.stdout)
                    self.assertEqual(report['file_inspection'], 'incomplete')
                    self.assertCountEqual(report['inspection_gaps'], GAPS)
                    self.assertEqual(report['catalog'], [
                        {'id': 'config-1:config', 'source': 'config-1', 'name': 'config',
                         'kind': 'configuration file', 'observations': [NOTICE]},
                        {'id': 'config-1:features.apps', 'source': 'config-1', 'name': 'features.apps',
                         'kind': 'MCP server', 'observations': CHATGPT_APPS},
                        expected_entry,
                        {'id': 'rules-1:rules', 'source': 'rules-1', 'name': 'rules',
                         'kind': 'rules file', 'observations': ['absent']},
                    ])
                    self.assertEqual(report['risks'], [{
                        'rule': 'environment_inheritance', 'entry': expected_entry['id'], 'explanation': EXPLANATION,
                        'incidents': ['I23'], 'configured_evidence': DEFAULTS,
                        'rule_source': prefix + 'stay_safe/rules.py', 'interpretation_source': prefix + 'harnesses/codex.md',
                    }])
                    self.assertEqual(report['incident_links'], {
                        'I23': prefix + 'incidents.md#i23-production-tables-dropped-by-a-dev-only-migration-command'})
                    self.assertEqual((report['provenance']['source_revision'], report['provenance']['source_status']),
                                     (revision, 'checkout commit'))
                else:
                    self.assertEqual(run.stdout.splitlines()[2], '1 finding, 2 things not checked.')
                    self.assertIn('*Rule `environment_inheritance` · setting `config-1:shell_environment_policy` = '
                                  + '`' + '; '.join(DEFAULTS) + '`*\n', run.stdout)
                    self.assertIn('(reported, not verified)', run.stdout)
                    self.assertCountEqual(gap_items(run.stdout), [gap_text(gap, absent=True, file='$CODEX_HOME/config.toml') for gap in GAPS])
                    self.assertIn('\n- Config file: none found, so stay-safe assessed Codex\'s documented defaults (the '
                                  'environment of commands and the ChatGPT Apps connection)\n', section(run.stdout, 'Your setup') + '\n')
                    self.assertIn('\n- Whether connections work, or what Codex actually allows when it runs: ', run.stdout)
                    for path in ('harnesses/codex.md', 'stay_safe/rules.py', 'incidents.md#i23-'):
                        self.assertIn(prefix + path, run.stdout)

    def test_missing_home_dot_codex_with_unset_codex_home_uses_defaults(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'home', return_value=self.root), redirect_stdout(output):
            self.assertEqual(main(['--format', 'json']), 2)
        report = json.loads(output.getvalue())
        self.assertIn(NOTICE, output.getvalue())
        self.assertCountEqual(report['inspection_gaps'], GAPS)
        self.assertEqual([r['rule'] for r in report['risks']], ['environment_inheritance'])

    def test_readable_default_file_keeps_its_policy_and_has_no_absence_notice(self):
        for content, expected in [('', DEFAULTS), (BASE + '[shell_environment_policy]\ninherit="none"',
                                                  ['inherit: none (explicit)', 'ignore_default_excludes: true (default)'])]:
            with self.subTest(content=content):
                self.config(content)
                status, report = self.report()
                self.assertEqual(status, 2 if not content else 0)
                self.assertNotIn(NOTICE, json.dumps(report))
                policy, = [e for e in report['catalog'] if e['name'] == 'shell_environment_policy']
                self.assertEqual(policy['observations'], expected)
                self.assertEqual([r['rule'] for r in report['risks']], ['environment_inheritance'] if not content else [])

    def test_rejected_defaults_never_gain_default_observations(self):
        cases = [('malformed', b'model="private-secret', READ_GAP),
                 ('invalid-utf8', b'\xff', READ_GAP),
                 ('oversize', b' ' * (1024 * 1024 + 1), 'config-1: Input exceeds the 1 MiB size limit.'),
                 ('directory', None, READ_GAP),
                 ('symlink', None, READ_GAP), ('dangling', None, READ_GAP)]
        for name, data, gap in cases:
            with self.subTest(input=name):
                home = self.root / name
                home.mkdir()
                path = home / 'config.toml'
                if data is not None:
                    path.write_bytes(data)
                elif name == 'directory':
                    path.mkdir()
                else:
                    target = home / 'target.toml'
                    if name == 'symlink':
                        target.write_text('')
                    path.symlink_to(target)
                status, report = self.report(home=home)
                self.assertEqual((status, report['inspection_gaps']), (2, [gap]))
                self.assertEqual([e for e in report['catalog'] if e['source'] == 'config-1'], [])
                self.assertEqual(report['risks'], [])
                self.assertNotIn(NOTICE, json.dumps(report))

    def test_permission_failure_is_a_gap_without_defaults(self):
        path = self.config('')
        original_open = os.open
        def denied(file, *args, **kwargs):
            if file == path:
                raise PermissionError('private-error')
            return original_open(file, *args, **kwargs)
        with patch('stay_safe.codex.os.open', side_effect=denied):
            status, report = self.report()
        self.assertEqual((status, report['inspection_gaps'], report['risks']), (2, [READ_GAP], []))
        self.assertNotIn(NOTICE, json.dumps(report))
        self.assertNotIn('private-error', json.dumps(report))

    def test_fifo_is_rejected_without_blocking(self):
        self.require_no_system_folder()
        os.mkfifo(self.root / 'config.toml')
        run = self.cli('--format', 'json')
        self.assertEqual((run.returncode, run.stderr), (2, ''))
        report = json.loads(run.stdout)
        self.assertEqual(report['inspection_gaps'], ['config-1: Input is not a regular file.'])
        self.assertEqual(report['risks'], [])
        self.assertNotIn(NOTICE, run.stdout)

    def test_explicit_selection_never_assesses_the_absent_default(self):
        missing = self.root / 'config.toml'
        clean = self.config(BASE + '[shell_environment_policy]\ninherit="none"', 'clean.toml')
        for args, source in [(['--config', str(missing)], 'config-1'),
                             (['--config', str(clean), '--config', str(missing)], 'config-2'),
                             (['--config', str(missing), '--config', str(clean)], 'config-1')]:
            with self.subTest(args=args):
                status, report = self.report(args)
                self.assertEqual((status, report['inspection_gaps'], report['risks']),
                                 (2, [READ_GAP.replace('config-1', source)], []))
                self.assertNotIn(NOTICE, json.dumps(report))
                if len(args) > 2:
                    self.assertEqual({e['source'] for e in report['catalog']}, {'config-1' if source == 'config-2' else 'config-2'})
        rules = self.root / 'selected.rules'
        rules.write_text(ALLOW)
        status, report = self.report(['--rules', str(rules)])
        self.assertEqual((status, report['inspection_gaps']), (0, []))
        self.assertEqual([r['rule'] for r in report['risks']], ['saved_approval'])
        self.assertEqual({e['source'] for e in report['catalog']}, {'rules-1'})

    def test_default_rules_findings_and_gaps_survive_config_absence(self):
        (self.root / 'rules').mkdir()
        (self.root / 'rules' / 'default.rules').write_text(ALLOW + 'unsupported-rule\n')
        status, report = self.report()
        self.assertEqual(status, 2)
        self.assertEqual({(r['rule'], r['entry']) for r in report['risks']}, {
            ('environment_inheritance', 'config-1:shell_environment_policy'),
            ('saved_approval', 'rules-1:prefix_rule.1'),
        })
        self.assertCountEqual(report['inspection_gaps'], GAPS + [
            'rules-1: Rules contain lines that are not inspected.',
        ])
