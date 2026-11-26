import json

import re

from tests.support import ConfigCase, ReportRuns, items, section, without_rule_links

SETTINGS = {"permissions": {"defaultMode": "bypassPermissions", "allow": ["Bash", "Bash(git push:*)", "WebFetch"]},
            "sandbox": {"enabled": False}}
BYPASS_SCOPE = "From v2.1.257, project and project-local settings cannot enable this mode."


class ClaudeRiskTests(ConfigCase, ReportRuns):
    def test_each_claude_code_warning_names_its_rule_setting_and_incidents(self):
        path = self.config(json.dumps(SETTINGS), "settings.json")
        run = self.run_cli("--agent", "claude", "--config", str(path), "--format", "json")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        report = json.loads(run.stdout)
        self.assertEqual([(risk["rule"], risk["entry"], risk["incidents"], risk["configured_evidence"])
                          for risk in report["risks"]], [
            ("commands_without_prompts", "settings-1:permissions.defaultMode", ["I2", "I3", "I24"],
             ["bypassPermissions"]),
            ("saved_approval", "settings-1:permissions.allow.1", ["I26", "I30"], ["tool: Bash", "broad: every command"]),
            ("saved_approval", "settings-1:permissions.allow.2", ["I26", "I30"], ["tool: Bash", "program: git"]),
            ("network_access", "settings-1:permissions.allow.3", ["I15", "I21"], ["tool: WebFetch", "every address"]),
        ])
        self.assertTrue(all(risk["interpretation_source"] is None or
                            risk["interpretation_source"].endswith("/harnesses/claude-code.md") for risk in report["risks"]))

        run = self.run_cli("--agent", "claude", "--config", str(path))
        text = without_rule_links(run.stdout)
        found = items(section(text, "Claude Code findings").split("\n\n", 1)[1])
        self.assertTrue(all(re.match(r"### Claude Code finding \d+\n\n", item) for item in found))
        heads = [item.split("\n\n")[1].split("** ", 1)[0] + "**" for item in found]
        self.assertEqual(heads, [
            f"**This file selects bypassPermissions, which can skip permission prompts. {BYPASS_SCOPE}**",
            "**This file has an allow rule for every Bash command.**",
            "**This file has an allow rule for matching Bash commands.**",
            "**This file has a WebFetch allow rule for every web address.**",
        ])
        for rule, setting in (("commands_without_prompts", "settings-1:permissions.defaultMode"),
                              ("saved_approval", "settings-1:permissions.allow.2"),
                              ("network_access", "settings-1:permissions.allow.3")):
            self.assertIn(f"*Rule `{rule}` · setting `{setting}`", text)

    def test_bypass_finding_explains_file_scope_and_version_in_json_and_markdown(self):
        project = self.root / "project/.claude"
        project.mkdir(parents=True)
        path = project / "settings.json"
        args = ("--agent", "claude", "--config", str(path))
        path.write_text('{"permissions":{"defaultMode":"bypassPermissions"}}')
        data = self.run_cli(*args, "--format", "json")
        self.assertEqual((data.returncode, data.stderr), (0, ""))
        risk, = json.loads(data.stdout)["risks"]
        self.assertIn(BYPASS_SCOPE, risk["explanation"])
        markdown = self.run_cli(*args, "--format", "markdown")
        self.assertEqual((markdown.returncode, markdown.stderr), (0, ""))
        self.assertIn(risk["explanation"], section(markdown.stdout, "Claude Code findings"))

        path.write_text('{"permissions":{"defaultMode":"default"}}')
        self.assertEqual(json.loads(self.run_cli(*args, "--format", "json").stdout)["risks"], [])
        self.assertNotIn(BYPASS_SCOPE, self.run_cli(*args, "--format", "markdown").stdout)

    def test_competing_permission_rules_are_visible_on_each_affected_finding(self):
        for key in ("ask", "deny"):
            with self.subTest(key=key):
                rules = ["Bash(git status)", "WebFetch"]
                path = self.config(json.dumps({"permissions": {"defaultMode": "default", "allow": rules, key: rules},
                                               "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": False}}))
                args = ("--agent", "claude", "--config", str(path))
                data = self.run_cli(*args, "--format", "json")
                self.assertEqual(data.returncode, 2)
                report = json.loads(data.stdout)
                self.assertIn("permissions." + key, " ".join(report["inspection_gaps"]))
                self.assertEqual([r["rule"] for r in report["risks"]], ["saved_approval", "network_access"])
                md = self.run_cli(*args, "--format", "markdown").stdout
                overview, details = md.split("## Claude Code findings", 1)
                for risk in report["risks"]:
                    lead = risk["explanation"]
                    self.assertIn(key + " rules", lead)
                    self.assertIn("matches were not checked", lead)
                    self.assertNotIn("outside the sandbox", lead)
                    self.assertIn(lead, overview)
                    self.assertIn(lead, details)
