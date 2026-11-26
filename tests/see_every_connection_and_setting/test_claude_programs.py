import json
import os
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import INCOMPLETE, ConfigCase, agent_home, run_home

HOOK = {"SessionStart": [{"hooks": [{"type": "command", "command": "seed-hook-command --token sk-seed"}]}]}
DECIDES = "can approve or change tool calls"
NEVER = "never runs: if is set on an event without tool calls"
MCP = "MCP tool hook; server and tool withheld"
UNKNOWN = ("hooks contains an event Claude Code doesn't document; its name was withheld and its hooks were not "
           "evaluated.")
EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "PostToolBatch",
          "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted", "Stop", "SessionEnd")


def read_file(*args, **kwargs):
    from stay_safe import claude
    return claude.read_file(*args, **kwargs)


class ClaudeProgramSettingsTests(ConfigCase):
    def read(self, settings, scope=None):
        path = self.config(json.dumps(settings), "settings.json")
        return read_file(path, "settings-1", **({"scope": scope} if scope else {}))

    def hooks(self, entries):
        return {entry["name"]: (entry["observations"],
                                entry["facts"].get("configured_program", entry["facts"].get("network_access")))
                for entry in entries if entry["kind"] == "hook"}

    def test_a_command_hook_on_any_event_is_listed_with_its_command_withheld(self):
        for event in EVENTS:
            with self.subTest(event=event):
                hooks = {event: [{"matcher": "*", "hooks": [{"type": "command", "command": "seed-hook-command"}]}]}
                entries, gaps = self.read({"permissions": {"defaultMode": "default"}, "hooks": hooks})
                line = f"{event}: matcher group 1, hook 1"
                if event in ("PreToolUse", "PermissionRequest"):
                    line += f"; {DECIDES}"
                self.assertEqual(self.hooks(entries), {"hooks": (["command withheld", line], True)})
                self.assertEqual(gaps, [])
                self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_project_settings_mark_hooks_and_take_the_mode_from_other_files(self):
        entries, gaps = self.read({"hooks": HOOK}, "project")
        self.assertEqual(self.hooks(entries), {"hooks": (
            ["command withheld", "SessionStart: matcher group 1, hook 1", "project settings"], True)})
        self.assertEqual(gaps, [])
        self.assertEqual([entry["name"] for entry in entries], ["hooks"])
        self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_disable_all_hooks_turns_off_hooks_in_the_same_file(self):
        entries, gaps = self.read({"permissions": {"defaultMode": "default"}, "hooks": HOOK, "disableAllHooks": True})
        self.assertEqual(self.hooks(entries), {"hooks": (
            ["command withheld", "SessionStart: matcher group 1, hook 1", "turned off by disableAllHooks in this file"],
            False)})
        self.assertIn(("disableAllHooks", ["true"]), [(e["name"], e["observations"]) for e in entries])

        entries, gaps = self.read({"hooks": HOOK, "disableAllHooks": "yes"})
        self.assertEqual(self.hooks(entries)["hooks"],
                         (["command withheld", "SessionStart: matcher group 1, hook 1"], True))
        self.assertIn(("disableAllHooks", ["not true or false"]), [(e["name"], e["observations"]) for e in entries])
        self.assertIn("settings-1: disableAllHooks has an invalid boolean; its behavior is unknown.", gaps)

    def test_if_filters_and_exec_form_are_noted_and_unknown_events_are_gaps(self):
        hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "seed", "if": "Bash(seed *)"}]}],
                 "PreToolUse": [{"hooks": [{"type": "command", "command": "seed", "if": "Bash(seed *)",
                                            "args": ["--seed"]}]}],
                 "Stop": [{"hooks": [{"type": "mcp_tool", "server": "seed", "tool": "seed", "if": "Bash(seed)"}]}],
                 "SesssionStart": [{"hooks": [{"type": "command", "command": "seed"}]}]}
        entries, gaps = self.read({"permissions": {"defaultMode": "default"}, "hooks": hooks})
        self.assertEqual(self.hooks(entries), {
            "hooks": (["command withheld", f"SessionStart: matcher group 1, hook 1; {NEVER}",
                       "PreToolUse: matcher group 1, hook 1; exec form; arguments withheld; runs only for matching "
                       f"tool calls; if rule withheld; {DECIDES}"], True),
            "hooks.mcp_tool": ([MCP, f"Stop: matcher group 1, hook 1; {NEVER}"], None)})
        self.assertEqual(gaps, [f"settings-1: {UNKNOWN}"])
        self.assertNotIn("Sesssion", json.dumps([entries, gaps]))
        self.assertNotIn("seed", json.dumps([entries, gaps]))

        only = {"SessionStart": hooks["SessionStart"]}
        entries, gaps = self.read({"permissions": {"defaultMode": "default"}, "hooks": only})
        self.assertEqual(self.hooks(entries),
                         {"hooks": (["command withheld", f"SessionStart: matcher group 1, hook 1; {NEVER}"], False)})

    def test_http_and_mcp_hooks_are_labelled_by_kind_and_event(self):
        http = {"type": "http", "url": "https://seed-host.example/hook"}
        hooks = {"PreToolUse": [{"hooks": [http, {**http, "async": True}]}],
                 "Stop": [{"hooks": [{"type": "mcp_tool", "server": "seed", "tool": "seed-tool"}]}]}
        entries, gaps = self.read({"permissions": {"defaultMode": "default"}, "hooks": hooks}, "project")
        self.assertEqual(self.hooks(entries), {
            "hooks.http": (["HTTP hook", "address withheld", f"PreToolUse: matcher group 1, hook 1; {DECIDES}",
                            f"PreToolUse: matcher group 1, hook 2; {DECIDES}", "project settings"], True),
            "hooks.mcp_tool": ([MCP, "Stop: matcher group 1, hook 1", "project settings"], None)})
        self.assertEqual(gaps, [])
        self.assertNotIn("seed", json.dumps([entries, gaps]))

        entries, _ = self.read({"hooks": hooks, "disableAllHooks": True})
        self.assertEqual(self.hooks(entries)["hooks.http"][1], False)

    def test_malformed_hooks_name_the_field(self):
        invalid = "hooks contains a handler that is not a valid hook; it was not evaluated."
        cases = {
            "hooks is not an object of hook events; its hooks were not evaluated.": {"hooks": []},
            "hooks contains an event that is not a list of matcher groups; it was not evaluated.":
                {"hooks": {"SessionStart": {}}},
            "hooks contains a matcher group without a list of handlers; it was not evaluated.":
                {"hooks": {"SessionStart": [{"matcher": "x"}]}},
            invalid: {"hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": "  "}, {"type": "http"}, {"type": "prompt", "prompt": ""},
                {"type": "seed"}, {"type": ["seed"]}, {"type": "command", "command": "seed", "args": "--seed"},
                {"type": "command", "command": "seed", "args": [1]}, {"type": "http", "url": "seed", "args": []},
                {"type": "command", "command": "seed", "if": 3}]}]}},
            "allowedHttpHookUrls is not a list of URL patterns; it was not evaluated.":
                {"allowedHttpHookUrls": "https://seed-host.example/*"},
        }
        for message, settings in cases.items():
            with self.subTest(message=message):
                entries, gaps = self.read({"permissions": {"defaultMode": "default"}, **settings})
                self.assertEqual(gaps, [f"settings-1: {message}"])
                self.assertEqual(self.hooks(entries), {})
                self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_unreadable_project_folder_is_a_named_gap(self):
        home = agent_home(self.root, claude='{"permissions": {"defaultMode": "default"}}')
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(json.dumps({"hooks": HOOK}), encoding="utf-8")
        original = os.listdir

        def listdir(path):
            if Path(path) == Path(".claude"):
                raise PermissionError(13, "Permission denied")
            return original(path)

        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(project)
        output, errors = StringIO(), StringIO()
        with patch.dict(os.environ, {"HOME": str(home)}, clear=True), \
                patch("stay_safe.cli.os.listdir", listdir), redirect_stdout(output), redirect_stderr(errors):
            status = main(["--agent", "claude", "--format", "json"])
        self.assertEqual((status, errors.getvalue()), (2, INCOMPLETE))
        report = json.loads(output.getvalue())
        self.assertEqual(report["sources_read"], ["settings-1"])
        self.assertEqual(report["inspection_gaps"],
                         ["The project's .claude folder could not be checked; its settings were not inspected."])
        self.assertEqual(report["risks"], [])
        self.assertNotIn("seed", json.dumps(report))

    def test_discovery_reads_the_project_file_in_the_current_folder_once(self):
        home = agent_home(self.root, claude='{"permissions": {"defaultMode": "default"}}')
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(json.dumps({"hooks": HOOK}), encoding="utf-8")
        run = run_home(home, "--agent", "claude", "--format", "json", cwd=project)
        report = json.loads(run.stdout)
        self.assertEqual((run.returncode, report["sources_read"]), (0, ["settings-1", "settings-2"]))

        run = run_home(home, "--agent", "claude", "--format", "json", cwd=home)
        self.assertEqual(json.loads(run.stdout)["sources_read"], ["settings-1"])
