import json

from tests.support import ConfigCase, agent_home, run_home

USER = {"permissions": {"defaultMode": "default"}, "processWrapper": "/seed/corp-launcher --flag"}
PROJECT = {"processWrapper": "/seed/corp-launcher --flag"}
RISKS = [["settings-1:processWrapper", 'On macOS and Linux, Claude Code 2.1.210 or later can use `processWrapper` when it starts another Claude Code process, including a background session or a split-pane teammate. If you set `CLAUDE_CODE_PROCESS_WRAPPER`, Claude Code uses that launcher instead.']]
MARKDOWN = [
    "Remove `processWrapper` from `~/.claude/settings.json`",
    "Claude Code ignores `processWrapper` in `.claude/settings.json`.",
    "read that script before you trust it.",
]


class ClaudeProcessWrapperRiskTests(ConfigCase):
    def test_process_wrapper_finding_names_its_file_and_withholds_the_command(self):
        home = agent_home(self.root, claude=json.dumps(USER))
        project = self.root / "repo"
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "settings.json").write_text(json.dumps(PROJECT), encoding="utf-8")
        run = run_home(home, "--agent", "claude", "--format", "json", cwd=project)
        report = json.loads(run.stdout)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertCountEqual([[risk["entry"], risk["explanation"]] for risk in report["risks"]], RISKS)
        self.assertEqual({risk["rule"] for risk in report["risks"]}, {"configured_program"})
        markdown = run_home(home, "--agent", "claude", cwd=project).stdout
        for line in MARKDOWN:
            self.assertIn(line, markdown)
        self.assertNotIn("seed", (run.stdout + markdown).lower())

    def test_selected_file_names_scope_and_project_values_cannot_enable_a_wrapper(self):
        home = agent_home(self.root, claude=json.dumps({"permissions": {"defaultMode": "default"}}))
        repo = self.root / "repo"
        folder = repo / ".claude"
        folder.mkdir(parents=True)
        path = folder / "settings.json"
        path.write_text(json.dumps(USER))
        selected = run_home(home, "--agent", "claude", "--format", "json", "--config", str(path), cwd=repo)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        finding, = json.loads(selected.stdout)["risks"]
        self.assertIn("Claude Code uses `processWrapper` only in user or managed settings.", finding["explanation"])
        path.write_text(json.dumps({"processWrapper": []}))
        discovered = run_home(home, "--agent", "claude", "--format", "json", cwd=repo)
        self.assertEqual(discovered.returncode, 0, discovered.stderr)
        self.assertEqual(json.loads(discovered.stdout)["risks"], [])
