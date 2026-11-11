import json
import unittest

from tests.support import ROOT


class ChallengeFormTests(unittest.TestCase):
    # JSON is a YAML subset: https://yaml.org/spec/1.2.2/ext/changes/
    # Field ids, required fields and textarea semantics:
    # https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema
    def test_form_declares_the_challenge_record_as_required_and_the_report_as_optional(self):
        form = json.loads((ROOT / ".github/ISSUE_TEMPLATE/challenge.yml").read_text())
        for key in ("name", "description"):
            self.assertIsInstance(form[key], str)
            self.assertTrue(form[key].strip())
        fields = [field for field in form["body"] if field["type"] != "markdown"]
        for field in fields:
            self.assertRegex(field["id"], r"^[A-Za-z0-9_-]+$")
        declared = {}
        for field in fields:
            self.assertNotIn(field["id"], declared)
            declared[field["id"]] = (field["attributes"]["label"], field["type"],
                                     field.get("validations", {}).get("required") is True)
        self.assertEqual(declared, {
            "finding": ("Finding", "textarea", True),
            "revision": ("Report revisions", "textarea", True),
            "disputed-claim": ("Disputed claim", "textarea", True),
            "evidence": ("Evidence and reproduction", "textarea", True),
            "report": ("Report or independent record", "textarea", False),
        })
