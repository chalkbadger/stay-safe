import json
import subprocess
import sys

from tests.support import ConfigCase, ROOT, items, section, gap_items
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text


BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
PROFILE = BASE + 'profile="selected"\nfuture_setting=true\n'
UNKNOWN = BASE + '[future_policy]\nvalue="hidden"\n'
PROFILE_GAP = 'Profiles are outside reader coverage; a selected profile can override the reported settings.'
UNKNOWN_GAP = 'Configuration contains fields outside reader coverage; their values were withheld.'

class MultiFileGapTests(ConfigCase):
    def assert_cli_gaps(self, configurations, expected):
        paths = [self.config(text, f'input-{index}.toml')
                 for index, text in enumerate(configurations, 1)]
        arguments = [argument for path in paths for argument in ('--config', str(path))]
        for format_name in ('markdown', 'json'):
            with self.subTest(format=format_name):
                run = subprocess.run(
                    [sys.executable, '-B', '-m', 'stay_safe', *arguments, '--format', format_name],
                    cwd=ROOT, env={}, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual((run.returncode, run.stderr), (2, ''))
                if format_name == 'json':
                    report = json.loads(run.stdout)
                    self.assertEqual(report['file_inspection'], 'incomplete')
                    self.assertCountEqual(report['inspection_gaps'], expected)
                else:
                    self.assertIn(f', {len(expected)} things not checked.\n', run.stdout)
                    self.assertCountEqual(gap_items(run.stdout),
                                          [gap_text(gap) for gap in expected])

    def test_both_files_keep_distinct_gaps_and_argument_order_sources(self):
        self.assert_cli_gaps((PROFILE, UNKNOWN), [
            f'config-1: {PROFILE_GAP}',
            f'config-1: {UNKNOWN_GAP}',
            f'config-2: {UNKNOWN_GAP}',
        ])

    def test_first_file_gaps_survive_a_gap_free_second_file(self):
        self.assert_cli_gaps((PROFILE, BASE), [
            f'config-1: {PROFILE_GAP}',
            f'config-1: {UNKNOWN_GAP}',
        ])

    def test_second_file_gaps_survive_a_gap_free_first_file(self):
        self.assert_cli_gaps((BASE, PROFILE), [
            f'config-2: {PROFILE_GAP}',
            f'config-2: {UNKNOWN_GAP}',
        ])
