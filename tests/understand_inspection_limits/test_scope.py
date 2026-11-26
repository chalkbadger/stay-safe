from stay_safe.report import inspect, render
from tests.support import ConfigCase, copy_checkout, full_scope, run_checkout, section


class ScopeTests(ConfigCase):
    def test_the_full_scope_holds_every_scope_line(self):
        report = inspect([self.config('approval_policy = "on-request"\nsandbox_mode = "read-only"\n')])
        self.assertIn("docs/report.md#full-scope)", render(report, "markdown"))
        full = " ".join(full_scope().split())
        self.assertIn("Connection reachability, authentication, active tools and effective permissions are not tested.",
                      full)
        for line in report["scope"] + ["Local modifications to the checkout or unzipped release are not checked; the JSON report's "
                                       "`tool_revision` and `rules_revision` fingerprints identify the files that ran."]:
            with self.subTest(limit=line):
                self.assertIn(" ".join(line.split()), full)

    def test_selected_rules_file_is_named_when_it_has_no_saved_approvals(self):
        checkout = copy_checkout(self.root / "checkout")
        cleared = self.config("", "cleared.rules")
        commented = self.config("  # removed\n\n", "commented.rules")
        saved = self.config('prefix_rule(pattern=["git"], decision="allow")\n', "saved.rules")
        unsupported = self.config("unsupported_rule()\n", "unsupported.rules")
        missing = self.root / "missing.rules"
        refused = self.root / "link.rules"
        refused.symlink_to(saved)
        quiet = 'approval_policy="on-request"\nsandbox_mode="read-only"\nshell_environment_policy={inherit="none"}\n'
        for config, rules, status, named, empty in (
            (None, cleared, 0, True, True), (None, commented, 0, True, True),
            (quiet, cleared, 0, True, True), (quiet + "unknown_setting=true\n", cleared, 2, True, True),
            (quiet, None, 0, False, False), (None, saved, 0, True, False), (None, unsupported, 2, True, False),
            (None, missing, 2, False, False), (None, refused, 2, False, False),
        ):
            with self.subTest(config=config, rules=rules):
                args = ["--config", str(self.config(config))] if config is not None else []
                if rules is not None:
                    args.extend(["--rules", str(rules)])
                run = run_checkout(checkout, *args, "--format", "markdown", cwd=self.root)
                self.assertEqual(run.returncode, status)
                intro, heading, _ = run.stdout.partition("\n\n## Findings\n\n")
                self.assertTrue(heading)
                self.assertEqual("your saved approvals (`rules-1`)" in intro, named)
                self.assertEqual("your Codex settings (`config-1`)" in intro, config is not None)
                self.assertEqual("no saved approvals" in intro.lower(), empty)
                if status == 0:
                    self.assertIn("0 things not checked", intro)
                if rules in (missing, refused):
                    reason = "doesn't exist" if rules == missing else "couldn't read it"
                    self.assertIn(reason, section(run.stdout, "Not checked"))
                if rules == saved:
                    self.assertIn("rules-1:prefix_rule.1", section(run.stdout, "Findings"))
