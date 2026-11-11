from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase

# Approval expectations: ../../harnesses/codex.md, documented in source at
# openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a.


BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
DEFAULTS = ['inherit: all (default)', 'ignore_default_excludes: true (default)']
BASE_CATALOG = {'approval_policy': ['on-request'], 'sandbox_mode': ['read-only'], 'shell_environment_policy': DEFAULTS,
                'features.apps': CHATGPT_APPS}
HOOK_POLICY = 'config-1: Hook execution policy is outside reader coverage.'
TEMPLATE_OFF = '[apps._default]\nenabled=false\ndefault_tools_approval_mode="approve"\ndestructive_enabled=true\n'
PROFILE_GAPS = ['config-1: Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.',
                'config-1: default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.']


class ConfiguredConditionTests(ConfigCase):
    def report(self, text):
        return inspect([self.config(text)])

    def assert_risks(self, text, expected):
        report = self.report(text)
        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]],
                         [(rule, "config-1:" + entry) for rule, entry in expected]
                         + [("environment_inheritance", "config-1:shell_environment_policy")])
        return report

    def assert_silent(self, text, catalog, gaps):
        """A negative case shows its whole result, so a configuration rejected for another reason fails."""
        report = self.assert_risks(text, [])
        self.assertEqual({e['name']: e['observations'] for e in report['catalog']}, {**BASE_CATALOG, **catalog})
        self.assertEqual(report['inspection_gaps'], gaps)
        return report

    def test_command_prompt_and_filesystem_rules_have_independent_positive_and_negative_cases(self):
        for approval, mode, expected in [
            ("never", "read-only", [("commands_without_prompts", "approval_policy")]),
            ("on-request", "danger-full-access", [("unrestricted_filesystem", "sandbox_mode")]),
        ]:
            with self.subTest(approval=approval, mode=mode):
                self.assert_risks(f'approval_policy="{approval}"\nsandbox_mode="{mode}"', expected)
        for mode in ("read-only", "workspace-write"):
            with self.subTest(approval="on-request", mode=mode):
                self.assert_silent(f'approval_policy="on-request"\nsandbox_mode="{mode}"', {'sandbox_mode': [mode]}, [])
        self.assert_silent('approval_policy="on-request"\nsandbox_mode="danger-full-access"\ndefault_permissions=":read-only"', {
            'sandbox_mode': ['danger-full-access', 'permission-profile selection is uninspected'],
        }, PROFILE_GAPS)

    def test_program_rule_requires_a_configured_enabled_command(self):
        for tail, expected in [
            ('[mcp_servers.local]\ncommand="synthetic-command"', [("configured_program", "mcp_servers.local"), ("self_described_tools", "mcp_servers.local")]),
            ('[mcp_servers.local]\nurl="https://example.com"', [("self_described_tools", "mcp_servers.local")]),
            ('[mcp_servers.local]\nurl="https://example.com"\nhttp_headers_helper="synthetic-helper"', [("configured_program", "mcp_servers.local"), ("self_described_tools", "mcp_servers.local")]),
            ('notify=["synthetic-command"]', [("configured_program", "notify")]),
            ('[hooks]\nSessionStart=[{hooks=[{type="command", command="synthetic-command fake-secret"}]}]', [("configured_program", "hooks.SessionStart")]),
        ]:
            with self.subTest(tail=tail):
                result = self.assert_risks(BASE + tail, expected)
                self.assertNotIn("fake-secret", str(result))
        for tail, catalog, gaps in [
            ('[mcp_servers.local]\ncommand="synthetic-command"\nenabled=false',
             {'mcp_servers.local': ['disabled', 'stdio; command withheld', 'tool approval: auto (default)']}, []),
            ('[mcp_servers.local]\ncommand=""',
             {'mcp_servers.local': ['configured enabled', 'transport unknown', 'tool approval: auto (default)']},
             ['config-1: An MCP transport is missing, conflicting or invalid.']),
            ('notify=[]', {}, ['config-1: notify is not a command list with a nonempty program.']),
            ('[hooks]\nSessionStart=[]', {'hooks.SessionStart': ['contents withheld']}, [HOOK_POLICY]),
        ]:
            with self.subTest(tail=tail):
                self.assert_silent(BASE + tail, catalog, gaps)

    def test_preapproved_and_destructive_tools_stop_when_disabled_not_when_only_apps_default_is_off(self):
        for approval in ("approve", "auto", "prompt", "writes"):
            for enabled in (True, False):
                with self.subTest(approval=approval, enabled=enabled):
                    tail = f'[mcp_servers.remote]\nurl="https://example.com"\nenabled={str(enabled).lower()}\ndefault_tools_approval_mode="{approval}"'
                    expected = {"approve": [("automatic_tools", "mcp_servers.remote")],
                                "auto": [("self_described_tools", "mcp_servers.remote")],
                                "writes": [("self_described_tools", "mcp_servers.remote")], "prompt": []}[approval] if enabled else []
                    if expected:
                        self.assert_risks(BASE + tail, expected)
                    else:
                        self.assert_silent(BASE + tail, {'mcp_servers.remote': [
                            'configured enabled' if enabled else 'disabled', 'HTTP; endpoint withheld', f'tool approval: {approval}']}, [])
        for tail, expected in [
            ('[apps.files]\ndefault_tools_approval_mode="approve"', [("automatic_tools", "apps.files"), ("destructive_tools", "apps.files")]),
            # apps._default.enabled disables no named app (archived issue #90): a named app's `enabled` defaults to true and
            # is read before the template (openai/codex@086ccc8, rust-v0.167.0, codex-rs/config/src/types.rs
            # L537-L540, codex-rs/connectors/src/app_tool_policy.rs L174-L185), as the recorded Codex 0.167.0 run
            # shows (https://github.com/chalkbadger/stay-safe-archive/issues/90#issuecomment-6726050010, cases A and C).
            # The app still inherits the template's approval mode (app_tool_policy.rs L255-L270 at 086ccc8).
            (TEMPLATE_OFF + '[apps.files]', [("automatic_tools", "apps.files"), ("destructive_tools", "apps.files")]),
        ]:
            with self.subTest(tail=tail):
                self.assert_risks(BASE + tail, expected)
        template_off = ['disabled', 'tool approval: approve']
        for tail, catalog in [
            ('[apps.files]\nenabled=false\ndefault_tools_approval_mode="approve"\ndestructive_enabled=true',
             {'apps.files': ['disabled', 'tool approval: approve']}),
            # The app's own enabled = false stops the risks it would inherit (run case B).
            (TEMPLATE_OFF + '[apps.files]\nenabled=false',
             {'apps._default': template_off, 'apps.files': template_off}),
            ('[apps.files]\ndefault_tools_enabled=false\ndefault_tools_approval_mode="approve"\ndestructive_enabled=true',
             {'apps.files': ['configured enabled', 'default tools disabled or unknown', 'tool approval: approve']}),
            ('[mcp_servers.remote]\nurl="https://example.com"\ndefault_tools_approval_mode="approve"\nenabled_tools=["write"]\ndisabled_tools=["write"]',
             {'mcp_servers.remote': ['configured enabled', 'HTTP; endpoint withheld', 'tool approval: approve'],
              'mcp_servers.remote.disabled_tools': ['configured names: write'],
              'mcp_servers.remote.enabled_tools': ['configured names: write']}),
        ]:
            with self.subTest(tail=tail):
                self.assert_silent(BASE + tail, catalog, [])

    def test_preapproved_mcp_tool_stops_when_its_server_or_lists_make_it_unavailable(self):
        # harnesses/codex.md rows mcp_servers.*.enabled `false`, mcp_servers.*.enabled_tools and
        # mcp_servers.*.tools.*.approval_mode `approve`; Codex 086ccc8 codex-rs/codex-mcp/src/tools.rs
        # L63-L95 (an allowlist, even empty, permits only its names) and codex-rs/config/src/mcp_types.rs
        # L243-L245 (a disabled server is not started), L292-L297 (each list is a list of strings).
        tool = '\n[mcp_servers.remote.tools.read]\napproval_mode="approve"'
        for setting, gaps in [
            ('enabled_tools=["read", 7]', ['config-1: A tool allow/deny list is invalid; tool availability is unknown.']),
            ('enabled=false', []),
            ('enabled_tools=[]', []),
        ]:
            with self.subTest(setting=setting):
                report = self.assert_risks(BASE + '[mcp_servers.remote]\nurl="https://example.com"\n' + setting + tool, [])
                self.assertEqual(report['inspection_gaps'], gaps)

    def test_network_rule_requires_active_workspace_options(self):
        for mode, enabled, selected, expected in [
            ("workspace-write", True, False, [("network_access", "sandbox_workspace_write.network_access")]),
            ("workspace-write", False, False, []),
            ("read-only", True, False, []),
            ("workspace-write", True, True, []),
        ]:
            with self.subTest(mode=mode, enabled=enabled, selected=selected):
                text = f'approval_policy="on-request"\nsandbox_mode="{mode}"\n'
                if selected:
                    text += 'default_permissions=":read-only"\n'
                text += f'[sandbox_workspace_write]\nnetwork_access={str(enabled).lower()}'
                label = "workspace-write option" if mode == "workspace-write" and not selected else "inactive or selection unknown"
                catalog = {
                    'sandbox_mode': [mode, 'permission-profile selection is uninspected'] if selected else [mode],
                    'sandbox_workspace_write.network_access': [str(enabled).lower(), label],
                }
                if expected:
                    report = self.assert_risks(text, expected)
                    self.assertEqual({e['name']: e['observations'] for e in report['catalog']}, {**BASE_CATALOG, **catalog})
                else:
                    self.assert_silent(text, catalog, PROFILE_GAPS if selected else [])

    def test_unknown_web_search_is_a_gap_and_never_a_supported_mode(self):
        for mode in ("disabled", "cached", "indexed", "live"):
            report = self.assert_risks(BASE + f'web_search="{mode}"', [])
            self.assertEqual(report["inspection_gaps"], [])
            self.assertEqual([e["observations"] for e in report["catalog"] if e["name"] == "web_search"], [[mode]])
        report = self.assert_risks(BASE + 'web_search="fake-secret-future-mode"', [])
        self.assertEqual(report["inspection_gaps"], ["config-1: web_search is unsupported or invalid; its value was withheld."])
        self.assertNotIn("web_search", [e["name"] for e in report["catalog"]])
        self.assertNotIn("fake-secret", str(report))
