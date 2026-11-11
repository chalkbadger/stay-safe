import unittest

from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase

# Each case is a file without the bad setting and the same file with it (archived issue #61).
# Expected results are written from the harnesses/codex.md rows, not from the reader:
# `approval_policy` `on-request`, `sandbox_mode` `read-only`, `shell_environment_policy` `omitted`, `features.apps` `omitted`,
# and the MCP, app and model-provider rows each case names.
TOP = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
BASELINE = {"approval_policy": ["on-request"], "sandbox_mode": ["read-only"], "features.apps": CHATGPT_APPS,
            "shell_environment_policy": ["inherit: all (default)", "ignore_default_excludes: true (default)"]}
BASELINE_RISKS = [("environment_inheritance", "shell_environment_policy")]
HTTP_APPROVE = ["configured enabled", "HTTP; endpoint withheld", "tool approval: approve"]
# `apps.*.default_tools_approval_mode` and `apps.*.destructive_enabled` `omitted` rows.
APP_APPROVE = ["configured enabled", "destructive tools enabled by Codex default", "tool approval: approve"]
APP_APPROVE_RISKS = [("automatic_tools", "apps.drive"), ("destructive_tools", "apps.drive")]
NOT_A_TABLE = "{} contains an entry that is not a table."
OUTSIDE = "apps contains fields outside reader coverage; their values were withheld."


class MalformedTableTests(ConfigCase):
    maxDiff = None

    def inspect(self, text):
        result = inspect([self.config(TOP + text)])
        return ({e["name"]: e["observations"] for e in result["catalog"]},
                sorted((r["rule"], r["entry"].removeprefix("config-1:")) for r in result["risks"]),
                result["inspection_gaps"])

    def assert_report(self, text, entries, risks, gaps):
        self.assertEqual(self.inspect(text), ({**BASELINE, **entries}, sorted(BASELINE_RISKS + risks),
                                              [f"config-1: {gap}" for gap in gaps]))

    def assert_pair(self, without, bad, entries, risks, gaps):
        """The file without the bad setting gives `entries` and `risks`; with it, the same plus `gaps`."""
        self.assert_report(without, entries, risks, [])
        self.assert_report(bad, entries, risks, gaps)

    def test_a_value_that_must_be_a_table_is_a_gap_and_otherwise_absent(self):
        server = '[mcp_servers.target]\nurl="https://example.com"\ndefault_tools_approval_mode="approve"\n'
        cases = {
            # The After's example: meant as [apps.files] enabled = false.
            "app": ('[apps.drive]\ndefault_tools_approval_mode="approve"\n',
                    '[apps]\nfiles=false\n[apps.drive]\ndefault_tools_approval_mode="approve"\n',
                    {"apps.drive": APP_APPROVE}, APP_APPROVE_RISKS, [NOT_A_TABLE.format("apps")]),
            "MCP server": (server, '[mcp_servers]\nother="https://example.com"\n' + server,
                           {"mcp_servers.target": HTTP_APPROVE}, [("automatic_tools", "mcp_servers.target")],
                           [NOT_A_TABLE.format("mcp_servers")]),
            # "auth-command" would match a substring test for the provider's `auth` field.
            "model provider": ('[model_providers.internal]\nbase_url="https://example.com"\n',
                               '[model_providers]\nother="auth-command"\n[model_providers.internal]\nbase_url="https://example.com"\n',
                               {"model_providers.internal": ["configured; endpoint and credentials withheld"]}, [],
                               [NOT_A_TABLE.format("model_providers")]),
            # Only `search` is allowed; read as absent, it inherits the server's approve mode.
            "tool": (server + 'enabled_tools=["search"]\n',
                     server + 'enabled_tools=["search"]\ntools={search=5}\n',
                     {"mcp_servers.target": HTTP_APPROVE, "mcp_servers.target.enabled_tools": ["configured names: search"]},
                     [("automatic_tools", "mcp_servers.target")], [NOT_A_TABLE.format("tools")]),
            # With default_tools_enabled = false, read as absent, `read` adds no tool entry or risk.
            "app tool": ('[apps.drive]\ndefault_tools_enabled=false\ndefault_tools_approval_mode="approve"\n',
                         '[apps.drive]\ndefault_tools_enabled=false\ndefault_tools_approval_mode="approve"\ntools={read="prompt"}\n',
                         {"apps.drive": ["configured enabled", "default tools disabled or unknown", "tool approval: approve"]},
                         [], [NOT_A_TABLE.format("tools")]),
            "MCP tools block": (server, server + 'tools=["read"]\n',
                                {"mcp_servers.target": HTTP_APPROVE}, [("automatic_tools", "mcp_servers.target")],
                                ["tools must be a table."]),
            "app tools block": ('[apps.drive]\ndefault_tools_approval_mode="approve"\n',
                                '[apps.drive]\ndefault_tools_approval_mode="approve"\ntools=["read"]\n',
                                {"apps.drive": APP_APPROVE}, APP_APPROVE_RISKS, ["tools must be a table."]),
        }
        for name, case in cases.items():
            with self.subTest(name):
                self.assert_pair(*case)

    def test_a_template_that_is_not_a_table_leaves_inherited_app_settings_unknown(self):
        # Each case: the file without `_default = false` and its expected report, then the expected
        # report with it. Codex's defaults apply only where the template is absent, not malformed.
        codex_defaults = ["configured enabled", "destructive tools enabled by Codex default", "tool approval: auto (default)"]
        default_risks = [("destructive_tools", "apps.drive"), ("self_described_tools", "apps.drive")]
        own = ('[apps.drive]\nenabled=true\ndefault_tools_approval_mode="approve"\ndestructive_enabled=true\n'
               '[apps.drive.tools.read]\napproval_mode="prompt"\n')
        own_entries = {"apps.drive": ["configured enabled", "destructive tools enabled by destructive_enabled", "tool approval: approve"],
                       "apps.drive.tools.read": ["configured enabled", "tool approval: prompt"]}
        own_risks = [("automatic_tools", "apps.drive"), ("destructive_tools", "apps.drive")]
        cases = {
            # Codex rejects this file; stay-safe's rule for invalid input applies (contracts/claims.md [see_every_connection_and_setting]):
            # the template gives a gap and the app's own settings are reported as usual. A named app's enablement
            # never comes from the template (archived issue #90), so it is enabled. The approval mode and destructive_enabled
            # left to the template are unknown, so no risk.
            "sets nothing": ('[apps.drive]\n', {"apps.drive": codex_defaults}, default_risks,
                             {"apps.drive": ["configured enabled"]}, []),
            # The approval mode and destructive_enabled left to the template are unknown, for the app
            # and for its tool that inherits the mode.
            "sets enabled": ('[apps.drive]\nenabled=true\n[apps.drive.tools.read]\n',
                             {"apps.drive": codex_defaults, "apps.drive.tools.read": ["configured enabled", "tool approval: auto"]},
                             default_risks,
                             {"apps.drive": ["configured enabled"], "apps.drive.tools.read": ["configured enabled"]}, []),
            # Settings the app and its tool set themselves are reported as usual.
            "sets everything": (own, own_entries, own_risks, own_entries, own_risks),
            # default_tools_enabled is the app's own and comes before destructive_enabled in Codex's order.
            "sets default_tools_enabled": ('[apps.drive]\nenabled=true\ndefault_tools_enabled=true\n',
                                           {"apps.drive": ["configured enabled", "destructive tools enabled by default_tools_enabled",
                                                           "tool approval: auto (default)"]}, default_risks,
                                           {"apps.drive": ["configured enabled", "destructive tools enabled by default_tools_enabled"]},
                                           [("destructive_tools", "apps.drive")]),
        }
        for name, (without, entries, risks, bad_entries, bad_risks) in cases.items():
            with self.subTest(name):
                self.assert_report(without, entries, risks, [])
                self.assert_report('[apps]\n_default=false\n' + without, bad_entries, bad_risks,
                                   ["apps._default must be a table."])

    def test_app_tool_lists_are_a_gap_and_change_nothing_else(self):
        approve = '[apps.drive]\ndefault_tools_approval_mode="approve"\n'
        tool = '[apps.drive]\ndefault_tools_approval_mode="prompt"\n{}[apps.drive.tools.delete]\napproval_mode="approve"\n'
        tool_entries = {"apps.drive": ["configured enabled", "destructive tools enabled by Codex default", "tool approval: prompt"],
                        "apps.drive.tools.delete": ["configured enabled", "tool approval: approve"]}
        tool_risks = [("destructive_tools", "apps.drive"), ("automatic_tools", "apps.drive.tools.delete")]
        cases = {
            # The After's example: enabled_tools = [] does not block Drive's tools.
            "empty enabled_tools": (approve, approve + 'enabled_tools=[]\n', {"apps.drive": APP_APPROVE}, APP_APPROVE_RISKS),
            "invalid enabled_tools": (approve, approve + 'enabled_tools="read"\n', {"apps.drive": APP_APPROVE}, APP_APPROVE_RISKS),
            # disabled_tools does not hide a tool's own risk.
            "disabled_tools": (tool.format(""), tool.format('disabled_tools=["delete"]\n'), tool_entries, tool_risks),
        }
        for name, (without, bad, entries, risks) in cases.items():
            with self.subTest(name):
                self.assert_pair(without, bad, entries, risks, [OUTSIDE])

if __name__ == "__main__":
    unittest.main()
