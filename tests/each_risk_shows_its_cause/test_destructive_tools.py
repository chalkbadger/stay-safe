"""destructive_tools follows the setting Codex uses to decide whether a destructive tool can run.

Expected results come from Codex at 086ccc8, not from the reader's output. For a tool of an
enabled app, Codex uses the first of these that is set: the tool's own `enabled`, the app's
`default_tools_enabled`, then `destructive_enabled` from the app, then `apps._default`, then true.
A tool without a destructive mark counts as destructive.
- Order: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/connectors/src/app_tool_policy.rs#L279-L305
- Tests of that order: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/connectors/src/app_tool_policy_tests.rs#L685-L770
- An `apps._default` table without `destructive_enabled` holds true:
  https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/types.rs#L471-L476
"""

from stay_safe.report import inspect
from tests.support import ConfigCase


BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
AUTO = "tool approval: auto (default)"


class DestructiveToolTests(ConfigCase):
    def destructive(self, tail):
        """Return each destructive_tools risk as (entry, configured evidence)."""
        report = inspect([self.config(BASE + tail)])
        self.assertEqual(report["inspection_gaps"], [])
        return [(r["entry"].removeprefix("config-1:"), r["configured_evidence"])
                for r in report["risks"] if r["rule"] == "destructive_tools"], report

    def assert_destructive(self, tail, expected):
        with self.subTest(tail=tail):
            self.assertEqual(self.destructive(tail)[0], expected)

    def test_app_with_nothing_set_reports_codex_default(self):
        for tail, evidence in [
            ('[apps.files]', ["configured enabled", "destructive tools enabled by Codex default", AUTO]),
            ('[apps.files]\nenabled=true', ["configured enabled", "destructive tools enabled by Codex default", AUTO]),
            ('[apps._default]\n[apps.files]', ["configured enabled", "destructive tools enabled by Codex default", AUTO]),
        ]:
            self.assert_destructive(tail, [("apps.files", evidence)])

    def test_risk_names_where_destructive_enabled_true_comes_from(self):
        for tail, source in [
            ('[apps.files]\ndestructive_enabled=true', "destructive_enabled"),
            ('[apps._default]\ndestructive_enabled=false\n[apps.files]\ndestructive_enabled=true', "destructive_enabled"),
            ('[apps._default]\ndestructive_enabled=true\n[apps.files]', "apps._default.destructive_enabled"),
            # apps._default.enabled = false leaves this app enabled (archived issue #90; app_tool_policy.rs L174-L185 at
            # 086ccc8), and destructive_enabled still falls back to the template (L287-L294 at 086ccc8).
            ('[apps._default]\nenabled=false\ndestructive_enabled=true\n[apps.files]', "apps._default.destructive_enabled"),
        ]:
            self.assert_destructive(tail, [("apps.files", ["configured enabled", "destructive tools enabled by " + source, AUTO])])

    def test_default_tools_enabled_true_decides_whatever_destructive_enabled_says(self):
        evidence = ["configured enabled", "destructive tools enabled by default_tools_enabled", AUTO]
        for tail in [
            '[apps.files]\ndefault_tools_enabled=true',
            '[apps.files]\ndefault_tools_enabled=true\ndestructive_enabled=false',
            '[apps.files]\ndefault_tools_enabled=true\ndestructive_enabled=true',
            '[apps._default]\ndestructive_enabled=false\n[apps.files]\ndefault_tools_enabled=true',
        ]:
            self.assert_destructive(tail, [("apps.files", evidence)])

    def test_tool_enabled_true_reports_on_the_tool_whatever_the_app_says(self):
        tool = ("apps.files.tools.delete", ["configured enabled", "enabled even if destructive", "tool approval: auto"])
        enable = '\n[apps.files.tools.delete]\nenabled=true'
        for app, app_risk in [
            ('destructive_enabled=false', []),
            ('default_tools_enabled=false\ndestructive_enabled=true', []),
            ('default_tools_enabled=false\ndestructive_enabled=false', []),
            ('default_tools_enabled=true\ndestructive_enabled=false',
             [("apps.files", ["configured enabled", "destructive tools enabled by default_tools_enabled", AUTO])]),
            ('', [("apps.files", ["configured enabled", "destructive tools enabled by Codex default", AUTO])]),
        ]:
            self.assert_destructive('[apps.files]\n' + app + enable, app_risk + [tool])
        self.assert_destructive('[apps._default]\ndestructive_enabled=false\n[apps.files]' + enable, [tool])

    def test_no_risk_when_no_setting_lets_destructive_tools_run(self):
        for tail, observations in [
            # A disabled app runs no tools, whatever its tool settings say (app_tool_policy.rs L272-L277).
            ('[apps.files]\nenabled=false\ndefault_tools_enabled=true\n[apps.files.tools.delete]\nenabled=true',
             {"apps.files": ["disabled", AUTO],
              "apps.files.tools.delete": ["disabled or enablement unknown", "tool approval: auto"]}),
            ('[apps.files]\nenabled=false',
             {"apps.files": ["disabled", AUTO]}),
            ('[apps.files]\ndefault_tools_enabled=false\ndestructive_enabled=true\n[apps.files.tools.read]\nenabled=false',
             {"apps.files": ["configured enabled", "default tools disabled or unknown", "tool approval: auto (default)"],
              "apps.files.tools.read": ["disabled or enablement unknown", "tool approval: auto"]}),
            ('[apps.files]\ndestructive_enabled=false\n[apps.files.tools.read]\napproval_mode="prompt"',
             {"apps.files": ["configured enabled", "destructive tools disabled by destructive_enabled", AUTO],
              "apps.files.tools.read": ["configured enabled", "tool approval: prompt"]}),
            ('[apps._default]\ndestructive_enabled=false\n[apps.files]',
             {"apps._default": ["configured enabled", AUTO],
              "apps.files": ["configured enabled", "destructive tools disabled by apps._default.destructive_enabled", AUTO]}),
            # The same under apps._default.enabled = false, which disables no named app (archived issue #90; app_tool_policy.rs
            # L174-L185 at 086ccc8); destructive_enabled still falls back to the template (L287-L294 at 086ccc8).
            ('[apps._default]\nenabled=false\ndestructive_enabled=false\n[apps.files]',
             {"apps._default": ["disabled", AUTO],
              "apps.files": ["configured enabled", "destructive tools disabled by apps._default.destructive_enabled", AUTO]}),
        ]:
            with self.subTest(tail=tail):
                risks, report = self.destructive(tail)
                self.assertEqual(risks, [])
                self.assertEqual({e["name"]: e["observations"] for e in report["catalog"] if e["name"].startswith("apps.")},
                                 observations)
