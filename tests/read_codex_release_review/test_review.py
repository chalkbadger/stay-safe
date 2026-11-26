import json
from pathlib import Path
import re
import tomllib

from tests.support import TABLES_GAP
from tests.support import ConfigCase, copy_checkout, run_checkout, section


DOCS = Path(__file__).resolve().parents[2] / "docs"


class ReviewTests(ConfigCase):
    def field_reviews(self):
        return json.loads((DOCS / "codex-scan-state.json").read_text())["field_reviews"]

    def test_each_indexed_release_leads_to_its_review_and_pinned_sources(self):
        reviews = self.field_reviews()
        self.assertTrue(reviews)
        for tag, filename in reviews.items():
            with self.subTest(release=tag):
                text = (DOCS / filename).read_text()
                self.assertIn(tag.removeprefix("rust-v"), text.splitlines()[0])
                sources = re.findall(r"https://github\.com/openai/codex/blob/([^/\s]+)/", text)
                self.assertTrue(sources)
                for revision in sources:
                    self.assertRegex(revision, r"^[0-9a-f]{40}$")

    def review_0_172(self):
        return (DOCS / self.field_reviews()["rust-v0.172.0"]).read_text()

    def test_scan_record_links_to_field_dispositions_and_pinned_sources(self):
        text = self.review_0_172()
        sources = dict(re.findall(r"^\[([\w-]+)\]: (\S+)$", text, re.MULTILINE))
        rows = {}
        for line in text.splitlines():
            if line.startswith("| "):
                settings, explanation = line.strip("|").split("|")
                for field in re.findall(r"`([^`]+)`", settings):
                    rows[field] = explanation
        feature_gap = "Stay-safe gives the general `features` gap."
        groups = (
            (["apps.*.tools.*.approvals_reviewer"], "either automatic value produces a named gap", "reviewer"),
            (["plugins.*.apps.*.tools.*.approvals_reviewer"], "whole `plugins` section under “Not checked.”", "overlays"),
            (["features.guardianv3.housekeeper", "features.guardianv3.housekeeper.routing_instructions",
              "features.guardianv3.housekeeper.batch_timeout_ms"], feature_gap, "housekeeper"),
            (["features.guardianv3.reviewer", "features.guardianv3.reviewer.retrieval_instructions",
              "features.guardianv3.max_instruction_tokens"], feature_gap, "board"),
            (["features.guardianv3.message_board_in_memory"], feature_gap, "resume"),
            (["features.connector_tool_result_passthrough"], feature_gap, "capture"),
            (["features.realtime_frames_local"], feature_gap, "enrollment"),
            (["profiles.*."], "conditional warning for a table alone", "profile-layer"),
            (["tui.keymap", "tui.keymap.agents", "tui.keymap.agents.next_group", "tui.keymap.agents.next_group[]",
              "tui.keymap.agents.previous_group", "tui.keymap.agents.previous_group[]"],
             "outside its permissions report and gives no gap", "navigation"),
        )
        for fields, disposition, source in groups:
            for field in fields:
                with self.subTest(field=field):
                    self.assertIn(disposition, rows[field])
                    self.assertIn(f"][{source}]", rows[field])
            self.assertRegex(sources[source], r"^https://github\.com/openai/codex/blob/"
                             r"3d86e43b075adeba2193ec5c22ac92f55afd82e6/.+#L\d+-L\d+$")
        profile_features = {f"profiles.*.{field}" for field in rows if field.startswith("features.")}
        self.assertEqual(len(profile_features), 9)
        self.assertIn("The schema repeats all nine inside legacy profile tables.", rows["profiles.*."])

    def test_published_example_reports_match_the_cli(self):
        text = self.review_0_172()
        checkout = copy_checkout(self.root / "checkout")
        for heading in ("Profile example", "App tool example"):
            with self.subTest(example=heading):
                example = section(text, heading)
                config = re.search(r"```toml\n(.*?)```", example, re.DOTALL)
                markdown = re.search(r"^> (\*\*.+?\.\*\* .*)$", example, re.MULTILINE)
                machine = re.search(r"```json\n(.*?)```", example, re.DOTALL)
                self.assertIsNotNone(config)
                self.assertIsNotNone(markdown)
                self.assertIsNotNone(machine)
                if heading == "Profile example":
                    settings = tomllib.loads(config[1])
                    self.assertEqual(settings.get("profile"), "work")
                    self.assertTrue(settings["profiles"]["work"]["features"]["realtime_frames_local"])
                path = str(self.config(config[1]))
                human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                machine_run = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                self.assertEqual((human.returncode, machine_run.returncode), (2, 2))
                self.assertIn(markdown[1], section(human.stdout, "Not checked").splitlines())
                self.assertEqual(json.loads(machine[1]), json.loads(machine_run.stdout)["inspection_gaps"])

    def test_field_groups_give_the_documented_gaps_and_exit_status(self):
        checkout = copy_checkout(self.root / "checkout")
        base = 'approval_policy="on-request"\nsandbox_mode="read-only"\nshell_environment_policy.inherit="none"\n'
        feature_gap = "config-1: features contains fields outside reader coverage; their values were withheld."
        profile_gap = "config-1: " + TABLES_GAP
        plugin_gap = "config-1: Unchecked section plugins; its settings were not evaluated."
        cases = [
            ('plugins."example@local".apps.calendar.tools.read.approvals_reviewer="auto_review"',
             "Not checked: `plugins`", plugin_gap),
            ('tui.keymap.agents.next_group=["ctrl-j"]', None, None),
            ('tui.keymap.agents.previous_group=["ctrl-k"]', None, None),
        ]
        for field in ('guardianv3.housekeeper={}', 'guardianv3.housekeeper.routing_instructions="example"',
                      'guardianv3.housekeeper.batch_timeout_ms=100', 'guardianv3.reviewer={}',
                      'guardianv3.reviewer.retrieval_instructions="example"', 'guardianv3.max_instruction_tokens=32',
                      'guardianv3.message_board_in_memory=true', 'connector_tool_result_passthrough=true',
                      'realtime_frames_local=true'):
            cases.append(("features." + field, "Not checked: some `features` settings", feature_gap))
            cases.append(("profiles.work.features." + field, "This file defines a profile but doesn’t select it", profile_gap))
        for setting, label, gap in cases:
            with self.subTest(setting=setting):
                path = str(self.config(base + setting + "\n"))
                human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                machine = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                status = 2 if gap else 0
                self.assertEqual((human.returncode, machine.returncode), (status, status))
                self.assertEqual(json.loads(machine.stdout)["inspection_gaps"], [gap] if gap else [])
                headings = re.findall(r"^\*\*(.*?)\.\*\*", section(human.stdout, "Not checked"), re.MULTILINE)
                self.assertEqual(headings, [label] if label else [])
