import json

from stay_safe.report import inspect
from tests.support import ConfigCase, copy_checkout, run_checkout


class NamedAppValidationTests(ConfigCase):
    def test_markdown_explains_how_to_correct_a_quoted_boolean(self):
        checkout = copy_checkout(self.root / "checkout")
        settings = ('approval_policy="on-request"\nsandbox_mode="workspace-write"\n'
                    'shell_environment_policy.inherit="none"\n[apps.calendar]\nopen_world_enabled=')
        field = "`apps.calendar.open_world_enabled`"
        for value, status in (('"false"', 2), ('false', 0)):
            run = run_checkout(checkout, "--agent", "codex", "--config", str(self.config(settings + value)),
                               "--format", "markdown", cwd=self.root)
            with self.subTest(value=value, part="exit status"):
                self.assertEqual(run.returncode, status)
            for advice in (f"{field} must be `true` or `false` without quotes.",
                           f"Set {field} to `true` or `false` without quotes."):
                with self.subTest(value=value, advice=advice):
                    self.assertEqual(advice in run.stdout, status == 2)

    def test_invalid_open_world_flag_names_the_app_and_preserves_its_sibling(self):
        checkout = copy_checkout(self.root / "checkout")
        config = ('approval_policy="on-request"\nsandbox_mode="workspace-write"\n'
                  'shell_environment_policy.inherit="none"\n[apps.calendar]\n'
                  'destructive_enabled=true\nopen_world_enabled=')
        notes = '\n[apps.notes]\ndestructive_enabled=false\ndefault_tools_approval_mode="approve"\n'
        child = '\n[apps.calendar.tools.erase]\nenabled=true\napproval_mode="approve"\n'
        notes_risk = ("config-1:apps.notes", "automatic_tools")
        calendar_risks = {("config-1:apps.calendar", "destructive_tools"),
                          ("config-1:apps.calendar", "self_described_tools")}
        for value, extra, valid in (('"false"', '', False), ('0', child, False),
                                    ('false', '', True), ('true', '', True)):
            with self.subTest(value=value):
                path = self.config(config + value + extra + notes)
                run = run_checkout(checkout, "--agent", "codex", "--config", str(path),
                                   "--format", "json", cwd=self.root)
                report = json.loads(run.stdout)
                self.assertEqual(run.returncode, 0 if valid else 2)
                observed = {(r["entry"], r["rule"]) for r in report["risks"]}
                self.assertEqual(observed, {notes_risk} | (calendar_risks if valid else set()))
                if valid:
                    self.assertEqual(report["inspection_gaps"], [])
                else:
                    self.assertEqual(len(report["inspection_gaps"]), 1)
                    gap = report["inspection_gaps"][0]
                    self.assertIn("calendar", gap)
                    self.assertIn("open_world_enabled", gap)
                    self.assertIn("bool", gap.lower())

    def test_invalid_flag_on_a_disabled_app_keeps_the_off_reason_and_only_the_validation_gap(self):
        checkout = copy_checkout(self.root / "checkout")
        base = 'approval_policy="on-request"\nsandbox_mode="read-only"\nshell_environment_policy.inherit="none"\n'
        settings = ('links={example={default_tools_approval_mode="prompt"}}\n'
                    '[apps.notes]\ndestructive_enabled=false\ndefault_tools_approval_mode="approve"\n')
        for route, config, reason, expected_risks in (
            ("named App off", '[apps.calendar]\nenabled=false\n', "disabled", [("config-1:apps.notes", "automatic_tools")]),
            ("Apps off", 'features.apps=false\n[apps.calendar]\n', "disabled by features.apps = false", []),
        ):
            for field in ("open_world_enabled", "destructive_enabled"):
                with self.subTest(route=route, field=field):
                    path = self.config(base + config + f'{field}="false"\n' + settings)
                    run = run_checkout(checkout, "--agent", "codex", "--config", str(path),
                                       "--format", "json", cwd=self.root)
                    report = json.loads(run.stdout)
                    calendar = next(entry for entry in report["catalog"] if entry["name"] == "apps.calendar")
                    self.assertIn(reason, calendar["observations"])
                    self.assertEqual(run.returncode, 2)
                    self.assertEqual(report["inspection_gaps"],
                                     [f"config-1: Codex cannot load this configuration file because apps.calendar.{field} is not a boolean."])
                    self.assertEqual([(r["entry"], r["rule"]) for r in report["risks"]], expected_risks)

    def test_both_flags_reject_the_file_and_preserve_independent_app_settings(self):
        checkout = copy_checkout(self.root / "checkout")
        top = 'approval_policy="on-request"\nsandbox_mode="read-only"\nshell_environment_policy.inherit="none"\n'
        sibling = '[apps.notes]\ndestructive_enabled=false\ndefault_tools_approval_mode="approve"\n'
        for name in ("calendar", "_default"):
            for field in ("open_world_enabled", "destructive_enabled"):
                with self.subTest(name=name, field=field):
                    path = self.config(top + f'[apps.{name}]\n{field}="false"\ndefault_tools_approval_mode="approve"\n'
                                       + sibling)
                    run = run_checkout(checkout, "--agent", "codex", "--config", str(path),
                                       "--format", "json", cwd=self.root)
                    report = json.loads(run.stdout)
                    self.assertEqual(run.returncode, 2)
                    self.assertEqual(report["inspection_gaps"],
                                     [f"config-1: Codex cannot load this configuration file because apps.{name}.{field} is not a boolean."])
                    entry = next(row for row in report["catalog"] if row["name"] == f"apps.{name}")
                    self.assertIn("Codex cannot load this configuration file", entry["observations"])
                    self.assertEqual([(r["entry"], r["rule"]) for r in report["risks"]],
                                     [("config-1:apps.notes", "automatic_tools")])

    def test_app_tool_load_errors_name_the_field_in_both_formats(self):
        checkout = copy_checkout(self.root / "checkout")
        top = 'approval_policy="on-request"\nsandbox_mode="read-only"\n[apps.cal]\n'
        sibling = '[apps.cal.tools.archive]\nenabled=true\napproval_mode="approve"\n[apps.notes]\ndefault_tools_approval_mode="approve"\n'
        for field, reason, control in (
            ("default_tools_enabled", "is not a boolean", "false"),
            ("default_tools_approval_mode", "is not one of auto, prompt, writes, approve", '"prompt"'),
            ("tools.delete.enabled", "is not a boolean", "false"),
            ("tools.delete.approval_mode", "is not one of auto, prompt, writes, approve", '"prompt"'),
        ):
            message = f"Codex cannot load this configuration file because apps.cal.{field} {reason}."
            for enabled in ("false", "true"):
                for value in ('"yes"', control):
                    path = self.config(top + f"enabled={enabled}\n{field}={value}\n" + sibling)
                    for fmt in ("json", "markdown"):
                        with self.subTest(field=field, enabled=enabled, value=value, fmt=fmt):
                            run = run_checkout(checkout, "--config", str(path), "--format", fmt, cwd=self.root)
                            invalid = value != control
                            self.assertEqual(run.returncode, 2 if invalid else 0)
                            self.assertNotRegex(run.stdout + run.stderr, r"\byes\b")
                            if fmt == "markdown":
                                label = f"`apps.cal.{field}`"
                                if not invalid:
                                    self.assertIn("0 things not checked", run.stdout)
                                elif reason == "is not a boolean":
                                    self.assertIn(f"**Codex cannot load this configuration file.** "
                                                  f"{label} must be `true` or `false` without quotes.", run.stdout)
                                    self.assertIn(f"Set {label} to `true` or `false` without quotes.", run.stdout)
                                else:
                                    self.assertIn(message, run.stdout)
                                    self.assertIn(f'Set {label} to `"auto"`, `"prompt"`, `"writes"` or `"approve"`.',
                                                  run.stdout)
                                continue
                            report = json.loads(run.stdout)
                            self.assertEqual(report["inspection_gaps"], ["config-1: " + message] if invalid else [])
                            rows = {row["name"]: row["observations"] for row in report["catalog"]}
                            risks = {risk["entry"] for risk in report["risks"]}
                            self.assertIn("config-1:apps.notes", risks)
                            if enabled == "false":
                                self.assertIn("disabled", rows["apps.cal"])
                            elif invalid:
                                for name in ("apps.cal", "apps.cal.tools.archive"):
                                    self.assertIn("Codex cannot load this configuration file", rows[name])
                            else:
                                self.assertIn("configured enabled", rows["apps.cal"])
                                self.assertIn("config-1:apps.cal.tools.archive", risks)
                            if invalid or enabled == "false":
                                self.assertFalse(any(key.startswith("config-1:apps.cal") for key in risks))

    def test_app_and_tool_flags_reject_integer_zero_and_one(self):
        top = 'approval_policy="on-request"\nsandbox_mode="read-only"\n[apps.cal]\n'
        for field in ("default_tools_enabled", "tools.delete.enabled"):
            for value in (0, 1):
                with self.subTest(field=field, value=value):
                    report = inspect([self.config(top + f"{field}={value}\n")])
                    self.assertEqual(report["inspection_gaps"], [
                        f"config-1: Codex cannot load this configuration file because apps.cal.{field} is not a boolean."
                    ])

    def test_app_and_tool_accept_each_codex_approval_mode(self):
        top = 'approval_policy="on-request"\nsandbox_mode="read-only"\n[apps.cal]\n'
        for field in ("default_tools_approval_mode", "tools.delete.approval_mode"):
            for mode in ("auto", "prompt", "writes", "approve"):
                with self.subTest(field=field, mode=mode):
                    report = inspect([self.config(top + f'{field}="{mode}"\n')])
                    self.assertEqual(report["inspection_gaps"], [])
                    parent = "apps.cal" if field == "default_tools_approval_mode" else "apps.cal.tools.delete"
                    entry = next(row for row in report["catalog"] if row["name"] == parent)
                    self.assertIn(f"tool approval: {mode}", entry["observations"])

    def test_disabled_app_reports_a_malformed_setting_when_its_tool_name_is_withheld(self):
        checkout = copy_checkout(self.root / "checkout")
        for app, field, control, reason in (
            ("apps.cal", "enabled", "false", "is not a boolean"),
            ('apps."work.cal"', "approval_mode", '"prompt"', "is not one of auto, prompt, writes, approve"),
        ):
            top = (f'approval_policy="on-request"\nsandbox_mode="read-only"\n[{app}]\nenabled=false\n'
                   f'[{app}.tools."user@example.invalid"]\n')
            message = f"Codex cannot load this configuration file because {app}.tools.*.{field} {reason}."
            for value, status in (('"private-value"', 2), (control, 0)):
                path = self.config(top + f"{field}={value}\n")
                for fmt in ("json", "markdown"):
                    with self.subTest(field=field, value=value, fmt=fmt):
                        run = run_checkout(checkout, "--config", str(path), "--format", fmt, cwd=self.root)
                        self.assertEqual(run.returncode, status)
                        self.assertNotIn("user@example.invalid", run.stdout + run.stderr)
                        self.assertNotIn("private-value", run.stdout + run.stderr)
                        if fmt == "json":
                            gaps = json.loads(run.stdout)["inspection_gaps"]
                            self.assertEqual(gaps, ["config-1: " + message] if status else [])
                        elif status:
                            if reason == "is not a boolean":
                                self.assertIn(f"`{app}.tools.*.{field}` must be `true` or `false` without quotes.", run.stdout)
                            else:
                                self.assertIn(message, run.stdout)


    def test_withheld_invalid_tool_marks_all_public_tools_unloadable_unless_apps_are_off(self):
        checkout = copy_checkout(self.root / "checkout")
        app = ('[apps.cal]\ndestructive_enabled=true\n[apps.cal.tools.archive]\nenabled=true\n'
               '[apps.cal.tools."user@example.invalid"]\napproval_mode="private-value"\n')
        for feature, reason in (("true", "Codex cannot load this configuration file"), ("false", "disabled by features.apps = false")):
            with self.subTest(feature=feature):
                path = self.config('approval_policy="on-request"\nsandbox_mode="read-only"\nfeatures.apps=' + feature + '\n' + app)
                run = run_checkout(checkout, "--config", str(path), "--format", "json", cwd=self.root)
                self.assertEqual(run.returncode, 2)
                self.assertNotIn("user@example.invalid", run.stdout)
                self.assertNotIn("private-value", run.stdout)
                report = json.loads(run.stdout)
                rows = {row["name"]: row["observations"] for row in report["catalog"]}
                for name in ("apps.cal", "apps.cal.tools.archive"):
                    self.assertIn(reason, rows[name])
                self.assertFalse(any(risk["entry"].startswith("config-1:apps.cal") for risk in report["risks"]))
                self.assertTrue(any("apps.cal.tools.*.approval_mode" in gap for gap in report["inspection_gaps"]))

    def test_invalid_default_mode_is_attributed_to_its_declaration_and_an_independent_app_can_override_it(self):
        checkout = copy_checkout(self.root / "checkout")
        for value, status in (('"private-mode"', 2), ('"prompt"', 0)):
            path = self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n'
                               f'[apps._default]\ndefault_tools_approval_mode={value}\n'
                               '[apps.inherited]\n[apps.notes]\ndefault_tools_approval_mode="approve"\n')
            with self.subTest(value=value):
                run = run_checkout(checkout, "--config", str(path), "--format", "json", cwd=self.root)
                self.assertEqual(run.returncode, status)
                report = json.loads(run.stdout)
                self.assertEqual(report["inspection_gaps"], [
                    "config-1: Codex cannot load this configuration file because "
                    "apps._default.default_tools_approval_mode is not one of auto, prompt, writes, approve."
                ] if status else [])
                self.assertIn(("config-1:apps.notes", "automatic_tools"), [(r["entry"], r["rule"]) for r in report["risks"]])
                rows = {r["name"]: r["observations"] for r in report["catalog"]}
                if status:
                    self.assertIn("Codex cannot load this configuration file", rows["apps._default"])
                    self.assertNotIn("private-mode", run.stdout)
                else:
                    self.assertIn("tool approval: prompt", rows["apps.inherited"])
