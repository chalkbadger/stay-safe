import json
import re
import subprocess
import sys

from stay_safe.report import inspect, render
from tests.support import INCOMPLETE
from tests.support import FIRST, NOTE_LABEL, SECOND, ConfigCase, ROOT, finding_items, section

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
    "writable roots": [("sandbox_workspace_write.writable_roots", "paths under workspace-write")],
}
CONFIRMED = {"documented", "documented in source"}
SETTINGS = {
    ("approval_policy", 1): {'approval_policy = "on-request"': "approval on-request",
                             'sandbox_mode = "workspace-write"': "sandbox workspace-write",
                             'sandbox_mode = "read-only"': "sandbox read-only", "writable_roots": "writable roots"},
    ("sandbox_mode", 1): {'sandbox_mode = "workspace-write"': "sandbox workspace-write",
                          'sandbox_mode = "read-only"': "sandbox read-only", "writable_roots": "writable roots"},
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
    return f"`<{label}>`"


FILE = WHERE = passed("config-1")
SHOW = "; show only what you change."
TOP = "near the top of the file, before any `[section]`"
PLACEHOLDERS = ("`<config-1>` and similar labels stand for a file you passed with `--config` or `--rules`; put its "
                "path in before you paste. ")
NOTE = ("*Before you change anything:* {placeholders}Codex reads the whole file to edit it. The app, profiles and flags "
        "such as `--ask-for-approval`, `--sandbox`, `--profile` and `-c` can override any file. Codex can allow or "
        "block a tool call without asking you. This report does not test which calls Codex allows.")


def block(what, where, ask, check=None):
    parts = [f"*What to do:* {what}", f"*Change it:* {where}, or ask Codex: \"{ask}{SHOW}\""]
    return "\n\n".join(parts + ([f"*Check:* {check}"] if check else []))


def automatic_group(kind, name, table, file=FILE):
    allowlist = (", or list only the tools you use in `enabled_tools`"
                 if kind == "MCP server" else "")
    return block(
        "Set `default_tools_approval_mode = \"writes\"` (uses server hints)"
        f"{allowlist}. Stricter: `default_tools_approval_mode = \"prompt\"`.",
        f"under `[{table}]`",
        f"Edit {file} to set `default_tools_approval_mode = \"writes\"` for my `{name}` {kind}")


def labels_group(kind, name, table, file=FILE):
    allowlist = (", or list only the tools you use in `enabled_tools`"
                 if kind == "MCP server" else "")
    return block(
        "Set `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for tools you trust"
        f"{allowlist}. Stricter: `default_tools_approval_mode = \"prompt\"` for every tool.",
        f"under `[{table}]`, with each trusted tool's `approval_mode` under `[{table}.tools.<tool>]`",
        f"Edit {file} so my `{name}` {kind} uses `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for these tools I trust: <tool names>")


def tool_prompt(tool, kind, name, table, file=FILE):
    return block(
        "Set `approval_mode = \"prompt\"` for this tool.",
        f"under `[{table}]`",
        f"Edit {file} to set `approval_mode = \"prompt\"` for the `{tool}` tool of my `{name}` {kind}")


def destructive_app(name, file=FILE):
    return block(
        "Set `destructive_enabled = false` and leave `default_tools_enabled` unset (tools the app marks as not "
        "destructive stay on; tools marked destructive, or not marked, turn off). Stricter: `enabled = false`, if you "
        "don't need the app.",
        f"under `[apps.{name}]`, removing any `default_tools_enabled` line there",
        f"Edit {file} to set `destructive_enabled = false` for my `{name}` app and remove its `default_tools_enabled` "
        "line if it has one")


def destructive_tool(tool, app, file=FILE):
    return block(
        "If you don't need this tool, set `enabled = false` for it.",
        f"under `[apps.{app}.tools.{tool}]`",
        f"Edit {file} to set `enabled = false` for the `{tool}` tool of my `{app}` app")


def program_server(name, file=FILE, where=WHERE):
    return block(
        "Keep it if you trust the program it starts. Stricter: `enabled = false`; if nothing you use stops working, "
        "leave it off.",
        f"under `[mcp_servers.{name}]`",
        f"Edit {file} to set `enabled = false` for my `{name}` MCP server",
        check=f"Under `[mcp_servers.{name}]` in {where}, the program is `command` with its `args` (or "
              "`http_headers_helper`); for a launcher such as `npx`, `uvx`, `docker`, `node` or `python`, what runs "
              "is named in `args`. Find out who publishes it before you trust it.")


SAVED_STILL = "commands a saved approval allows still run outside the sandbox."
ASK = "If you want Codex to ask before running some commands it currently blocks, choose "
ORDINARY = "Ordinary commands can still run inside the sandbox without asking you."


def commands(sandbox=None, file=FILE, where=WHERE, other=None, profile=False):
    check = f"Look for `approval_policy` and `sandbox_mode` in {where}."
    keep = f"Edit {file} to set `approval_policy = \"on-request\"` without changing `sandbox_mode`"
    approval_only = f"`approval_policy` {TOP}"
    if profile:
        mode = f"This file sets `sandbox_mode` to `{sandbox}`. " if sandbox else ""
        return block(
            f'{ASK}`approval_policy = "on-request"`. {ORDINARY} '
            f"For read-only access, check that any profile you use blocks writes. Even then, {SAVED_STILL}",
            approval_only, keep, f"{mode}Review `default_permissions` in {profile} and any profile it names.")
    if sandbox == "read-only":
        return block(
            f"{ASK}`approval_policy = \"on-request\"` and keep `sandbox_mode = \"read-only\"` (commands still can't "
            f"write files). {ORDINARY} But {SAVED_STILL}",
            approval_only, keep, check)
    if sandbox == "workspace-write":
        return block(
            f"{ASK}`approval_policy = \"on-request\"` and keep `sandbox_mode = \"workspace-write\"` (commands can still "
            f"write in your workspace). {ORDINARY} Stricter: also `sandbox_mode = \"read-only\"` "
            f"(commands can't write files). Either way, {SAVED_STILL}",
            approval_only, keep, check)
    if other:
        value, label = other
        return block(
            f"{ASK}`approval_policy = \"on-request\"` without loosening the "
            f"`sandbox_mode = \"{value}\"` in `{label}`. {ORDINARY} But {SAVED_STILL}",
            approval_only, keep, check)
    return block(
        f"{ASK}`approval_policy = \"on-request\"` with `sandbox_mode = \"workspace-write\"` (commands can write in your "
        f"workspace and in any extra folders in `writable_roots`, so review that list). {ORDINARY} Stricter: "
        f"`sandbox_mode = \"read-only\"` (commands can't write files). Either way, {SAVED_STILL}",
        TOP,
        f"Edit {file} to set `approval_policy = \"on-request\"` and `sandbox_mode = \"workspace-write\"`", check)


def full_access_tools(file=FILE):
    return block(
        "Set `sandbox_mode = \"workspace-write\"` (each server's and app's tool approval mode then applies, and Codex "
        "refuses calls that need approval instead of asking), and review any extra folders in `writable_roots`. "
        "Stricter: `sandbox_mode = \"read-only\"` (commands "
        "can't write files).",
        "`sandbox_mode` " + TOP, f"Edit {file} to set `sandbox_mode = \"workspace-write\"` without changing `approval_policy`")


def sandbox(file=FILE, other=None):
    if other:
        return block(
            f"Set `sandbox_mode = \"read-only\"`, as `{other}` does (commands can't write files).",
            TOP, f"Edit {file} to set `sandbox_mode = \"read-only\"`")
    return block(
        "Set `sandbox_mode = \"workspace-write\"` (commands can write in your workspace and in any extra folders in "
        "`writable_roots`, so review that list). Stricter: "
        "`sandbox_mode = \"read-only\"` (commands can't write files).",
        TOP, f"Edit {file} to set `sandbox_mode = \"workspace-write\"`")


ENV_CHECK = ("In a terminal like the one you start Codex from, run `awk 'BEGIN { for (name in ENVIRON) print name }'` "
             "to list the names of your environment variables without their values, and look for names that suggest "
             "credentials.")


def environment(file=FILE):
    return block(
        "Set `inherit = \"core\"` (commands get only core variables, such as `HOME` and `PATH`, plus any you list "
        "under `set`). Stricter: `inherit = \"none\"` (no inherited variables).",
        "under `[shell_environment_policy]` (inside its `{ }` if it's on one line)",
        f"Edit {file} to set `inherit = \"core\"` under `[shell_environment_policy]`", ENV_CHECK)


def network(file=FILE):
    return block(
        "Set `network_access = false` unless commands need the network.",
        "under `[sandbox_workspace_write]`",
        f"Edit {file} to set `network_access = false` under `[sandbox_workspace_write]`")


def saved(line, file=None, where=None):
    file = where = file or passed("rules-1")
    return block(
        "Replace it with a rule whose `pattern` has more words (it then covers only the commands you meant), for "
        f"example `[\"git\", \"status\"]` instead of `[\"git\"]`. Stricter: delete line {line}.",
        f"on line {line}, add the next words of the command you meant to the `pattern` list",
        f"Edit {file} to replace line {line} with a rule that allows only <the command you meant>",
        f"Open {where} and read line {line}: its `pattern` lists the words a command must start with.")


def notify(file=FILE, where=WHERE):
    return block(
        "Keep it if you trust the program it starts. Stricter: remove `notify` if you don't need notifications.",
        "delete the `notify` setting, including any lines its list continues on",
        f"Edit {file} to remove the `notify` setting",
        f"In {where}, the first item in the `notify` list is the program it starts; for a launcher such as `node` or "
        "`npx`, the next items name what runs. Find out who publishes it before you trust it.")


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

EXPECTED = {
    ("commands_without_prompts", "config-1:approval_policy"): commands("danger-full-access"),
    ("unrestricted_filesystem", "config-1:sandbox_mode"): sandbox(),
    ("automatic_tools", "config-1:approval_policy"): full_access_tools(),
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
    paragraphs = finding.split("\n\n")
    return "\n\n".join(paragraphs[2:-1])


def options(text):
    return [text.split("\n\n", 1)[0][len("*What to do:* "):]]


USER_READ_ONLY = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
USER_WORKSPACE = 'approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n'
COMMANDS_KEY = ("commands_without_prompts", "config-2:approval_policy")


class WhatToDoTests(ConfigCase):
    def test_profile_in_either_file_preserves_approval_and_gap_advice(self):
        profile = 'default_permissions=":read-only"\napproval_policy="on-request"\n'
        never = 'approval_policy="never"\n'
        cases = [(1, (never, profile), "`config-2`"), (2, (profile, never), "`config-1`"),
                 (1, (never, profile + 'sandbox_mode="read-only"\n'), "`config-2`"),
                 (1, (never, 'default_permissions=false\n'), "`config-2`"),
                 (2, (profile, never, profile), "`config-1`, `config-3`"),
                 (1, (never, '[permissions.dev]\n'), None)]
        for index, texts, selector_files in cases:
            with self.subTest(files=texts):
                report = self.run_cli(*self.files(*texts)).stdout
                finding = next(item for item in finding_items(report) if "Rule `commands_without_prompts`" in item)
                advice = what_to_do(finding)
                file = passed(f"config-{index}")
                self.assertEqual(advice, commands(file=file, where=file, profile=selector_files))
                gap = next(item for item in section(report, "Not checked").split("\n\n---\n\n")
                           if "**Not checked: your sandbox setting.**" in item and f"*File `config-{index}`*" in item)
                step = gap.split("*What to do:* ")[1].split("\n\n")[0]
                expected = (f"Review `default_permissions` in {selector_files} and any profile it names." if selector_files else
                            "Check the sandbox setting wherever you run Codex (the app or the command line). "
                            'To set it in a file, add `sandbox_mode = "workspace-write"` or `"read-only"` to your config file.')
                self.assertEqual(step, expected)
                self.assertIn("**Not checked: your permission profiles.** Stay-safe doesn't check permission profiles "
                              "or what commands they allow.", report)

        found = self.findings(*self.files(profile, never + 'sandbox_mode="workspace-write"\n'))
        project = passed("config-2")
        self.assertEqual(found[COMMANDS_KEY], commands("workspace-write", project, project, profile="`config-1`"))

    def run_cli(self, *args, env=None):
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=ROOT, env=env or {},
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(run.stderr, INCOMPLETE if run.returncode == 2 else "")
        return run

    def findings(self, *args, env=None):
        risks = json.loads(self.run_cli(*args, "--format", "json", env=env).stdout)["risks"]
        markdown = self.run_cli(*args, env=env).stdout
        found = {}
        for item in finding_items(markdown):
            trace = re.fullmatch(r"\*Rule `(\w+)` · (?:setting|rules entry) `(.+?)` = `.*`\*", item.split("\n\n")[-1])
            self.assertIsNotNone(trace, item)
            found[trace.groups()] = what_to_do(item)
        self.assertCountEqual(found, [(risk["rule"], risk["entry"]) for risk in risks])
        self.assertEqual(len(found), len(risks))
        return found

    def files(self, *texts):
        return [arg for index, text in enumerate(texts, 1)
                for arg in ("--config", str(self.config(text, f"file-{index}.toml")))]

    def explicit(self):
        return ["--config", str(self.config(FIRST, "first.toml")), "--config", str(self.config(SECOND, "second.toml")),
                "--rules", str(self.config(RULES, "selected.rules"))]

    def test_environment_check_lists_variable_names_without_values(self):
        found = self.findings(*self.explicit())
        check = found[("environment_inheritance", "config-1:shell_environment_policy")].split("\n\n")[-1]
        command = re.search(r"run `([^`]+)`", check).group(1)
        env = {"PATH": "/usr/bin:/bin", "SAFE_NAME": "visible-value", "MULTI_LINE": "first-line\nsecret-line\nx=y"}
        run = subprocess.run(["/bin/sh", "-c", command], env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        lines = run.stdout.splitlines()
        self.assertLessEqual(set(env), set(lines))
        for line in lines:
            self.assertRegex(line, r"^[A-Za-z_][A-Za-z0-9_]*$")
        for value in ("visible-value", "first-line", "secret-line", "x=y", "y"):
            self.assertNotIn(value, lines)

    def test_each_finding_gives_lower_friction_then_stricter_option_then_how_to_change_it(self):
        found = self.findings(*self.explicit())
        self.assertEqual(set(found), set(EXPECTED))
        for key, expected in EXPECTED.items():
            with self.subTest(rule=key[0], entry=key[1]):
                self.assertEqual(found[key], expected)

    def test_app_template_findings_cover_apps_the_file_does_not_name(self):
        text = ('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                '[apps._default]\ndefault_tools_approval_mode = "approve"\ndestructive_enabled = true\n')
        args = self.files(text)
        found = self.findings(*args)
        self.assertEqual(found[("automatic_tools", "config-1:apps._default")], block(
            'Set `default_tools_approval_mode = "writes"` (uses server hints). Stricter: '
            '`default_tools_approval_mode = "prompt"`. Apps you name without their own mode change too.',
            "under `[apps._default]`",
            f'Edit {FILE} to set `default_tools_approval_mode = "writes"` under `[apps._default]`'))
        self.assertEqual(found[("destructive_tools", "config-1:apps._default")], block(
            "Set `destructive_enabled = false` (tools marked as not destructive stay on; tools marked destructive, or "
            "not marked, turn off). Stricter: `enabled = false` (apps your config doesn't name turn off; apps you "
            "name stay on).",
            "under `[apps._default]`",
            f"Edit {FILE} to set `destructive_enabled = false` under `[apps._default]`"))
        markdown = self.run_cli(*args).stdout
        self.assertIn("**Apps your config doesn't name use tool approval mode `approve`, set in `apps._default`.** "
                      "Untrusted tool content could lead to unwanted actions.", markdown)
        self.assertIn("**Apps your config doesn't name have tools that can change or delete data turned on, set in "
                      "`apps._default`.** A mistaken operation could change or delete data in the connected service.",
                      markdown)
        self.assertNotIn("`_default` app", markdown)

    def test_shared_note_keeps_approval_outcomes_unassessed_for_each_policy(self):
        never = 'approval_policy = "never"\n'
        on_request = 'approval_policy = "on-request"\n'
        for policies in ((never,), (on_request,), ("",), (never, on_request)):
            with self.subTest(policies=policies):
                paths = [self.config(text, f"policy-{index}.toml") for index, text in enumerate(policies)]
                markdown = render(inspect(paths), "markdown")
                self.assertEqual(section(markdown, "Findings").split("\n\n", 1)[0].split(),
                                 NOTE.format(placeholders=PLACEHOLDERS).split())
                self.assertEqual(markdown.count(NOTE_LABEL), 1)
        clean = self.run_cli("--config", str(self.config('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                                                            'shell_environment_policy = { inherit = "core" }\n'
                                                            'features = { apps = false }\n'))).stdout
        self.assertNotIn(NOTE_LABEL, clean)

    def test_commands_advice_never_loosens_the_configured_sandbox(self):
        for sandbox_mode in ("read-only", "workspace-write", "danger-full-access", None):
            with self.subTest(sandbox_mode=sandbox_mode):
                text = 'approval_policy = "never"\n' + (f'sandbox_mode = "{sandbox_mode}"\n' if sandbox_mode else "")
                found = self.findings("--config", str(self.config(text)))
                self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")], commands(sandbox_mode))

    def test_full_access_findings_on_the_approval_policy_say_to_change_the_sandbox(self):
        args = ("--config", str(self.config('approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n')))
        found = self.findings(*args)
        self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")], block(
            'Set `sandbox_mode = "workspace-write"` and keep `approval_policy = "on-request"` (commands can write in '
            f'your workspace and in any extra folders in `writable_roots`, so review that list). {ORDINARY} Stricter: '
            '`sandbox_mode = "read-only"` (commands '
            "can't write files). Either way, commands a saved approval allows still run outside the sandbox.",
            "`sandbox_mode` " + TOP,
            f'Edit {FILE} to set `sandbox_mode = "workspace-write"` without changing `approval_policy`',
            f"Look for `approval_policy` and `sandbox_mode` in {WHERE}."))
        self.assertIn("**With these settings, Codex runs most commands without asking you.** With "
                      '`sandbox_mode = "danger-full-access"`, ordinary commands can run without asking, including ones '
                      "that delete or change files. For commands without a matching rule, Codex asks first only if it "
                      "flags the command as dangerous, such as a forced `rm`.", self.run_cli(*args).stdout)
        found = self.findings("--config", str(self.config('approval_policy = "never"\nsandbox_mode = "danger-full-access"\n')))
        self.assertEqual(found[("automatic_tools", "config-1:approval_policy")], full_access_tools())

    def test_following_the_sandbox_advice_with_writable_roots_leaves_them_to_review(self):
        roots = '[sandbox_workspace_write]\nwritable_roots = ["/outside-project"]\n'
        gap = ("config-1: sandbox_workspace_write.writable_roots lists extra folders commands may write, "
               "some possibly outside the workspace. Their paths are withheld. "
               "No --workspace was supplied to check project .codex. The folders' other effects were not assessed.")
        for approval, key in (("on-request", ("commands_without_prompts", "config-1:approval_policy")), ("never", ("automatic_tools", "config-1:approval_policy"))):
            with self.subTest(approval=approval):
                server = '[mcp_servers.search]\nurl = "https://example.invalid/mcp"\n' if approval == "never" else ""
                before = f'approval_policy = "{approval}"\nsandbox_mode = "danger-full-access"\n' + server + roots
                self.assertIn("`writable_roots`", self.findings("--config", str(self.config(before)))[key])
                after = self.config(before.replace("danger-full-access", "workspace-write"))
                report = json.loads(self.run_cli("--config", str(after), "--format", "json").stdout)
                self.assertNotIn(key, [(r["rule"], r["entry"]) for r in report["risks"]])
                self.assertIn(gap, report["inspection_gaps"])
                self.assertNotIn("outside-project", json.dumps(report))

    def test_advice_never_loosens_a_sandbox_another_inspected_file_sets(self):
        first, second = passed("config-1"), passed("config-2")
        commands_1 = ("commands_without_prompts", "config-1:approval_policy")
        never = 'approval_policy = "never"\n'
        cases = [
            ((USER_READ_ONLY, never),
             {COMMANDS_KEY: commands(file=second, where=second, other=("read-only", "config-1"))}),
            ((USER_WORKSPACE, never), {COMMANDS_KEY: commands(file=second, where=second)}),
            ((USER_READ_ONLY, never + 'sandbox_mode = "workspace-write"\n'),
             {COMMANDS_KEY: commands("workspace-write", second, second)}),
            ((USER_READ_ONLY, never + 'sandbox_mode = "danger-full-access"\n'),
             {COMMANDS_KEY: commands(file=second, where=second, other=("read-only", "config-1")),
              ("unrestricted_filesystem", "config-2:sandbox_mode"): sandbox(second, other="config-1")}),
            ((USER_WORKSPACE, 'approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n'),
             {("unrestricted_filesystem", "config-2:sandbox_mode"): sandbox(second)}),
            ((never, USER_READ_ONLY), {commands_1: commands(file=first, where=first, other=("read-only", "config-2"))}),
            ((never, USER_WORKSPACE, USER_READ_ONLY),
             {commands_1: commands(file=first, where=first, other=("read-only", "config-3"))}),
            ((never + 'sandbox_mode="danger-full-access"\n', 'default_permissions="dev"\nsandbox_mode="read-only"\n'),
             {commands_1: commands("danger-full-access", first, first, profile="`config-2`"),
              ("unrestricted_filesystem", "config-1:sandbox_mode"): sandbox(first, other="config-2")}),
        ]
        for texts, expected in cases:
            with self.subTest(files=texts):
                found = self.findings(*self.files(*texts))
                for key, text in expected.items():
                    self.assertEqual(found[key], text, key)

    def test_full_access_advice_matches_the_read_only_edit_when_another_file_sets_read_only(self):
        first = passed("config-1")
        read_only = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
        for approval, key in (("on-request", ("commands_without_prompts", "config-1:approval_policy")),
                              ("never", ("automatic_tools", "config-1:approval_policy"))):
            full = f'approval_policy = "{approval}"\nsandbox_mode = "danger-full-access"\n'
            with self.subTest(approval=approval, files="with read-only"):
                found = self.findings(*self.files(full, read_only))
                self.assertEqual(found[("unrestricted_filesystem", "config-1:sandbox_mode")], sandbox(first, other="config-2"))
                what = found[key]
                self.assertTrue(what.startswith('*What to do:* Set `sandbox_mode = "read-only"`, as `config-2` does'), what)
                self.assertIn(f'ask Codex: "Edit {first} to set `sandbox_mode = "read-only"` without changing '
                              '`approval_policy`', what)
                self.assertNotIn("workspace-write", what)
                if approval == "on-request":
                    self.assertEqual(what, block(
                        'Set `sandbox_mode = "read-only"`, as `config-2` does, and keep `approval_policy = "on-request"` '
                        f"(commands can't write files). {ORDINARY} But {SAVED_STILL}",
                        "`sandbox_mode` " + TOP,
                        f'Edit {first} to set `sandbox_mode = "read-only"` without changing `approval_policy`',
                        f"Look for `approval_policy` and `sandbox_mode` in {first}."))
            with self.subTest(approval=approval, files="alone"):
                what = self.findings(*self.files(full))[key]
                self.assertTrue(what.startswith('*What to do:* Set `sandbox_mode = "workspace-write"`'), what)

    def test_a_selected_permission_profile_gets_no_sandbox_mode_advice(self):
        for mode in (None, "read-only", "danger-full-access"):
            with self.subTest(sandbox_mode=mode):
                text = 'approval_policy = "never"\ndefault_permissions = "work"\n'
                if mode:
                    text += f'sandbox_mode="{mode}"\n'
                found = self.findings("--config", str(self.config(text)))
                self.assertEqual(found[("commands_without_prompts", "config-1:approval_policy")],
                                 commands(mode, profile="`config-1`"))
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
                self.assertEqual(section(markdown, "Findings").split("\n\n", 1)[0].split(),
                                 NOTE.format(placeholders="").split())
                found = self.findings(env={variable: str(home)})
                file, rules = f"`{base}/config.toml`", f"`{base}/rules/default.rules`"
                self.assertEqual(found, {
                    ("commands_without_prompts", "config-1:approval_policy"):
                        commands("danger-full-access", file, file),
                    ("unrestricted_filesystem", "config-1:sandbox_mode"): sandbox(file),
                    ("automatic_tools", "config-1:approval_policy"): full_access_tools(file),
                    ("configured_program", "config-1:notify"): notify(file, file),
                    ("configured_program", "config-1:mcp_servers.github"): program_server("github", file, file),
                    ("self_described_tools", "config-1:mcp_servers.github"):
                        labels_group("MCP server", "github", "mcp_servers.github", file),
                    ("environment_inheritance", "config-1:shell_environment_policy"): environment(file),
                    ("saved_approval", "rules-1:prefix_rule.1"): saved(1, rules),
                })
