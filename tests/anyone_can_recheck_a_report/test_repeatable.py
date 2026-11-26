from tests.support import INCOMPLETE, SEEDED, ReportRuns
from tests.support import REPORT, ConfigCase, copy_checkout, run_checkout


class RepeatableReportTests(ReportRuns, ConfigCase):
    def test_report_is_deterministic(self):
        path = self.config(SEEDED)
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                one = self.run_cli("--config", str(path), "--format", format_name)
                two = self.run_cli("--config", str(path), "--format", format_name)
                self.assertEqual((one.returncode, one.stderr), (2, INCOMPLETE))
                self.assertEqual(one.stdout, two.stdout)
        checkout = copy_checkout(self.root / "checkout")
        saved = []
        for _ in range(2):
            run = run_checkout(checkout, "--config", str(path), "--save", cwd=self.root)
            self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
            saved.append((run.stdout, (checkout / REPORT).read_text(encoding="utf-8")))
        self.assertEqual(saved[0], saved[1])
