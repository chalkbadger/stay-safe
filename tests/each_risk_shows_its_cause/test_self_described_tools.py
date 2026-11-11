"""Independent conditions for the source-documented hint-based approval rule.

Expected modes and overrides: ../../harnesses/codex.md and
https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/src/mcp_tool_call.rs
requires_mcp_tool_approval_for_mode. This diagnostic does not execute Codex or
observe a server's hints; it reports the configured dependence on those hints.
"""

from stay_safe.report import inspect
from tests.support import ConfigCase


BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
MCP = '[mcp_servers.remote]\nurl="https://example.com"\n'


class SelfDescribedToolTests(ConfigCase):
    def check(self, tail, names, gap=False):
        report = inspect([self.config(BASE + tail)])
        self.assertEqual([(risk["entry"], risk["incidents"]) for risk in report["risks"]
                          if risk["rule"] == "self_described_tools"],
                         [("config-1:" + name, ["I15", "I21"]) for name in names])
        self.assertEqual(bool(report["inspection_gaps"]), gap)
        return report

    def test_explicit_modes_and_omitted_auto_default_on_named_connections(self):
        for prefix, name in [(MCP, "mcp_servers.remote"), ('[apps.files]\n', "apps.files")]:
            for setting, label, expected in [
                ('', 'auto (default)', [name]),
                ('default_tools_approval_mode="auto"', 'auto', [name]),
                ('default_tools_approval_mode="writes"', 'writes', [name]),
                ('default_tools_approval_mode="prompt"', 'prompt', []),
                ('default_tools_approval_mode="approve"', 'approve', []),
            ]:
                with self.subTest(name=name, mode=label):
                    report = self.check(prefix + setting, expected)
                    entry = next(e for e in report["catalog"] if e["name"] == name)
                    self.assertIn("tool approval: " + label, entry["observations"])

    def test_disabled_and_invalid_connections_do_not_supply_the_condition(self):
        for tail, gap in [
            (MCP + 'enabled=false', False),
            ('[mcp_servers.remote]\ncommand="synthetic-command"\nenabled=false', False),
            ('[apps.files]\nenabled=false\ndefault_tools_approval_mode="writes"', False),
            ('[apps.files]\ndefault_tools_enabled=false', False),
            ('[mcp_servers.remote]\nurl=["invalid-private-endpoint"]', True),
        ]:
            with self.subTest(tail=tail):
                self.check(tail, [], gap)

    def test_app_defaults_are_inherited_but_are_not_a_connection(self):
        for tail, expected in [
            ('[apps._default]', []),
            ('[apps._default]\ndefault_tools_approval_mode="writes"', []),
            ('[apps._default]\ndefault_tools_approval_mode="writes"\n[apps.files]', ['apps.files']),
            ('[apps._default]\ndefault_tools_approval_mode="prompt"\n[apps.files]', []),
            ('[apps._default]\ndefault_tools_approval_mode="writes"\n[apps.files]\ndefault_tools_approval_mode="prompt"', []),
            # apps._default.enabled disables no named app (archived issue #90; openai/codex@086ccc8
            # codex-rs/connectors/src/app_tool_policy.rs L174-L185 and the recorded run,
            # https://github.com/chalkbadger/stay-safe-archive/issues/90#issuecomment-6726050010).
            ('[apps._default]\nenabled=false\ndefault_tools_approval_mode="writes"\n[apps.files]', ['apps.files']),
            ('[apps._default]\nenabled=false\ndefault_tools_approval_mode="writes"\n[apps.files]\nenabled=true', ['apps.files']),
        ]:
            with self.subTest(tail=tail):
                self.check(tail, expected)

    def test_closed_filters_and_tool_overrides_preserve_only_applicable_identities(self):
        for tail, expected in [
            ('enabled_tools=[]', []),
            ('enabled_tools=["read"]', ['mcp_servers.remote']),
            ('enabled_tools=["read"]\ndisabled_tools=["other"]', ['mcp_servers.remote']),
            ('enabled_tools=["read"]\ndisabled_tools=["read"]', []),
            ('enabled_tools=["read"]\n[mcp_servers.remote.tools.read]\napproval_mode="prompt"', []),
            ('enabled_tools=["read"]\n[mcp_servers.remote.tools.read]\napproval_mode="writes"', ['mcp_servers.remote.tools.read']),
            ('enabled_tools=["read"]\ndisabled_tools=["other"]\n[mcp_servers.remote.tools.read]\napproval_mode="writes"', ['mcp_servers.remote.tools.read']),
            ('default_tools_approval_mode="prompt"\n[mcp_servers.remote.tools.read]\napproval_mode="auto"', ['mcp_servers.remote.tools.read']),
            ('enabled_tools=["read"]\ndisabled_tools=["read"]\n[mcp_servers.remote.tools.read]\napproval_mode="writes"', []),
            ('enabled_tools=["read"]\n[mcp_servers.remote.tools.unlisted]\napproval_mode="writes"', ['mcp_servers.remote']),
            ('default_tools_approval_mode="writes"\n[mcp_servers.remote.tools.read]\napproval_mode="prompt"', ['mcp_servers.remote']),
        ]:
            with self.subTest(tail=tail):
                self.check(MCP + tail, expected)

    def test_template_tool_blocks_are_skipped_and_named_app_overrides_still_work(self):
        # AppsDefaultConfig has no tools field; AppConfig has per-tool overrides.
        # Source: ../../harnesses/codex.md [apps] and [configuration-reference].
        for mode, expected_rule in [("auto", "self_described_tools"), ("writes", "self_described_tools"),
                                    ("approve", "automatic_tools"), ("prompt", None)]:
            with self.subTest(mode=mode):
                template = '[apps._default.tools.read]\napproval_mode="' + mode + '"'
                report = self.check(template, [], gap=True)
                self.assertEqual([r["rule"] for r in report["risks"]], ["environment_inheritance"])
                self.assertEqual([e["name"] for e in report["catalog"]],
                                 ["approval_policy", "apps._default", "features.apps", "sandbox_mode", "shell_environment_policy"])
                self.assertEqual(report["inspection_gaps"], [
                    "config-1: apps._default contains fields outside reader coverage; their values were withheld.",
                ])
                control = '[apps._default]\ndefault_tools_approval_mode="prompt"\n' + template
                control += '\n[apps.files.tools.read]\napproval_mode="' + mode + '"'
                report = self.check(control, ["apps.files.tools.read"] if expected_rule == "self_described_tools" else [], gap=True)
                # The named app sets nothing else, so Codex's default lets it run destructive tools.
                self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]],
                                 [("destructive_tools", "config-1:apps.files")]
                                 + ([(expected_rule, "config-1:apps.files.tools.read")] if expected_rule else [])
                                 + [("environment_inheritance", "config-1:shell_environment_policy")])
                self.assertFalse(any(e["name"].startswith("apps._default.tools.") for e in report["catalog"]))
                self.assertEqual([e["observations"] for e in report["catalog"] if e["name"] == "apps.files.tools.read"],
                                 [["configured enabled", "tool approval: " + mode]])

    def test_app_tool_enablement_and_approval_overrides(self):
        for tail, expected in [
            ('default_tools_enabled=false\n[apps.files.tools.read]\nenabled=true', ['apps.files']),
            ('default_tools_enabled=false\n[apps.files.tools.read]\nenabled=true\napproval_mode="prompt"', []),
            ('default_tools_approval_mode="prompt"\n[apps.files.tools.read]\napproval_mode="writes"', ['apps.files.tools.read']),
            ('default_tools_approval_mode="prompt"\n[apps.files.tools.read]\nenabled=false\napproval_mode="writes"', []),
            ('enabled=false\n[apps.files.tools.read]\nenabled=true\napproval_mode="writes"', []),
        ]:
            with self.subTest(tail=tail):
                self.check('[apps.files]\n' + tail, expected)

    def test_invalid_modes_and_filters_are_gaps_without_auto_fallback(self):
        for tail in ['default_tools_approval_mode="future-private-mode"',
                     'default_tools_approval_mode=false', 'default_tools_approval_mode=[]',
                     'enabled_tools=[7]', 'disabled_tools="private-invalid"']:
            with self.subTest(tail=tail):
                self.check(MCP + tail, [], gap=True)
        self.check(MCP + 'tools=[]', ['mcp_servers.remote'], gap=True)
        self.check(MCP + 'default_tools_approval_mode="prompt"\n[mcp_servers.remote.tools.read]\napproval_mode=[]', [], gap=True)
        self.check('[apps._default]\ndefault_tools_approval_mode="private-invalid"\n[apps.files]', [], gap=True)
        self.check(MCP + 'default_tools_approval_mode="private-invalid"\n[mcp_servers.remote.tools.read]\napproval_mode="writes"',
                   ['mcp_servers.remote.tools.read'], gap=True)
