import json
import os
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import FEEDBACK, INCOMPLETE, ConfigCase, agent_home, run_home

CODEX = 'approval_policy = "never"\nsandbox_mode = "read-only"\n'
CLAUDE = '{"permissions": {"defaultMode": "bypassPermissions"}, "sandbox": {"enabled": false}}'


class AgentSelectionTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.require_no_system_folder()

    def json_run(self, home, *args, **env):
        run = run_home(home, "--format", "json", *args, **env)
        self.assertEqual(run.stderr, INCOMPLETE if run.returncode == 2 else "")
        return run.returncode, json.loads(run.stdout)

    def test_default_run_reports_every_installed_agent(self):
        home = agent_home(self.root, codex=CODEX, claude=CLAUDE)
        status, report = self.json_run(home)
        self.assertEqual([part["harness"] for part in report["reports"]], ["Codex", "Claude Code"])
        codex, claude = report["reports"]
        self.assertEqual(status, 2 if codex["inspection_gaps"] or claude["inspection_gaps"] else 0)
        self.assertIn(("config-1:approval_policy", "commands_without_prompts"),
                      {(risk["entry"], risk["rule"]) for risk in codex["risks"]})
        self.assertEqual([(risk["entry"], risk["rule"]) for risk in claude["risks"]],
                         [("settings-1:permissions.defaultMode", "commands_without_prompts")])
        self.assertEqual(claude["inspection_gaps"], [])

        run = run_home(home)
        self.assertEqual((run.returncode, run.stderr), (status, INCOMPLETE if status else ""))
        self.assertEqual([line for line in run.stdout.splitlines() if line.startswith("# ")],
                         ["# Codex configuration diagnostic", "# Claude Code configuration diagnostic"])
        self.assertIn(f"**{claude['risks'][0]['explanation']}**", run.stdout)

    def test_without_a_claude_folder_the_default_run_is_the_codex_report(self):
        home = agent_home(self.root, codex=CODEX)
        for format_args in ((), ("--format", "json")):
            default, chosen = run_home(home, *format_args), run_home(home, "--agent", "codex", *format_args)
            self.assertEqual((default.returncode, default.stdout, default.stderr),
                             (chosen.returncode, chosen.stdout, chosen.stderr))
        self.assertEqual(json.loads(default.stdout)["harness"], "Codex")
        self.assertNotIn("Claude Code", default.stdout)

    def test_agent_claude_reports_only_claude_code(self):
        home = agent_home(self.root, codex=CODEX, claude=CLAUDE)
        status, report = self.json_run(home, "--agent", "claude")
        self.assertEqual((status, report["harness"]), (0, "Claude Code"))
        self.assertEqual([entry["id"] for entry in report["catalog"]],
                         ["settings-1:permissions.defaultMode", "settings-1:sandbox.enabled"])

    def test_claude_config_dir_selects_the_claude_folder(self):
        home = agent_home(self.root, claude='{"permissions": {"defaultMode": "plan"}}')
        moved = self.root / "moved"
        moved.mkdir()
        (moved / "settings.json").write_text(CLAUDE, encoding="utf-8")
        status, report = self.json_run(home, "--agent", "claude", CLAUDE_CONFIG_DIR=str(moved))
        self.assertEqual(status, 0)
        self.assertEqual(report["catalog"][0]["observations"], ["bypassPermissions"])

    def test_agent_claude_without_its_folder_says_nothing_was_inspected(self):
        home = agent_home(self.root, codex=CODEX)
        status, report = self.json_run(home, "--agent", "claude")
        self.assertEqual(status, 2)
        self.assertEqual((report["catalog"], report["risks"]), ([], []))
        self.assertEqual(report["inspection_gaps"][0],
                         "Claude Code home: ~/.claude was not found; no Claude Code files were inspected.")
        status, report = self.json_run(home, "--agent", "claude", CLAUDE_CONFIG_DIR=str(self.root / "missing"))
        self.assertEqual(report["inspection_gaps"][0],
                         "Claude Code home: $CLAUDE_CONFIG_DIR was not found; no Claude Code files were inspected.")

    def test_selected_files_need_exactly_one_agent_and_rules_need_codex(self):
        home = agent_home(self.root)
        settings = self.config(CLAUDE, "settings.json")
        cases = [
            (("--agent", "codex", "--agent", "claude", "--config", str(settings)),
             "--config needs one --agent: choose codex or claude.\n"),
            (("--agent", "claude", "--rules", str(settings)), "--rules reads Codex files only.\n"),
            (("--agent", "cursor",), "Invalid arguments. Use --help.\n"),
        ]
        for args, message in cases:
            with self.subTest(args=args[:-1]):
                run = run_home(home, *args)
                self.assertEqual((run.returncode, run.stdout, run.stderr), (2, "", message + FEEDBACK))
                self.assertNotIn(str(settings), run.stderr)
        status, report = self.json_run(home, "--agent", "claude", "--config", str(settings))
        self.assertEqual((status, report["harness"], report["risks"][0]["entry"]),
                         (0, "Claude Code", "settings-1:permissions.defaultMode"))

    def test_claude_only_home_keeps_just_its_report_even_with_account_and_extensions(self):
        home = agent_home(self.root, claude=CLAUDE)
        (home / ".claude.json").touch()
        (home / ".claude" / "plugins").mkdir()
        (home / ".claude" / "plugins" / "private-plugin").touch()
        status, report = self.json_run(home)
        self.assertEqual((status, report.get("harness"), report.get("inspection_gaps")), (0, "Claude Code", []))

    def test_bad_configured_claude_home_keeps_codex_findings_and_reports_gap(self):
        home = agent_home(self.root, codex=CODEX)
        for path in (self.root / "missing", self.config("not a directory", "file")):
            with self.subTest(path=path.name):
                status, report = self.json_run(home, CLAUDE_CONFIG_DIR=str(path))
                self.assertEqual(status, 2)
                codex, claude = report["reports"]
                self.assertIn("commands_without_prompts", [r["rule"] for r in codex["risks"]])
                self.assertEqual(claude["catalog"], [])
                self.assertIn("$CLAUDE_CONFIG_DIR", claude["inspection_gaps"][0])
                self.assertNotIn(str(path), json.dumps(report))

    def test_selected_account_file_never_reaches_the_opener(self):
        home = agent_home(self.root)
        for args in (("--config",), ("--agent", "codex", "--config"), ("--agent", "claude", "--config"), ("--rules",)):
            for name in (".claude.json", ".credentials.json"):
                with self.subTest(args=args, name=name), patch("os.open", side_effect=FileNotFoundError) as opener, \
                     redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()):
                    self.assertEqual(main([*args, str(home / name), "--format", "json"]), 2)
                    opener.assert_not_called()
                    report = json.loads(output.getvalue())
                    self.assertIn("account", report["inspection_gaps"][0])
                    self.assertEqual(report["catalog"], [])

        config = self.config(CODEX)
        status, mixed = self.json_run(home, "--config", str(home / ".claude.json"), "--config", str(config),
                                      "--rules", str(home / ".credentials.json"))
        self.assertEqual(status, 2)
        self.assertEqual({g.split(":")[0] for g in mixed["inspection_gaps"]}, {"config-1", "rules-1"})
        self.assertIn("config-2:approval_policy", [r["entry"] for r in mixed["risks"]])
        text = run_home(home, "--rules", str(home / ".credentials.json")).stdout
        self.assertNotIn("stay-safe read one file", text)

    def test_neither_home_keeps_codex_defaults_and_any_explicit_claude_gap(self):
        home = agent_home(self.root)
        status, default = self.json_run(home)
        self.assertEqual((status, default), self.json_run(home, "--agent", "codex"))
        status, report = self.json_run(home, CLAUDE_CONFIG_DIR=str(home / "missing"))
        self.assertEqual(status, 2)
        self.assertEqual(report["reports"][0], default)
        self.assertIn("$CLAUDE_CONFIG_DIR", report["reports"][1]["inspection_gaps"][0])

    def test_inaccessible_claude_directory_keeps_the_other_report(self):
        home = agent_home(self.root, codex=CODEX, claude=CLAUDE)
        original = Path.stat

        def stat(path, *args, **kwargs):
            if path == home / ".claude":
                raise PermissionError
            return original(path, *args, **kwargs)

        with patch.dict(os.environ, {"HOME": str(home)}, clear=True), patch.object(Path, "stat", stat), \
             redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()):
            self.assertEqual(main(["--format", "json"]), 2)
        codex, claude = json.loads(output.getvalue())["reports"]
        self.assertIn("commands_without_prompts", [r["rule"] for r in codex["risks"]])
        self.assertIn("could not be checked", claude["inspection_gaps"][0])
