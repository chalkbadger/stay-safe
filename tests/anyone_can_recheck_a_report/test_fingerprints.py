import json

from tests.support import INCOMPLETE
from tests.support import items, section, gap_items
from tests.anyone_can_recheck_a_report.git_support import GitCase
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text

INCIDENT_GAP = "Committed incident citations are incomplete; source links are unavailable."


class FingerprintTests(GitCase):
    def test_missing_fingerprinted_file_is_a_named_gap_and_findings_remain(self):
        """Each fingerprinted file the diagnostic can run without gives a gap naming its path when missing."""
        config = self.config('approval_policy="never"\nsandbox_mode="read-only"')
        for path, other_gaps in (("harnesses/codex.md", []), ("incidents.md", [INCIDENT_GAP]),
                                 ("stay_safe/__init__.py", [])):
            with self.subTest(path):
                checkout = self.checkout(path.replace("/", "-"))
                (checkout / path).unlink()
                gap = f"Incomplete fingerprint: {path} could not be read."
                run = self.run_cli(checkout, config)
                self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                report = json.loads(run.stdout)
                self.assertCountEqual(report["inspection_gaps"], [gap, *other_gaps])
                self.assertEqual(report["file_inspection"], "incomplete")
                self.assertIn("commands_without_prompts", [risk["rule"] for risk in report["risks"]])
                self.assertRegex(report["provenance"]["source_revision"], r"^[0-9a-f]{40}$")
                run = self.run_cli(checkout, config, "markdown")
                self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                self.assertIn(gap_text(gap), gap_items(run.stdout))
                self.assertIn("Rule `commands_without_prompts` · setting `config-1:approval_policy` = `never`", run.stdout)
