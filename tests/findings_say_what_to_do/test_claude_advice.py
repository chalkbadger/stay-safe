import json
import re

from tests.support import ConfigCase, agent_home, items, run_home, section

SETTINGS = ('{"permissions": {"defaultMode": "bypassPermissions", "allow": ["Bash(*)", "Bash(git push:*)", '
            '"WebFetch(domain:seed-host.example)"]}, "sandbox": {"enabled": false}}')


class ClaudeAdviceTests(ConfigCase):
    def test_auto_mode_edit_is_conditional_on_user_settings(self):
        settings = '{"permissions":{"defaultMode":"auto"}}'
        home = agent_home(self.root, claude=settings)
        project = self.root / "project" / ".claude"
        project.mkdir(parents=True)
        for name in ("settings.json", "settings.local.json"):
            (project / name).write_text(settings)
        for path in (home / ".claude/settings.json", project / "settings.json", project / "settings.local.json"):
            with self.subTest(path=path):
                run = run_home(home, "--agent", "claude", "--config", str(path))
                self.assertEqual(run.returncode, 2, run.stderr)
                gap = section(run.stdout, "Claude Code not checked")
                self.assertIn("ignores `auto` in project and project-local settings", gap)
                advice = gap.split("*What to do:* ", 1)[1]
                self.assertTrue(advice.startswith("If this is your user settings file, set `permissions.defaultMode` "
                                                  "to `default`"), advice)

    def test_each_claude_code_finding_says_what_to_change_where_and_how_to_check(self):
        home = agent_home(self.root, claude=SETTINGS)
        run = run_home(home, "--agent", "claude")
        self.assertEqual(run.returncode, 0, run.stderr)
        found = items(section(run.stdout, "Claude Code findings").split("\n\n", 1)[1])
        steps = [[p for p in item.split("\n\n") if p.startswith(("*What to do:*", "*Change it:*", "*Check:*"))]
                 for item in found]
        self.assertEqual(steps, [
            ["*What to do:* Set `permissions.defaultMode` to `default` to stop requesting bypass in this file. "
             "Review any separate allow rules for actions you want to approve yourself.",
             "*Change it:* `permissions.defaultMode` in `~/.claude/settings.json`, or ask Claude Code: \"Edit "
             "`~/.claude/settings.json` to set `permissions.defaultMode` to `default`; show only what you change.\"",
             "*Check:* Look for `defaultMode` under `permissions` in `~/.claude/settings.json`. A `--permission-mode` "
             "flag or managed settings can still choose another mode."],
            ["*What to do:* Remove this rule and allow only the commands you run often, for example "
             "`Bash(npm run test *)`.",
             "*Change it:* rule 1 of `permissions.allow` in `~/.claude/settings.json`, or ask Claude Code: \"Show me "
             "rule 1 of `permissions.allow` in `~/.claude/settings.json` and remove it; show only what you change.\"",
             "*Check:* Look at `permissions.allow` in `~/.claude/settings.json`."],
            ["*What to do:* Check that this rule covers only the commands you meant, and remove it if you no longer "
             "need it.",
             "*Change it:* rule 2 of `permissions.allow` in `~/.claude/settings.json`, or ask Claude Code: \"Show me "
             "rule 2 of `permissions.allow` in `~/.claude/settings.json` and remove it; show only what you change.\"",
             "*Check:* Look at `permissions.allow` in `~/.claude/settings.json`."],
            ["*What to do:* Check that you trust the domains this rule covers, and remove the rule if you no longer need it.",
             "*Change it:* rule 3 of `permissions.allow` in `~/.claude/settings.json`, or ask Claude Code: \"Show me "
             "rule 3 of `permissions.allow` in `~/.claude/settings.json` and remove it; show only what you change.\"",
             "*Check:* Look at `permissions.allow` in `~/.claude/settings.json`."],
        ])
        self.assertNotIn("seed-host", run.stdout)
        self.assertTrue(all(re.match(r"### Claude Code finding \d+\n\n", item) for item in found))

    def test_all_domain_rule_gets_broad_advice_and_distinct_evidence(self):
        home = agent_home(self.root)
        for rule, scope in (("WebFetch", "every address"), ("WebFetch(domain:*)", "every domain"),
                            ("WebFetch(domain:private.example)", "addresses withheld")):
            with self.subTest(rule=rule):
                path = self.config(json.dumps({"permissions": {"defaultMode": "default", "allow": [rule]}}))
                args = ("--agent", "claude", "--config", str(path))
                report = json.loads(run_home(home, *args, "--format", "json").stdout)
                risk, = report["risks"]
                self.assertIn(scope, risk["configured_evidence"])
                text = run_home(home, *args).stdout
                finding = section(text, "Claude Code findings")
                advice = next(p for p in finding.split("\n\n") if p.startswith("*What to do:*"))
                if rule == "WebFetch":
                    self.assertIn("Remove", advice)
                    self.assertNotIn("domain:", advice)
                elif rule == "WebFetch(domain:*)":
                    self.assertIn("Remove", advice)
                    self.assertNotIn("limit it to", advice)
                    self.assertNotIn("domain:", advice)
                    for version in ("v2.1.172", "v2.1.186"):
                        self.assertIn(version, risk["explanation"])
                    self.assertIn(risk["explanation"], finding)
                else:
                    self.assertIn("trust", advice)
                self.assertNotIn("private.example", text)

    def test_switching_mode_explains_the_sandbox_approval_left_in_each_file(self):
        home = agent_home(self.root)
        args = ["--agent", "claude"]
        paths = []
        for i, sandbox in enumerate(({"enabled": True, "autoAllowBashIfSandboxed": True},
                                     {"enabled": True, "autoAllowBashIfSandboxed": False},
                                     {"enabled": True}, {"enabled": False, "autoAllowBashIfSandboxed": True},
                                     {"enabled": True, "autoAllowBashIfSandboxed": "bad"})):
            path = self.config(json.dumps({"permissions": {"defaultMode": "bypassPermissions"}, "sandbox": sandbox}),
                               f"selected-{i}.json")
            args.extend(("--config", str(path)))
            paths.append(path)
        report = run_home(home, *args)
        self.assertEqual(report.returncode, 2)
        findings = items(section(report.stdout, "Claude Code findings").split("\n\n", 1)[1])
        self.assertEqual(len(findings), 5)
        self.assertIn("autoAllowBashIfSandboxed", findings[0])
        self.assertIn("without a prompt", findings[0])
        self.assertNotIn("autoAllowBashIfSandboxed", findings[1])
        self.assertIn("v2.1.324", findings[2])
        self.assertNotIn("autoAllowBashIfSandboxed", findings[3])
        self.assertIn("autoAllowBashIfSandboxed", findings[4])
        self.assertIn("invalid", findings[4])
        self.assertNotIn("v2.1.324", findings[4])
        encoded = json.loads(run_home(home, *args, "--format", "json").stdout)
        for i, (finding, risk) in enumerate(zip(findings, encoded["risks"], strict=True)):
            self.assertIn(f"<settings-{i + 1}>", finding)
            self.assertIn(risk["explanation"], finding)
        selected = json.loads(paths[0].read_text())
        selected["permissions"]["defaultMode"] = "default"
        paths[0].write_text(json.dumps(selected))
        after = json.loads(run_home(home, "--agent", "claude", "--config", str(paths[0]), "--format", "json").stdout)
        self.assertEqual(after["risks"], [])
        self.assertIn(("sandbox.autoAllowBashIfSandboxed", ["true"]),
                      [(e["name"], e["observations"]) for e in after["catalog"]])

    def test_auto_mode_advice_identifies_bash_auto_approval_that_survives_the_edit(self):
        home = agent_home(self.root)
        settings = {"permissions": {"defaultMode": "auto"},
                    "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True}}
        enabled = self.config(json.dumps(settings), "enabled.json")
        regular = {**settings, "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": False}}
        disabled = self.config(json.dumps(regular), "disabled.json")
        args = ("--agent", "claude", "--config", str(enabled))
        before = run_home(home, *args, "--config", str(disabled))
        self.assertEqual(before.returncode, 2, before.stderr)
        warning, control = items(section(before.stdout, "Claude Code not checked").split("\n\n", 1)[1])
        self.assertIn("Not checked: auto mode", warning)
        self.assertIn("*File `settings-1`*", warning)
        self.assertIn("`permissions.defaultMode` to `default`", warning)
        self.assertIn("sandbox.autoAllowBashIfSandboxed", warning)
        self.assertIn("eligible sandboxed Bash commands can still run without a prompt", warning)
        self.assertIn("false", warning)
        self.assertIn("regular permission checks", warning)
        self.assertIn("Not checked: auto mode", control)
        self.assertIn("*File `settings-2`*", control)
        self.assertNotIn("without a prompt", control)

        settings["permissions"]["defaultMode"] = "default"
        enabled.write_text(json.dumps(settings))
        after = run_home(home, *args, "--format", "json")
        self.assertEqual(after.returncode, 0, after.stderr)
        report = json.loads(after.stdout)
        self.assertEqual(report["risks"], [])
        self.assertEqual(report["inspection_gaps"], [])
        self.assertIn(("sandbox.autoAllowBashIfSandboxed", ["true"]),
                      [(entry["name"], entry["observations"]) for entry in report["catalog"]])

    def test_program_settings_say_how_to_remove_them_and_where_to_look(self):
        home = agent_home(self.root, claude='{"permissions": {"defaultMode": "default"}, "hooks": {"PostToolUse": '
                                            '[{"matcher": "Edit", "hooks": [{"type": "command", "command": "seed-fmt"}]}]}}')
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(
            '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "seed-hook"}]}]}}')
        run = run_home(home, "--agent", "claude", cwd=project)
        self.assertEqual(run.returncode, 0, run.stderr)
        found = items(section(run.stdout, "Claude Code findings").split("\n\n", 1)[1])
        steps = [[p for p in item.split("\n\n") if p.startswith(("*What to do:*", "*Change it:*", "*Check:*"))]
                 for item in found]
        keep = ("*What to do:* Keep it if you trust the command it runs. Stricter: remove the setting if you don't "
                "use it.")
        script = ("If it runs a script file, check that file too: changes to the script don't show in {}. Find out who "
                  "wrote them before you trust them.")
        user = "hook 1 of matcher group 1 under `hooks.PostToolUse`"
        project = "hook 1 of matcher group 1 under `hooks.Stop`"
        self.assertEqual(steps, [
            [keep,
             f"*Change it:* in `~/.claude/settings.json`, remove {user}, or ask Claude Code: \"Show me {user} in "
             "`~/.claude/settings.json` and remove only that hook; show only what you change.\"",
             "*Check:* In `~/.claude/settings.json`, this hook's `command` is what it runs. "
             + script.format("`~/.claude/settings.json`")],
            [keep,
             f"*Change it:* in `.claude/settings.json`, remove {project}, or ask Claude Code: \"Show me {project} in "
             "`.claude/settings.json` and remove only that hook; show only what you change.\"",
             "*Check:* In `.claude/settings.json`, this hook's `command` is what it runs. "
             + script.format("`.claude/settings.json`")
             + " In a git repository, `git log -p -- .claude/` shows who changed the settings and scripts there."],
        ])
        self.assertNotIn("seed", run.stdout)
