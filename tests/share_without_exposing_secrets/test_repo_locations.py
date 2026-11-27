import json
import subprocess

from tests.support import ConfigCase, ROOT, run_checkout


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

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def export(self, *args, opt=True, cwd=None, env=None):
        flags = ["--sarif-repo-locations"] if opt else []
        result = run_checkout(ROOT, "--format", "sarif", *flags, *map(str, args), cwd=cwd or self.repo, env=env)
        self.assertIn(result.returncode, (0, 2))
        self.assertNotIn("PRIVATE_COMMAND", result.stdout + result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        run, = json.loads(result.stdout)["runs"]
        return {item["locations"][0]["logicalLocations"][0]["fullyQualifiedName"] + "/" + item["ruleId"]:
                item["locations"][0].get("physicalLocation") for item in run["results"]}

    def test_only_an_opted_in_tracked_selected_config_shows_its_relative_uri_and_setting_line(self):
        key = "config-1:approval_policy/commands_without_prompts"
        expected = {"artifactLocation": {"uri": "team%20%231%25.toml"}, "region": {"startLine": 2}}
        for version in ("2", "3", "4"):
            self.git("update-index", "--index-version", version)
            with self.subTest(version=version):
                loc = self.export("--config", self.sample.name)
                self.assertEqual(loc[key], expected)
                self.assertIsNone(loc["config-1:shell_environment_policy/environment_inheritance"])
                self.assertEqual(loc["config-1:notify/configured_program"]["region"]["startLine"], 4)
                self.assertEqual(self.export("--config", self.sample.name, opt=False), dict.fromkeys(loc))
        sub = self.repo / "sub"
        sub.mkdir()
        self.assertEqual(self.export("--config", self.sample, cwd=sub)[key], expected)
        outside = self.root.resolve() / "private.toml"
        outside.write_bytes(self.sample.read_bytes())
        other = self.repo / "untracked.toml"
        other.write_bytes(outside.read_bytes())
        reported = self.export("--config", outside, "--config", other, "--config", self.sample)
        self.assertIsNone(reported[key])
        self.assertIsNone(reported[key.replace("1:", "2:")])
        self.assertEqual(reported[key.replace("1:", "3:")], expected)
        home = self.repo / "home"
        (home / "rules").mkdir(parents=True)
        (home / "config.toml").write_bytes(self.sample.read_bytes())
        (home / "rules" / "default.rules").write_text('prefix_rule(pattern=["PRIVATE_COMMAND"], decision="allow")')
        self.git("add", "--", "home")
        self.assertFalse(any(self.export("--agent", "codex", env={"CODEX_HOME": str(home)}).values()))
        self.assertFalse(any(self.export("--rules", home / "rules" / "default.rules").values()))

    def test_unverified_checkout_symlinks_and_unmerged_index_entries_keep_locations_private(self):
        key = "config-1:approval_policy/commands_without_prompts"
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
        self.assertIsNone(self.export("--config", folder / "input")[key])
        link = self.repo / "linked"
        link.symlink_to(self.sample)
        self.git("add", "--", "linked")
        self.assertFalse(any(self.export("--config", link).values()))
        self.assertIsNone(self.export("--config", self.sample, cwd=outside)[key])
        self.git("update-index", "--force-remove", "--", self.sample.name)
        oid = subprocess.check_output(["git", "hash-object", str(self.sample)], cwd=self.repo).decode().strip()
        subprocess.run(["git", "update-index", "--index-info"], cwd=self.repo,
                       input=f"100644 {oid} 2\t{self.sample.name}\n", text=True, check=True)
        self.assertIsNone(self.export("--config", self.sample)[key])
        (self.repo / ".git" / "index").write_bytes(b"truncated")
        self.assertIsNone(self.export("--config", self.sample)[key])

    def test_codex_points_to_the_explicit_setting_across_toml_syntax(self):
        body = ('model = """decoy\napproval_policy = "never"\n"""\n'
                'approval_policy="on-request"\nsandbox_mode="danger-full-access"\n'
                '''"shell_environment_policy".inherit="all"\n'''
                '''[mcp_servers."demo.server"]\ncommand="PRIVATE_COMMAND"\n''')
        self.sample.write_text(body)
        loc = self.export("--config", self.sample)
        self.assertIsNone(loc["config-1:approval_policy/commands_without_prompts"])
        for key, expected in [("sandbox_mode/unrestricted_filesystem", 5),
                              ("shell_environment_policy/environment_inheritance", 6),
                              ('mcp_servers."demo.server"/configured_program', 8)]:
            self.assertEqual(loc["config-1:" + key]["region"]["startLine"], expected)
        self.sample.write_text('shell_environment_policy = {inherit = "all"} # inline\n')
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
        self.assertIsNone(self.export("--agent", "claude", "--config", path)
                          ["settings-1:permissions.defaultMode/commands_without_prompts"])

    def test_location_flag_requires_sarif_before_reading_config(self):
        result = run_checkout(ROOT, "--config", str(self.sample), "--sarif-repo-locations", cwd=self.repo)
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertIn("--sarif-repo-locations needs --format sarif.", result.stderr)
