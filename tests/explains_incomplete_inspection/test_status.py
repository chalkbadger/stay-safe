"""Expected status explanation comes from stay-safe issue #18, not production text."""
import io
import json
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase, copy_checkout, run_checkout


EXPLANATION = "Inspection incomplete (exit 2). See the report for what wasn't checked.\n"
COMPLETE = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'


class StatusTests(ConfigCase):
    def test_reports_with_gaps_explain_exit_two_on_stderr_only(self):
        checkout = copy_checkout(self.root / "checkout")
        private = self.config('private_key = "secret-value"\n', "private-input-name.toml")
        for args in (["--format", "markdown"], ["--format", "json"], ["--save"]):
            with self.subTest(args=args):
                run = run_checkout(checkout, "--config", str(private), *args, cwd=self.root)
                self.assertEqual((run.returncode, run.stderr), (2, EXPLANATION))
                self.assertNotIn(EXPLANATION.strip(), run.stdout)
                for secret in (str(private), "private-input-name", "secret-value"):
                    self.assertNotIn(secret, run.stdout + run.stderr)
                if "json" in args:
                    self.assertTrue(json.loads(run.stdout)["inspection_gaps"])
                else:
                    self.assertIn("## Not checked", run.stdout)

    def test_complete_reports_and_invalid_arguments_do_not_get_the_explanation(self):
        checkout = copy_checkout(self.root / "checkout")
        config = self.config(COMPLETE)
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                run = run_checkout(checkout, "--config", str(config), "--format", format_name, cwd=self.root)
                self.assertEqual((run.returncode, run.stderr), (0, ""))
        for args, expected in ((["--unknown"], "Invalid arguments. Use --help.\n"),
                               (["--format", "json", "--save"], "--save can't be combined with --format json. Use --help.\n")):
            with self.subTest(args=args):
                run = run_checkout(checkout, *args, cwd=self.root)
                self.assertEqual((run.returncode, run.stdout, run.stderr), (2, "", expected))

    def test_report_is_flushed_before_the_explanation_is_written(self):
        config = self.config("")
        events = []

        class Output(io.StringIO):
            def flush(self):
                events.append(("flushed", self.getvalue()))

        class Errors(io.StringIO):
            def write(self, text):
                events.append(("stderr", text))
                return super().write(text)

        with patch("sys.stdout", Output()), patch("sys.stderr", Errors()):
            status = main(["--config", str(config), "--format", "json"])
        self.assertEqual(status, 2)
        self.assertEqual([kind for kind, text in events], ["flushed", "stderr"])
        self.assertTrue(json.loads(events[0][1])["inspection_gaps"])
        self.assertEqual(events[1][1], EXPLANATION)
