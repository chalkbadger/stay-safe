import json

from stay_safe.report import inspect, render
from tests.support import ConfigCase, INCOMPLETE, ReportRuns, gap_items
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text

BASE = '''approval_policy="on-request"
sandbox_mode="read-only"
notify=["private-program"]
[features]
apps=false
[shell_environment_policy]
inherit="none"
'''
MODE_GAP = 'A tool approval mode is unsupported or invalid; its value was withheld.'
OWN_MODE_GAP = 'A per-tool approval mode is unsupported or invalid; its value was withheld.'
APP_GAP = 'apps has an invalid boolean; its behavior is unknown.'
OWN_APP_GAP = 'tools has an invalid boolean; its behavior is unknown.'
# Expected inheritance follows harnesses/codex.md [tool-approval] and [app-tool-policy];
# issue #63 specifies that an inherited invalid value is reported only at its source.
PARENTS = (
    ('mcp_servers.example', 'url="https://private-endpoint.invalid"\ndefault_tools_approval_mode="private-invalid"\n',
     'approval_mode', MODE_GAP, OWN_MODE_GAP, '"approve"', [('automatic_tools', 'mcp_servers.example.tools.lookup')]),
    ('apps.example', 'destructive_enabled=false\ndefault_tools_approval_mode="private-invalid"\n',
     'approval_mode', MODE_GAP, OWN_MODE_GAP, '"approve"', [('automatic_tools', 'apps.example.tools.lookup')]),
    ('apps.example', 'destructive_enabled=false\ndefault_tools_approval_mode="prompt"\ndefault_tools_enabled="private-invalid"\n',
     'enabled', APP_GAP, OWN_APP_GAP, 'true', [('destructive_tools', 'apps.example.tools.lookup')]),
)


class InheritedGapTests(ConfigCase, ReportRuns):
    def check_report(self, parent, fields, own, gaps, risks):
        path = self.config(BASE + f'[{parent}]\n{fields}[{parent}.tools.lookup]\n{own}')
        report = inspect([path])
        expected = ['config-1: ' + gap for gap in gaps]
        self.assertEqual(report['inspection_gaps'], sorted(expected))
        self.assertCountEqual([(r['rule'], r['entry']) for r in report['risks']],
                              [('configured_program', 'config-1:notify')] +
                              [(rule, 'config-1:' + entry) for rule, entry in risks])
        markdown = render(report)
        self.assertCountEqual(gap_items(markdown), [gap_text(gap) for gap in expected])
        count = '1 thing not checked.' if len(gaps) == 1 else f'{len(gaps)} things not checked.'
        self.assertIn(count, markdown)
        encoded = render(report, 'json')
        self.assertEqual(json.loads(encoded)['inspection_gaps'], sorted(expected))
        for private in ('private-invalid', 'private-override', 'private-program', 'private-endpoint'):
            self.assertNotIn(private, markdown + encoded)
        return path

    def test_inherited_invalid_values_report_only_the_parent_in_both_formats(self):
        for parent, fields, key, gap, own_gap, valid, risks in PARENTS:
            with self.subTest(parent=parent, key=key):
                self.check_report(parent, fields, '', [gap], [])

    def test_invalid_tool_overrides_keep_their_own_gap(self):
        for parent, fields, key, gap, own_gap, valid, risks in PARENTS:
            with self.subTest(parent=parent, key=key):
                self.check_report(parent, fields, f'{key}="private-override"\n', [gap, own_gap], [])

    def test_valid_tool_overrides_keep_their_findings_with_an_invalid_parent(self):
        for parent, fields, key, gap, own_gap, valid, risks in PARENTS:
            with self.subTest(parent=parent, key=key):
                self.check_report(parent, fields, f'{key}={valid}\n', [gap], risks)

    def test_inherited_gap_cli_remains_incomplete_without_private_values(self):
        parent, fields, *_ = PARENTS[0]
        path = self.config(BASE + f'[{parent}]\n{fields}[{parent}.tools.lookup]\n')
        for format_name in ('markdown', 'json'):
            with self.subTest(format=format_name):
                run = self.run_cli('--config', str(path), '--format', format_name, env={})
                self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                self.assertNotIn('private-invalid', run.stdout + run.stderr)
                self.assertNotIn(str(path), run.stdout + run.stderr)
                if format_name == 'json':
                    self.assertEqual(json.loads(run.stdout)['inspection_gaps'], ['config-1: ' + MODE_GAP])
                else:
                    self.assertEqual(gap_items(run.stdout), [gap_text('config-1: ' + MODE_GAP)])
