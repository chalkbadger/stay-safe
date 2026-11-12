import unittest

from stay_safe.rules import RULES, evaluate
from stay_safe.report import incident_links
from tests.support import ROOT, ConfigCase


class RuleTests(ConfigCase):
    def test_rules_accept_harness_neutral_observations(self):
        cases = [
            ("saved_approval", ["I26"]),
            ("commands_without_prompts", ["I2", "I3", "I24"]),
            ("unrestricted_filesystem", ["I1", "I3"]),
            ("configured_program", ["I13", "I14", "I19"]),
            ("automatic_tools", ["I15", "I20"]),
            ("destructive_tools", ["I7", "I8"]),
            ("network_access", ["I15", "I21"]),
            ("self_described_tools", ["I15", "I21"]),
            ("environment_inheritance", ["I23"]),
        ]
        for fact, incidents in cases:
            with self.subTest(fact=fact):
                results = evaluate([{"id": "another-harness:original-setting-name", "facts": {fact: True}}])
                self.assertEqual([(r["rule"], r["entry"], r["incidents"]) for r in results],
                                 [(fact, "another-harness:original-setting-name", incidents)])
                self.assertTrue(results[0]["explanation"])

    def test_false_missing_and_unknown_facts_do_not_match(self):
        for facts in ({}, {r.id: False for r in RULES}, {"unrecognized": True}, {r.id: "true" for r in RULES},
                      {r.id: 1 for r in RULES}, {r.id: 1.0 for r in RULES}):
            with self.subTest(facts=facts):
                self.assertEqual(evaluate([{"id": "test", "facts": facts}]), [])

    def test_every_rule_cites_complete_committed_reported_incidents(self):
        text = (ROOT / "incidents.md").read_text()
        self.assertIn("Each entry is **reported, not verified**", text)
        entries = {}
        for block in text.split("\n## ")[1:]:
            heading, body = block.split("\n", 1)
            identifier = heading.split(".", 1)[0]
            entries[identifier] = (heading, body)
        self.assertEqual(len({r.id for r in RULES}), len(RULES))
        for rule in RULES:
            with self.subTest(rule=rule.id):
                self.assertTrue(rule.incidents)
                for identifier in rule.incidents:
                    heading, body = entries[identifier]
                    for field in ("Harness", "What happened", "Enabling condition"):
                        self.assertRegex(body, rf"(?m)^- {field}: .+\S$")
                    self.assertRegex(body, r"(?m)^- Sources?: .*\]\(https://[^ )]+\)")
                    self.assertTrue(incident_links(revision="a" * 40)[identifier])

    def test_incident_anchors_follow_github_heading_links(self):
        # GitHub lowercases a heading, removes punctuation other than hyphens and turns spaces into hyphens:
        # https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links
        links = incident_links(revision="a" * 40)
        prefix = "https://github.com/chalkbadger/stay-safe/blob/" + "a" * 40 + "/incidents.md#"
        self.assertEqual({identifier: links[identifier] for identifier in ("I1", "I23", "I24")}, {
            "I1": prefix + "i1-home-directory-deleted-by-rm--rf",
            "I23": prefix + "i23-production-tables-dropped-by-a-dev-only-migration-command",
            "I24": prefix + "i24-driver-update-followed-by-boot-and-network-failures",
        })

    def test_links_follow_changed_incident_titles_without_a_code_mapping(self):
        path = self.config("# Reported incidents\n\n## I15. New `title` for this report\n", "incidents.md")
        self.assertEqual(incident_links(path, revision="a" * 40), {
            "I15": "https://github.com/chalkbadger/stay-safe/blob/" + "a" * 40 + "/incidents.md#i15-new-title-for-this-report",
        })


if __name__ == "__main__":
    unittest.main()
