import unittest

from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase

TOP = {"approval_policy": '"on-request"', "sandbox_mode": '"read-only"'}
ANCHOR = '[mcp_servers.anchor]\ncommand="synthetic-command"\n'
BASELINE = {"approval_policy": ["on-request"], "sandbox_mode": ["read-only"],
            "mcp_servers.anchor": ["configured enabled", "stdio; command withheld", "tool approval: auto (default)"],
            "shell_environment_policy": ["inherit: all (default)", "ignore_default_excludes: true (default)"],
            "features.apps": CHATGPT_APPS}
BASELINE_RISKS = [("configured_program", "mcp_servers.anchor"), ("self_described_tools", "mcp_servers.anchor"),
                  ("environment_inheritance", "shell_environment_policy")]
BOOLEAN_GAP = "{} has an invalid boolean; its behavior is unknown."
HOOKS_GAP = "Hook execution policy is outside reader coverage."
APP = '[apps.cal]\nenabled=true\n'
LOAD_ERROR = "Codex cannot load this configuration file"
TARGET_HTTP = ["configured enabled", "HTTP; endpoint withheld", "tool approval: auto (default)"]

CASES = {
    "approval_policy": ({"approval_policy": '"yes"'}, "",
                        ["approval_policy is unsupported or invalid; its value was withheld."],
                        {"approval_policy": None}, []),
    "sandbox_mode": ({"sandbox_mode": '"yes"'}, "",
                     ["sandbox_mode is unsupported or invalid; its value was withheld."], {"sandbox_mode": None}, []),
    "sandbox_workspace_write.network_access": ({"sandbox_mode": '"workspace-write"'}, '[sandbox_workspace_write]\nnetwork_access="yes"\n',
                                               [BOOLEAN_GAP.format("sandbox_workspace_write")],
                                               {"sandbox_mode": ["workspace-write"], "sandbox_workspace_write.network_access": None}, []),
    "shell_environment_policy.inherit": ({}, '[shell_environment_policy]\ninherit="yes"\n',
                                         ["shell_environment_policy.inherit is unsupported or invalid; its value was withheld."],
                                         {"shell_environment_policy": None}, []),
    "shell_environment_policy.ignore_default_excludes": ({}, '[shell_environment_policy]\nignore_default_excludes="yes"\n',
                                                         ["shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown."],
                                                         {"shell_environment_policy": None}, []),
    "mcp_servers.*.enabled": ({}, '[mcp_servers.target]\nenabled="yes"\ncommand="synthetic-command"\ndefault_tools_approval_mode="approve"\n',
                              [BOOLEAN_GAP.format("mcp_servers")], {"mcp_servers.target": ["enablement unknown", "stdio; command withheld", "tool approval: approve"]}, []),
    "mcp_servers.*.command": ({}, '[mcp_servers.target]\ncommand=["synthetic-command"]\n',
                              ["An MCP transport is missing, conflicting or invalid."], {"mcp_servers.target": ["configured enabled", "transport unknown", "tool approval: auto (default)"]}, []),
    "mcp_servers.*.url": ({}, '[mcp_servers.target]\nurl=["https://example.com"]\n',
                          ["An MCP transport is missing, conflicting or invalid."], {"mcp_servers.target": ["configured enabled", "transport unknown", "tool approval: auto (default)"]}, []),
    "mcp_servers.*.http_headers_helper": ({}, '[mcp_servers.target]\nurl="https://example.com"\nhttp_headers_helper=["synthetic-command"]\n',
                                          ["An MCP header-helper command is invalid; its value was withheld."], {"mcp_servers.target": TARGET_HTTP},
                                          [("self_described_tools", "mcp_servers.target")]),
    "mcp_servers.*.enabled_tools": ({}, '[mcp_servers.target]\nurl="https://example.com"\nenabled_tools="search"\n',
                                    ["A tool allow/deny list is invalid; tool availability is unknown."],
                                    {"mcp_servers.target": TARGET_HTTP, "mcp_servers.target.enabled_tools": None}, []),
    "mcp_servers.*.default_tools_approval_mode": ({}, '[mcp_servers.target]\nurl="https://example.com"\ndefault_tools_approval_mode="yes"\n',
                                                  ["A tool approval mode is unsupported or invalid; its value was withheld."], {"mcp_servers.target": ["configured enabled", "HTTP; endpoint withheld"]}, []),
    "mcp_servers.*.tools.*.approval_mode": ({}, '[mcp_servers.target]\nurl="https://example.com"\n[mcp_servers.target.tools.search]\napproval_mode="yes"\n',
                                            ["A per-tool approval mode is unsupported or invalid; its value was withheld."],
                                            {"mcp_servers.target": TARGET_HTTP, "mcp_servers.target.tools.search": ["configured enabled"]},
                                            [("self_described_tools", "mcp_servers.target")]),
    "apps._default.enabled": ({}, '[apps._default]\nenabled="yes"\n[apps.cal]\ndefault_tools_approval_mode="approve"\n',
                              [BOOLEAN_GAP.format("apps")],
                              {"apps._default": ["enablement unknown", "tool approval: auto (default)"],
                               "features.apps": CHATGPT_APPS[:3] + ["apps not named in this file: settings unknown"],
                               "apps.cal": ["configured enabled", "destructive tools enabled by Codex default", "tool approval: approve"]},
                              [("automatic_tools", "apps.cal"), ("destructive_tools", "apps.cal")]),
    "apps.*.enabled": ({}, '[apps.cal]\nenabled="yes"\ndefault_tools_approval_mode="approve"\n',
                       [BOOLEAN_GAP.format("apps")], {"apps.cal": ["enablement unknown", "tool approval: approve"]}, []),
    "apps.*.default_tools_enabled": ({}, APP + 'default_tools_enabled="yes"\ndefault_tools_approval_mode="approve"\n',
                                     ["Codex cannot load this configuration file because apps.cal.default_tools_enabled is not a boolean."], {"apps.cal": [LOAD_ERROR, "default tools disabled or unknown", "tool approval: approve"]}, []),
    "apps.*.destructive_enabled": ({}, APP + 'destructive_enabled="yes"\n', ["Codex cannot load this configuration file because apps.cal.destructive_enabled is not a boolean."],
                                   {"apps.cal": ["Codex cannot load this configuration file", "tool approval: auto (default)"]}, []),
    "apps.*.destructive_enabled under apps._default.enabled = false": ({}, '[apps._default]\nenabled=false\n[apps.cal]\ndestructive_enabled="yes"\n',
                                                                     ["Codex cannot load this configuration file because apps.cal.destructive_enabled is not a boolean."],
                                                                     {"apps._default": ["disabled", "tool approval: auto (default)"], "features.apps": CHATGPT_APPS[:3] + ["apps not named in this file: disabled by apps._default.enabled"], 
                                                                      "apps.cal": ["Codex cannot load this configuration file", "tool approval: auto (default)"]}, []),
    "apps._default.destructive_enabled under apps._default.enabled = false": ({}, '[apps._default]\nenabled=false\ndestructive_enabled="yes"\n',
                                                                             ["Codex cannot load this configuration file because apps._default.destructive_enabled is not a boolean."],
                                                                             {"apps._default": ["disabled", "tool approval: auto (default)"],
                                                                              "features.apps": CHATGPT_APPS[:3] + ["apps not named in this file: disabled by apps._default.enabled"]}, []),
    "apps.*.default_tools_approval_mode": ({}, APP + 'default_tools_approval_mode="yes"\n',
                                           ["Codex cannot load this configuration file because apps.cal.default_tools_approval_mode is not one of auto, prompt, writes, approve."],
                                           {"apps.cal": [LOAD_ERROR]}, []),
    "apps.*.tools.*.enabled": ({}, APP + '[apps.cal.tools.delete]\nenabled="yes"\napproval_mode="approve"\n',
                               ["Codex cannot load this configuration file because apps.cal.tools.delete.enabled is not a boolean."], {"apps.cal": [LOAD_ERROR, "tool approval: auto (default)"], "apps.cal.tools.delete": [LOAD_ERROR, "tool approval: approve"]}, []),
    "apps.*.tools.*.enabled under unknown app enablement": ({}, '[apps.cal]\nenabled="yes"\n[apps.cal.tools.delete]\nenabled="yes"\napproval_mode="approve"\n',
                                                         [BOOLEAN_GAP.format("apps"), "Codex cannot load this configuration file because apps.cal.tools.delete.enabled is not a boolean."],
                                                         {"apps.cal": [LOAD_ERROR, "tool approval: auto (default)"],
                                                          "apps.cal.tools.delete": [LOAD_ERROR, "tool approval: approve"]}, []),
    "apps.*.tools.*.approval_mode": ({}, APP + '[apps.cal.tools.delete]\napproval_mode="yes"\n',
                                     ["Codex cannot load this configuration file because apps.cal.tools.delete.approval_mode is not one of auto, prompt, writes, approve."],
                                     {"apps.cal": [LOAD_ERROR, "tool approval: auto (default)"], "apps.cal.tools.delete": [LOAD_ERROR]}, []),
    "notify": ({"notify": '"synthetic-command"'}, "", ["notify is not a command list with a nonempty program."], {"notify": None}, []),
    "notify empty program": ({"notify": '[""]'}, "", ["notify is not a command list with a nonempty program."], {"notify": None}, []),
    "notify non-string argument": ({"notify": '["synthetic-command", 1]'}, "", ["notify is not a command list with a nonempty program."],
                                   {"notify": None}, []),
    "hooks.*": ({}, '[hooks.PreToolUse]\nhooks=[{type="command", command="synthetic-command"}]\n',
                ["hooks contains an invalid event configuration.", HOOKS_GAP], {"hooks.PreToolUse": None}, []),
    "hooks.*.hooks": ({}, '[[hooks.PreToolUse]]\nhooks={type="command", command="synthetic-command"}\n',
                      ["hooks contains an invalid handler group.", HOOKS_GAP], {"hooks.PreToolUse": ["contents withheld"]}, []),
    "features.apps": ({}, '[features]\napps="yes"\n', [BOOLEAN_GAP.format("features.apps")], {"features.apps": None}, []),
    "web_search": ({"web_search": '"yes"'}, "", ["web_search is unsupported or invalid; its value was withheld."], {"web_search": None}, []),
}


def configuration(top, tables):
    keys = {**TOP, **top}
    return "".join(f"{key}={value}\n" for key, value in keys.items() if value is not None) + tables + ANCHOR


def catalog(report):
    return {e["name"]: e["observations"] for e in report["catalog"]}


class InvalidValueTests(ConfigCase):
    def test_each_invalid_value_is_a_gap_without_findings_and_keeps_unrelated_findings(self):
        for field, (top, tables, gaps, entries, risks) in CASES.items():
            with self.subTest(field=field):
                report = inspect([self.config(configuration(top, tables))])
                self.assertEqual(report["inspection_gaps"], sorted(f"config-1: {gap}" for gap in gaps))
                expected = {name: obs for name, obs in {**BASELINE, **entries}.items() if obs is not None}
                self.assertEqual(catalog(report), expected)
                expected = [risk for risk in BASELINE_RISKS if risk[1] not in entries] + risks
                self.assertCountEqual([(r["rule"], r["entry"].removeprefix("config-1:")) for r in report["risks"]], expected)

    def test_a_disabled_app_gives_no_gap_for_unknown_fields_or_valid_links(self):
        settings = {"unknown tool field": ("", "[apps.cal.tools.delete]\nsynthetic=1\n"),
                    "unknown app field": ("synthetic=1\n", ""),
                    "links": ("", "[apps.cal.links.account]\ndefault_tools_approval_mode=\"approve\"\n")}
        for setting, (field, tables) in settings.items():
            with self.subTest(setting=setting):
                report = inspect([self.config(configuration({}, "[apps.cal]\nenabled=false\n" + field + tables))])
                self.assertEqual(report["inspection_gaps"], [])
                self.assertEqual(catalog(report)["apps.cal"][0], "disabled")
                self.assertCountEqual([(r["rule"], r["entry"].removeprefix("config-1:")) for r in report["risks"]], BASELINE_RISKS)

    def test_a_disabled_app_keeps_the_gaps_of_an_app_before_it(self):
        tables = '[apps.cal]\ndestructive_enabled="yes"\n[apps.other]\nenabled=false\n'
        report = inspect([self.config(configuration({}, tables))])
        self.assertEqual(report["inspection_gaps"], [f"config-1: {gap}" for gap in CASES["apps.*.destructive_enabled"][2]])

    def test_an_app_under_a_non_table_apps_default_keeps_its_gaps(self):
        report = inspect([self.config(configuration({}, '[apps]\n_default=1\n[apps.cal]\n[apps.cal.tools.delete]\nenabled="yes"\n'))])
        self.assertEqual(report["inspection_gaps"], [
            "config-1: Codex cannot load this configuration file because apps.cal.tools.delete.enabled is not a boolean.",
            "config-1: apps._default must be a table.",
        ])

    def test_notify_arguments_after_the_program_may_be_empty(self):
        report = inspect([self.config(configuration({"notify": '["synthetic-command", ""]'}, ""))])
        self.assertEqual(report["inspection_gaps"], [])
        self.assertIn(("configured_program", "config-1:notify"), [(r["rule"], r["entry"]) for r in report["risks"]])


if __name__ == "__main__":
    unittest.main()
