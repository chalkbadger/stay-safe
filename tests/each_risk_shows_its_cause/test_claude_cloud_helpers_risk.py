import json

from tests.support import ConfigCase, agent_home, run_home

TIMING = {
    "awsAuthRefresh": "when the AWS credential check fails",
    "awsCredentialExport": "at session start and on each AWS credential reload",
    "gcpAuthRefresh": "when Google Cloud credentials expire or cannot be loaded",
    "otelHeadersHelper": "at startup and periodically to generate telemetry headers",
}


class ClaudeHelperRiskTests(ConfigCase):
    def test_each_project_helper_names_its_file_and_withholds_the_command(self):
        home = agent_home(self.root, claude='{"permissions": {"defaultMode": "default"}}')
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude/settings.json").write_text(json.dumps(dict.fromkeys(TIMING, "seed-project")))
        run = run_home(home, "--agent", "claude", "--format", "json", cwd=project)
        self.assertEqual(run.returncode, 0, run.stderr)
        risks = {risk["entry"]: risk for risk in json.loads(run.stdout)["risks"]}
        self.assertEqual(set(risks), {f"settings-2:{name}" for name in TIMING})
        markdown = run_home(home, "--agent", "claude", cwd=project).stdout
        for name, timing in TIMING.items():
            risk = risks[f"settings-2:{name}"]
            self.assertEqual(risk["rule"], "configured_program")
            self.assertIn(timing, risk["explanation"])
            self.assertIn("without a trust prompt", risk["explanation"])
            self.assertIn("`claude -p`", risk["explanation"])
            self.assertIn("parent folder", risk["explanation"])
            self.assertIn(f"[`{name}`](#claude-code-finding-", markdown)
            self.assertIn(f"Remove `{name}` from `.claude/settings.json`", markdown)
        self.assertIn("read that script", markdown)
        self.assertIn("git log -p -- .claude/", markdown)
        self.assertNotIn("ask Claude Code", markdown)
        self.assertNotIn("seed", run.stdout + markdown)

    def test_project_helper_overrides_user_helper_only_during_discovery(self):
        user = {"awsAuthRefresh": "seed-user", "otelHeadersHelper": "seed-otel"}
        home = agent_home(self.root, claude=json.dumps(user))
        project = self.root / "repo"
        path = project / ".claude/settings.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"awsAuthRefresh": "seed-project"}')
        user_file = home / ".claude/settings.json"
        for args, overridden in [((), True), (("--config", str(user_file), "--config", str(path)), False)]:
            with self.subTest(args=args):
                run = run_home(home, "--agent", "claude", "--format", "json", *args, cwd=project)
                report = json.loads(run.stdout)
                entries = {entry["id"]: entry["observations"] for entry in report["catalog"]}
                key = "settings-1:awsAuthRefresh"
                self.assertEqual("overridden by settings-2" in entries[key], overridden)
                risks = {risk["entry"] for risk in report["risks"]}
                self.assertEqual(risks, {"settings-2:awsAuthRefresh", "settings-1:otelHeadersHelper"}
                                 | (set() if overridden else {key}))
                self.assertNotIn("seed", run.stdout)
