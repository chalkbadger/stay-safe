import json
import re

from stay_safe.report import inspect
from tests.support import ConfigCase, ROOT


class PublishedMeaningTests(ConfigCase):
    def test_reader_matches_every_published_meaning_example(self):
        text = (ROOT / "harnesses/codex.md").read_text(encoding="utf-8")
        rows = {}
        for line in text.splitlines():
            if not line.startswith("| `"):
                continue
            setting, value, meaning, source, status = [part.strip() for part in line.strip("|").split("|")]
            key = (setting.strip("`"), value.strip("`"))
            self.assertNotIn(key, rows)
            self.assertIn(status, {"documented", "documented in source", "documented: retired", "documented: deprecated",
                                   "inferred", "confirmed by the maintainer", "disputed", "open"})
            self.assertRegex(text, rf"(?m)^{re.escape(source)}: https://(?:github.com/openai/codex/blob/[0-9a-f]{{40}}/|learn.chatgpt.com/docs/config-file/config-reference$)")
            match = re.search(r"(?:^| )Catalog: (.+)\. Rules: (.+)\. Gap: (yes|no)\.$", meaning)
            self.assertIsNotNone(match, key)
            catalog, rules, gap = match.groups()
            rows[key] = (None if catalog == "none" else re.findall(r"`([^`]+)`", catalog),
                         [] if rules == "none" else re.findall(r"`([^`]+)`", rules), gap == "yes")
        fixtures = json.loads((ROOT / "tests/see_every_connection_and_setting/meanings.json").read_text(encoding="utf-8"))
        keys = [(case["setting"], case["value"]) for case in fixtures]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), set(rows), "Every meaning needs a fixture, and every fixture needs a meaning.")
        # Every fixture shares one baseline, whose expected entries are these rows.
        baseline = [('approval_policy="on-request"', ("approval_policy", "on-request")),
                    ('sandbox_mode="read-only"', ("sandbox_mode", "read-only")),
                    (None, ("shell_environment_policy", "omitted"))]
        for case in fixtures:
            key = (case["setting"], case["value"])
            with self.subTest(setting=key[0], value=key[1]):
                report = inspect([self.config(case["config"])])
                catalog = {e["name"]: e["observations"] for e in report["catalog"]}

                def assert_entry(name, row):
                    observations, rules, _ = rows[row]
                    self.assertEqual(catalog.get(name), observations, name)
                    self.assertEqual([r["rule"] for r in report["risks"] if r["entry"] == "config-1:" + name], rules, name)

                assert_entry(case["entry"], key)
                for line, row in baseline:
                    kept = (line in case["config"].splitlines() if line
                            else "shell_environment_policy" not in case["config"])
                    if kept and row[0] != case["entry"]:
                        assert_entry(row[0], row)
                gaps = case.get("gaps", [])
                self.assertEqual(bool(gaps), rows[key][2])
                self.assertEqual(report["inspection_gaps"], ["config-1: " + text for text in gaps])
