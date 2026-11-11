"""`--save` writes only its own report file in the checkout, then prints the Markdown report and a command that
opens the page (archived issue #106 and @weiks's decision after his macOS run).

Each run uses a copy of the checkout outside the home and working directories, with Python's bytecode cache off:
the claim is about stay-safe's code, and Python's own cache (stay_safe/__pycache__, in .gitignore) is outside it.
"""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from unittest.mock import patch

from stay_safe.__main__ import main
from tests.see_every_connection_and_setting.test_report_order import AFTER
from tests.support import ConfigCase, REPORT, copy_checkout, run_checkout, tree_state

NO_GAPS = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\nshell_environment_policy = { inherit = "none" }\n'
# The one line archived issue #106 asks for when the file can't be written; error details are withheld.
NOT_SAVED = "Could not save stay-safe-report.html in the stay-safe folder; the full report follows.\n"
# The last line archived issue #106 now asks for, before its command; the command is `open` on macOS, `xdg-open` elsewhere.
OPEN_WITH = "Saved the formatted report. Open it with: "
OPENER = "open" if sys.platform == "darwin" else "xdg-open"
# A checkout folder name a shell would misread unless the path is quoted: a space, double quotes, `$`, a backtick,
# a single quote, `!`, `#` and `%`.
FOLDER = "check out \"1\" $HOME `id` it's !x #2 %20"


class SaveTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.checkout = copy_checkout(self.root / FOLDER)
        self.home, self.work = self.root / "home", self.root / "work"
        self.home.mkdir()
        self.work.mkdir()
        self.env = {"HOME": str(self.home)}

    def run_save(self, *args, user=None):
        return run_checkout(self.checkout, *args, cwd=self.work, env=self.env, user=user)

    def test_without_save_nothing_is_written_and_with_save_only_the_report_is_added_or_replaced(self):
        self.require_no_system_folder()  # one run below is a default run
        config = str(self.config(AFTER))
        report = self.checkout / REPORT
        before = tree_state(self.root)
        for args in (["--config", config], ["--config", config, "--format", "json"], []):
            with self.subTest(args=args):
                run = self.run_save(*args)
                self.assertEqual((run.returncode, run.stderr), (2, ""))
                self.assertEqual(tree_state(self.root), before)
        for previous in (None, "an older report\n"):
            with self.subTest(previous=previous):
                if previous:
                    report.write_text(previous, encoding="utf-8")
                run = self.run_save("--config", config, "--save")
                self.assertEqual((run.returncode, run.stderr), (2, ""))
                after = tree_state(self.root)
                self.assertEqual(set(after) - set(before), {str(report)})
                self.assertEqual({k: v for k, v in after.items() if k != str(report)}, before)
                self.assertTrue(report.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
        with self.subTest(previous="symlink to a file outside the checkout"):
            outside = self.root / "outside.html"
            outside.write_text("outside\n", encoding="utf-8")
            report.unlink()
            report.symlink_to(outside)
            before = tree_state(self.root)
            run = self.run_save("--config", config, "--save")
            self.assertEqual((run.returncode, run.stderr), (2, ""))
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")
            self.assertFalse(report.is_symlink())
            self.assertTrue(report.is_file())
            self.assertTrue(report.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
            after = tree_state(self.root)
            self.assertEqual(set(after), set(before))
            self.assertEqual({k: v for k, v in after.items() if k != str(report)},
                             {k: v for k, v in before.items() if k != str(report)})

    def test_save_prints_the_markdown_report_then_a_command_that_opens_the_saved_page(self):
        page = str((self.checkout / REPORT).resolve())
        for text, status in ((AFTER, 2), (NO_GAPS, 0)):
            with self.subTest(status=status):
                config = str(self.config(text, f"status-{status}.toml"))
                plain = self.run_save("--config", config)
                run = self.run_save("--config", config, "--save")
                self.assertEqual((run.returncode, run.stderr, plain.returncode), (status, "", status))
                self.assertTrue(plain.stdout.startswith("# Codex configuration diagnostic\n"))
                self.assertEqual(run.stdout[:len(plain.stdout)], plain.stdout)
                last = run.stdout[len(plain.stdout):]
                self.assertTrue(last.startswith(OPEN_WITH) and last.endswith("\n") and last.count("\n") == 1, last)
                # The shell's own reading of the command (shlex follows POSIX sh quoting) gives the page's plain path.
                self.assertEqual(shlex.split(last[len(OPEN_WITH):]), [OPENER, page])
        # Pasted into a shell, the command hands the opener exactly that path; a stand-in opener records it.
        command = last[len(OPEN_WITH):].rstrip("\n")
        tools, record = self.root / "tools", self.root / "opened.txt"
        tools.mkdir()
        for name in ("open", "xdg-open"):
            (tools / name).write_text('#!/bin/sh\nprintf \'%s\' "$*" > "$RECORD"\n', encoding="utf-8")
            (tools / name).chmod(0o755)
        shells = [shell for shell in ("sh", "bash", "zsh") if shutil.which(shell)]
        self.assertIn("sh", shells)
        for shell in shells:
            with self.subTest(shell=shell):
                record.unlink(missing_ok=True)
                subprocess.run([shutil.which(shell), "-c", command], env={"PATH": f"{tools}:/usr/bin:/bin",
                               "RECORD": str(record)}, check=True, timeout=10)
                self.assertEqual(record.read_text(encoding="utf-8"), page)
                self.assertTrue(Path(page).is_file())

    def test_the_command_is_open_on_macos_and_xdg_open_elsewhere(self):
        page = self.root / FOLDER / "page.html"
        config = str(self.config(NO_GAPS))
        for platform, opener in (("darwin", "open"), ("linux", "xdg-open"), ("freebsd14", "xdg-open")):
            with self.subTest(platform=platform):
                output = io.StringIO()
                with patch("stay_safe.__main__.save", return_value=page), patch.object(sys, "platform", platform), \
                        redirect_stdout(output):
                    status = main(["--config", config, "--save"])
                self.assertEqual(status, 0)
                last = output.getvalue().splitlines()[-1]
                self.assertEqual(shlex.split(last[len(OPEN_WITH):]), [opener, str(page)])

    def test_when_the_report_cannot_be_written_one_line_says_so_then_the_markdown_report_follows(self):
        cases = [("report path is a folder", None)]
        if os.geteuid() == 0:
            cases.append(("checkout is read-only", "nobody"))  # root can write to a read-only folder
        else:
            cases.append(("checkout is read-only", None))
        for name, user in cases:
            with self.subTest(case=name):
                report = self.checkout / REPORT
                if name == "report path is a folder":
                    report.mkdir()
                else:
                    report.rmdir()
                    for path in (self.root, self.home, self.work, *self.root.glob("*.toml")):
                        path.chmod(0o777 if path in (self.home, self.work) else 0o755)
                    self.checkout.chmod(0o555)
                    self.addCleanup(self.checkout.chmod, 0o755)
                for text, status in ((AFTER, 2), (NO_GAPS, 0)):
                    config = str(self.config(text, f"status-{status}.toml"))
                    if user:
                        os.chmod(config, 0o644)
                    markdown = self.run_save("--config", config, user=user)
                    before = tree_state(self.root)
                    run = self.run_save("--config", config, "--save", user=user)
                    self.assertEqual((run.returncode, run.stderr, run.stdout), (status, NOT_SAVED, markdown.stdout))
                    self.assertTrue(markdown.stdout.startswith("# Codex configuration diagnostic\n"))
                    self.assertEqual(tree_state(self.root), before)

    def test_save_with_json_format_is_rejected_without_a_report_or_file(self):
        config = str(self.config(AFTER))
        before = tree_state(self.root)
        run = self.run_save("--config", config, "--format", "json", "--save")
        self.assertEqual((run.returncode, run.stdout, run.stderr),
                         (2, "", "--save can't be combined with --format json. Use --help.\n"))
        help_text = self.run_save("--help").stdout
        self.assertIn("Not with --format json.", " ".join(help_text.split()))
        self.assertEqual(tree_state(self.root), before)
