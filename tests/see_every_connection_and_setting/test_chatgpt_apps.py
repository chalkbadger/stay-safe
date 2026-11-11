import unittest

from stay_safe.report import inspect, render
from tests.support import CHATGPT_APPS, ConfigCase

# Meaning and sources: harnesses/codex.md row `features.apps` `omitted`.
TOP = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'


def connection(report):
    return [(e["id"], e["kind"], e["observations"]) for e in report["catalog"] if e["name"] == "features.apps"]


class ChatGptAppsTests(ConfigCase):
    def test_configuration_without_apps_false_names_the_chatgpt_apps_connection(self):
        for case, text in {"no features table": TOP, "empty features table": TOP + "[features]\n",
                           "apps = true": TOP + "[features]\napps=true\n"}.items():
            with self.subTest(case=case):
                report = inspect([self.config(text)])
                self.assertEqual(connection(report), [("config-1:features.apps", "MCP server", CHATGPT_APPS)])
                self.assertEqual(report["inspection_gaps"], [])
                self.assertEqual([r for r in report["risks"] if r["entry"] == "config-1:features.apps"], [])

    def test_absent_default_configuration_names_the_chatgpt_apps_connection(self):
        report = inspect([self.root / "missing.toml"], discovered=True)
        self.assertEqual(connection(report), [("config-1:features.apps", "MCP server", CHATGPT_APPS)])

    def test_apps_false_gives_no_chatgpt_apps_connection(self):
        report = inspect([self.config(TOP + "[features]\napps=false\n")])
        self.assertEqual(connection(report), [])
        self.assertNotIn("ChatGPT", render(report))
        self.assertEqual(report["inspection_gaps"], [])


if __name__ == "__main__":
    unittest.main()
