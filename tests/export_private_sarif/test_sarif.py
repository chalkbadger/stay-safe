import hashlib
import json
from pathlib import Path

import fastjsonschema
from fastjsonschema.draft06 import CodeGeneratorDraft06

from tests.support import COPY_REVISION, SEEDED, SEEDS, ConfigCase, copy_checkout, run_checkout


SCHEMA = Path(__file__).with_name("sarif-schema-2.1.0.json")
INCOMPLETE = "Inspection incomplete (exit 2). See the report for what wasn't checked.\n"
QUIET = """approval_policy = "on-request"
sandbox_mode = "read-only"
shell_environment_policy = { inherit = "none" }
[features]
apps = false
"""


class SarifTests(ConfigCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(SCHEMA.read_bytes()).hexdigest() != "c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e":
            raise AssertionError("The test schema differs from the pinned OASIS SARIF 2.1.0 schema.")
        formats = {"uri-reference": CodeGeneratorDraft06.FORMAT_REGEXS["uri-reference"]}
        cls.validate = staticmethod(fastjsonschema.compile(json.loads(SCHEMA.read_text()), formats=formats, use_default=False))

    def setUp(self):
        super().setUp()
        self.checkout = copy_checkout(self.root / "checkout")

    def export(self, *args, status, env=None):
        result = run_checkout(self.checkout, "--format", "sarif", *args, cwd=self.root, env=env)
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(result.stderr, INCOMPLETE if status else "")
        document = json.loads(result.stdout)
        self.validate(document)
        self.assertEqual(document["version"], "2.1.0")
        return document

    def test_complete_and_gaps_only_reports_distinguish_an_empty_result_from_incomplete_inspection(self):
        path = self.config(QUIET)
        complete, = self.export("--config", str(path), status=0)["runs"]
        self.assertEqual(complete["results"], [])
        self.assertTrue(complete["invocations"][0]["executionSuccessful"])
        self.assertEqual(complete["invocations"][0].get("toolExecutionNotifications", []), [])

        missing, = self.export("--rules", str(self.root / "missing.rules"), status=2)["runs"]
        self.assertEqual(missing["results"], [])
        invocation, = missing["invocations"]
        self.assertFalse(invocation["executionSuccessful"])
        self.assertEqual([(n["level"], n["message"]["text"]) for n in invocation["toolExecutionNotifications"]],
                         [("warning", "rules-1: Selected rules input is missing; its path was withheld.")])

    def test_each_risk_keeps_its_rule_explanation_and_logical_entry_and_each_gap_is_a_warning(self):
        rules = self.config('\nprefix_rule(pattern=["seed-private"], decision="allow")\n'
                            'prefix_rule(pattern=["second-private"], decision="allow")\n', "personal.rules")
        run, = self.export("--rules", str(rules), status=0)["runs"]
        self.assertEqual(run["tool"]["driver"]["name"], "stay-safe")
        results = run["results"]
        self.assertEqual([(r["ruleId"], r["level"], r["message"]["text"]) for r in results],
                         [("saved_approval", "warning", "A saved rule declares matching commands allowed outside the sandbox without prompting.")] * 2)
        self.assertEqual([r["locations"] for r in results],
                         [[{"logicalLocations": [{"fullyQualifiedName": f"rules-1:prefix_rule.{line}"}]}] for line in (2, 3)])
        rule, = run["tool"]["driver"]["rules"]
        self.assertEqual(rule["id"], "saved_approval")
        self.assertEqual(rule["helpUri"], f"https://github.com/chalkbadger/stay-safe/blob/{COPY_REVISION}/docs/rules.md#saved_approval")

        (self.checkout / ".git" / "HEAD").unlink()
        run, = self.export("--rules", str(rules), status=2)["runs"]
        self.assertEqual(run["results"], results)
        self.assertNotIn("helpUri", run["tool"]["driver"]["rules"][0])
        notes = run["invocations"][0]["toolExecutionNotifications"]
        self.assertEqual([(n["level"], n["message"]["text"]) for n in notes],
                         [("warning", "Revision unknown; checkout source links are withheld.")])

    def test_two_agents_keep_their_own_results_and_notifications(self):
        self.require_no_system_folder()
        codex = self.root / "codex"
        (codex / "rules").mkdir(parents=True)
        (codex / "config.toml").write_text(QUIET)
        (codex / "rules" / "default.rules").write_text('prefix_rule(pattern=["private"], decision="allow")\nunknown\n')
        claude = self.root / "claude"
        claude.mkdir()
        (claude / "settings.json").write_text('{"permissions":{"defaultMode":"bypassPermissions"}}')
        runs = self.export("--agent", "codex", "--agent", "claude", status=2,
                           env={"CODEX_HOME": str(codex), "CLAUDE_CONFIG_DIR": str(claude)})["runs"]
        self.assertEqual([r["automationDetails"]["id"] for r in runs], ["Codex", "Claude Code"])
        self.assertEqual([[r["ruleId"] for r in run["results"]] for run in runs],
                         [["saved_approval"], ["commands_without_prompts"]])
        self.assertEqual([[n["message"]["text"] for n in run["invocations"][0].get("toolExecutionNotifications", [])]
                          for run in runs], [["rules-1: Rules contain lines that are not inspected."], []])

    def test_private_inputs_stay_withheld_throughout_the_document(self):
        path = self.config(SEEDED, "private-settings-path.toml")
        run = run_checkout(self.checkout, "--config", str(path), "--format", "sarif", cwd=self.root)
        self.assertIn(run.returncode, (0, 2))
        document = json.loads(run.stdout)
        self.validate(document)
        entries = [location["fullyQualifiedName"] for result in document["runs"][0]["results"]
                   for item in result["locations"] for location in item["logicalLocations"]]
        self.assertIn("config-1:mcp_servers.local", entries)
        encoded = json.dumps(document, ensure_ascii=False) + run.stderr
        for private in [*SEEDS.values(), str(self.root), path.name]:
            with self.subTest(private=private):
                self.assertNotIn(private, encoded)
        self.assertNotIn("physicalLocation", encoded)

    def test_save_rejects_sarif_before_writing_any_report(self):
        result = run_checkout(self.checkout, "--save", "--format", "sarif", cwd=self.root)
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertIn("--save can't be combined with --format sarif.", result.stderr)
        self.assertFalse((self.checkout / "stay-safe-report.html").exists())
        self.assertFalse((self.root / "stay-safe-report.html").exists())
