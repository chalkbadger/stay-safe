import json

from tests.support import ConfigCase, agent_home, run_home

USER = {"permissions": {"defaultMode": "default"}}
PROJECT = {"fileSuggestion": {"type": "command", "command": "~/seed/file-index.sh"}}
HEADLINE = 'After you trust the workspace, Claude Code can run the command in `fileSuggestion` to suggest files when you type `@`. Trust inherited from a parent folder also counts.'


class ClaudeFileSuggestionRiskTests(ConfigCase):
    def test_file_suggestion_finding_names_its_file_and_withholds_the_command(self):
        home = agent_home(self.root, claude=json.dumps(USER))
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(json.dumps(PROJECT), encoding="utf-8")
        run = run_home(home, "--agent", "claude", "--format", "json", cwd=project)
        report = json.loads(run.stdout)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([(risk["entry"], risk["explanation"]) for risk in report["risks"]],
                         [("settings-2:fileSuggestion", HEADLINE)])
        self.assertEqual({risk["rule"] for risk in report["risks"]}, {"configured_program"})
        markdown = run_home(home, "--agent", "claude", cwd=project).stdout
        self.assertIn("Remove `fileSuggestion` from `.claude/settings.json` using a text editor.", markdown)
        self.assertIn("`fileSuggestion.command`", markdown)
        self.assertNotIn("seed", (run.stdout + markdown).lower())

    def test_a_project_disable_all_hooks_turns_off_a_user_file_suggestion(self):
        home = agent_home(self.root, claude=json.dumps({**USER, **PROJECT}))
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        settings = project / ".claude" / "settings.json"
        settings.with_name("settings.local.json").write_text(json.dumps({"disableAllHooks": False}), encoding="utf-8")
        settings.write_text(json.dumps({"disableAllHooks": True}), encoding="utf-8")
        report = json.loads(run_home(home, "--agent", "claude", "--format", "json", cwd=project).stdout)
        entries = {entry["name"]: entry["observations"] for entry in report["catalog"]}
        self.assertEqual(entries["fileSuggestion"], ["command withheld", "disableAllHooks is true in settings-2"])
        self.assertEqual(report["risks"], [])
        self.assertEqual(report["inspection_gaps"], [
            "The settings checked set disableAllHooks to true. The fileSuggestion command can still run if a "
            "higher-priority setting changes disableAllHooks to false. Check .claude/settings.local.json, "
            "any --settings used to start Claude Code, and your organization's managed settings. "
            "Managed settings can also supply their own command."
        ])
        markdown = run_home(home, "--agent", "claude", cwd=project).stdout
        self.assertIn("`.claude/settings.json` sets `disableAllHooks` to `true`.", markdown)
        self.assertIn("**The `fileSuggestion` command can still run** if a higher-priority setting changes `disableAllHooks` to `false`.", markdown)
        self.assertIn("Check `.claude/settings.local.json`, any `--settings` used to start Claude Code, and your organization's managed settings.", markdown)
        settings.write_text(json.dumps({"disableAllHooks": False}), encoding="utf-8")
        run = run_home(home, "--agent", "claude", "--format", "json", cwd=project)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([risk["entry"] for risk in json.loads(run.stdout)["risks"]], ["settings-1:fileSuggestion"])

    def test_precedence_fallback_trust_and_independent_files(self):
        home = agent_home(self.root, claude=json.dumps({**USER, **PROJECT}))
        user_file = home / ".claude/settings.json"
        project = self.root / "repo"
        path = project / ".claude/settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({**USER, **PROJECT}))
        user, shared = "settings-1:fileSuggestion", "settings-2:fileSuggestion"

        def inspect(*extra):
            run = run_home(home, "--agent", "claude", "--format", "json", *extra, cwd=project)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertNotIn("seed", run.stdout)
            report = json.loads(run.stdout)
            return ({r["entry"]: r["explanation"] for r in report["risks"]},
                    {e["id"]: e["observations"] for e in report["catalog"] if e["name"] == "fileSuggestion"})

        risks, entries = inspect()
        self.assertEqual(risks, {shared: HEADLINE})
        self.assertEqual(set(entries), {user, shared})
        self.assertIn("overridden by settings-2", entries[user])
        markdown = run_home(home, "--agent", "claude", cwd=project).stdout
        self.assertIn("The project file `.claude/settings.json` also sets `fileSuggestion`. "
                      "Its command takes precedence over the one in this file.", markdown)
        self.assertNotIn("seed", markdown)
        risks, _ = inspect("--config", str(user_file), "--config", str(path))
        self.assertEqual(risks, {user: HEADLINE, shared: HEADLINE})
        path.write_text("{}")
        risks, _ = inspect()
        self.assertEqual(risks, {user: HEADLINE})
        path.write_text(json.dumps({"fileSuggestion": {}}))
        run = run_home(home, "--agent", "claude", cwd=project)
        self.assertEqual(run.returncode, 2)
        self.assertIn('Set `fileSuggestion.type` to `"command"`.', run.stdout)
        self.assertIn("Then put the command you want to run in `fileSuggestion.command`.", run.stdout)
