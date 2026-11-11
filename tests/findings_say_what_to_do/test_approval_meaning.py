"""Issue #12: expectations from Codex 086ccc8, not the report's wording table.

mcp/mod.rs L91-L110: approve/profile exemptions precede tool annotations.
mcp_tool_call.rs L1563-L1698: hints/history precede the human never denial.
L2597-L2632: auto and writes have different hint conditions.
"""
import json
import subprocess
import sys

from stay_safe.report import inspect, render, setup_words
from tests.support import ConfigCase, ROOT, section


class ApprovalMeaningTests(ConfigCase):
    def test_modes_describe_requirements_without_promising_a_prompt(self):
        expected = {
            'approve': 'allowed without asking when strict automatic review is off',
            'auto': 'approval depends on server hints, other exemptions and review',
            'writes': 'a read-only hint exempts approval when strict automatic review is off; other exemptions and review still apply',
            'prompt': 'requires approval unless another exemption applies; review can change the outcome',
        }
        for mode, meaning in expected.items():
            for suffix in ('', ' (default)'):
                with self.subTest(mode=mode, suffix=suffix):
                    text = setup_words(['mcp_servers', 'sample'], 'tool approval: ' + mode + suffix)
                    self.assertIn('`' + mode + '` (' + meaning + ')', text)

    def test_each_snapshot_keeps_its_policy_and_hint_risk_in_both_formats(self):
        paths = []
        for index, policy in enumerate(('never', 'on-request', None)):
            text = (f'approval_policy = "{policy}"\n' if policy else '')
            text += 'sandbox_mode = "read-only"\n[mcp_servers.sample]\nurl = "https://private.example"\n'
            paths.append(self.config(text, f'policy-{index}.toml'))
        report = inspect(paths)
        hints = [risk for risk in report['risks'] if risk['rule'] == 'self_described_tools']
        self.assertEqual([r['entry'] for r in hints], [f'config-{i}:mcp_servers.sample' for i in (1, 2, 3)])
        for risk in hints:
            self.assertIn('allowed without asking', risk['explanation'])
            self.assertIn('strict automatic review', risk['explanation'])
            self.assertIn('not successful execution', risk['explanation'])
            self.assertIn('runtime state requiring automated review', risk['explanation'])
            self.assertIn('reviewer state are not inspected', risk['explanation'])
        md = render(report, 'markdown')
        groups = section(md, 'Your setup').split('**Config file ')
        self.assertIn('human-review requests are denied', groups[1])
        self.assertNotIn('human-review requests are denied', groups[2])
        self.assertNotIn('human-review requests are denied', groups[3])
        self.assertIn('human-review requests require a decision', groups[2])
        self.assertNotIn('asks before every call', md)
        self.assertNotIn('https://private.example', md)
        self.assertEqual(json.loads(render(report, 'json'))['inspection_gaps'],
                         ['config-3: approval_policy is absent; the reader does not infer its effective value.'])

    def test_cli_approval_meaning_keeps_status_and_private_values_withheld(self):
        path = self.config('approval_policy = "never"\nsandbox_mode = "read-only"\n'
                           '[mcp_servers.sample]\nurl = "https://private.example"\n'
                           'default_tools_approval_mode = "approve"\n')
        for format_name in ('markdown', 'json'):
            run = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--config', str(path),
                                  '--format', format_name], cwd=ROOT, env={}, capture_output=True,
                                 text=True, timeout=10)
            self.assertEqual((run.returncode, run.stderr), (0, ''))
            self.assertIn('allowed without asking', run.stdout)
            self.assertIn('strict automatic review', run.stdout)
            self.assertNotIn('https://private.example', run.stdout)
