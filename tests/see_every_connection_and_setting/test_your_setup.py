"""Markdown's "Your setup" lists every catalog entry in plain words, under its file (archived issue #105, reading check).

The JSON catalog is unchanged. Each expected line below restates an entry's observations from their meaning in
harnesses/codex.md and docs/usage.md, written by hand rather than copied from the report.
"""

import json
import subprocess
import sys

from stay_safe.report import inspect, markdown
from tests.see_every_connection_and_setting.test_config import FIXTURE
from tests.support import CHATGPT_APPS, FIRST, SECOND, ConfigCase, ROOT, section

# Approval mode settings: harnesses/codex.md.
AUTO = "tool approval `auto`"
DEFAULT_AUTO = ("tool approval left at the default, `auto`")
# (entry id, kind, observations) -> expected line, covering every observation the readers can produce.
ENTRIES = [
    ("config-1:approval_policy", "permission", ["never"], "Approval: `never` (doesn't ask before commands)"),
    ("config-1:apps._default", "app policy", ["configured enabled", "tool approval: writes"],
     "Defaults for all apps (`_default`): on, tool approval `writes`"),
    ("config-2:apps._default", "app policy", ["disabled"],
     "Defaults for all apps (`_default`): off (this doesn't turn off your named apps)"),
    ("config-1:apps.calendar", "app policy",
     ["configured enabled", "destructive tools enabled by Codex default", "tool approval: approve"],
     "App `calendar`: on, tools that change or delete data on (Codex default), tool approval `approve`"),
    ("config-1:apps.drive", "app policy", ["disabled", "tool approval: prompt"],
     "App `drive`: off, tool approval `prompt`"),
    ("config-1:apps.files", "app policy",
     ["enablement unknown", "default tools disabled or unknown", "destructive tools disabled by destructive_enabled",
      "tool approval: auto"],
     f"App `files`: on or off unknown, tools off unless turned on one by one (or unknown), tools that change or "
     f"delete data off (set by `destructive_enabled`), {AUTO}"),
    ("config-1:apps.files.tools.delete", "tool policy",
     ["configured enabled", "enabled even if destructive", "tool approval: approve"],
     "Tool `delete` of app `files`: on, even if it can change or delete data, tool approval `approve`"),
    ("config-1:apps.mail", "app policy",
     ["configured enabled", "destructive tools enabled by apps._default.destructive_enabled", "tool approval: auto (default)"],
     f"App `mail`: on, tools that change or delete data on (set by `apps._default.destructive_enabled`), {DEFAULT_AUTO}"),
    ("config-1:apps.notes", "app policy",
     ["configured enabled", "destructive tools disabled by apps._default.destructive_enabled"],
     "App `notes`: on, tools that change or delete data off (set by `apps._default.destructive_enabled`)"),
    ("config-1:apps.sheets", "app policy",
     ["configured enabled", "destructive tools enabled by default_tools_enabled"],
     "App `sheets`: on, tools that change or delete data on (set by `default_tools_enabled`)"),
    ("config-1:apps.slides", "app policy", ["configured enabled", "destructive tools enabled by destructive_enabled"],
     "App `slides`: on, tools that change or delete data on (set by `destructive_enabled`)"),
    ("config-1:hooks.PreToolUse", "automation", ["contents withheld"], "`PreToolUse` hooks: set (contents left out)"),
    ("config-1:mcp_servers.broken", "MCP server", ["configured enabled", "transport unknown"],
     "MCP server `broken`: on, connection type unknown"),
    ("config-1:mcp_servers.docs", "MCP server", ["configured enabled", "HTTP; endpoint withheld", "tool approval: auto (default)"],
     f"MCP server `docs`: on, connects over HTTP (address left out), {DEFAULT_AUTO}"),
    ("config-1:mcp_servers.docs.disabled_tools", "tool filter", ["no reportable configured names", "some names withheld"],
     "Blocked tools of MCP server `docs`: no names that can be shown, some names left out"),
    ("config-1:mcp_servers.docs.enabled_tools", "tool filter", ["configured names: read, files/write"],
     "Allowed tools of MCP server `docs`: `read`, `files/write`"),
    ("config-1:mcp_servers.docs.tools.read", "tool policy", ["disabled or enablement unknown", "tool approval: approve"],
     "Tool `read` of MCP server `docs`: off or unknown, tool approval `approve`"),
    ('config-1:mcp_servers."team.wiki"', "MCP server", ["disabled", "stdio; command withheld", "tool approval: auto (default)"],
     f"MCP server `team.wiki`: off, starts a program on your computer (command left out), {DEFAULT_AUTO}"),
    ("config-1:model_providers.internal", "model provider", ["configured; endpoint and credentials withheld"],
     "Model provider `internal`: set up (address and credentials left out)"),
    ("config-1:notify", "automation", ["notification command configured; command withheld"],
     "Notifications: start a program (command left out)"),
    ("config-1:sandbox_mode", "permission", ["danger-full-access", "permission-profile selection is uninspected"],
     "Sandbox: `danger-full-access` (no sandbox), a permission profile may replace it (not checked)"),
    ("config-1:sandbox_workspace_write.network_access", "permission", ["true", "inactive or selection unknown"],
     "Network access for commands: on (applies only in `workspace-write` mode, which isn't selected or is unknown)"),
    ("config-1:shell_environment_policy", "permission", ["inherit: all (default)", "ignore_default_excludes: true (default)"],
     "Environment for commands: all variables passed on (default), `ignore_default_excludes` true (default)"),
    ("config-1:web_search", "connection policy", ["live"], "Web search: `live`"),
    ("config-2:approval_policy", "permission", ["on-request"], "Approval: `on-request` (Codex can ask before commands)"),
    ("config-2:sandbox_mode", "permission", ["workspace-write"],
     "Sandbox: `workspace-write` (commands can write in your workspace)"),
    ("config-2:sandbox_workspace_write.network_access", "permission", ["false", "workspace-write option"],
     "Network access for commands: off (applies in `workspace-write` mode)"),
    ("config-2:shell_environment_policy", "permission", ["inherit: core (explicit)", "ignore_default_excludes: false (explicit)"],
     "Environment for commands: only core variables passed on (you set this), `ignore_default_excludes` false (you set this)"),
    ("config-3:config", "configuration file",
     ["No default Codex configuration file was found. Assessed defaults: command environment and ChatGPT Apps."],
     "Config file: none found, so stay-safe assessed Codex's documented defaults (the environment of commands and "
     "the ChatGPT Apps connection)"),
    # Archived issue #121, harnesses/codex.md row `features.apps` `omitted`: Codex adds this MCP connection to ChatGPT when it
    # is signed in with ChatGPT, which stay-safe doesn't check; `false` removes it.
    ("config-3:features.apps", "MCP server", CHATGPT_APPS,
     "ChatGPT Apps connection: an MCP connection to ChatGPT, only when Codex is signed in with ChatGPT (stay-safe "
     "doesn't check sign-in), `features.apps = false` turns it off"),
    ("config-3:sandbox_mode", "permission", ["read-only"], "Sandbox: `read-only` (commands can't write files)"),
    ("config-3:shell_environment_policy", "permission", ["inherit: none (explicit)", "ignore_default_excludes: true (default)"],
     "Environment for commands: none passed on (you set this), `ignore_default_excludes` true (default)"),
    # An observation without plain wording is shown as it is, not dropped.
    ("config-3:future_setting", "permission", ["a future observation"], "`future_setting`: a future observation"),
    ("rules-1:prefix_rule.2", "saved approval", ["program: git", "tokens: 2"], "Saved approval, line 2: starts with `git`, 2 words"),
    ("rules-1:prefix_rule.3", "saved approval", ["program: curl", "tokens: 1", "broad: one-token prefix"],
     "Saved approval, line 3: starts with `curl`, 1 word, covers every use of that program"),
    ("rules-1:prefix_rule.4", "saved approval", ["tokens: 3"], "Saved approval, line 4: 3 words"),
    ("rules-2:rules", "rules file", ["absent"], "Saved approvals file: none found"),
]
# Each file passed with --config or --rules keeps its label, explained once with how Codex uses such a file
# (reading check, 2026-11-09).
CONFIG_USE = "Codex reads settings from config files like this."
RULES_USE = "Codex loads saved approvals from rules files like this."
HEADINGS = {f"config-{n}": f"**Config file `config-{n}`**: the {word} file you passed with `--config`. {CONFIG_USE}"
            for n, word in ((1, "first"), (2, "second"), (3, "third"))}
HEADINGS |= {f"rules-{n}": f"**Rules file `rules-{n}`**: the file you passed with `--rules`. {RULES_USE}" for n in (1, 2)}
# Said once, before the lists, when a value is left out or a saved approval's words are counted, not shown.
WITHHELD = ("stay-safe doesn't show commands, addresses, credentials, hook contents, tool names that look private "
            "or the words of saved approvals, because they can hold private paths or tokens. You'll find them in the file named in each list's "
            "heading, for example a server's command under `[mcp_servers.<name>]`.")


class YourSetupTests(ConfigCase):
    def test_each_observation_reads_in_plain_words_under_its_file(self):
        report = inspect([])
        report["catalog"] = [{"id": i, "source": i.split(":", 1)[0], "name": i.split(":", 1)[1], "kind": kind,
                              "observations": observations} for i, kind, observations, _ in ENTRIES]
        groups = {}
        for i, _, _, line in ENTRIES:
            groups.setdefault(i.split(":", 1)[0], []).append(f"- {line}")
        self.assertEqual(section(markdown(report), "Your setup"), WITHHELD + "\n\n" +
                         "\n\n".join(HEADINGS[source] + "\n" + "\n".join(lines) for source, lines in groups.items()))

    def test_a_real_run_lists_every_entry_once_under_its_file(self):
        args = ["--config", str(self.config(FIRST, "first.toml")), "--config", str(self.config(SECOND, "second.toml")),
                "--config", str(FIXTURE), "--rules", str(self.config('prefix_rule(pattern=["git", "x"], decision="allow")\n'
                                                                      'prefix_rule(pattern=["deploy"], decision="allow")\n',
                                                                      "selected.rules"))]
        runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args, "--format", f], cwd=ROOT, env={},
                               text=True, capture_output=True, timeout=10) for f in ("json", "markdown")]
        catalog = json.loads(runs[0].stdout)["catalog"]
        setup = section(runs[1].stdout, "Your setup").removeprefix(WITHHELD + "\n\n")
        counts = {}
        for entry in catalog:
            counts[entry["source"]] = counts.get(entry["source"], 0) + 1
        self.assertEqual([(group.splitlines()[0], len(group.splitlines()) - 1) for group in setup.split("\n\n")],
                         [(HEADINGS[source], count) for source, count in counts.items()])
        # Every observation has plain wording: none of the catalog's own phrasing is shown.
        for raw in ("withheld", "configured enabled", "tool approval:", "tokens:", "program:", "inherit:", "broad:"):
            self.assertNotIn(raw, setup)

    def test_the_withheld_explanation_appears_for_saved_approval_words_and_only_when_something_is_withheld(self):
        # A saved approval's words are counted, not shown, so they need the explanation even with no "left out" value;
        # a setup with nothing withheld has none (re-review F29).
        approval = {"id": "config-1:approval_policy", "source": "config-1", "name": "approval_policy",
                    "kind": "permission", "observations": ["never"]}
        saved = {"id": "rules-1:prefix_rule.1", "source": "rules-1", "name": "prefix_rule.1",
                 "kind": "saved approval", "observations": ["program: git", "tokens: 2"]}
        for name, catalog, expected in [("saved approval only", [approval, saved], True), ("nothing withheld", [approval], False)]:
            with self.subTest(case=name):
                report = inspect([])
                report["catalog"] = catalog
                self.assertEqual(section(markdown(report), "Your setup").startswith(WITHHELD + "\n\n"), expected)

    def test_an_empty_catalog_says_there_is_nothing_to_list(self):
        report = inspect([])
        report["catalog"] = []
        self.assertEqual(section(markdown(report), "Your setup"), "stay-safe found no settings to list.")
