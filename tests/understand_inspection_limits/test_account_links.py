import json

from tests.support import ConfigCase, copy_checkout, run_checkout


class AppAccountPolicyTests(ConfigCase):
    def test_only_an_empty_account_map_clears_the_account_gap(self):
        checkout = copy_checkout(self.root / "checkout")
        config = ('approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n'
                  'shell_environment_policy.inherit = "none"\n[apps.calendar]\n')
        account_gap = "config-1: Per-account app policy is not evaluated; account identifiers were withheld."
        app_findings = {("config-1:apps.calendar", "destructive_tools"),
                        ("config-1:apps.calendar", "self_described_tools")}
        cases = [
            ("", [], app_findings),
            ("links = {}", [], app_findings),
            ('links = { private_account = { default_tools_approval_mode = "prompt" } }', [account_gap], app_findings),
            ("links = false", [account_gap], app_findings),
            ('enabled = "false"\nlinks = {}',
             [account_gap, "config-1: apps has an invalid boolean; its behavior is unknown."], set()),
        ]
        for field, expected_gaps, findings in cases:
            with self.subTest(field=field):
                path = str(self.config(config + field))
                run = run_checkout(checkout, "--agent", "codex", "--config", path, "--format", "json", cwd=self.root)
                report = json.loads(run.stdout)
                self.assertEqual(report["inspection_gaps"], expected_gaps)
                self.assertEqual(run.returncode, 2 if expected_gaps else 0)
                self.assertEqual({(risk["entry"], risk["rule"]) for risk in report["risks"]},
                                 findings)
                self.assertNotIn("private_account", run.stdout + run.stderr)
