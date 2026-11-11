"""Each Markdown gap leads with what stay-safe could not check and why, then what to do, then its file label
(archived issue #105 and its reading check).

The JSON gap texts are unchanged; the expected Markdown wording below restates each one in the style of the
issue's After example ("Not checked: your approval setting."), written from the gap's meaning, not copied from
the report.
"""

import json
import subprocess
import sys

from stay_safe.report import inspect, markdown
from tests.support import ConfigCase, ROOT, items, section, gap_items

WITHHELD = "The value is left out of this report."
# JSON gap text, without its source label -> expected Markdown lead.
PLAIN = {
    # Reading a configuration file
    "Input is not a regular file.":
        "**Not checked: your config file.** It isn't a regular file, so stay-safe didn't read it.",
    "Input exceeds the 1 MiB size limit.":
        "**Not checked: your config file.** It's larger than 1 MiB, so stay-safe didn't read any of it.",
    "Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.":
        "**Not checked: your config file.** stay-safe couldn't read it: it's missing, unreadable, a symlink, or "
        "not valid UTF-8 TOML. Error details are left out of this report.",
    # Approval, sandbox and profiles
    "approval_policy is absent; the reader does not infer its effective value.":
        "**Not checked: your approval setting.** `approval_policy` isn't in your config file, so stay-safe can't "
        "tell whether Codex asks before running commands.",
    "approval_policy has a known but unhandled value; its behavior is not evaluated.":
        "**Not checked: your approval setting.** stay-safe recognizes your `approval_policy` value but doesn't "
        "assess it, so it can't tell when Codex asks before running commands.",
    "approval_policy is unsupported or invalid; its value was withheld.":
        "**Not checked: your approval setting.** Your `approval_policy` value isn't one stay-safe supports, so it "
        f"can't tell whether Codex asks before running commands. {WITHHELD}",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "**Not checked: your sandbox setting.** `sandbox_mode` isn't in your config file, so stay-safe can't tell "
        "what commands Codex runs are allowed to do.",
    "sandbox_mode is unsupported or invalid; its value was withheld.":
        "**Not checked: your sandbox setting.** Your `sandbox_mode` value isn't one stay-safe supports, so it "
        f"can't tell what commands Codex runs are allowed to do. {WITHHELD}",
    "Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.":
        "**Not checked: your permission profiles.** Your config file has named permission profiles, which "
        "stay-safe doesn't read. They can change what commands are allowed to do, so your sandbox settings may "
        "not show what commands can really do.",
    "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.":
        "**Not checked: which sandbox Codex uses.** Your config file sets both `default_permissions` and "
        "`sandbox_mode`, so stay-safe can't tell which one Codex uses.",
    "Profiles are outside reader coverage; a selected profile can override the reported settings.":
        "**Not checked: your profiles.** Your config file has profiles, which stay-safe doesn't read. A profile "
        "Codex uses can override the settings in this report.",
    # Shell environment
    "shell_environment_policy.inherit is unsupported or invalid; its value was withheld.":
        "**Not checked: whether commands get your environment variables.** Your "
        f"`shell_environment_policy.inherit` value isn't one stay-safe supports. {WITHHELD}",
    "shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown.":
        "**Not checked: whether commands get your environment variables.** Your "
        "`shell_environment_policy.ignore_default_excludes` isn't true or false.",
    # Tables, fields and names, for each label they occur with
    **{f"{label} must be a table.":
       f"**Not checked: your `{label}` settings.** `{label}` isn't written as a group of settings, such as a "
       "`[section]`, so stay-safe couldn't read the settings in it."
       for label in ("sandbox_workspace_write", "shell_environment_policy", "mcp_servers", "apps", "apps._default",
                     "tools", "model_providers", "hooks", "features")},
    "Configuration contains fields outside reader coverage; their values were withheld.":
        "**Not checked: some settings in your config file.** Some settings in your config file aren't ones "
        "stay-safe reads, so it can't tell what they change. Their values are left out of this report.",
    **{f"{label} contains fields outside reader coverage; their values were withheld.":
       f"**Not checked: some `{label}` settings.** Some fields in `{label}` aren't ones stay-safe reads, so it "
       "can't tell what they change. Their values are left out of this report."
       for label in ("sandbox_workspace_write", "shell_environment_policy", "mcp_servers", "apps", "apps._default",
                     "tools", "hooks", "features")},
    **{f"{label} has an invalid boolean; its behavior is unknown.":
       f"**Not checked: an on/off setting in `{label}`.** A setting in `{label}` that should be true or false "
       "isn't, so stay-safe can't tell what it does."
       for label in ("sandbox_workspace_write", "mcp_servers", "apps", "tools")},
    **{f"{label} contains a name that cannot be included in a shareable report.":
       f"**Not checked: an entry in `{label}`.** Its name looks like it could be private, such as an address or "
       "a key, so stay-safe left the entry out of this report."
       for label in ("mcp_servers", "apps", "tools", "model_providers")},
    **{f"{label} contains an entry that is not a table.":
       f"**Not checked: an entry in `{label}`.** It isn't written as a group of settings, such as a `[section]`, "
       "so stay-safe couldn't read it."
       for label in ("mcp_servers", "apps", "tools", "model_providers")},
    # MCP servers, apps and tools
    "A tool approval mode is unsupported or invalid; its value was withheld.":
        "**Not checked: a tool approval setting.** A `default_tools_approval_mode` value isn't one stay-safe "
        f"supports, so it can't tell when Codex asks before using those tools. {WITHHELD}",
    "A per-tool approval mode is unsupported or invalid; its value was withheld.":
        "**Not checked: a tool approval setting.** A tool's `approval_mode` value isn't one stay-safe supports, "
        f"so it can't tell when Codex asks before using that tool. {WITHHELD}",
    "A tool allow/deny list contains a name that cannot be included in a shareable report.":
        "**Not shown: a tool name in an allow or deny list.** A name in `enabled_tools` or `disabled_tools` looks "
        "like it could be private, so it's left out of this report.",
    "A tool allow/deny list is invalid; tool availability is unknown.":
        "**Not checked: which tools are available.** An `enabled_tools` or `disabled_tools` list isn't a list of "
        "names, so stay-safe can't tell which tools Codex can use.",
    "An MCP transport is missing, conflicting or invalid.":
        "**Not checked: how an MCP server connects.** An MCP server needs either a `command` or a `url`; this one "
        "has neither, both, or an invalid one, so stay-safe can't tell how it connects.",
    "An MCP header-helper command is invalid; its value was withheld.":
        "**Not checked: an MCP header-helper command.** An `http_headers_helper` value isn't a valid command, so "
        f"stay-safe didn't assess it. {WITHHELD}",
    "apps has an invalid destructive_enabled flag.":
        "**Not checked: an app's `destructive_enabled` setting.** It isn't true or false, so stay-safe can't tell "
        "whether that app's tools that change or delete data are turned on.",
    "Per-account app policy is not evaluated; account identifiers were withheld.":
        "**Not checked: per-account app settings.** An app has per-account settings (`links`), which stay-safe "
        "doesn't assess. Account identifiers are left out of this report.",
    "Model-provider command-backed authentication is outside reader coverage.":
        "**Not checked: a model provider's sign-in command.** A model provider gets its credentials by running a "
        "command (`auth`), which stay-safe doesn't assess.",
    # notify and hooks
    "notify is not a command list with a nonempty program.":
        "**Not checked: your `notify` setting.** It isn't a list that starts with a program name, so stay-safe "
        "can't tell whether it starts a program.",
    "hooks contains an invalid event configuration.":
        "**Not checked: a hook event.** A hook event in your config file isn't a list, so stay-safe couldn't read "
        "its hooks.",
    "hooks contains an invalid handler group.":
        "**Not checked: a group of hooks.** A hook group in your config file isn't in the expected form, so "
        "stay-safe couldn't read the hooks in it.",
    "Hook execution policy is outside reader coverage.":
        "**Not checked: whether your hooks are trusted and turned on.** stay-safe doesn't read the settings that "
        "decide whether Codex runs your hooks, so it treats each hook command as able to run.",
    "web_search is unsupported or invalid; its value was withheld.":
        f"**Not checked: your web search setting.** Your `web_search` value isn't one stay-safe supports. {WITHHELD}",
    # Rules files
    "Rules input is not a regular file.":
        "**Not checked: your rules file.** It isn't a regular file, so stay-safe didn't read it.",
    "Rules input exceeds the 1 MiB size limit.":
        "**Not checked: your rules file.** It's larger than 1 MiB, so stay-safe didn't read any of it.",
    "Selected rules input is missing; its path was withheld.":
        "**Not checked: your rules file.** The rules file you selected doesn't exist. Its path is left out of "
        "this report.",
    "Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.":
        "**Not checked: your rules file.** stay-safe couldn't read it: it's unreadable, a symlink, or not valid "
        "UTF-8. Error details are left out of this report.",
    "Rules contain lines that are not inspected.":
        "**Not checked: some lines in your rules file.** stay-safe reads only one-line saved approvals. Other "
        "lines, such as rules that ask first or forbid a command, could change what the listed approvals do.",
    "The rules directory cannot be listed; other rules files may exist and were not inspected.":
        "**Not checked: other rules files.** stay-safe couldn't list your `rules` folder, so there may be rules "
        "files it didn't read.",
    "Other rules files exist and were not inspected.":
        "**Not checked: other rules files.** Your `rules` folder has other `.rules` files besides "
        "`default.rules`. Codex reads them too, but stay-safe doesn't.",
    # The Codex home
    "Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; "
    "Codex would not start, so no default files were inspected.":
        "**Not checked: your Codex folder.** `CODEX_HOME` points to something that's missing, isn't a folder or "
        "can't be checked. Codex wouldn't start, so stay-safe read no files.",
    "Codex home: CODEX_HOME is unset and the home directory cannot be determined; no default files were inspected.":
        "**Not checked: your Codex folder.** `CODEX_HOME` isn't set and stay-safe couldn't find your home "
        "folder, so it read no files.",
    "System config folder: /etc/codex holds Codex configuration that was not inspected.":
        "**Not checked: Codex's system folder.** `/etc/codex` holds Codex settings, hooks or rules that stay-safe "
        "doesn't read.",
    # Archived issues #116 and #121 (harnesses/codex.md row `features.apps`).
    "Codex home: plugins/cache holds Codex plugins that were not inspected.":
        "**Not checked: your Codex plugins.** Your Codex folder has plugins in `plugins/cache`, which stay-safe "
        "doesn't read.",
    "features.apps has an invalid boolean; its behavior is unknown.":
        "**Not checked: the ChatGPT Apps connection.** Your `features.apps` isn't true or false, so stay-safe can't "
        "tell whether Codex adds the ChatGPT Apps connection.",
    "Codex home: hooks.json exists and was not inspected.":
        "**Not checked: your `hooks.json` file.** Your Codex folder has a `hooks.json` file, which stay-safe "
        "doesn't read.",
    # stay-safe's own files
    "Committed incident citations are incomplete; source links are unavailable.":
        "**Not checked: some cited incidents.** stay-safe couldn't find every cited incident in its incident list, "
        "so those incidents appear without links.",
    **{f"Incomplete fingerprint: {name} could not be read.":
       f"**Not checked: stay-safe's own file `{name}`.** stay-safe couldn't read it, so the fingerprint that "
       "identifies this version of stay-safe is incomplete."
       for name in ("stay_safe/__init__.py", "harnesses/codex.md", "incidents.md")},
    "Revision unknown; checkout source links are withheld.":
        "**Not checked: which version of stay-safe made this report.** stay-safe couldn't tell which commit it's "
        "running from, so links to its rules, evidence and incidents are left out.",
}
# With no Codex config file found, the two absent-setting gaps say so instead (archived issue #105 review F2).
ABSENT = {
    "approval_policy is absent; the reader does not infer its effective value.":
        "**Not checked: your approval setting.** stay-safe found no Codex config file, so it can't tell whether "
        "Codex asks before running commands.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "**Not checked: your sandbox setting.** stay-safe found no Codex config file, so it can't tell what "
        "commands Codex runs are allowed to do.",
}
# JSON gap text -> the follow-up the reader can act on (reading check, 2026-11-09), from the meanings table and docs/usage.md.
STEPS = {
    "Input is not a regular file.": "Make sure the path is a regular file, then run stay-safe again.",
    "Input exceeds the 1 MiB size limit.": "Check that you selected the right file and that it's under 1 MiB.",
    "Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.":
        "Check that the file exists, is readable and is valid TOML; for a symlink, select the file it points to.",
    "approval_policy is absent; the reader does not infer its effective value.":
        "Check the approval setting wherever you run Codex (the app or the command line). To set it in a file, add "
        "`approval_policy = \"on-request\"` to your config file.",
    "approval_policy has a known but unhandled value; its behavior is not evaluated.":
        "Review this setting yourself, or switch to `\"on-request\"`, which stay-safe can assess.",
    "approval_policy is unsupported or invalid; its value was withheld.":
        "Set it to a supported value such as `\"on-request\"`.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "Check the sandbox setting wherever you run Codex (the app or the command line). To set it in a file, add "
        "`sandbox_mode = \"workspace-write\"` or `\"read-only\"` to your config file.",
    "sandbox_mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"read-only\"`, `\"workspace-write\"` or `\"danger-full-access\"`.",
    "Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.":
        "Review your permission profiles yourself; findings about this file's sandbox may not apply.",
    "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.":
        "Keep only one of `default_permissions` and `sandbox_mode`, then run stay-safe again.",
    "Profiles are outside reader coverage; a selected profile can override the reported settings.":
        "Review your profiles yourself, especially their approval and sandbox settings.",
    "shell_environment_policy.inherit is unsupported or invalid; its value was withheld.":
        "Set `inherit` to `\"all\"`, `\"core\"` or `\"none\"`.",
    "shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown.":
        "Set `ignore_default_excludes` to `true` or `false`.",
    "Configuration contains fields outside reader coverage; their values were withheld.":
        "Review those settings yourself; stay-safe didn't evaluate them.",
    **{message: "Rewrite it as a group of settings, then run stay-safe again."
       for message in PLAIN if message.endswith((" must be a table.", " contains an entry that is not a table."))},
    **{message: f"Review the other settings under `{message.split(' ', 1)[0]}` yourself; stay-safe didn't evaluate them."
       for message in PLAIN if message.endswith(" contains fields outside reader coverage; their values were withheld.")
       and not message.startswith("Configuration ")},
    **{message: "Set it to `true` or `false`."
       for message in PLAIN if message.endswith(" has an invalid boolean; its behavior is unknown.")
       and not message.startswith("shell_environment_policy")},
    **{message: "Review that entry yourself, since it isn't in this report."
       for message in PLAIN if message.endswith(" contains a name that cannot be included in a shareable report.")
       and not message.startswith("A tool")},
    "A tool approval mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"auto\"`, `\"prompt\"`, `\"writes\"` or `\"approve\"`; `\"prompt\"` asks before every call "
        "unless `approval_policy = \"never\"`.",
    "A per-tool approval mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"auto\"`, `\"prompt\"`, `\"writes\"` or `\"approve\"`; `\"prompt\"` asks before every call "
        "unless `approval_policy = \"never\"`.",
    "A tool allow/deny list contains a name that cannot be included in a shareable report.":
        "Review the full list in your config file yourself.",
    "A tool allow/deny list is invalid; tool availability is unknown.":
        "Make `enabled_tools` and `disabled_tools` lists of tool names.",
    "An MCP transport is missing, conflicting or invalid.": "Give the server either a `command` or a `url`, not both.",
    "An MCP header-helper command is invalid; its value was withheld.":
        "Set `http_headers_helper` to the command you mean to run, or remove it.",
    "apps has an invalid destructive_enabled flag.": "Set `destructive_enabled` to `true` or `false`.",
    "Per-account app policy is not evaluated; account identifiers were withheld.":
        "Review those per-account settings yourself.",
    "Model-provider command-backed authentication is outside reader coverage.":
        "Review that command yourself; stay-safe doesn't check it.",
    "notify is not a command list with a nonempty program.":
        "Write `notify` as a list that starts with the program, or remove it.",
    "hooks contains an invalid event configuration.": "Write each hook event as a list of hook groups, or remove it.",
    "hooks contains an invalid handler group.": "Fix or remove that hook group.",
    "Hook execution policy is outside reader coverage.":
        "Check which hooks Codex trusts and has turned on, and remove any you don't use.",
    "web_search is unsupported or invalid; its value was withheld.":
        "Set it to `\"disabled\"`, `\"cached\"`, `\"indexed\"` or `\"live\"`.",
    "Rules input is not a regular file.": "Select the rules file itself with `--rules`.",
    "Rules input exceeds the 1 MiB size limit.": "Check that you selected the right rules file and that it's under 1 MiB.",
    "Selected rules input is missing; its path was withheld.": "Check the path you gave with `--rules`.",
    "Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.":
        "Check that the file is readable and valid UTF-8; for a symlink, select the file it points to.",
    "Rules contain lines that are not inspected.":
        "Review the other lines in your rules file yourself, especially rules that ask first or forbid a command.",
    "The rules directory cannot be listed; other rules files may exist and were not inspected.":
        "Check that `rules` in your Codex folder is a folder you can read, then run stay-safe again.",
    "Other rules files exist and were not inspected.":
        "Review the other `.rules` files yourself, or check one with `--rules`.",
    "Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; "
    "Codex would not start, so no default files were inspected.":
        "Point `CODEX_HOME` at your Codex folder, or unset it to use `~/.codex`.",
    "Codex home: CODEX_HOME is unset and the home directory cannot be determined; no default files were inspected.":
        "Set `HOME` or `CODEX_HOME`, or select files with `--config` and `--rules`.",
    "Codex home: hooks.json exists and was not inspected.": "Review the hooks in `hooks.json` yourself.",
    "Codex home: plugins/cache holds Codex plugins that were not inspected.":
        "Review the plugins in `plugins/cache` yourself.",
    "features.apps has an invalid boolean; its behavior is unknown.": "Set `features.apps` to `true` or `false`.",
    "System config folder: /etc/codex holds Codex configuration that was not inspected.":
        "Review the files in `/etc/codex` yourself.",
    "Committed incident citations are incomplete; source links are unavailable.":
        "Get a fresh copy of stay-safe so its incident list is complete.",
    **{message: "Restore that file, for example by cloning stay-safe again."
       for message in PLAIN if message.startswith("Incomplete fingerprint:")},
    "Revision unknown; checkout source links are withheld.":
        "Run stay-safe from a git clone so the report can link to the exact version.",
}
# With no Codex config file found, the follow-up says to create one (re-review F11, owner direction).
ABSENT_STEPS = {
    "approval_policy is absent; the reader does not infer its effective value.":
        "Check the approval setting wherever you run Codex (the app or the command line). To set it in a file, "
        "create `~/.codex/config.toml` (or `config.toml` in the folder `CODEX_HOME` names) with "
        "`approval_policy = \"on-request\"`.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "Check the sandbox setting wherever you run Codex (the app or the command line). To set it in a file, "
        "create `~/.codex/config.toml` (or `config.toml` in the folder `CODEX_HOME` names) with "
        "`sandbox_mode = \"workspace-write\"` or `\"read-only\"`.",
}
RULES_GAPS = {message for message in PLAIN if message.startswith(("Rules", "Selected rules", "The rules", "Other rules"))}
UNSOURCED = {message for message in PLAIN
             if message.startswith(("Codex home:", "System config folder:", "Committed", "Incomplete", "Revision"))}


def gap_text(gap, absent=False, file=None):
    """The expected Markdown paragraph for a JSON gap: its plain lead, what to do, then its file label, if any.

    absent: the gap's source is a Codex config file that automatic discovery did not find.
    file: how the report names an automatically found file, such as `~/.codex/config.toml`; files you pass keep
    their source label, such as `config-1` (reading check, 2026-11-09).
    """
    source, _, message = gap.partition(": ")
    if source.startswith(("config-", "rules-")):
        lead, step = ((ABSENT[message], ABSENT_STEPS[message]) if absent and message in ABSENT
                      else (PLAIN[message], STEPS[message]))
        return f"{lead}\n\n*What to do:* {step}\n\n*File `{file or source}`*"
    return f"{PLAIN[gap]}\n\n*What to do:* {STEPS[gap]}"


def labelled(message):
    if message in UNSOURCED:
        return message
    return ("rules-1: " if message in RULES_GAPS else "config-2: ") + message


class PlainGapTests(ConfigCase):
    def test_absent_settings_say_there_is_no_config_file_when_none_was_found(self):
        self.require_no_system_folder()
        home = self.root / "empty-codex-home"
        home.mkdir()
        runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--format", f], cwd=ROOT,
                               env={"CODEX_HOME": str(home)}, text=True, capture_output=True, timeout=10)
                for f in ("json", "markdown")]
        gaps = json.loads(runs[0].stdout)["inspection_gaps"]
        self.assertCountEqual([gap.split(": ", 1)[1] for gap in gaps], ABSENT)
        self.assertEqual(gap_items(runs[1].stdout), [gap_text(gap, absent=True, file="$CODEX_HOME/config.toml")
                                                     for gap in gaps])
        self.assertNotIn("isn't in your config file", runs[1].stdout)

    def test_each_gap_leads_with_what_was_not_checked_then_its_source(self):
        report = inspect([])
        for message in PLAIN:
            with self.subTest(gap=message):
                report["inspection_gaps"] = [labelled(message)]
                self.assertEqual(gap_items(markdown(report)), [gap_text(labelled(message))])

    def test_every_gap_gets_its_own_paragraph_and_none_is_dropped(self):
        report = inspect([])
        report["inspection_gaps"] = [labelled(message) for message in PLAIN] + ["config-1: A future gap text."]
        self.assertEqual(gap_items(markdown(report)),
                         [gap_text(labelled(message)) for message in PLAIN]
                         + ["**Not checked:** A future gap text.\n\n*What to do:* Review this part of your setup "
                            "yourself.\n\n*File `config-1`*"])

    def test_gaps_from_real_inputs_keep_their_wording_and_order(self):
        config = self.config("""profile = "work"
future_setting = 1
approval_policy = "untrusted"
default_permissions = "team"
sandbox_mode = "everything"
notify = []
web_search = "sometimes"
shell_environment_policy = { inherit = "some", ignore_default_excludes = "no" }

[sandbox_workspace_write]
network_access = "yes"
future = 1

[mcp_servers]
oddity = 5

[mcp_servers.broken]
url = "https://seed-host.example"
command = "seed-command"
http_headers_helper = ""
enabled = "maybe"
future_option = 1
enabled_tools = [1]
default_tools_approval_mode = "sometimes"
tools = 5

[mcp_servers."sk-seed-secret"]
url = "https://seed-host.example"

[mcp_servers.listed]
url = "https://seed-host.example"
disabled_tools = ["sk-seed-tool"]

[mcp_servers.listed.tools.t]
approval_mode = "sometimes"

[model_providers.p]
auth = { command = "seed-auth" }

[apps.team]
destructive_enabled = "x"
links = { account = "seed-account" }

[hooks]
PreToolUse = 5
PostToolUse = [5]

[features]
apps = "maybe"
future_feature = 1
""")
        rules = self.config('prefix_rule(pattern=["curl"], decision="prompt")\n', "selected.rules")
        missing = self.root / "seed-missing.toml"
        # An existing file without approval or sandbox settings keeps "isn't in your config file".
        unset = self.config('model = "gpt-5"\n', "unset.toml")
        args = ["-B", "-m", "stay_safe", "--config", str(missing), "--config", str(config), "--config", str(unset),
                "--rules", str(rules)]
        runs = [subprocess.run([sys.executable, *args, "--format", f], cwd=ROOT, env={}, text=True,
                               capture_output=True, timeout=10) for f in ("json", "markdown")]
        gaps = json.loads(runs[0].stdout)["inspection_gaps"]
        self.assertGreaterEqual(len(gaps), 25)
        self.assertIn("config-3: approval_policy is absent; the reader does not infer its effective value.", gaps)
        self.assertEqual(gap_items(runs[1].stdout), [gap_text(gap) for gap in gaps])
        self.assertNotIn("seed-", runs[1].stdout)

