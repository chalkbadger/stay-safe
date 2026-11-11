"""Each Markdown finding's "What to do" names its lower-friction option, if the Codex meanings table backs one, then
its stricter option, then how to change it: where the setting goes and a sentence to ask Codex, and for some rules a
Check step that changes nothing and shows no values. One shared note opens the findings (archived issue #119;
reviews of archived PR #129 at 143ba19 and 29d5a8c).

The expected text below was written from the rows of harnesses/codex.md named in BACKING and from the issue's table,
not copied from the report. Codex facts outside a row's own wording are cited where they are used.
"""

import json
import re
import subprocess
import sys

from stay_safe.report import inspect, render
from tests.support import FIRST, NOTE_LABEL, SECOND, ConfigCase, ROOT, finding_items, section

# Meanings rows (setting, value) an option rests on. Mode meanings are defined once, on the MCP server rows; the app
# rows say apps use the same modes ("the hint-dependent meaning is defined in the mode rows above").
BACKING = {
    "approval never": [("approval_policy", "never")],
    "approval on-request": [("approval_policy", "on-request")],
    "sandbox workspace-write": [("sandbox_mode", "workspace-write")],
    "sandbox read-only": [("sandbox_mode", "read-only")],
    "server writes": [("mcp_servers.*.default_tools_approval_mode", "writes")],
    "server prompt": [("mcp_servers.*.default_tools_approval_mode", "prompt")],
    "server enabled_tools": [("mcp_servers.*.enabled_tools", "named allowlist")],
    "server tool approve": [("mcp_servers.*.tools.*.approval_mode", "approve")],
    "server off": [("mcp_servers.*.enabled", "false")],
    "app writes": [("apps.*.default_tools_approval_mode", "writes inherited from _default"),
                   ("mcp_servers.*.default_tools_approval_mode", "writes")],
    "app prompt": [("mcp_servers.*.default_tools_approval_mode", "prompt")],
    "app tool approve": [("apps.*.tools.*.approval_mode", "approve")],
    "app destructive off": [("apps.*.destructive_enabled", "false inherited from _default")],
    "app default tools": [("apps.*.default_tools_enabled", "true")],
    "app off": [("apps.*.enabled", "false")],
    "app tool off": [("apps.*.tools.*.enabled", "false")],
    "inherit core": [("shell_environment_policy.inherit", "core")],
    "inherit none": [("shell_environment_policy.inherit", "none")],
    "network off": [("sandbox_workspace_write.network_access", "false")],
}
CONFIRMED = {"documented", "documented in source"}
# A setting a report's option names, by the kind of entry the finding is on -> its BACKING key. Code text in an option
# that is not a setting: core variable names (openai/codex 086ccc8, protocol/src/shell_environment.rs L178-L181), the
# `set` table Codex adds after `inherit` (same file, L153-L158), and a saved approval's pattern words.
SETTINGS = {
    ("approval_policy", 1): {'approval_policy = "on-request"': "approval on-request",
                             'sandbox_mode = "workspace-write"': "sandbox workspace-write",
                             'sandbox_mode = "read-only"': "sandbox read-only"},
    ("sandbox_mode", 1): {'sandbox_mode = "workspace-write"': "sandbox workspace-write",
                          'sandbox_mode = "read-only"': "sandbox read-only"},
    ("mcp_servers", 2): {'default_tools_approval_mode = "writes"': "server writes",
                         'default_tools_approval_mode = "prompt"': "server prompt",
                         'approval_policy = "never"': "approval never", "enabled_tools": "server enabled_tools",
                         'approval_mode = "approve"': "server tool approve", "enabled = false": "server off"},
    ("mcp_servers", 4): {'approval_mode = "prompt"': "server prompt", 'approval_policy = "never"': "approval never"},
    ("apps", 2): {'default_tools_approval_mode = "writes"': "app writes",
                  'default_tools_approval_mode = "prompt"': "app prompt",
                  'approval_policy = "never"': "approval never", 'approval_mode = "approve"': "app tool approve",
                  "destructive_enabled = false": "app destructive off", "default_tools_enabled": "app default tools",
                  "enabled = false": "app off"},
    ("apps", 4): {'approval_mode = "prompt"': "app prompt", 'approval_policy = "never"': "approval never",
                  "enabled = false": "app tool off"},
    ("shell_environment_policy", 1): {'inherit = "core"': "inherit core", 'inherit = "none"': "inherit none"},
    ("sandbox_workspace_write", 2): {"network_access = false": "network off"},
}
NOT_SETTINGS = {"HOME", "PATH", "set", "pattern", '["git", "status"]', '["git"]', "notify",
                "default_permissions", "sandbox_mode"}


def passed(label):
    """How the report names a file passed with --config or --rules: a placeholder with its label, never its path."""
    return f"`<{label}>`"


FILE = WHERE = passed("config-1")
SHOW = "; show only what you change."
TOP = "near the top of the file, before any `[section]`"
# One shared note before the findings (re-review F15 step 1): placeholders, Codex reads the file, what overrides a
# file (`codex --help` 0.167.0: `-a, --ask-for-approval`, `-s, --sandbox`, `-p, --profile`, `-c, --config`), and
# no prompt can accompany either approval or denial (issue #30; openai/codex
# 086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a, codex-rs/codex-mcp/src/mcp/mod.rs L91-L110
# and codex-rs/core/src/mcp_tool_call.rs L1691-L1698); this file inspection observes neither live outcome.
PLACEHOLDERS = ("`<config-1>` and similar labels stand for a file you passed with `--config` or `--rules`; put its "
                "path in before you paste. ")
NOTE = ("*Before you change anything:* {placeholders}Codex reads the whole file to edit it. The app, profiles and flags "
        "such as `--ask-for-approval`, `--sandbox`, `--profile` and `-c` can override any file. A tool call can be "
        "allowed or denied without an approval prompt. This report does not verify runtime approval behavior.")


def block(what, where, ask, check=None):
    """What to do and Change it, one line each (F15 steps 3 and 4), then a Check when the finding has one."""
    parts = [f"*What to do:* {what}", f"*Change it:* {where}, or ask Codex: \"{ask}{SHOW}\""]
    return "\n\n".join(parts + ([f"*Check:* {check}"] if check else []))


# Rows: server/app writes (asks unless the tool declares readOnlyHint=true, which the server sets and Codex doesn't
# check: core/src/mcp_tool_call.rs L2621-L2623), server enabled_tools (MCP servers only; the listed tools keep their
# mode, so they still run without asking), server/app prompt.
def automatic_group(kind, name, table, file=FILE):
    allowlist = (", or list only the tools you use in `enabled_tools` (those still run without asking)"
                 if kind == "MCP server" else "")
    return block(
        "Set `default_tools_approval_mode = \"writes\"` (Codex then asks unless the server labels a tool read-only, "
        f"which Codex doesn't check){allowlist}. Stricter: `default_tools_approval_mode = \"prompt\"`, so Codex asks "
        "before every call.",
        f"under `[{table}]`",
        f"Edit {file} to set `default_tools_approval_mode = \"writes\"` for my `{name}` {kind}")


# Rows: server/app prompt, server/app tool approve (a tool set to approve runs without asking), server enabled_tools
# (the listed tools keep following their labels).
def labels_group(kind, name, table, file=FILE):
    allowlist = (", or list only the tools you use in `enabled_tools` (those still follow their labels)"
                 if kind == "MCP server" else "")
    return block(
        "Set `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for tools you trust "
        f"(those run without asking){allowlist}. Stricter: `default_tools_approval_mode = \"prompt\"` for every tool, "
        "so Codex asks before every call.",
        f"under `[{table}]`, with each trusted tool's `approval_mode` under `[{table}.tools.<tool>]`",
        f"Edit {file} so my `{name}` {kind} asks before every tool call except these tools I trust: <tool names>")


# One tool's own mode: no lower-friction option has a row (server prompt row, tool override rows).
def tool_prompt(tool, kind, name, table, file=FILE):
    return block(
        "Set `approval_mode = \"prompt\"` for this tool, so Codex asks before calling it.",
        f"under `[{table}]`",
        f"Edit {file} to set `approval_mode = \"prompt\"` for the `{tool}` tool of my `{name}` {kind}")


# Rows: app destructive off, app default tools (`true` turns destructive tools back on), app off.
def destructive_app(name, file=FILE):
    return block(
        "Set `destructive_enabled = false` and leave `default_tools_enabled` unset (tools the app marks as not "
        "destructive stay on; tools marked destructive, or not marked, turn off). Stricter: `enabled = false`, if you "
        "don't need the app.",
        f"under `[apps.{name}]`, removing any `default_tools_enabled` line there",
        f"Edit {file} to set `destructive_enabled = false` for my `{name}` app and remove its `default_tools_enabled` "
        "line if it has one")


def destructive_tool(tool, app, file=FILE):  # Row: app tool off.
    return block(
        "If you don't need this tool, set `enabled = false` for it.",
        f"under `[apps.{app}.tools.{tool}]`",
        f"Edit {file} to set `enabled = false` for the `{tool}` tool of my `{app}` app")


# Lower-friction: keep a trusted program (no setting). Stricter: row server off; turning it off to see what breaks
# changes the setup, so it is not the Check. A stdio server runs `command` with `args` (openai/codex 086ccc8,
# config/src/mcp_types.rs L393-L397), so with a launcher or interpreter what runs is in `args` (F5, F16);
# `http_headers_helper` is a program too (L411).
def program_server(name, file=FILE, where=WHERE):
    return block(
        "Keep it if you trust the program it starts. Stricter: `enabled = false`; if nothing you use stops working, "
        "leave it off.",
        f"under `[mcp_servers.{name}]`",
        f"Edit {file} to set `enabled = false` for my `{name}` MCP server",
        check=f"Under `[mcp_servers.{name}]` in {where}, the program is `command` with its `args` (or "
              "`http_headers_helper`); for a launcher such as `npx`, `uvx`, `docker`, `node` or `python`, what runs "
              "is named in `args`. Find out who publishes it before you trust it.")


# Rows: approval on-request, sandbox workspace-write and read-only. The advice never suggests a sandbox looser than one
# set by the finding's file or any other inspected file (F2, F13): `workspace-write` only when no inspected file sets
# the stricter `read-only`. With `default_permissions`, the permission profile, not `sandbox_mode`, decides
# what commands can write (openai/codex 086ccc8, core/src/config/mod.rs L2712-L2722; F14). A saved approval runs its
# commands outside the sandbox (Saved approval records).
SAVED_STILL = "commands a saved approval allows still run outside the sandbox."


def commands(sandbox=None, file=FILE, where=WHERE, other=None, profile=False):
    check = f"Look for `approval_policy` and `sandbox_mode` in {where}."
    keep = f"Edit {file} to set `approval_policy = \"on-request\"` without changing `sandbox_mode`"
    approval_only = f"`approval_policy` {TOP}"
    if profile:
        return block(
            "Set `approval_policy = \"on-request\"` (Codex decides when to ask you first). Your `default_permissions` "
            "profile, not `sandbox_mode`, decides what commands can write; review it.",
            approval_only, keep, check)
    if sandbox == "read-only":
        return block(
            "Set `approval_policy = \"on-request\"` and keep `sandbox_mode = \"read-only\"` (Codex decides when to ask "
            f"you first; commands still can't write files). But {SAVED_STILL}",
            approval_only, keep, check)
    if sandbox == "workspace-write":
        return block(
            "Set `approval_policy = \"on-request\"` and keep `sandbox_mode = \"workspace-write\"` (Codex decides when to "
            "ask you first; commands can still write in your workspace). Stricter: also `sandbox_mode = \"read-only\"` "
            f"(commands can't write files). Either way, {SAVED_STILL}",
            approval_only, keep, check)
    if other:
        value, label = other
        return block(
            f"Set `approval_policy = \"on-request\"` (Codex decides when to ask you first) without loosening the "
            f"`sandbox_mode = \"{value}\"` in `{label}`. But {SAVED_STILL}",
            approval_only, keep, check)
    return block(
        "Set `approval_policy = \"on-request\"` with `sandbox_mode = \"workspace-write\"` (commands can write only in "
        "your workspace; Codex decides when to ask you first). Stricter: `sandbox_mode = \"read-only\"` (commands "
        f"can't write files). Either way, {SAVED_STILL}",
        TOP,
        f"Edit {file} to set `approval_policy = \"on-request\"` and `sandbox_mode = \"workspace-write\"`", check)


# Rows: sandbox workspace-write, sandbox read-only. With `read-only` in another inspected file, `workspace-write` would
# be looser, so only `read-only` is offered (F13).
def sandbox(file=FILE, other=None):
    if other:
        return block(
            f"Set `sandbox_mode = \"read-only\"`, as `{other}` does (commands can't write files).",
            TOP, f"Edit {file} to set `sandbox_mode = \"read-only\"`")
    return block(
        "Set `sandbox_mode = \"workspace-write\"` (commands can write only in your workspace). Stricter: "
        "`sandbox_mode = \"read-only\"` (commands can't write files).",
        TOP, f"Edit {file} to set `sandbox_mode = \"workspace-write\"`")


# Rows: inherit core, inherit none. Core variables on Unix include HOME and PATH, and Codex adds `set` entries after
# `inherit` (openai/codex 086ccc8, protocol/src/shell_environment.rs L153-L158, L178-L181). The Check prints names
# only: `env | cut -d= -f1` would print each line of a multi-line value that has no `=`, so it uses awk's ENVIRON.
ENV_CHECK = ("In a terminal like the one you start Codex from, run `awk 'BEGIN { for (name in ENVIRON) print name }'` "
             "to list the names of your environment variables without their values, and look for names that suggest "
             "credentials.")


def environment(file=FILE):
    return block(
        "Set `inherit = \"core\"` (commands get only core variables, such as `HOME` and `PATH`, plus any you list "
        "under `set`). Stricter: `inherit = \"none\"` (no inherited variables).",
        "under `[shell_environment_policy]` (inside its `{ }` if it's on one line)",
        f"Edit {file} to set `inherit = \"core\"` under `[shell_environment_policy]`", ENV_CHECK)


def network(file=FILE):  # Row: network off. No lower-friction option has a row (archived issue #127).
    return block(
        "Set `network_access = false` unless commands need the network.",
        "under `[sandbox_workspace_write]`",
        f"Edit {file} to set `network_access = false` under `[sandbox_workspace_write]`")


# Saved approval records: a record covers every command that starts with its pattern's words (openai/codex 086ccc8
# execpolicy/src/rule.rs L55-L72), so a pattern with more words covers fewer commands.
def saved(line, file=None, where=None):
    file = where = file or passed("rules-1")
    return block(
        "Replace it with a rule whose `pattern` has more words (it then covers only the commands you meant), for "
        f"example `[\"git\", \"status\"]` instead of `[\"git\"]`. Stricter: delete line {line}.",
        f"on line {line}, add the next words of the command you meant to the `pattern` list",
        f"Edit {file} to replace line {line} with a rule that allows only <the command you meant>",
        f"Open {where} and read line {line}: its `pattern` lists the words a command must start with.")


# `notify` is a list whose first item is the program (row notify); a list can continue over several lines, and Codex
# 0.167.0 refuses a file with only its first line deleted (review F1).
def notify(file=FILE, where=WHERE):
    return block(
        "Keep it if you trust the program it starts. Stricter: remove `notify` if you don't need notifications.",
        "delete the `notify` setting, including any lines its list continues on",
        f"Edit {file} to remove the `notify` setting",
        f"In {where}, the first item in the `notify` list is the program it starts; for a launcher such as `node` or "
        "`npx`, the next items name what runs. Find out who publishes it before you trust it.")


# Codex writes each matcher group's handlers as `[[hooks.<Event>.hooks]]` sections (MatcherGroup, openai/codex
# 086ccc8 protocol/src/hooks.rs L140-L145; app-server/tests/suite/v2/hooks_list.rs L80-L87). Deleting only the
# `[[hooks.<Event>]]` lines leaves those sections behind, which Codex 0.167.0 refuses to load (review F1).
def hooks(event, file=FILE, where=WHERE):
    return block(
        "Keep them if you trust the commands they run. Stricter: remove these hooks if you don't use them.",
        f"delete each `[[hooks.{event}]]` section with everything under it, including its `[[hooks.{event}.hooks]]` "
        "sections",
        f"Edit {file} to remove my `{event}` hooks",
        f"In {where}, each `command` in the `hooks` of `[[hooks.{event}]]`, often written as `[[hooks.{event}.hooks]]` "
        "sections, is a command they run. Find out who publishes the program it starts before you trust it.")


RULES = 'prefix_rule(pattern=["git", "seed-rule-word"], decision="allow")\n'
SECOND_FILE = passed("config-2")

# (rule, entry) -> What to do, for the explicit files of tests/findings_say_what_to_do/test_plain_findings.py.
EXPECTED = {
    ("commands_without_prompts", "config-1:approval_policy"): commands("danger-full-access"),
    ("unrestricted_filesystem", "config-1:sandbox_mode"): sandbox(),
    ("configured_program", "config-1:notify"): notify(),
    ("configured_program", "config-1:mcp_servers.github"): program_server("github"),
    ("self_described_tools", "config-1:mcp_servers.github"): labels_group("MCP server", "github", "mcp_servers.github"),
    ("automatic_tools", "config-1:mcp_servers.search"): automatic_group("MCP server", "search", "mcp_servers.search"),
    ("self_described_tools", 'config-1:mcp_servers."team.wiki"'):
        labels_group("MCP server", "team.wiki", 'mcp_servers."team.wiki"'),
    ("automatic_tools", "config-1:mcp_servers.docs.tools.publish"):
        tool_prompt("publish", "MCP server", "docs", "mcp_servers.docs.tools.publish"),
    ("self_described_tools", "config-1:mcp_servers.docs.tools.lookup"):
        tool_prompt("lookup", "MCP server", "docs", "mcp_servers.docs.tools.lookup"),
    ("automatic_tools", "config-1:apps.calendar"): automatic_group("app", "calendar", "apps.calendar"),
    ("destructive_tools", "config-1:apps.calendar"): destructive_app("calendar"),
    ("destructive_tools", "config-1:apps.drive"): destructive_app("drive"),
    ("self_described_tools", "config-1:apps.drive"): labels_group("app", "drive", "apps.drive"),
    ("automatic_tools", "config-1:apps.files.tools.delete"):
        tool_prompt("delete", "app", "files", "apps.files.tools.delete"),
    ("destructive_tools", "config-1:apps.files.tools.delete"): destructive_tool("delete", "files"),
    ("destructive_tools", "config-1:apps.files.tools.read"): destructive_tool("read", "files"),
    ("self_described_tools", "config-1:apps.files.tools.read"): tool_prompt("read", "app", "files", "apps.files.tools.read"),
    ("configured_program", "config-1:hooks.PreToolUse"): hooks("PreToolUse"),
    ("environment_inheritance", "config-1:shell_environment_policy"): environment(),
    ("network_access", "config-2:sandbox_workspace_write.network_access"): network(SECOND_FILE),
    ("saved_approval", "rules-1:prefix_rule.1"): saved(1),
}


def what_to_do(finding):
    """A finding's parts between its incident line and its trace line."""
    paragraphs = finding.split("\n\n")
    return "\n\n".join(paragraphs[2:-1])


def options(text):
    """The option sentences of a What to do line."""
    return [text.split("\n\n", 1)[0][len("*What to do:* "):]]


# Two files as in the example in docs/usage.md (`--config user.toml --config project.toml`), the second setting `never`.
USER_READ_ONLY = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
USER_WORKSPACE = 'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n'
COMMANDS_KEY = ("commands_without_prompts", "config-2:approval_policy")


class WhatToDoTests(ConfigCase):
    def run_cli(self, *args, env=None):
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=ROOT, env=env or {},
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(run.stderr, "")
        return run

    def findings(self, *args, env=None):
        risks = json.loads(self.run_cli(*args, "--format", "json", env=env).stdout)["risks"]
        markdown = self.run_cli(*args, env=env).stdout
        return {(risk["rule"], risk["entry"]): what_to_do(item) for risk, item in zip(risks, finding_items(markdown))}

    def files(self, *texts):
        return [arg for index, text in enumerate(texts, 1)
                for arg in ("--config", str(self.config(text, f"file-{index}.toml")))]

    def explicit(self):
        return ["--config", str(self.config(FIRST, "first.toml")), "--config", str(self.config(SECOND, "second.toml")),
                "--rules", str(self.config(RULES, "selected.rules"))]

    def test_each_finding_gives_lower_friction_then_stricter_option_then_how_to_change_it(self):
        found = self.findings(*self.explicit())
        self.assertEqual(set(found), set(EXPECTED))
        for key, expected in EXPECTED.items():
            with self.subTest(rule=key[0], entry=key[1]):
                self.assertEqual(found[key], expected)

    def test_findings_open_with_one_shared_note(self):
        markdown = self.run_cli(*self.explicit()).stdout
        self.assertEqual(section(markdown, "Findings").split("\n\n", 1)[0], NOTE.format(placeholders=PLACEHOLDERS))
        self.assertEqual(markdown.count("Codex reads the whole file"), 1)
        clean = self.run_cli("--config", str(self.config('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                                                            'shell_environment_policy = { inherit = "core" }\n'
                                                            'features = { apps = false }\n'))).stdout
        self.assertNotIn(NOTE_LABEL, clean)

    def test_shared_note_keeps_approval_outcomes_unassessed_for_each_policy(self):
        never = 'approval_policy = "never"\n'
        on_request = 'approval_policy = "on-request"\n'
        for policies in ((never,), (on_request,), ("",), (never, on_request)):
            with self.subTest(policies=policies):
                paths = [self.config(text, f"policy-{index}.toml") for index, text in enumerate(policies)]
                markdown = render(inspect(paths), "markdown")
                self.assertEqual(section(markdown, "Findings").split("\n\n", 1)[0],
                                 NOTE.format(placeholders=PLACEHOLDERS))
                self.assertEqual(markdown.count(NOTE_LABEL), 1)

    def test_commands_advice_never_loosens_the_configured_sandbox(self):
        for sandbox_mode in ("read-only", "workspace-write", "danger-full-access", None):
            with self.subTest(sandbox_mode=sandbox_mode):
                text = 'approval_policy = "never"\n' + (f'sandbox_mode = "{sandbox_mode}"\n' if sandbox_mode else "")
                found = self.findings("--config", str(self.config(text)))
                self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")], commands(sandbox_mode))

    def test_advice_never_loosens_a_sandbox_another_inspected_file_sets(self):
        first, second = passed("config-1"), passed("config-2")
        commands_1 = ("commands_without_prompts", "config-1:approval_policy")
        never = 'approval_policy = "never"\n'
        cases = [
            # The two-file example in docs/usage.md: the project file sets `never` and no sandbox.
            ((USER_READ_ONLY, never),
             {COMMANDS_KEY: commands(file=second, where=second, other=("read-only", "config-1"))}),
            # `workspace-write` elsewhere is not stricter than the `workspace-write` this advice suggests.
            ((USER_WORKSPACE, never), {COMMANDS_KEY: commands(file=second, where=second)}),
            # The finding's own file sets a sandbox: its own value decides, not the other file's.
            ((USER_READ_ONLY, never + 'sandbox_mode = "workspace-write"\n'),
             {COMMANDS_KEY: commands("workspace-write", second, second)}),
            # Its own file turns the sandbox off: `workspace-write` would be looser than the other file's `read-only`.
            ((USER_READ_ONLY, never + 'sandbox_mode = "danger-full-access"\n'),
             {COMMANDS_KEY: commands(file=second, where=second, other=("read-only", "config-1")),
              ("unrestricted_filesystem", "config-2:sandbox_mode"): sandbox(second, other="config-1")}),
            ((USER_WORKSPACE, 'approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n'),
             {("unrestricted_filesystem", "config-2:sandbox_mode"): sandbox(second)}),
            # Reversed order: a later file's `read-only` counts too (narrow re-review F17).
            ((never, USER_READ_ONLY), {commands_1: commands(file=first, where=first, other=("read-only", "config-2"))}),
            # Three files: `read-only` in the third counts, even after a `workspace-write` in the second (F17).
            ((never, USER_WORKSPACE, USER_READ_ONLY),
             {commands_1: commands(file=first, where=first, other=("read-only", "config-3"))}),
            # A file that selects a profile and also sets `read-only` counts too: in a later layer, an added
            # `sandbox_mode` would replace that profile (openai/codex 086ccc8 core/src/config/mod.rs L2717-L2719; F18).
            ((never, 'default_permissions = "dev"\nsandbox_mode = "read-only"\n[permissions.dev]\n'),
             {commands_1: commands(file=first, where=first, other=("read-only", "config-2"))}),
        ]
        for texts, expected in cases:
            with self.subTest(files=texts):
                found = self.findings(*self.files(*texts))
                for key, text in expected.items():
                    self.assertEqual(found[key], text, key)

    def test_a_selected_permission_profile_gets_no_sandbox_mode_advice(self):
        for extra in ("", 'sandbox_mode = "read-only"\n', 'sandbox_mode = "danger-full-access"\n'):
            with self.subTest(sandbox_mode=extra.strip()):
                text = 'approval_policy = "never"\ndefault_permissions = "work"\n' + extra
                found = self.findings("--config", str(self.config(text)))
                self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")],
                                 commands(profile=True))
        # Unselected `[permissions.*]` definitions don't replace `sandbox_mode` (meanings row `permissions`).
        found = self.findings("--config", str(self.config('approval_policy = "never"\nsandbox_mode = "read-only"\n'
                                                          '[permissions.work]\n', "definitions.toml")))
        self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")], commands("read-only"))
        found = self.findings("--config", str(self.config('approval_policy = "never"\n[permissions.work]\n',
                                                          "definitions-only.toml")))
        self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")], commands())

    def test_every_setting_an_option_names_rests_on_a_confirmed_meanings_row(self):
        text = (ROOT / "harnesses/codex.md").read_text(encoding="utf-8")
        rows = {}
        for line in text.splitlines():
            if line.startswith("| `"):
                setting, value, _, _, status = [part.strip() for part in line.strip("|").split("|")]
                rows[(setting.strip("`"), value.strip("`"))] = status
        found = dict(self.findings(*self.explicit()))
        variants = [('approval_policy = "never"\nsandbox_mode = "read-only"\n',),
                    ('approval_policy = "never"\nsandbox_mode = "workspace-write"\n',),
                    ('approval_policy = "never"\ndefault_permissions = "work"\n',),
                    (USER_READ_ONLY, 'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n')]
        for index, texts in enumerate(variants):
            for key, what in self.findings(*self.files(*texts)).items():
                found[(key[0], f"{key[1]}#{index}")] = what
        named = 0
        for (rule, entry), what in found.items():
            keys = re.findall(r'"(?:[^"\\]|\\.)*"|[^."]+', entry.split(":", 1)[1].split("#")[0])
            shape = (keys[0], len(keys))
            for option in options(what):
                for code in re.findall(r"`([^`]+)`", option):
                    if (code in NOT_SETTINGS or code.startswith("[") or re.fullmatch(r"(config|rules)-\d+", code)
                            or rule == "saved_approval"):
                        continue
                    with self.subTest(rule=rule, entry=entry, setting=code):
                        self.assertIn(code, SETTINGS.get(shape, {}))
                        for row in BACKING[SETTINGS[shape][code]]:
                            self.assertIn(rows.get(row), CONFIRMED, row)
                        named += 1
        self.assertGreater(named, 30)

    def test_files_found_automatically_are_named_where_codex_keeps_them(self):
        config = ('approval_policy = "never"\nsandbox_mode = "danger-full-access"\n'
                  'notify = ["seed-notify-program"]\n[mcp_servers.github]\ncommand = "seed-github-command"\n')
        self.require_no_system_folder()
        for variable, base in (("HOME", "~/.codex"), ("CODEX_HOME", "$CODEX_HOME")):
            with self.subTest(variable=variable):
                home = self.root / variable
                codex = home / ".codex" if variable == "HOME" else home
                (codex / "rules").mkdir(parents=True)
                (codex / "config.toml").write_text(config, encoding="utf-8")
                (codex / "rules" / "default.rules").write_text(RULES, encoding="utf-8")
                markdown = self.run_cli(env={variable: str(home)}).stdout
                self.assertEqual(section(markdown, "Findings").split("\n\n", 1)[0], NOTE.format(placeholders=""))
                found = self.findings(env={variable: str(home)})
                file, rules = f"`{base}/config.toml`", f"`{base}/rules/default.rules`"
                self.assertEqual(found, {
                    ("commands_without_prompts", "config-1:approval_policy"):
                        commands("danger-full-access", file, file),
                    ("unrestricted_filesystem", "config-1:sandbox_mode"): sandbox(file),
                    ("configured_program", "config-1:notify"): notify(file, file),
                    ("configured_program", "config-1:mcp_servers.github"): program_server("github", file, file),
                    ("self_described_tools", "config-1:mcp_servers.github"):
                        labels_group("MCP server", "github", "mcp_servers.github", file),
                    ("environment_inheritance", "config-1:shell_environment_policy"): environment(file),
                    ("saved_approval", "rules-1:prefix_rule.1"): saved(1, rules),
                })
