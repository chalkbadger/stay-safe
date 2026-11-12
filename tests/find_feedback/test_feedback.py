import json
import subprocess
import sys
import unittest

from tests.support import ROOT
from stay_safe.report import inspect, render

URL = "https://github.com/chalkbadger/stay-safe/issues/new/choose"
LABEL = "Report a problem or suggest an idea"


class FeedbackTests(unittest.TestCase):
    def test_reports_link_once_and_json_stays_a_document(self):
        sample = ROOT / "tests/runs_without_a_coding_agent/sample.toml"
        for path in (sample, ROOT / "missing-feedback-config.toml"):
            for fmt in ("markdown", "html"):
                with self.subTest(path=path, format=fmt):
                    output = render(inspect([path]), fmt)
                    self.assertEqual(output.count(URL), 1)
                    self.assertEqual(output.count(LABEL), 1)
                    link = f"[{LABEL}]({URL})" if fmt == "markdown" else f'<a href="{URL}">{LABEL}</a>'
                    self.assertIn(link, output)
            for args in ([], ["--format", "json"]):
                result = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(path), *args],
                                        cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0 if path == sample else 2)
                self.assertNotIn(URL, result.stderr)
                if args:
                    self.assertIsInstance(json.loads(result.stdout), dict)
                    self.assertNotIn(URL, result.stdout)
                else:
                    self.assertEqual(result.stdout.count(URL), 1)

    def test_argument_errors_link_once_without_echoing_private_arguments(self):
        private = "/private/customer-token/report.html"
        for args in (["--unknown", private], ["--save", private], ["--save", "--format", "json"],
                     ["--rules", private, "--rules", private]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=ROOT,
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual((result.returncode, result.stdout), (2, ""))
                self.assertEqual(result.stderr.count(LABEL + ": " + URL), 1)
                self.assertNotIn(private, result.stderr)
        help_run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--help"], cwd=ROOT,
                                  capture_output=True, text=True, timeout=20)
        self.assertEqual((help_run.returncode, help_run.stderr), (0, ""))

    def test_error_and_idea_forms_collect_relevant_details_without_requiring_reports(self):
        expected = {
            "error": {"attempt": ("What were you trying to do?", True),
                      "error": ("What error did you see?", True),
                      "setup": ("Version and setup", False), "report": ("Report (optional)", False)},
            "idea": {"goal": ("What would you like to do?", True),
                     "change": ("What would help?", True), "report": ("Report (optional)", False)},
        }
        for name, fields in expected.items():
            path = ROOT / ".github/ISSUE_TEMPLATE" / (name + ".yml")
            self.assertTrue(path.is_file(), "The feedback form is missing")
            form = json.loads(path.read_text())
            self.assertTrue(form["name"])
            self.assertTrue(form["description"])
            actual = {f["id"]: (f["attributes"]["label"], f.get("validations", {}).get("required", False))
                      for f in form["body"] if f["type"] == "textarea"}
            self.assertEqual(actual, fields)
            guidance = " ".join(f["attributes"]["value"] for f in form["body"] if f["type"] == "markdown")
            for phrase in ("review names", "credentials", "raw private configuration", "optional"):
                self.assertIn(phrase, guidance)
