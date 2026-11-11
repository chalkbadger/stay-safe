from pathlib import Path
import unittest

from stay_safe.report import inspect, markdown
from tests.support import CHATGPT_APPS, ConfigCase, section

# Tool approval/default expectations are documented in ../../harnesses/codex.md,
# citing openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a.

FIXTURE = Path(__file__).with_name("known.toml")


class CatalogTests(ConfigCase):
    def test_standalone_tool_filters_keep_names_and_report_withheld_names(self):
        base = 'approval_policy="on-request"\nsandbox_mode="read-only"\n[mcp_servers.github]\nurl="https://example.com/mcp"\n'
        report = inspect([self.config(base + 'enabled_tools=["get_issue", "files/create"]\ndisabled_tools=["delete_repository"]')])
        self.assertEqual([(e["id"], e["observations"]) for e in report["catalog"] if e["kind"] == "tool filter"], [
            ("config-1:mcp_servers.github.disabled_tools", ["configured names: delete_repository"]),
            ("config-1:mcp_servers.github.enabled_tools", ["configured names: get_issue, files/create"]),
        ])
        self.assertEqual(report["inspection_gaps"], [])
        withheld = inspect([self.config(base + 'enabled_tools=["get_issue", "sk-fake-secret", "alice@example.com"]\ndisabled_tools=[]')])
        self.assertEqual([(e["name"], e["observations"]) for e in withheld["catalog"] if e["kind"] == "tool filter"], [
            ("mcp_servers.github.disabled_tools", ["no reportable configured names"]),
            ("mcp_servers.github.enabled_tools", ["configured names: get_issue", "some names withheld"]),
        ])
        self.assertEqual(withheld["inspection_gaps"], ["config-1: A tool allow/deny list contains a name that cannot be included in a shareable report."])
        self.assertNotIn("fake-secret", str(withheld))
        self.assertNotIn("alice@example.com", str(withheld))
        invalid = inspect([self.config(base + 'enabled_tools=[7]')])
        self.assertEqual(invalid["inspection_gaps"], ["config-1: A tool allow/deny list is invalid; tool availability is unknown."])

    def test_empty_catalog_does_not_claim_a_read_failure(self):
        text = markdown(inspect([self.config('model = "gpt-5"\nshell_environment_policy=[]\n[features]\napps=false\n')]))
        self.assertEqual(section(text, "Your setup"), "stay-safe found no settings to list.")
        self.assertEqual(section(text, "Not checked").count("**Not checked:"), 3)
        self.assertNotIn("Not checked: your config file.", text)
        populated = markdown(inspect([self.config('approval_policy="on-request"\n')]))
        self.assertIn("\n- Approval: `on-request` (Codex can ask before commands)\n", populated)
        self.assertIn("`sandbox_mode` isn't in your config file", populated)
        self.assertNotIn("found no settings to list", populated)

    def test_known_configuration_has_exact_named_catalog_and_risks(self):
        report = inspect([FIXTURE])
        catalog = [(e["name"], e["kind"], e["observations"]) for e in report["catalog"]]
        self.assertEqual(catalog, [
            ("approval_policy", "permission", ["never"]),
            ("apps._default", "app policy", ["disabled", "tool approval: auto (default)"]),
            ("apps.backup", "app policy", ["disabled", "tool approval: approve"]),
            ("apps.calendar", "app policy", ["configured enabled", "destructive tools disabled by destructive_enabled", "tool approval: writes"]),
            ("features.apps", "MCP server", CHATGPT_APPS),
            ("mcp_servers.git", "MCP server", ["configured enabled", "stdio; command withheld", "tool approval: prompt"]),
            ("mcp_servers.lookup", "MCP server", ["configured enabled", "HTTP; endpoint withheld", "tool approval: approve"]),
            ("mcp_servers.lookup.disabled_tools", "tool filter", ["configured names: delete"]),
            ("mcp_servers.lookup.enabled_tools", "tool filter", ["configured names: search, delete"]),
            ("mcp_servers.lookup.tools.delete", "tool policy", ["disabled or enablement unknown", "tool approval: approve"]),
            ("mcp_servers.lookup.tools.search", "tool policy", ["configured enabled", "tool approval: prompt"]),
            ("mcp_servers.mail", "MCP server", ["disabled", "HTTP; endpoint withheld", "tool approval: approve"]),
            ("model_providers.internal", "model provider", ["configured; endpoint and credentials withheld"]),
            ("notify", "automation", ["notification command configured; command withheld"]),
            ("sandbox_mode", "permission", ["workspace-write"]),
            ("sandbox_workspace_write.network_access", "permission", ["false", "workspace-write option"]),
            ("shell_environment_policy", "permission", ["inherit: all (default)", "ignore_default_excludes: true (default)"]),
            ("web_search", "connection policy", ["disabled"]),
        ])
        self.assertEqual([(r["rule"], r["entry"], r["incidents"]) for r in report["risks"]], [
            ("commands_without_prompts", "config-1:approval_policy", ["I2", "I3", "I24"]),
            ("self_described_tools", "config-1:apps.calendar", ["I15", "I21"]),
            ("configured_program", "config-1:mcp_servers.git", ["I13", "I14", "I19"]),
            ("configured_program", "config-1:notify", ["I13", "I14", "I19"]),
            ("environment_inheritance", "config-1:shell_environment_policy", ["I23"]),
        ])
        self.assertEqual(report["inspection_gaps"], [])
        self.assertEqual(report["file_inspection"], "complete for supported fields")
        self.assertIn("runtime overrides are not inspected", " ".join(report["scope"]))

    def test_files_remain_independent_and_identity_preserves_dotted_name(self):
        one = self.config('approval_policy="never"\nsandbox_mode="read-only"\n[mcp_servers."a.b"]\nurl="https://example.com"', "user.toml")
        two = self.config('approval_policy="on-request"\nsandbox_mode="workspace-write"', "project.toml")
        report = inspect([one, two])
        self.assertEqual([(e["id"], e["observations"]) for e in report["catalog"] if e["name"] == "approval_policy"],
                         [("config-1:approval_policy", ["never"]), ("config-2:approval_policy", ["on-request"])])
        self.assertIn('config-1:mcp_servers."a.b"', [e["id"] for e in report["catalog"]])

    def test_profiles_warn_that_reported_settings_can_be_overridden(self):
        for profile in (
            'profile="private-profile"',
            '[profiles.private-profile.shell_environment_policy]\ninherit="none"',
            'profile="private-profile"\n[profiles.private-profile.shell_environment_policy]\ninherit="none"',
            'profile=false',
            'profiles={}',
        ):
            with self.subTest(profile=profile):
                report = inspect([self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n' + profile)])
                self.assertEqual(report['inspection_gaps'], [
                    'config-1: Profiles are outside reader coverage; a selected profile can override the reported settings.',
                ])
                self.assertEqual(report['file_inspection'], 'incomplete')
                self.assertEqual([(r['rule'], r['entry']) for r in report['risks']],
                                 [('environment_inheritance', 'config-1:shell_environment_policy')])
                self.assertEqual(report['catalog'][-1]['observations'],
                                 ['inherit: all (default)', 'ignore_default_excludes: true (default)'])
                self.assertNotIn('private-profile', str(report))

    def test_never_is_not_sandbox_bypass(self):
        report = inspect([self.config('approval_policy="never"\nsandbox_mode="read-only"')])
        self.assertEqual([r["rule"] for r in report["risks"]], ["commands_without_prompts", "environment_inheritance"])
        self.assertIn("sandbox still applies", report["risks"][0]["explanation"])

    def test_disabled_tools_and_deny_over_allow_do_not_add_active_risks(self):
        path = self.config('''approval_policy="on-request"
sandbox_mode="read-only"
[apps._default]
enabled=false
default_tools_approval_mode="approve"
destructive_enabled=true
[apps.calendar]
enabled=true
default_tools_enabled=false
[apps.calendar.tools.lookup]
enabled=true
approval_mode="prompt"
[mcp_servers.search]
url="https://example.com"
enabled_tools=["delete"]
disabled_tools=["delete"]
[mcp_servers.search.tools.delete]
approval_mode="approve"
''')
        report = inspect([path])
        # The explicitly enabled tool can run even if destructive (archived issue #63).
        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]],
                         [("destructive_tools", "config-1:apps.calendar.tools.lookup"),
                          ("environment_inheritance", "config-1:shell_environment_policy")])
        self.assertEqual(report["inspection_gaps"], [])
        entries = {e["name"]: e for e in report["catalog"]}
        self.assertIn("default tools disabled or unknown", entries["apps.calendar"]["observations"])
        self.assertEqual(entries["apps.calendar.tools.lookup"]["observations"],
                         ["configured enabled", "enabled even if destructive", "tool approval: prompt"])
        self.assertEqual(entries["mcp_servers.search.tools.delete"]["observations"], ["disabled or enablement unknown", "tool approval: approve"])

    def test_unsupported_default_does_not_disable_app_tools(self):
        # The same with the template disabled: apps._default.enabled = false disables no named app (archived issue #90;
        # app_tool_policy.rs L174-L185 at 086ccc8), and Codex still reads the template's other settings for it
        # (L255-L270, L287-L301), so the template's unsupported field keeps its gap.
        for template in ("", "enabled=false\n"):
            with self.subTest(template=template):
                report = inspect([self.config('''approval_policy="on-request"
sandbox_mode="read-only"
[apps._default]
''' + template + '''default_tools_enabled=false
[apps.files]
default_tools_approval_mode="approve"
''')])
                self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]], [("automatic_tools", "config-1:apps.files"),
                                 ("destructive_tools", "config-1:apps.files"),
                                 ("environment_inheritance", "config-1:shell_environment_policy")])
                self.assertEqual(report["inspection_gaps"], ["config-1: apps._default contains fields outside reader coverage; their values were withheld."])

    def test_closed_tool_allowlists_remove_superseded_default_approval_risks(self):
        report = inspect([self.config('''approval_policy="on-request"
sandbox_mode="read-only"
[mcp_servers.denied]
url="https://example.com"
default_tools_approval_mode="approve"
enabled_tools=["delete"]
disabled_tools=["delete"]
[mcp_servers.overridden]
url="https://example.com"
default_tools_approval_mode="approve"
enabled_tools=["search"]
[mcp_servers.overridden.tools.search]
approval_mode="prompt"
[mcp_servers.remaining]
url="https://example.com"
default_tools_approval_mode="approve"
enabled_tools=["read", "write"]
[mcp_servers.remaining.tools.read]
approval_mode="prompt"
[mcp_servers.open]
url="https://example.com"
default_tools_approval_mode="approve"
[mcp_servers.open.tools.read]
approval_mode="prompt"
''')])
        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]], [
            ("automatic_tools", "config-1:mcp_servers.open"),
            ("automatic_tools", "config-1:mcp_servers.remaining"),
            ("environment_inheritance", "config-1:shell_environment_policy"),
        ])
        self.assertEqual(report["inspection_gaps"], [])

    def test_mcp_tool_enabled_is_not_an_app_style_disable(self):
        report = inspect([self.config('''approval_policy="on-request"
sandbox_mode="read-only"
[mcp_servers.a]
url="https://example.com"
[mcp_servers.a.tools.write]
enabled=false
approval_mode="approve"
''')])
        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]], [
            ("self_described_tools", "config-1:mcp_servers.a"),
            ("automatic_tools", "config-1:mcp_servers.a.tools.write"),
            ("environment_inheritance", "config-1:shell_environment_policy"),
        ])
        self.assertEqual(report["inspection_gaps"], ["config-1: tools contains fields outside reader coverage; their values were withheld."])

    def test_named_permissions_do_not_use_legacy_sandbox_as_effective_policy(self):
        path = self.config('approval_policy="on-request"\nsandbox_mode="danger-full-access"\ndefault_permissions=":read-only"')
        report = inspect([path])
        self.assertEqual([r["rule"] for r in report["risks"]], ["environment_inheritance"])
        self.assertIn("Named permission profiles are outside reader coverage", " ".join(report["inspection_gaps"]))
        self.assertIn("default_permissions and sandbox_mode conflict", " ".join(report["inspection_gaps"]))
        definitions = inspect([self.config('approval_policy="on-request"\nsandbox_mode="danger-full-access"\n[permissions.example]\nextends=":read-only"')])
        self.assertEqual([r["rule"] for r in definitions["risks"]], ["unrestricted_filesystem", "environment_inheritance"])

    def test_preapproved_tools_are_distinct_from_auto_and_keep_slash_names(self):
        path = self.config('''approval_policy="on-request"
sandbox_mode="read-only"
[mcp_servers.a]
url="https://example.com"
default_tools_approval_mode="auto"
[mcp_servers.b]
url="https://example.com"
default_tools_approval_mode="approve"
[apps.files]
default_tools_approval_mode="auto"
[apps.files.tools."files/delete"]
approval_mode="approve"
[apps.files.tools."repos/list"]
approval_mode="prompt"
''')
        report = inspect([path])
        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]], [
            ("destructive_tools", "config-1:apps.files"),
            ("self_described_tools", "config-1:apps.files"),
            ("automatic_tools", 'config-1:apps.files.tools."files/delete"'),
            ("self_described_tools", "config-1:mcp_servers.a"),
            ("automatic_tools", "config-1:mcp_servers.b"),
            ("environment_inheritance", "config-1:shell_environment_policy"),
        ])
        self.assertEqual(report["inspection_gaps"], [])
        self.assertIn('apps.files.tools."repos/list"', [e["name"] for e in report["catalog"]])

    def test_incomplete_unknown_and_malformed_inputs_are_reported(self):
        empty = inspect([self.config("")])
        self.assertEqual(empty["file_inspection"], "incomplete")
        self.assertEqual(empty["inspection_gaps"], [
            "config-1: approval_policy is absent; the reader does not infer its effective value.",
            "config-1: sandbox_mode is absent; the reader does not infer its effective value.",
        ])
        self.assertEqual([(e["name"], e["observations"]) for e in empty["catalog"]], [
            ("features.apps", CHATGPT_APPS),
            ("shell_environment_policy", ["inherit: all (default)", "ignore_default_excludes: true (default)"]),
        ])
        unknown = inspect([self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n[future_policy]\nvalue="hidden"')])
        self.assertEqual(unknown["inspection_gaps"], ["config-1: Configuration contains fields outside reader coverage; their values were withheld."])
        self.assertEqual([(e["name"], e["observations"]) for e in unknown["catalog"]], [
            ("approval_policy", ["on-request"]),
            ("features.apps", CHATGPT_APPS),
            ("sandbox_mode", ["read-only"]),
            ("shell_environment_policy", ["inherit: all (default)", "ignore_default_excludes: true (default)"]),
        ])
        self.assertEqual([r["rule"] for r in unknown["risks"]], ["environment_inheritance"])
        in_server = inspect([self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n[mcp_servers.remote]\nurl="https://example.com"\nfuture_field=1')])
        self.assertEqual(in_server["inspection_gaps"], ["config-1: mcp_servers contains fields outside reader coverage; their values were withheld."])
        self.assertEqual([(e["name"], e["observations"]) for e in in_server["catalog"]], [
            ("approval_policy", ["on-request"]),
            ("features.apps", CHATGPT_APPS),
            ("mcp_servers.remote", ["configured enabled", "HTTP; endpoint withheld", "tool approval: auto (default)"]),
            ("sandbox_mode", ["read-only"]),
            ("shell_environment_policy", ["inherit: all (default)", "ignore_default_excludes: true (default)"]),
        ])
        self.assertEqual([(r["rule"], r["entry"]) for r in in_server["risks"]], [
            ("self_described_tools", "config-1:mcp_servers.remote"),
            ("environment_inheritance", "config-1:shell_environment_policy"),
        ])
        malformed = inspect([self.config('approval_policy="never"\nsandbox_mode=["secret"]\n[mcp_servers.a]\ncommand="echo"\nurl="https://example.com"\nhttp_headers_helper=true')])
        self.assertEqual([r["rule"] for r in malformed["risks"]], ["commands_without_prompts", "environment_inheritance"])
        self.assertEqual(malformed["inspection_gaps"], [
            "config-1: An MCP header-helper command is invalid; its value was withheld.",
            "config-1: An MCP transport is missing, conflicting or invalid.",
            "config-1: sandbox_mode is unsupported or invalid; its value was withheld.",
        ])
        self.assertEqual([(e["name"], e["observations"]) for e in malformed["catalog"]], [
            ("approval_policy", ["never"]),
            ("features.apps", CHATGPT_APPS),
            ("mcp_servers.a", ["configured enabled", "transport unknown", "tool approval: auto (default)"]),
            ("shell_environment_policy", ["inherit: all (default)", "ignore_default_excludes: true (default)"]),
        ])
        # Codex reads `connectors` as a legacy alias for `apps`, so this file may turn the connection back on:
        # openai/codex@086ccc8 codex-rs/features/src/legacy.rs L11-L15, L58-L66.
        alias = inspect([self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n[features]\napps=false\nconnectors=true\n')])
        self.assertEqual(alias["inspection_gaps"], ["config-1: features contains fields outside reader coverage; their values were withheld."])
        self.assertNotIn("features.apps", [e["name"] for e in alias["catalog"]])
        not_table = inspect([self.config('approval_policy="on-request"\nsandbox_mode="read-only"\nfeatures=true\n')])
        self.assertEqual(not_table["inspection_gaps"], ["config-1: features must be a table."])

    def test_any_string_url_without_command_is_http_and_withheld(self):
        # Codex chooses HTTP for any string `url` without `command` and checks no URL form there:
        # openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a codex-rs/config/src/mcp_types.rs#L407, #L512-L566.
        for url in ("https://mcp_server.internal/mcp", "localhost:8080/mcp", "https://?private-host-marker",
                    "https://example.com:70000", "https://[invalid", "https://999.1.1.1", "https://alice:fake-secret@/private",
                    "http://[::1]:3000/mcp", "https://example.com/m cp", ""):
            with self.subTest(url=url):
                report = inspect([self.config(f'approval_policy="on-request"\nsandbox_mode="read-only"\n'
                                              f'[mcp_servers.remote]\nurl="{url}"\ndefault_tools_approval_mode="approve"\n')])
                self.assertEqual(report["inspection_gaps"], [])
                self.assertEqual([e["observations"] for e in report["catalog"] if e["name"] == "mcp_servers.remote"],
                                 [["configured enabled", "HTTP; endpoint withheld", "tool approval: approve"]])
                self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]], [
                    ("automatic_tools", "config-1:mcp_servers.remote"),
                    ("environment_inheritance", "config-1:shell_environment_policy"),
                ])
                if url:
                    self.assertNotIn(url, str(report))


if __name__ == "__main__":
    unittest.main()
