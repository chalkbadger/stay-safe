import io
import json
import os
import subprocess
import sys
from contextlib import chdir, redirect_stderr, redirect_stdout
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase, INCOMPLETE, ROOT, finding_items, section


class WorkspaceSettingsTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.workspace = self.root.resolve() / "private-project-name"
        home = patch.dict(os.environ, {"HOME": str(self.root.resolve() / "user-home")})
        home.start()
        self.addCleanup(home.stop)
        self.workspace.mkdir()
        self.target = self.workspace / ".codex"
        self.target.mkdir()

    def settings(self, roots=None, *, mode='sandbox_mode="workspace-write"', name="config.toml", extra=""):
        lines = ['approval_policy="on-request"', 'shell_environment_policy={inherit="none"}', mode, extra]
        if roots is not None:
            lines += ["[sandbox_workspace_write]", "writable_roots=" + json.dumps(roots)]
        return self.config("\n".join(lines), name)

    def run_report(self, *paths, workspace=True, fmt="json", status=2):
        args = ["--agent", "codex", "--format", fmt]
        if workspace:
            args += ["--workspace", str(self.workspace)]
        for path in paths:
            args += ["--config", str(path)]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                result = main(args)
            except SystemExit as error:
                result = error.code
        self.assertEqual((result, err.getvalue()), (status, INCOMPLETE if status == 2 else ""))
        self.assertNotIn("private-project-name", out.getvalue())
        self.assertNotIn(str(self.root), out.getvalue())
        return json.loads(out.getvalue()) if fmt == "json" else out.getvalue()

    def test_direct_grant_warns_once_and_keeps_the_unchecked_effects_visible(self):
        path = self.settings([str(self.target), str(self.target)])
        report = self.run_report(path)
        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]],
                         [("writable_project_settings", "config-1:sandbox_workspace_write.writable_roots")])
        risk = report["risks"][0]
        self.assertIn("later trusted", risk["explanation"])
        self.assertEqual(len(report["inspection_gaps"]), 1)
        self.assertIn("other effects of extra folders", report["inspection_gaps"][0])
        markdown = self.run_report(path, fmt="markdown")
        finding, = finding_items(markdown)
        self.assertIn("later trusted", finding)
        self.assertIn("writable_roots", finding)
        edit_prompt = finding.split("or ask Codex: ", 1)[1].splitlines()[0]
        self.assertIn("remove the selected project's `.codex` directory from `writable_roots`", edit_prompt)
        self.assertIn("other effects of extra writable folders", section(markdown, "Not checked"))

    def test_removing_direct_grant_leaves_parent_sibling_lookalike_and_narrower_roots_without_a_warning(self):
        roots = [self.workspace, self.workspace.parent / "sibling", self.workspace / ".codex-backup",
                 self.target / "narrower"]
        self.assertEqual(self.run_report(self.settings([str(p) for p in roots] + [str(self.target)]))
                         ["risks"][0]["rule"], "writable_project_settings")
        report = self.run_report(self.settings([str(p) for p in roots]))
        self.assertEqual(report["risks"], [])
        self.assertIn("writable_roots", " ".join(report["inspection_gaps"]))

    def test_equivalent_home_and_parent_spellings_identify_only_direct_grants(self):
        elsewhere = self.workspace / "route"
        elsewhere.symlink_to(self.root.resolve(), target_is_directory=True)
        home = self.workspace.parent
        for root, selected_home, expected in [
                ("~/private-project-name/.codex", home, True),
                ("~//private-project-name/.codex", home, True),
                ("~", self.target, True),
                (str(elsewhere / ".." / ".codex"), home, True),
                (str(self.workspace / "missing" / ".." / ".codex"), home, True),
                (str(self.target / ".."), home, False),
                ("~/private-project-name", home, False),
                ("~/private-project-name/.codex", self.workspace, False),
                ("~someone/private-project-name/.codex", home, False)]:
            with self.subTest(root=root, home=selected_home), patch.dict(os.environ, {
                    "HOME": str(selected_home), "CODEX_HOME": str(self.root.resolve() / "private-codex-home")}):
                path = self.settings(["relative-unknown", root])
                report = self.run_report(path)
                self.assertEqual([r["entry"] for r in report["risks"]],
                                 ["config-1:sandbox_workspace_write.writable_roots"] if expected else [])

    def test_home_relative_root_with_unknown_home_keeps_independent_direct_grants(self):
        tilde = "~/private-project-name/.codex"
        direct = str(self.target)
        for home in (None, "", "private-relative-home", str(self.workspace.parent)):
            with patch.dict(os.environ, {"CODEX_HOME": str(self.root.resolve() / "private-codex-home")}):
                if home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = home
                known = home == str(self.workspace.parent)
                for roots in ([tilde], ["~"], [tilde, direct], [direct, tilde], [direct], ["~user"], ["relative"]):
                    with self.subTest(home=home, roots=roots):
                        report = self.run_report(self.settings(roots))
                        needs_home = tilde in roots or "~" in roots
                        named = [g for g in report["inspection_gaps"] if "HOME" in g and "absolute" in g]
                        self.assertEqual(len(named), int(needs_home and not known))
                        self.assertTrue(any("outside the workspace" in g for g in report["inspection_gaps"]))
                        self.assertNotIn("private-relative-home", json.dumps(report))
                        self.assertEqual([r["entry"] for r in report["risks"]],
                                         ["config-1:sandbox_workspace_write.writable_roots"]
                                         if direct in roots or tilde in roots and known else [])
                if not known:
                    with self.subTest(home=home, fmt="markdown"):
                        markdown = self.run_report(self.settings([tilde, direct]), fmt="markdown")
                        gap = section(markdown, "Not checked")
                        self.assertIn("home-relative", gap)
                        self.assertIn("HOME", gap)
                        self.assertIn("absolute", gap)
                        self.assertNotIn("private-relative-home", markdown)

    def test_unusable_workspace_names_the_gap_even_with_a_differently_spelled_root(self):
        alias = self.root.resolve() / "private-alias"
        alias.symlink_to(self.workspace, target_is_directory=True)
        file = self.config("private-contents", name="private-file")
        path = self.settings([str(self.target)])
        for workspace in (alias, file):
            with self.subTest(workspace=workspace.name), patch.object(self, "workspace", workspace):
                report = self.run_report(path)
                self.assertEqual(report["risks"], [])
                self.assertTrue(any(g.startswith("config-1: The project .codex comparison") for g in
                                    report["inspection_gaps"]), report["inspection_gaps"])
                self.assertEqual(self.run_report(self.settings([], name="empty.toml"), status=0)["inspection_gaps"], [])

    def test_repeated_workspace_is_rejected_without_disclosing_either_directory(self):
        out, err = io.StringIO(), io.StringIO()
        config = self.settings([str(self.target)])
        with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as rejected:
            main(["--config", str(config), "--workspace", "private-first", "--workspace", "private-second"])
        self.assertEqual(rejected.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("--workspace", err.getvalue())
        self.assertNotIn("private-", err.getvalue())

    def test_extra_folder_gap_explains_outside_access_and_withheld_paths(self):
        path = self.settings([str(self.target)])
        for supplied in (True, False):
            for fmt in ("markdown", "json"):
                with self.subTest(workspace=supplied, fmt=fmt):
                    report = self.run_report(path, workspace=supplied, fmt=fmt)
                    gap = " ".join(report["inspection_gaps"]) if fmt == "json" else section(report, "Not checked")
                    self.assertIn("outside", gap.lower())
                    self.assertRegex(gap.lower(), r"paths (?:were |are )?(?:withheld|left out)")
                    if fmt == "markdown":
                        self.assertIn("Docker socket", gap)

    def test_mode_and_roots_must_appear_in_the_same_selected_snapshot(self):
        eligible = self.settings()
        roots = self.settings([str(self.target)], mode="", name="roots.toml")
        report = self.run_report(eligible, roots)
        self.assertEqual(report["risks"], [])
        self.assertIn("config-2: sandbox_mode is absent", " ".join(report["inspection_gaps"]))
        eligible = self.settings([str(self.target)], name="eligible.toml")
        self.assertEqual([r["entry"] for r in self.run_report(roots, eligible)["risks"]],
                         ["config-2:sandbox_workspace_write.writable_roots"])

    def test_inactive_empty_invalid_and_profile_cases(self):
        root = [str(self.target)]
        for mode, roots, gap in [('sandbox_mode="read-only"', root, None),
                                 ('sandbox_mode="workspace-write"', [], None),
                                 ('sandbox_mode="workspace-write"', None, None),
                                 ('sandbox_mode="read-only"', 7, "invalid"),
                                 ('default_permissions=":workspace"', root, "profile"),
                                 ('default_permissions="private-profile"', root, "profile"),
                                 ('sandbox_mode="workspace-write"\nprofile="private-profile"', root, "profile")]:
            with self.subTest(mode=mode, roots=roots):
                report = self.run_report(self.settings(roots, mode=mode), status=2 if gap else 0)
                self.assertEqual(report["risks"], [])
                if gap:
                    self.assertIn(gap, " ".join(report["inspection_gaps"]).lower())

    def test_missing_workspace_and_unresolved_aliases_name_the_boundary(self):
        path = self.settings([str(self.target)])
        for fmt in ["json", "markdown"]:
            with chdir(self.workspace):
                report = self.run_report(path, workspace=False, fmt=fmt)
            if fmt == "json":
                self.assertEqual(report["risks"], [])
            gap = " ".join(report["inspection_gaps"]) if fmt == "json" else section(report, "Not checked")
            self.assertIn("--workspace", gap)
        err = io.StringIO()
        with chdir(self.workspace), redirect_stderr(err), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as invalid:
                main(["--workspace", "", "--config", str(path)])
        self.assertEqual(invalid.exception.code, 2)
        self.assertIn("--workspace needs a directory", err.getvalue())
        alias = self.workspace / "private-alias"
        alias.symlink_to(self.target, target_is_directory=True)
        ordinary = self.run_report(self.settings([str(self.workspace)]))
        for candidate in [str(alias), "../private-project-name/.codex"]:
            report = self.run_report(self.settings([candidate]))
            self.assertEqual(report["risks"], [])
            self.assertEqual(report["inspection_gaps"], ordinary["inspection_gaps"])

    def test_direct_grant_through_a_target_or_workspace_symlink_names_the_unresolved_path(self):
        workspace_link = self.root.resolve() / "private-workspace-alias"
        workspace_link.symlink_to(self.workspace, target_is_directory=True)
        linked_target_workspace = self.root.resolve() / "private-project-symlink"
        linked_target_workspace.mkdir()
        (linked_target_workspace / ".codex").symlink_to(self.target, target_is_directory=True)
        expected = ("config-1: The project .codex comparison depends on an unresolved path, symlink or directory "
                    "that could not be checked.")
        for workspace in (linked_target_workspace, workspace_link):
            with self.subTest(workspace=workspace.name), patch.object(self, "workspace", workspace):
                path = self.settings([str(workspace / ".codex")])
                report = self.run_report(path)
                self.assertIn(expected, report["inspection_gaps"])
                self.assertEqual(report["risks"], [])

    def test_user_codex_home_is_outside_the_project_settings_check(self):
        path = self.settings([str(self.target)])
        with patch.dict(os.environ, {"CODEX_HOME": str(self.target)}):
            report = self.run_report(path)
        self.assertEqual(report["risks"], [])
        self.assertIn("Codex home", " ".join(report["inspection_gaps"]))
        alias = self.root / "private-home-alias"
        alias.symlink_to(self.target, target_is_directory=True)
        with patch.dict(os.environ, {"CODEX_HOME": str(alias)}):
            report = self.run_report(path)
        self.assertEqual(report["risks"], [])
        self.assertIn("Codex home", " ".join(report["inspection_gaps"]))

    def test_different_home_spellings_use_directory_identity(self):
        candidate = self.workspace / ".CODEX"
        candidate.mkdir(exist_ok=True)
        path = self.settings([str(self.target)])
        with patch.dict(os.environ, {"CODEX_HOME": str(candidate)}):
            report = self.run_report(path)
        if candidate.samefile(self.target):
            self.assertEqual(report["risks"], [])
            self.assertIn("user Codex home", " ".join(report["inspection_gaps"]))
        else:
            self.assertEqual([r["rule"] for r in report["risks"]], ["writable_project_settings"])
        distinct = self.workspace / "other-home"
        distinct.mkdir()
        with patch.dict(os.environ, {"CODEX_HOME": str(distinct)}):
            self.assertEqual([r["rule"] for r in self.run_report(path)["risks"]], ["writable_project_settings"])
            alternate = self.run_report(self.settings([str(candidate)]))
            self.assertEqual(alternate["risks"], [])

    def test_missing_settings_directory_preserves_the_existing_parent_identity(self):
        self.target.rmdir()
        path = self.settings([str(self.target)])
        other_spelling = self.workspace.with_name(self.workspace.name.upper())
        other_spelling.mkdir(exist_ok=True)
        distinct = self.root.resolve() / "other-home"
        distinct.mkdir()
        for home in (other_spelling, distinct):
            with self.subTest(home=home.name), patch.dict(os.environ, {"HOME": str(home), "CODEX_HOME": ""}):
                report = self.run_report(path)
                if home.samefile(self.workspace):
                    self.assertEqual(report["risks"], [])
                    self.assertIn("user Codex home", " ".join(report["inspection_gaps"]))
                else:
                    self.assertEqual([r["rule"] for r in report["risks"]], ["writable_project_settings"])
        with patch.dict(os.environ, {"CODEX_HOME": str(self.workspace / ".CODEX")}):
            report = self.run_report(path)
        self.assertEqual(report["risks"], [])
        self.assertIn("could not be distinguished", " ".join(report["inspection_gaps"]))
        with patch.dict(os.environ, {"CODEX_HOME": str(self.workspace / "separate-missing-home")}):
            self.assertEqual([r["rule"] for r in self.run_report(path)["risks"]], ["writable_project_settings"])
        selected = self.workspace / "caf\u00e9"
        possible_home = self.workspace / "cafe\u0301" / ".codex"
        path = self.settings([str(selected / ".codex")])
        with patch.object(self, "workspace", selected), patch.dict(os.environ, {"CODEX_HOME": str(possible_home)}):
            report = self.run_report(path)
        self.assertEqual(report["risks"], [])
        self.assertIn("could not be distinguished", " ".join(report["inspection_gaps"]))

    def test_workspace_compares_discovered_settings_without_opening_project_contents(self):
        home = self.root.resolve() / "private-codex-home"
        home.mkdir()
        self.settings([str(self.target)]).rename(home / "config.toml")
        for name in ["config.toml", "auth.json", "AGENTS.md"]:
            (self.target / name).write_text("private-project-contents", encoding="utf-8")
        script = """
import sys
from pathlib import Path
from stay_safe.cli import main

workspace = Path(sys.argv[1])
def guard(event, args):
    if event in ("open", "os.listdir", "os.scandir") and isinstance(args[0], str):
        path = Path(args[0])
        if path == workspace or workspace in path.parents:
            raise RuntimeError("opened project contents")
sys.addaudithook(guard)
raise SystemExit(main(["--agent", "codex", "--workspace", str(workspace), "--format", "json"]))
"""
        run = subprocess.run([sys.executable, "-B", "-c", script, str(self.workspace)],
                             cwd=ROOT, env={**os.environ, "CODEX_HOME": str(home)},
                             capture_output=True, text=True, timeout=10)
        self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
        self.assertNotIn("private-", run.stdout)
        self.assertEqual([r["rule"] for r in json.loads(run.stdout)["risks"]], ["writable_project_settings"])
