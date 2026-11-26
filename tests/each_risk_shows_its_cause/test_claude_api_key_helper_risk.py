import json

from tests.support import ConfigCase, agent_home, run_home

USER = {"permissions": {"defaultMode": "default"}}
PROJECT = {"apiKeyHelper": "seed-vault-token --id sk-seed"}
HEADLINE = "Claude Code can run the command in `apiKeyHelper` to get the credential it sends with model requests."
TRUST = (" Claude Code can use this helper without a trust prompt in `claude -p` or when a parent folder's trust "
         "extends to this folder.")


class ClaudeApiKeyHelperRiskTests(ConfigCase):
    def test_api_key_helper_finding_names_its_file_and_withholds_the_command(self):
        home = agent_home(self.root, claude=json.dumps(USER))
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(json.dumps(PROJECT), encoding="utf-8")
        run = run_home(home, "--agent", "claude", "--format", "json", cwd=project)
        report = json.loads(run.stdout)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([(risk["entry"], risk["explanation"]) for risk in report["risks"]],
                         [("settings-2:apiKeyHelper", HEADLINE + TRUST)])
        self.assertEqual({risk["rule"] for risk in report["risks"]}, {"configured_program"})
        markdown = run_home(home, "--agent", "claude", cwd=project).stdout
        self.assertIn("Remove `apiKeyHelper` from `.claude/settings.json` using a text editor.", markdown)
        self.assertIn("`git log -p -- .claude/`", markdown)
        self.assertNotIn("seed", (run.stdout + markdown).lower())

    def test_discovery_reports_the_project_helper_and_falls_back_to_the_user_helper(self):
        home = agent_home(self.root, claude=json.dumps({**USER, "apiKeyHelper": "seed-user"}))
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        path = project / ".claude" / "settings.json"
        path.write_text(json.dumps({**USER, **PROJECT}))
        args = ("--agent", "claude", "--format", "json")
        user, shared = "settings-1:apiKeyHelper", "settings-2:apiKeyHelper"

        def inspect(*extra):
            run = run_home(home, *args, *extra, cwd=project)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertNotIn("seed", run.stdout)
            report = json.loads(run.stdout)
            return ([risk["entry"] for risk in report["risks"]],
                    {e["id"]: e["observations"] for e in report["catalog"] if e["name"] == "apiKeyHelper"})

        findings, catalog = inspect()
        self.assertEqual(findings, [shared])
        self.assertEqual(catalog, {user: ["command withheld", "overridden by settings-2"],
                                   shared: ["command withheld", "project settings"]})
        independent, _ = inspect("--config", str(home / ".claude" / "settings.json"), "--config", str(path))
        self.assertEqual(independent, [user, shared])
        path.write_text("{}")
        self.assertEqual(inspect(), ([user], {user: ["command withheld"]}))

    def test_malformed_helper_explains_how_to_fix_it(self):
        home = agent_home(self.root, claude=json.dumps(USER))
        path = home / ".claude" / "settings.json"
        for value, reason in (("  ", "The value is blank. There is no command to check."),
                              ([], "The value is not text. Claude Code expects a command written as text.")):
            with self.subTest(value=value):
                path.write_text(json.dumps({**USER, "apiKeyHelper": value}))
                run = run_home(home, "--agent", "claude")
                self.assertEqual(run.returncode, 2)
                self.assertIn("**Not checked: `apiKeyHelper`.** " + reason, run.stdout)
                self.assertIn("Set `apiKeyHelper` to the command you want Claude Code to run, or remove the setting.",
                              run.stdout)
