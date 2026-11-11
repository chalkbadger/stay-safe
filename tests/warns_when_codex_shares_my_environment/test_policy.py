"""Expected policy comes from OpenAI's pinned source, not the reader:
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/config_types.rs#L205-L272
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/shell_environment_policy.rs#L133-L169
Even with inherit = "all", Codex never passes on its non-inheritable launch variables:
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/shell_environment.rs#L14-L22
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/shell_environment.rs#L170-L172
I23 supplies the related credential-misuse rationale, not an observed Codex run.
"""

import json
import subprocess
import sys
from unittest.mock import patch

from stay_safe.report import inspect, render
from tests.support import ConfigCase, ROOT

BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
DEFAULTS = ['inherit: all (default)', 'ignore_default_excludes: true (default)']
EXPLANATION = ('The selected configuration starts shell command environments from the parent process environment, '
               'apart from a few Codex launch variables. '
               'Inherited credentials could be misused, even with automatic name filtering enabled.')

# The Markdown lead of the finding (archived issue #105).
MARKDOWN_LEAD = ("**With these settings, commands Codex runs get your environment variables.** They start with the "
                 "environment Codex was launched with, apart from a few Codex launch variables. Credentials in it "
                 "could be misused, even if Codex filters out some variable names.")


class EnvironmentInheritanceTests(ConfigCase):
    def test_absent_empty_partial_and_explicit_policies_identify_each_setting(self):
        for policy, observations in [
            ('', DEFAULTS),
            ('shell_environment_policy={}', DEFAULTS),
            ('[shell_environment_policy]', DEFAULTS),
            ('[shell_environment_policy]\ninherit="all"',
             ['inherit: all (explicit)', 'ignore_default_excludes: true (default)']),
            ('[shell_environment_policy]\nignore_default_excludes=true',
             ['inherit: all (default)', 'ignore_default_excludes: true (explicit)']),
            ('[shell_environment_policy]\ninherit="all"\nignore_default_excludes=true',
             ['inherit: all (explicit)', 'ignore_default_excludes: true (explicit)']),
        ]:
            with self.subTest(policy=policy):
                report = inspect([self.config(BASE + policy)])
                self.assertEqual([e for e in report['catalog'] if e['name'] == 'shell_environment_policy'], [{
                    'id': 'config-1:shell_environment_policy', 'source': 'config-1',
                    'name': 'shell_environment_policy', 'kind': 'permission', 'observations': observations,
                }])
                self.assertEqual([(r['rule'], r['entry'], r['configured_evidence'], r['incidents'])
                                  for r in report['risks']],
                                 [('environment_inheritance', 'config-1:shell_environment_policy', observations, ['I23'])])
                self.assertEqual(report['inspection_gaps'], [])

    def test_only_full_inheritance_matches_regardless_of_name_filtering(self):
        for inherit in ('all', 'none', 'core'):
            for excludes in ('true', 'false'):
                with self.subTest(inherit=inherit, excludes=excludes):
                    policy = f'[shell_environment_policy]\ninherit="{inherit}"\nignore_default_excludes={excludes}'
                    report = inspect([self.config('approval_policy="never"\nsandbox_mode="read-only"\n' + policy)])
                    expected = ['commands_without_prompts']
                    if inherit == 'all':
                        expected.append('environment_inheritance')
                    self.assertEqual([r['rule'] for r in report['risks']], expected)
                    self.assertEqual(report['catalog'][-1]['observations'],
                                     [f'inherit: {inherit} (explicit)', f'ignore_default_excludes: {excludes} (explicit)'])
                    self.assertEqual(report['inspection_gaps'], [])
        for policy, observations, rules in [
            ('inherit="none"', ['inherit: none (explicit)', 'ignore_default_excludes: true (default)'], []),
            ('inherit="core"', ['inherit: core (explicit)', 'ignore_default_excludes: true (default)'], []),
            ('ignore_default_excludes=false', ['inherit: all (default)', 'ignore_default_excludes: false (explicit)'],
             ['environment_inheritance']),
        ]:
            with self.subTest(partial=policy):
                report = inspect([self.config(BASE + '[shell_environment_policy]\n' + policy)])
                self.assertEqual([r['rule'] for r in report['risks']], rules)
                self.assertEqual(report['catalog'][-1]['observations'], observations)
                self.assertEqual(report['inspection_gaps'], [])

    def test_invalid_or_extra_fields_are_gaps_without_fabricated_defaults(self):
        table = 'config-1: shell_environment_policy must be a table.'
        inherit = 'config-1: shell_environment_policy.inherit is unsupported or invalid; its value was withheld.'
        excludes = 'config-1: shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown.'
        extra = 'config-1: shell_environment_policy contains fields outside reader coverage; their values were withheld.'
        for policy, gap in [
            *[('shell_environment_policy=' + value, table) for value in ('"private-value"', '[]', 'false')],
            *[('[shell_environment_policy]\ninherit=' + value, inherit)
              for value in ('"private-value"', '"ALL"', 'true', '1', '[]', '{}')],
            *[('[shell_environment_policy]\nignore_default_excludes=' + value, excludes)
              for value in ('"private-value"', '1', '0', '[]', '{}')],
            *[('[shell_environment_policy]\n' + field, extra)
              for field in ('exclude=[]', 'include_only=[]', 'set={}', 'filters={}', 'experimental_use_profile=false',
                            'exclude=["PRIVATE_NAME"]', 'include_only=["PRIVATE_NAME"]',
                            'set={PRIVATE_NAME="private-value"}', 'filters={PRIVATE_NAME="exclude"}',
                            'experimental_use_profile=true',
                            '"PRIVATE_NAME"="private-value"')],
            ('[shell_environment_policy]\ninherit="all"\nignore_default_excludes=true\nexclude=[]', extra),
        ]:
            with self.subTest(policy=policy):
                report = inspect([self.config('approval_policy="never"\nsandbox_mode="read-only"\n' + policy)])
                self.assertEqual([r['rule'] for r in report['risks']], ['commands_without_prompts'])
                self.assertEqual([e['name'] for e in report['catalog']], ['approval_policy', 'features.apps', 'sandbox_mode'])
                self.assertEqual(report['inspection_gaps'], [gap])
                self.assertNotIn('PRIVATE_NAME', render(report))
                self.assertNotIn('private-value', render(report, 'json'))

    def test_rejected_files_never_gain_default_entries(self):
        missing = self.root / 'missing.toml'
        malformed = self.config('model="private-value', 'malformed.toml')
        invalid_bytes = self.root / 'invalid.toml'
        invalid_bytes.write_bytes(b'\xff')
        unreadable = self.config(BASE, 'unreadable.toml')
        for path in (missing, malformed, invalid_bytes, self.root):
            with self.subTest(path=path.name):
                report = inspect([path])
                self.assertEqual((report['catalog'], report['risks']), ([], []))
                self.assertEqual(report['file_inspection'], 'incomplete')
        with patch('stay_safe.codex.os.open', side_effect=PermissionError):
            report = inspect([unreadable])
        self.assertEqual((report['catalog'], report['risks'], report['inspection_gaps']), ([], [], [
            'config-1: Selected config file could not be read. Check its permissions and that it is a readable regular file.']))

    def test_cli_formats_keep_evidence_citations_and_honest_status(self):
        for config, status in [('model="example"', 2), (BASE, 0)]:
            path = self.config(config)
            for format_name in ('markdown', 'json'):
                with self.subTest(config=config, format=format_name):
                    run = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--config', str(path),
                                          '--format', format_name], cwd=ROOT, text=True,
                                         capture_output=True, timeout=10)
                    self.assertEqual((run.returncode, run.stderr), (status, ''))
                    if format_name == 'json':
                        self.assertIn(EXPLANATION, run.stdout)
                        report = json.loads(run.stdout)
                        risk, = report['risks']
                        self.assertEqual((risk['rule'], risk['entry'], risk['configured_evidence'], risk['incidents']),
                                         ('environment_inheritance', 'config-1:shell_environment_policy', DEFAULTS, ['I23']))
                        self.assertEqual(report['incident_status'], 'reported, not verified')
                        revision = report['provenance']['source_revision']
                        prefix = f'https://github.com/chalkbadger/stay-safe/blob/{revision}/'
                        self.assertEqual(risk['interpretation_source'], prefix + 'harnesses/codex.md')
                        self.assertEqual(risk['rule_source'], prefix + 'stay_safe/rules.py')
                        self.assertEqual(report['incident_links']['I23'], prefix + 'incidents.md#i23-production-tables-dropped-by-a-dev-only-migration-command')
                    else:
                        self.assertIn(MARKDOWN_LEAD + '\n\n*How it has gone wrong:* ', run.stdout)
                        self.assertIn('\n\n*Rule `environment_inheritance` · setting `config-1:shell_environment_policy` = '
                                      + '`' + '; '.join(DEFAULTS) + '`*\n', run.stdout)
                        self.assertIn('(reported, not verified)', run.stdout)
                        self.assertRegex(run.stdout, r'\[I23\]\(https://github.com/chalkbadger/stay-safe/blob/[0-9a-f]{40}/incidents.md#i23-')
                        self.assertIn('/harnesses/codex.md)', run.stdout)
