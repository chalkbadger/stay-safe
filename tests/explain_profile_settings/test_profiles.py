import json

from tests.support import INLINE_OVERRIDE, SELECTOR_GAP, TABLES_GAP
from tests.support import ConfigCase, INCOMPLETE, copy_checkout, run_checkout, section


BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\nshell_environment_policy.inherit="none"\n'


class ProfileTests(ConfigCase):
    def test_selector_and_named_tables_report_different_loading_conditions(self):
        checkout = copy_checkout(self.root / "checkout")
        named = '[profiles.private-name]\nsandbox_mode="danger-full-access"\n'
        selector = 'profile="private-name"\n'
        for extra, expected in ((selector, SELECTOR_GAP), (selector + named, SELECTOR_GAP), (named, TABLES_GAP),
                                (named + '[profiles.other-private]\n', TABLES_GAP), ('profile=""\n', SELECTOR_GAP)):
            with self.subTest(extra=extra):
                path = str(self.config(BASE + extra))
                machine = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                self.assertEqual(json.loads(machine.stdout)["inspection_gaps"], ["config-1: " + expected])
                self.assertEqual(json.loads(machine.stdout)["risks"], [])
                message = section(human.stdout, "Not checked")
                self.assertEqual(message.count("*What to do:*"), 1)
                self.assertIn(INLINE_OVERRIDE, message)
                if expected == SELECTOR_GAP:
                    self.assertIn("**This file uses an old way to select a profile.**", message)
                    self.assertIn("Codex 0.172.0 stops if `profile` is in the configuration it uses at startup", message)
                    self.assertIn("Remove the `profile` setting.", message)
                    self.assertIn("`work.config.toml`", message)
                    self.assertIn("Remove the old table and start Codex with `--profile work`. Then run stay-safe with "
                                  "`--config` and the path to that file to check its settings.", message)
                else:
                    self.assertIn("**This file defines a profile but doesn’t select it.**", message)
                    self.assertIn("If this is your main `config.toml` and you start Codex 0.172.0 with `--profile` "
                                  "and a name defined here, the matching table stops Codex from loading.", message)
                    self.assertIn("Starting with a name this file doesn’t define does not trigger that conflict.", message)
                for run in (human, machine):
                    self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                    self.assertNotIn("private-name", run.stdout)
                    self.assertNotIn("other-private", run.stdout)

    def test_migrated_profile_can_be_inspected_separately_from_the_main_config(self):
        checkout = copy_checkout(self.root / "checkout")
        main = self.config(BASE)
        profile = self.config('sandbox_mode="danger-full-access"\n', "work.config.toml")
        human = run_checkout(checkout, "--config", str(main), cwd=self.root)
        self.assertEqual(human.returncode, 0)
        limits = section(human.stdout, "What this report can't see")
        self.assertIn("select a separate profile file with `--profile`", limits)
        self.assertIn("that file can override your main config", limits)
        self.assertIn("Run stay-safe with `--config` and the path to that file", limits)
        machine = run_checkout(checkout, "--config", str(main), "--config", str(profile),
                               "--format", "json", cwd=self.root)
        self.assertEqual((machine.returncode, machine.stderr), (2, INCOMPLETE))
        report = json.loads(machine.stdout)
        self.assertIn("A separately selected profile file can override the main config.", " ".join(report["scope"]))
        affected = [risk["entry"] for risk in report["risks"] if risk["rule"] == "unrestricted_filesystem"]
        self.assertEqual(affected, ["config-2:sandbox_mode"])

    def test_each_snapshot_keeps_its_own_profile_message_and_settings(self):
        checkout = copy_checkout(self.root / "checkout")
        one = self.config(BASE + 'profile="example"\nnotify=["example-program"]\n', "one.toml")
        two = self.config(BASE + '[profiles.example]\napproval_policy="never"\n', "two.toml")
        cli = ("--config", str(one), "--config", str(two))
        machine = run_checkout(checkout, *cli, "--format", "json", cwd=self.root)
        report = json.loads(machine.stdout)
        self.assertCountEqual(report["inspection_gaps"], ["config-1: " + SELECTOR_GAP, "config-2: " + TABLES_GAP])
        self.assertEqual([(r["entry"], r["rule"]) for r in report["risks"]], [("config-1:notify", "configured_program")])
        human = run_checkout(checkout, *cli, cwd=self.root)
        messages = section(human.stdout, "Not checked").split("*File `config-1`*")
        self.assertIn("**This file uses an old way to select a profile.**", messages[0])
        self.assertIn("**This file defines a profile but doesn’t select it.**", messages[1])
        self.assertIn("*File `config-2`*", messages[1])
        for run in (human, machine):
            self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))

    def test_selector_does_not_hide_a_malformed_profiles_value(self):
        checkout = copy_checkout(self.root / "checkout")
        table = "config-1: profiles must be a table."
        for selector, first in (('"private-name"', SELECTOR_GAP),
                                ('false', "Codex expects a string for the top-level profile setting. "
                                          "It ignores this setting in project configuration.")):
            with self.subTest(selector=selector):
                path = str(self.config(BASE + "profile=" + selector + '\nprofiles="private-value"\n'))
                machine = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                self.assertEqual(json.loads(machine.stdout)["inspection_gaps"], ["config-1: " + first, table])
                unchecked = section(human.stdout, "Not checked")
                self.assertIn("**Not checked: your `profiles` settings.**", unchecked)
                self.assertIn("*What to do:* Remove the malformed `profiles` value. If you want to use a profile, "
                              "put its settings in a separate profile file in your Codex folder.", unchecked)
                for run in (human, machine):
                    self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                    self.assertNotIn("private-name", run.stdout)
                    self.assertNotIn("private-value", run.stdout)
        both = str(self.config(BASE + 'profile="private-name"\n[profiles.private-name]\n', "both.toml"))
        valid = run_checkout(checkout, "--config", both, "--format", "json", cwd=self.root)
        self.assertEqual(json.loads(valid.stdout)["inspection_gaps"], ["config-1: " + SELECTOR_GAP])

    def test_project_file_explains_why_its_selector_can_be_ignored(self):
        checkout = copy_checkout(self.root / "checkout")
        project = self.root / "project"
        folder = project / ".codex"
        folder.mkdir(parents=True)
        path = folder / "config.toml"
        for selector, expected in (('"undisclosed"', "Codex 0.172.0"), ('false', "expects a string")):
            with self.subTest(selector=selector):
                path.write_text(BASE + "profile=" + selector, encoding="utf-8")
                for fmt in ("markdown", "json"):
                    run = run_checkout(checkout, "--workspace", str(project), "--config", str(path),
                                       "--format", fmt, cwd=self.root)
                    message = (section(run.stdout, "Not checked") if fmt == "markdown"
                               else json.loads(run.stdout)["inspection_gaps"][0])
                    self.assertIn(expected, message)
                    self.assertIn("gnores this setting in project configuration", message)
                    self.assertNotIn("undisclosed", run.stdout)
                    self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
