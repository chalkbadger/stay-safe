from html import escape
import json
import os
import subprocess
import sys

from stay_safe.report import inspect
from tests.see_every_connection_and_setting.test_config import FIXTURE
from tests.nothing_in_my_setup_changes.test_page import Page
from tests.support import REPORT, SEEDED, SEEDS, ConfigCase, ReportRuns, ROOT, copy_checkout, gap_items, run_checkout, section
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text


class ShareableTests(ReportRuns, ConfigCase):
    def test_report_excludes_private_values(self):
        # Running the same files twice gives the same output: tests/anyone_can_recheck_a_report/test_repeatable.py.
        path = self.config(SEEDED)
        before = path.read_bytes()
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                one = self.run_cli("--config", str(path), "--format", format_name)
                self.assertEqual((one.returncode, one.stderr), (0, ""))
                for field, seed in SEEDS.items():
                    for form in (seed, escape(seed, quote=True)):
                        self.assertNotIn(form, one.stdout, field)
                self.assertNotIn(str(path), one.stdout)
                if format_name == "json":
                    for identity in ("config-1:mcp_servers.disabled", "config-1:mcp_servers.local", "config-1:mcp_servers.remote", "config-1:model_providers.internal"):
                        self.assertIn(identity, one.stdout)
                else:
                    setup = section(one.stdout, "Your setup")
                    for name in ("MCP server `disabled`:", "MCP server `local`:", "MCP server `remote`:", "Model provider `internal`:"):
                        self.assertIn("\n- " + name, setup)
                self.assertIn("reported, not verified", one.stdout)
                self.assertIn("/incidents.md#i13-repository-settings-run-commands-on-collaborators-machines", one.stdout)
                # AGENTS.md names the agent's commentary section with an ASCII apostrophe.
                self.assertNotIn("Agent's own report", one.stdout)
                self.assertNotIn("No risks found", one.stdout)
        # --save: standard output (the Markdown report and the open command) and the saved page (archived issue #106).
        checkout = copy_checkout(self.root / "checkout")
        run = run_checkout(checkout, "--config", str(path), "--save", cwd=self.root)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        output_text, page = run.stdout, (checkout / REPORT).read_text(encoding="utf-8")
        self.assertTrue(output_text.splitlines()[-1].startswith("Saved the formatted report. Open it with: "))
        self.assertIn("**Your `local` MCP server can start a program on your computer.**", output_text)
        for output in (output_text, page):
            for field, seed in SEEDS.items():
                for form in (seed, escape(seed, quote=True), escape(seed, quote=False)):
                    self.assertNotIn(form, output, field)
            self.assertNotIn(str(path), output)
        shown = " ".join(Page(page).view()["words"])
        for name in ("MCP server disabled:", "MCP server local:", "MCP server remote:", "Model provider internal:"):
            self.assertIn(name, shown)
        self.assertIn("reported, not verified", page)
        self.assertIn("/incidents.md#i13-repository-settings-run-commands-on-collaborators-machines", page)
        self.assertEqual(before, path.read_bytes())

    def test_names_are_shown_as_written_and_the_report_says_to_check_them(self):
        lines = {"json": "Configuration names in the report, such as server, app, tool and provider names, "
                         "are shown as written and should be reviewed before sharing.",
                 "markdown": "Private values such as commands, addresses and tokens are left out, but names like "
                             "`github` are shown as written: names can identify a project or a person, so check them "
                             "before sharing."}
        names = {"json": "config-1:mcp_servers.acme-merger",
                 "markdown": "MCP server `acme-merger`: on, connects over HTTP (address left out), tool approval left "
                             "at the default, `auto` (asks depending on the tool's labels, unless `approval_policy` "
                             "is `never`)"}
        path = self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n'
                           '[mcp_servers.acme-merger]\nurl="https://example.com/mcp"\n')
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                scope, groups = self.scope_and_setup(self.run_cli("--config", str(path), "--format", format_name), format_name)
                self.assertIn(lines[format_name], scope)
                self.assertIn(names[format_name], groups["config-1"])

    def test_the_snapshot_note_counts_only_files_that_were_found(self):
        # A default run always lists config-1 and rules-1, found or not (re-review F22).
        self.require_no_system_folder()
        note = ("- These files are read as separate snapshots, not combined: Codex may apply several of them together, "
                "so a setting in one can change what another allows.")
        home = self.root / "codex-home"
        home.mkdir()
        cases = [("no files", [], False), ("config file only", ["config.toml"], False),
                 ("config and rules files", ["config.toml", "rules/default.rules"], True)]
        for name, files, expected in cases:
            with self.subTest(case=name):
                for file in files:
                    (home / file).parent.mkdir(parents=True, exist_ok=True)
                    (home / file).write_text('approval_policy="on-request"\nsandbox_mode="read-only"\n'
                                             if file == "config.toml" else 'prefix_rule(pattern=["git", "status"], decision="allow")\n')
                run = subprocess.run([sys.executable, "-B", "-m", "stay_safe"], cwd=ROOT, env={"CODEX_HOME": str(home)},
                                     text=True, capture_output=True, timeout=10)
                self.assertEqual(run.stderr, "")
                self.assertEqual(note in section(run.stdout, "What this report can't see").splitlines(), expected)

    def test_found_files_are_named_by_where_codex_keeps_them_without_the_users_folder(self):
        # Reading check (2026-11-09): a found file shows where it is, as `~/.codex/...` or `$CODEX_HOME/...`, never
        # the expanded folder, which can hold a user name.
        self.require_no_system_folder()
        # Codex also re-reads the file while it runs, and a file that wasn't found is read once it exists (F24).
        config_use = {True: "Codex reads its settings from this file.",
                      False: "Codex reads its settings from this file when it exists."}
        rules_use = "Codex saves \"don't ask again\" approvals to this file and loads them from it."
        home = self.root / "alice@example.com-home"
        codex_home = self.root / "alice@example.com-codex"
        # An empty CODEX_HOME counts as unset, as in Codex's find_codex_home (openai/codex 086ccc8,
        # utils/home-dir/src/lib.rs L13-L62); a set CODEX_HOME is named as such even when it is ~/.codex.
        empty, same = self.root / "alice@example.com-empty-codex-home", self.root / "alice@example.com-same"
        cases = [("home", {"HOME": str(home)}, home / ".codex", "~/.codex", True),
                 ("CODEX_HOME", {"CODEX_HOME": str(codex_home)}, codex_home, "$CODEX_HOME", True),
                 ("CODEX_HOME empty", {"HOME": str(empty), "CODEX_HOME": ""}, empty / ".codex", "~/.codex", True),
                 ("CODEX_HOME is HOME/.codex", {"HOME": str(same), "CODEX_HOME": str(same / ".codex")}, same / ".codex",
                  "$CODEX_HOME", True),
                 ("no files", {"HOME": str(self.root / "alice@example.com-empty")}, None, "~/.codex", False)]
        for name, env, folder, shown, files in cases:
            with self.subTest(case=name):
                if files:
                    (folder / "rules").mkdir(parents=True)
                    (folder / "config.toml").write_text('approval_policy="on-request"\n')
                    (folder / "rules" / "default.rules").write_text('prefix_rule(pattern=["git", "status"], decision="allow")\n')
                run = subprocess.run([sys.executable, "-B", "-m", "stay_safe"], cwd=ROOT, env=env,
                                     text=True, capture_output=True, timeout=10)
                self.assertEqual((run.returncode, run.stderr), (2, ""))
                setup = section(run.stdout, "Your setup")
                self.assertIn(f"\n**Config file `{shown}/config.toml`** (`config-1`): {config_use[files]}\n", "\n" + setup + "\n")
                self.assertIn(f"\n**Rules file `{shown}/rules/default.rules`** (`rules-1`): {rules_use}\n", "\n" + setup + "\n")
                self.assertTrue(gap_items(run.stdout)[0].endswith(f"\n\n*File `{shown}/config.toml`*"))
                for private in (str(self.root), "alice@example.com"):
                    self.assertNotIn(private, run.stdout)

    def test_gap_output_has_nonzero_status_and_preserves_safe_findings(self):
        missing = self.root / "alice@example.com-secret.toml"
        run = self.run_cli("--config", str(FIXTURE), "--config", str(missing))
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stderr, "")
        self.assertIn(gap_text("config-2: Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; "
                               "raw errors were withheld."), gap_items(run.stdout))
        self.assertIn("config-1:mcp_servers.git", run.stdout)
        self.assertNotIn(str(missing), run.stdout)

    def test_malformed_and_private_identifiers_never_echo_raw_input(self):
        examples = [
            'token = "fake-secret-do-not-share\n',
            'approval_policy="on-request"\nsandbox_mode="read-only"\n[mcp_servers."alice@example.com"]\nurl="https://example.com"',
            'approval_policy="on-request"\nsandbox_mode="read-only"\n[mcp_servers."sk-fake-secret-do-not-share"]\ncommand="python"',
            'approval_policy="fake-secret-do-not-share"\nsandbox_mode="read-only"',
        ]
        for text in examples:
            run = self.run_cli("--config", str(self.config(text)))
            self.assertEqual(run.returncode, 2)
            self.assertNotIn("fake-secret-do-not-share", run.stdout + run.stderr)
            self.assertNotIn("alice@example.com", run.stdout + run.stderr)
        for args in [("--unknown=fake-secret-do-not-share",),
                     ("--rules", "private-first.rules", "--rules", "private-second.rules")]:
            invalid = self.run_cli(*args)
            self.assertEqual((invalid.returncode, invalid.stdout, invalid.stderr), (2, "", "Invalid arguments. Use --help.\n"))

    def test_default_path_uses_codex_home_without_disclosing_it(self):
        self.require_no_system_folder()
        path = self.config('approval_policy="on-request"\nsandbox_mode="read-only"')
        run = self.run_cli("--format", "json", env={**os.environ, "CODEX_HOME": str(path.parent)})
        self.assertEqual(run.returncode, 0)
        self.assertEqual([e["name"] for e in json.loads(run.stdout)["catalog"] if e["source"] == "config-1"],
                         ["approval_policy", "features.apps", "sandbox_mode", "shell_environment_policy"])
        self.assertNotIn(str(path.parent), run.stdout)

    def test_symlink_nonregular_large_and_invalid_utf8_inputs_are_gaps(self):
        target = self.config('approval_policy="on-request"\nsandbox_mode="read-only"')
        link = self.root / "link.toml"
        link.symlink_to(target)
        directory = self.root / "directory"
        directory.mkdir()
        large = self.root / "large.toml"
        large.write_bytes(b" " * (1024 * 1024 + 1))
        invalid = self.root / "invalid.toml"
        invalid.write_bytes(b"\xff")
        for path in (link, directory, large, invalid):
            with self.subTest(input=path.name):
                report = inspect([path])
                self.assertEqual(report["file_inspection"], "incomplete")
                self.assertEqual(report["catalog"], [])
                self.assertTrue(report["inspection_gaps"])

    def test_absent_default_report_is_repeatable_without_disclosing_its_path(self):
        home = self.root / 'alice@example.com-private-home'
        home.mkdir()
        for format_name in ('markdown', 'json'):
            with self.subTest(format=format_name):
                args = ('--format', format_name)
                one = self.run_cli(*args, env={'HOME': str(home)})
                two = self.run_cli(*args, env={'HOME': str(home)})
                self.assertEqual((one.returncode, one.stderr), (2, ''))
                self.assertEqual((two.returncode, two.stderr, two.stdout), (2, '', one.stdout))
                self.assertIn('environment_inheritance', one.stdout)
                self.assertNotIn(str(self.root), one.stdout)
                self.assertNotIn('alice@example.com', one.stdout)
                self.assertEqual(list(home.iterdir()), [])

    def test_rejected_default_withholds_raw_errors_from_both_streams(self):
        self.require_no_system_folder()
        home = self.root / 'alice@example.com-private-home'
        home.mkdir()
        (home / 'config.toml').write_text('')
        home_file = self.root / 'alice@example.com-private-home-file'
        home_file.write_text('private-error-marker')
        script = r'''
import os, sys
from pathlib import Path
from unittest.mock import patch
from stay_safe.cli import main
path = Path(os.environ['CODEX_HOME']) / 'config.toml'
original_open = os.open
def denied(file, *args, **kwargs):
    if file == path:
        raise PermissionError(13, 'private-error-marker', str(path))
    return original_open(file, *args, **kwargs)
with patch('stay_safe.codex.os.open', side_effect=denied):
    sys.exit(main(['--format', sys.argv[1]]))
'''
        gap = 'config-1: Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.'
        cases = [
            ('permission', home, ['-c', script], [gap]),
            ('regular-file-home', home_file, ['-m', 'stay_safe', '--format'], [
                'Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; '
                'Codex would not start, so no default files were inspected.',
            ]),
        ]
        for name, selected_home, args, gaps in cases:
            for format_name in ('markdown', 'json'):
                with self.subTest(input=name, format=format_name):
                    run = subprocess.run([sys.executable, '-B', *args, format_name], cwd=ROOT,
                                         env={'CODEX_HOME': str(selected_home)}, text=True,
                                         capture_output=True, timeout=10)
                    self.assertEqual((run.returncode, run.stderr), (2, ''))
                    if format_name == 'json':
                        self.assertCountEqual(json.loads(run.stdout)['inspection_gaps'], gaps)
                    else:
                        # A default run names config-1 by where Codex keeps it, not by its folder.
                        self.assertCountEqual(gap_items(run.stdout),
                                              [gap_text(gap, file='$CODEX_HOME/config.toml') for gap in gaps])
                    for private in ('private-error-marker', 'alice@example.com', str(self.root)):
                        self.assertNotIn(private, run.stdout + run.stderr)
