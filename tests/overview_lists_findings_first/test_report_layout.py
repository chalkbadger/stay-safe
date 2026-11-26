import json
import subprocess
import sys

from tests.support import INCOMPLETE
from tests.support import ConfigCase, ROOT, section

AFTER = ('approval_policy = "never"\nsandbox_mode = "read-only"\nprofile = "work"\nfuture_setting = 1\n'
         '[mcp_servers.github]\ncommand = "seed-command"\n')
EMPTY_FINDINGS = ("None of stay-safe's rules matched your settings. That doesn't mean your setup is safe: "
                  "see what stay-safe didn't check and what this report can't see, below.")
EMPTY_GAPS = ("stay-safe checked every setting it supports in the files it read. What this report can't see, below, "
              "still applies.")
HEADINGS = ["## Findings", "## Not checked", "## Your setup", "## Sources", "## What this report can't see"]
CANT_SEE = [
    "- Settings you choose in the app or with command-line flags can override your config. "
    "Check how you start Codex. If you select a separate profile file with `--profile`, "
    "that file can override your main config. Run stay-safe with `--config` and the path "
    "to that file to inspect it separately.",
    "- Whether connections work, or what Codex actually allows when it runs: stay-safe only reads files; it doesn't "
    "start Codex or contact any service. Watch what Codex asks before it acts.",
    "- Private values such as commands, addresses and tokens are left out, but names like `github` are shown as "
    "written: names can identify a project or a person, so check them before sharing.",
]


class ReportLayoutTests(ConfigCase):
    def run_cli(self, text, format_name="markdown"):
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(self.config(text)),
                              "--format", format_name], cwd=ROOT, env={}, text=True, capture_output=True, timeout=10)
        self.assertEqual(run.stderr, INCOMPLETE if run.returncode == 2 else "")
        return run

    def test_report_keeps_results_and_limits_visible(self):
        run = self.run_cli(AFTER)
        self.assertEqual(run.returncode, 2)
        self.assertIn("4 findings, 2 things not checked.", run.stdout)
        for heading in HEADINGS:
            self.assertTrue(section(run.stdout, heading.removeprefix("## ")))
        limits = section(run.stdout, "What this report can't see")
        for warning in CANT_SEE:
            self.assertIn(warning, limits)
        self.assertIn("docs/report.md#full-scope)", limits)

    def test_summary_counts_one_and_none_and_empty_sections_say_what_that_means(self):
        one = self.run_cli('approval_policy = "never"\nshell_environment_policy = { inherit = "none" }\n')
        self.assertEqual(one.returncode, 2)
        self.assertIn("1 finding, 1 thing not checked.", one.stdout.splitlines())
        none = self.run_cli('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                            'shell_environment_policy = { inherit = "none" }\n')
        self.assertEqual(none.returncode, 0)
        self.assertIn("0 findings, 0 things not checked.", none.stdout.splitlines())
        self.assertEqual(section(none.stdout, "Findings"), EMPTY_FINDINGS)
        self.assertEqual(section(none.stdout, "Sources"), "No findings, so there are no rule sources to link.")
        self.assertEqual(section(none.stdout, "Not checked"),
                         EMPTY_GAPS)

    def test_empty_section_text_follows_its_own_section_and_the_count_includes_every_gap(self):
        self.require_no_system_folder()
        findings_only = self.run_cli('approval_policy = "never"\nsandbox_mode = "read-only"\n'
                                     'shell_environment_policy = { inherit = "none" }\n')
        self.assertIn("1 finding, 0 things not checked.", findings_only.stdout.splitlines())
        self.assertNotIn(EMPTY_FINDINGS, section(findings_only.stdout, "Findings"))
        self.assertEqual(section(findings_only.stdout, "Not checked"), EMPTY_GAPS)
        gaps_only = self.run_cli('approval_policy = "on-request"\nshell_environment_policy = { inherit = "none" }\n')
        self.assertIn("0 findings, 1 thing not checked.", gaps_only.stdout.splitlines())
        self.assertEqual(section(gaps_only.stdout, "Findings"), EMPTY_FINDINGS)
        self.assertNotIn(EMPTY_GAPS, section(gaps_only.stdout, "Not checked"))
        home = self.root / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                                          'shell_environment_policy = { inherit = "none" }\n')
        (home / "hooks.json").write_text("{}")
        runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--format", f], cwd=ROOT,
                               env={"CODEX_HOME": str(home)}, text=True, capture_output=True, timeout=10)
                for f in ("json", "markdown")]
        self.assertEqual(len(json.loads(runs[0].stdout)["inspection_gaps"]), 1)
        self.assertIn("0 findings, 1 thing not checked.", runs[1].stdout.splitlines())
