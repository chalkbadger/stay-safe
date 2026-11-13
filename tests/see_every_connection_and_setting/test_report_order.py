"""The Markdown report reads summary, findings and gaps first, scope and revision last (archived issue #105)."""

import json
import subprocess
import sys

from tests.support import INCOMPLETE
from tests.support import ConfigCase, ROOT, full_scope, section, NOT_CHECKED_INTRO, NOTE_LABEL

# Four findings (commands_without_prompts; configured_program and self_described_tools on github;
# environment_inheritance by default) and two gaps (profiles, an unread setting), as in the issue's After example.
AFTER = ('approval_policy = "never"\nsandbox_mode = "read-only"\nprofile = "work"\nfuture_setting = 1\n'
         '[mcp_servers.github]\ncommand = "seed-command"\n')
EMPTY_FINDINGS = ("None of stay-safe's rules matched your settings. That doesn't mean your setup is safe: "
                  "see what stay-safe didn't check and what this report can't see, below.")
EMPTY_GAPS = ("stay-safe checked every setting it supports in the files it read. What this report can't see, below, "
              "still applies.")
HEADINGS = ["## Findings", "## Not checked", "## Your setup", "## Sources", "## What this report can't see"]
# Each limit says why and what to do (reading check, 2026-11-09).
CANT_SEE = [
    "- Settings chosen in the app or with command-line flags, and which profile Codex uses: these can override the "
    "files listed under Your setup, and stay-safe can't see them. Check them where you start Codex, and the "
    "`profile` setting in your config file.",
    "- Whether connections work, or what Codex actually allows when it runs: stay-safe only reads files; it doesn't "
    "start Codex or contact any service. Watch what Codex asks before it acts.",
    "- Private values such as commands, addresses and tokens are left out, but names like `github` are shown as "
    "written: names can identify a project or a person, so check them before sharing.",
]
CHALLENGE = "[Report a problem or suggest an idea](https://github.com/chalkbadger/stay-safe/issues/new/choose)"


class ReportOrderTests(ConfigCase):
    def run_cli(self, text, format_name="markdown"):
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(self.config(text)),
                              "--format", format_name], cwd=ROOT, env={}, text=True, capture_output=True, timeout=10)
        self.assertEqual(run.stderr, INCOMPLETE if run.returncode == 2 else "")
        return run

    def test_summary_then_findings_and_gaps_then_setup_sources_limits_and_a_footer_last(self):
        run = self.run_cli(AFTER)
        report = json.loads(self.run_cli(AFTER, "json").stdout)
        self.assertEqual(run.returncode, 2)
        lines = run.stdout.splitlines()
        self.assertEqual(lines[:4], ["# Codex configuration diagnostic", "", "4 findings, 2 things not checked.", ""])
        self.assertEqual([line for line in lines if line.startswith("#")], ["# Codex configuration diagnostic", *HEADINGS])
        revision = report["provenance"]["source_revision"]
        self.assertEqual(section(run.stdout, "What this report can't see"), "\n".join([
            *CANT_SEE, "",
            f"[Full scope of this report](https://github.com/chalkbadger/stay-safe/blob/{revision}/docs/report.md#full-scope)",
            "", "---", "",
            f"Made by stay-safe `{revision[:7]}` · report format 3 · {CHALLENGE}"]))
        self.assertTrue(run.stdout.endswith(f"· {CHALLENGE}\n"))

    def test_findings_and_gaps_render_as_separate_paragraphs_divided_by_rules(self):
        # In rendered Markdown, lines without a blank line between them join into one paragraph (CommonMark 4.8), and
        # `---` right under a text line makes it a heading (4.3), so each part needs blank lines around it.
        report = self.run_cli(AFTER).stdout
        # Each part of a finding is one line: What to do, then Change it, then a Check when the finding has one (archived issue #119,
        # re-review F15). The shared note before the findings is one line too.
        finding = ["**", "*How it has gone wrong:* ", "*What to do:* ", "*Change it:* "]
        for name, labels, count in (("Findings", finding, 4),
                                    ("Not checked", ["**Not checked: ", "*What to do:* ", "*File `"], 2)):
            with self.subTest(section=name):
                body = section(report, name)
                if name == "Not checked":
                    self.assertTrue(body.startswith(NOT_CHECKED_INTRO + "\n\n"))
                    body = body[len(NOT_CHECKED_INTRO) + 2:]
                else:
                    note, body = body.split("\n\n", 1)
                    self.assertTrue(note.startswith(NOTE_LABEL) and "\n" not in note, note)
                entries = body.split("\n\n---\n\n")
                self.assertEqual(len(entries), count)
                for entry in entries:
                    parts = entry.split("\n\n")
                    if name == "Findings":
                        self.assertTrue(parts[-1].startswith("*Rule `"), parts[-1])
                        middle = parts[len(labels):-1]
                        self.assertIn(len(middle), (0, 1))
                        self.assertTrue(all(part.startswith("*Check:* ") for part in middle), middle)
                        parts = parts[:len(labels)]
                    self.assertEqual([part[:len(label)] for part, label in zip(parts, labels)], labels)
                    self.assertEqual(len(parts), len(labels))
                    for part in entry.split("\n\n"):
                        self.assertNotIn("\n", part)
                    self.assertTrue(entry.endswith("*"), entry)
        self.assertNotIn("\n\n\n", report)
        lines = report.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("## ") or line == "---":
                self.assertEqual((lines[index - 1], lines[index + 1]), ("", ""), line)

    def test_the_full_scope_holds_every_scope_line(self):
        report = json.loads(self.run_cli(AFTER, "json").stdout)
        full = full_scope()
        for line in report["scope"] + ["Local modifications to the checkout or unzipped release are not checked; the JSON report's "
                                       "`tool_revision` and `rules_revision` fingerprints identify the files that ran."]:
            self.assertIn(f"\n- {line}\n", f"\n{full}\n")

    def test_summary_counts_one_and_none_and_empty_sections_say_what_that_means(self):
        one = self.run_cli('approval_policy = "never"\nshell_environment_policy = { inherit = "none" }\n')
        self.assertEqual((one.returncode, one.stdout.splitlines()[2]), (2, "1 finding, 1 thing not checked."))
        none = self.run_cli('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                            'shell_environment_policy = { inherit = "none" }\n')
        self.assertEqual((none.returncode, none.stdout.splitlines()[2]), (0, "0 findings, 0 things not checked."))
        self.assertEqual(section(none.stdout, "Findings"), EMPTY_FINDINGS)
        self.assertEqual(section(none.stdout, "Sources"), "No findings, so there are no rule sources to link.")
        self.assertEqual(section(none.stdout, "Not checked"),
                         EMPTY_GAPS)

    def test_empty_section_text_follows_its_own_section_and_the_count_includes_every_gap(self):
        self.require_no_system_folder()
        findings_only = self.run_cli('approval_policy = "never"\nsandbox_mode = "read-only"\n'
                                     'shell_environment_policy = { inherit = "none" }\n')
        self.assertEqual(findings_only.stdout.splitlines()[2], "1 finding, 0 things not checked.")
        self.assertNotIn(EMPTY_FINDINGS, section(findings_only.stdout, "Findings"))
        self.assertEqual(section(findings_only.stdout, "Not checked"), EMPTY_GAPS)
        gaps_only = self.run_cli('approval_policy = "on-request"\nshell_environment_policy = { inherit = "none" }\n')
        self.assertEqual(gaps_only.stdout.splitlines()[2], "0 findings, 1 thing not checked.")
        self.assertEqual(section(gaps_only.stdout, "Findings"), EMPTY_FINDINGS)
        self.assertNotIn(EMPTY_GAPS, section(gaps_only.stdout, "Not checked"))
        # A gap without a source label: a hooks.json file in the Codex home, beside a config file without gaps.
        home = self.root / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                                          'shell_environment_policy = { inherit = "none" }\n')
        (home / "hooks.json").write_text("{}")
        runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--format", f], cwd=ROOT,
                               env={"CODEX_HOME": str(home)}, text=True, capture_output=True, timeout=10)
                for f in ("json", "markdown")]
        self.assertEqual(len(json.loads(runs[0].stdout)["inspection_gaps"]), 1)
        self.assertEqual(runs[1].stdout.splitlines()[2], "0 findings, 1 thing not checked.")
