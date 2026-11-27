import json
import subprocess
from contextlib import chdir

from stay_safe import report
from stay_safe.repo_locations import selected_files

from tests.support import ConfigCase, ROOT, run_checkout


APPROVAL = "config-1:approval_policy/commands_without_prompts"
LOCATION = {"artifactLocation": {"uri": "team%20%231%25.toml"}, "region": {"startLine": 2}}


class RepoLocationTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.repo = self.root.resolve() / "project"
        self.repo.mkdir()
        self.git("init", "-q")
        self.sample = self.repo / "team #1%.toml"
        self.sample.write_text('# approval_policy = "never"\napproval_policy="never"\n'
                               'sandbox_mode="read-only"\nnotify=["PRIVATE_COMMAND"]\n')
        self.git("add", "--", self.sample.name)
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Sample")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def run_export(self, *args, opt=True, cwd=None, env=None):
        flags = ["--sarif-repo-locations"] if opt else []
        result = run_checkout(ROOT, "--format", "sarif", *flags, *map(str, args), cwd=cwd or self.repo, env=env)
        self.assertIn(result.returncode, (0, 2))
        self.assertNotIn("PRIVATE_COMMAND", result.stdout + result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        run, = json.loads(result.stdout)["runs"]
        return result, run

    def export(self, *args, **options):
        _, run = self.run_export(*args, **options)
        return {item["locations"][0]["logicalLocations"][0]["fullyQualifiedName"] + "/" + item["ruleId"]:
                item["locations"][0].get("physicalLocation") for item in run["results"]}

    def test_only_an_opted_in_tracked_selected_config_shows_its_relative_uri_and_setting_line(self):
        sub = self.repo / "sub" / "nested"
        sub.mkdir(parents=True)
        for path, cwd in ((self.sample.name, self.repo), (self.sample, sub),
                          ("../../" + self.sample.name, sub)):
            with self.subTest(path=path, cwd=cwd):
                loc = self.export("--config", path, cwd=cwd)
                self.assertEqual(loc[APPROVAL], LOCATION)
                self.assertIsNone(loc["config-1:shell_environment_policy/environment_inheritance"])
                self.assertEqual(loc["config-1:notify/configured_program"]["region"]["startLine"], 4)
                self.assertEqual(self.export("--config", path, cwd=cwd, opt=False), dict.fromkeys(loc))

    def test_full_index_versions_identify_the_tracked_sample(self):
        for version in ("2", "3", "4"):
            self.git("update-index", "--index-version", version)
            with self.subTest(version=version):
                self.assertEqual(self.export("--config", self.sample)[APPROVAL], LOCATION)

    def test_discovery_and_selected_files_outside_the_index_or_checkout_keep_paths_private(self):
        outside = self.root.resolve() / "private.toml"
        outside.write_bytes(self.sample.read_bytes())
        other = self.repo / "untracked.toml"
        other.write_bytes(outside.read_bytes())
        reported = self.export("--config", outside, "--config", other, "--config", self.sample)
        self.assertIsNone(reported[APPROVAL])
        self.assertIsNone(reported[APPROVAL.replace("1:", "2:")])
        self.assertEqual(reported[APPROVAL.replace("1:", "3:")], LOCATION)
        home = self.repo / "home"
        (home / "rules").mkdir(parents=True)
        (home / "config.toml").write_bytes(self.sample.read_bytes())
        (home / "rules" / "default.rules").write_text('prefix_rule(pattern=["PRIVATE_COMMAND"], decision="allow")')
        self.git("add", "--", "home")
        self.assertFalse(any(self.export("--agent", "codex", env={"CODEX_HOME": str(home)}).values()))
        self.assertFalse(any(self.export("--rules", home / "rules" / "default.rules").values()))

    def test_symlinks_and_paths_that_leave_the_checkout_keep_locations_private(self):
        outside = self.root.resolve() / "outside"
        outside.mkdir()
        (outside / "input").write_bytes(self.sample.read_bytes())
        folder = self.repo / "dir"
        folder.mkdir()
        (folder / "input").write_bytes(self.sample.read_bytes())
        self.git("add", "--", "dir")
        (folder / "input").unlink()
        folder.rmdir()
        folder.symlink_to(outside, target_is_directory=True)
        self.assertIsNone(self.export("--config", folder / "input")[APPROVAL])
        link = self.repo / "linked"
        link.symlink_to(self.sample)
        self.git("add", "--", "linked")
        self.assertFalse(any(self.export("--config", link).values()))
        self.assertIsNone(self.export("--config", self.sample, cwd=outside)[APPROVAL])
        (outside.parent / self.sample.name).write_bytes(self.sample.read_bytes())
        self.assertIsNone(self.export("--config", "dir/../" + self.sample.name)[APPROVAL])
        self.assertIsNone(self.export("--config", "../project/" + self.sample.name)[APPROVAL])

    def test_unmerged_and_intent_to_add_entries_keep_locations_private(self):
        other = self.repo / "untracked.toml"
        other.write_bytes(self.sample.read_bytes())
        self.git("add", "-N", "--", other.name)
        self.assertIsNone(self.export("--config", other)[APPROVAL])
        self.git("update-index", "--force-remove", "--", self.sample.name)
        oid = subprocess.check_output(["git", "hash-object", str(self.sample)], cwd=self.repo).decode().strip()
        subprocess.run(["git", "update-index", "--index-info"], cwd=self.repo,
                       input=f"100644 {oid} 2\t{self.sample.name}\n", text=True, check=True)
        self.assertIsNone(self.export("--config", self.sample)[APPROVAL])

    def test_corrupt_index_keeps_locations_private(self):
        (self.repo / ".git" / "index").write_bytes(b"truncated")
        self.assertIsNone(self.export("--config", self.sample)[APPROVAL])

    def test_dirty_content_warns_without_a_path_and_reverting_restores_the_line(self):
        clean = self.sample.read_bytes()
        self.sample.write_bytes(b"\n\n\n" + clean)
        result, run = self.run_export("--config", self.sample)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        invocation, = run["invocations"]
        self.assertTrue(invocation["executionSuccessful"])
        warning, = invocation["toolExecutionNotifications"]
        self.assertEqual((warning["level"], warning["descriptor"]["id"]), ("warning", "no-repository-locations"))
        self.assertEqual(run["tool"]["driver"]["notifications"], [warning["descriptor"]])
        self.assertIn("No finding in this run has a verified repository file and line.", warning["message"]["text"])
        self.assertNotIn("physicalLocation", result.stdout)
        self.assertNotIn(self.sample.name, result.stdout)
        self.assertNotIn("team%20", result.stdout)
        self.assertIn("config-1:approval_policy", result.stdout)
        self.assertNotIn("no-repository-locations", self.run_export("--config", self.sample, opt=False)[0].stdout)
        self.sample.write_bytes(clean)
        self.assertEqual(self.export("--config", self.sample)[APPROVAL], LOCATION)

    def test_warnings_apply_only_to_runs_with_findings_and_no_verified_lines(self):
        outside = self.root / "private.toml"
        outside.write_bytes(self.sample.read_bytes())
        mixed, _ = self.run_export("--config", outside, "--config", self.sample)
        self.assertNotIn("no-repository-locations", mixed.stdout)
        outside.write_text('approval_policy="on-request"\nsandbox_mode="read-only"\nshell_environment_policy={inherit="none"}')
        clean, run = self.run_export("--config", outside)
        self.assertEqual(run["results"], [])
        self.assertNotIn("no-repository-locations", clean.stdout)

    def test_git_overrides_and_omitted_checksums_fall_back_without_disclosing_paths(self):
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
            with self.subTest(key=key):
                self.assertIsNone(self.export("--config", self.sample, env={key: str(self.root)})[APPROVAL])
        self.git("config", "index.skipHash", "true")
        self.git("update-index", "--force-write-index")
        self.assertEqual((self.repo / ".git/index").read_bytes()[-20:], bytes(20))
        self.assertIsNone(self.export("--config", self.sample)[APPROVAL])

    def test_sparse_checkout_verifies_only_individual_index_entries(self):
        for name in ("visible", "collapsed"):
            folder = self.repo / name
            folder.mkdir()
            (folder / "sample.toml").write_bytes(self.sample.read_bytes())
        self.git("add", "--", "visible", "collapsed")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Folders")
        self.git("sparse-checkout", "set", "--cone", "--sparse-index", "visible")
        self.assertIn(b"sdir", (self.repo / ".git/index").read_bytes())
        location = self.export("--config", "visible/sample.toml")[APPROVAL]
        self.assertEqual(location["artifactLocation"], {"uri": "visible/sample.toml"})
        (self.repo / "collapsed").mkdir()
        (self.repo / "collapsed/sample.toml").write_bytes(self.sample.read_bytes())
        self.assertIsNone(self.export("--config", "collapsed/sample.toml")[APPROVAL])

    def test_codex_points_to_the_explicit_setting_across_toml_syntax(self):
        body = ('model = """decoy\napproval_policy = "never"\n"""\n'
                'approval_policy="on-request"\nsandbox_mode="danger-full-access"\n'
                '''"shell_environment_policy".inherit="all"\n'''
                '''[mcp_servers."demo.server"]\ncommand="PRIVATE_COMMAND"\n''')
        self.sample.write_text(body)
        self.git("add", "--", self.sample.name)
        loc = self.export("--config", self.sample)
        self.assertIsNone(loc["config-1:approval_policy/commands_without_prompts"])
        for key, expected in [("sandbox_mode/unrestricted_filesystem", 5),
                              ("shell_environment_policy/environment_inheritance", 6),
                              ('mcp_servers."demo.server"/configured_program', 8)]:
            self.assertEqual(loc["config-1:" + key]["region"]["startLine"], expected)
        self.sample.write_text('shell_environment_policy = {inherit = "all"} # inline\n')
        self.git("add", "--", self.sample.name)
        self.assertEqual(self.export("--config", self.sample)["config-1:shell_environment_policy/environment_inheritance"]
                         ["region"]["startLine"], 1)

    def test_claude_settings_and_array_items_use_their_own_json_lines(self):
        path = self.repo / "settings.json"
        path.write_text('{\n"permissions": {\n"defaultMode": "bypassPermissions",\n'
                        '"allow": [\n"Bash(*)",\n"WebFetch(domain:*)"\n]},\n'
                        '"apiKeyHelper": "PRIVATE_COMMAND"\n}')
        self.git("add", "--", path.name)
        loc = self.export("--agent", "claude", "--config", path)
        for key, expected in [("permissions.defaultMode/commands_without_prompts", 3),
                              ("permissions.allow.1/saved_approval", 5),
                              ("permissions.allow.2/network_access", 6), ("apiKeyHelper/configured_program", 8)]:
            self.assertEqual(loc["settings-1:" + key]["region"]["startLine"], expected)
        path.write_text('{"permissions":{"defaultMode":"default",\n"defaultMode":"bypassPermissions"}}')
        self.git("add", "--", path.name)
        self.assertIsNone(self.export("--agent", "claude", "--config", path)
                          ["settings-1:permissions.defaultMode/commands_without_prompts"])

    def test_a_replaced_tracked_file_cannot_gain_the_selected_files_location(self):
        with chdir(self.repo):
            selected = selected_files([self.sample])
        self.assertIn(self.sample, selected)
        other = self.sample.with_name("replacement")
        other.write_bytes(self.sample.read_bytes())
        other.replace(self.sample)
        result = report.inspect([self.sample], repo_files=selected)
        sarif = json.loads(report.render(result, "sarif"))
        self.assertTrue(sarif["runs"][0]["results"])
        self.assertNotIn("physicalLocation", json.dumps(sarif))

    def test_one_claude_hook_has_a_command_line_and_grouped_hooks_keep_their_logical_id(self):
        path = self.repo / "hooks.json"
        hook = {"type": "command", "command": "PRIVATE_COMMAND"}
        def write(handlers):
            path.write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": handlers}]}}, indent=2))
        write([hook])
        self.git("add", "--", path.name)
        key = "settings-1:hooks/configured_program"
        line = next(i for i, text in enumerate(path.read_text().splitlines(), 1) if '"command":' in text)
        self.assertEqual(self.export("--agent", "claude", "--config", path)[key]["region"]["startLine"], line)
        write([hook, hook])
        self.git("add", "--", path.name)
        self.assertIsNone(self.export("--agent", "claude", "--config", path)[key])

    def test_location_flag_requires_sarif_before_reading_config(self):
        result = run_checkout(ROOT, "--config", str(self.sample), "--sarif-repo-locations", cwd=self.repo)
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertIn("--sarif-repo-locations needs --format sarif.", result.stderr)
