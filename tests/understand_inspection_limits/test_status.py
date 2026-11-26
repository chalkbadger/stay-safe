import io
import json
from unittest.mock import patch

from stay_safe.cli import main
from stay_safe.report import inspect, render
from tests.support import FEEDBACK, ConfigCase, copy_checkout, run_checkout, section


EXPLANATION = "Inspection incomplete (exit 2). See the report for what wasn't checked.\n"
COMPLETE = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\n'


class StatusTests(ConfigCase):
    def test_stdio_header_helper_names_the_rejected_setting(self):
        checkout = copy_checkout(self.root / "checkout")
        config = COMPLETE + 'shell_environment_policy.inherit="core"\n[mcp_servers."docs.local"]\n'
        command = 'command="private-server"\n'
        url = 'url="https://example.invalid/mcp"\n'
        helper = 'http_headers_helper="private-helper"\n'
        reason = ("config-1: Codex cannot load this configuration because stdio MCP server "
                  "docs.local sets http_headers_helper.")
        for settings, gaps, program in ((command + helper, [reason], False), ('command=""\n' + helper, [reason], False),
                                        (command + helper + 'enabled=false\n', [reason], False), (command, [], True),
                                        (url + helper, [], True), (url, [], False)):
            with self.subTest(settings=settings):
                path = str(self.config(config + settings))
                run = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                report = json.loads(run.stdout)
                self.assertEqual(report["inspection_gaps"], gaps)
                self.assertEqual(run.returncode, 2 if gaps else 0)
                programs = [risk["entry"] for risk in report["risks"] if risk["rule"] == "configured_program"]
                self.assertEqual(programs, ['config-1:mcp_servers."docs.local"'] if program else [])
                if gaps:
                    human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                    explanation = section(human.stdout, "Not checked")
                    self.assertIn("Codex can't load this configuration", explanation)
                    self.assertIn("the `docs.local` server", explanation.lower())
                    self.assertIn("remove `http_headers_helper`", explanation.lower())
                    self.assertNotIn("starts a program on your computer", section(human.stdout, "Your setup"))
                    for private in ("private-server", "private-helper"):
                        self.assertNotIn(private, run.stdout + human.stdout)

    def test_gateway_and_otel_helpers_name_unchecked_commands(self):
        quiet = COMPLETE + 'shell_environment_policy={inherit="none"}\nfeatures.apps=false\nnotify=["kept-program"]\n'
        generic = "config-1: Configuration contains fields outside reader coverage; their values were withheld."
        gateway = "Model-provider setting gateway_oauth.credential_export is for a credential command. Stay-safe did not check its value."
        otel = "otel.headers_helper is for a command that supplies telemetry headers. Stay-safe did not check its value."
        cases = (
            ("gateway_oauth.credential_export", "credential_export", "[model_providers.corp.gateway_oauth]\n", gateway),
            ("otel.headers_helper", "headers_helper", "[otel]\n", otel),
        )
        values = (None, '""', '"private-helper"', '{}', '{command="private-helper", args=["private-arg"]}')
        for label, key, table, message in cases:
            for selected in (False, True):
                for value in values:
                    with self.subTest(setting=label, selected=selected, value=value):
                        text = quiet
                        if label.startswith("gateway") and selected:
                            text += 'model_provider="corp"\n'
                        text += table
                        if label.startswith("otel") and selected:
                            text += 'exporter={otlp-http={endpoint="https://example.com/v1/logs", protocol="json"}}\n'
                        if value is not None:
                            text += f'{key}={value}\n'
                        path = self.config(text)
                        report = inspect([path])
                        expected = [generic] if selected or label.startswith("otel") else []
                        if value is not None:
                            expected.append("config-1: " + message)
                        self.assertCountEqual(report["inspection_gaps"], expected)
                        self.assertEqual([(r["rule"], r["entry"]) for r in report["risks"]],
                                         [("configured_program", "config-1:notify")])
                        human = render(report, "markdown")
                        unchecked = section(human, "Not checked") if expected else ""
                        self.assertEqual(unchecked.count("**Not checked:"), len(expected))
                        if value is not None:
                            plain = ("**Not checked: a model provider's `gateway_oauth.credential_export`.** This setting "
                                     "is for a credential command. Stay-safe did not check its value.\n\n"
                                     "*What to do:* Find `gateway_oauth.credential_export` under "
                                     "`[model_providers.<name>]` and review its value. If it specifies a command, check that you trust it."
                                     if label.startswith("gateway") else
                                     "**Not checked: `otel.headers_helper`.** This setting is for a command that supplies "
                                     "telemetry headers. Stay-safe did not check its value.\n\n"
                                     "*What to do:* Review `otel.headers_helper`. If it specifies a command, check that you trust it.")
                            self.assertIn(plain + "\n\n*File `config-1`*", unchecked)
                        for output in (human, json.dumps(report)):
                            for private in ("private-helper", "private-arg", "kept-program"):
                                self.assertNotIn(private, output)

        both = ('[model_providers.corp.gateway_oauth.credential_export]\n'
                'command="private-helper"\nargs=["private-arg"]\n'
                '[otel]\nheaders_helper="private-helper private-arg"\n')
        other_fields = "some settings in your config file"
        cli_cases = (
            (both, [generic, "config-1: " + gateway, "config-1: " + otel],
             [other_fields, "a model provider's `gateway_oauth.credential_export`", "`otel.headers_helper`"]),
            ('[model_providers.corp]\ngateway_oauth=false\n', ["config-1: gateway_oauth must be a table."],
             ["your `gateway_oauth` settings"]),
            ('otel="private-helper"\n', [generic], [other_fields]),
            ('otel=["private-arg"]\n', [generic], [other_fields]),
        )
        checkout = copy_checkout(self.root / "checkout")
        for settings, gaps, labels in cli_cases:
            with self.subTest(settings=settings):
                path = str(self.config(quiet + settings))
                human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                machine = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                self.assertCountEqual(json.loads(machine.stdout)["inspection_gaps"], gaps)
                unchecked = section(human.stdout, "Not checked")
                self.assertEqual(unchecked.count("**Not checked:"), len(labels))
                for label in labels:
                    self.assertIn(f"**Not checked: {label}.**", unchecked)
                for run in (human, machine):
                    self.assertEqual((run.returncode, run.stderr), (2, EXPLANATION))
                    for private in ("private-helper", "private-arg", "kept-program"):
                        self.assertNotIn(private, run.stdout + run.stderr)

    def test_aws_credentials_name_each_unchecked_command(self):
        checkout = copy_checkout(self.root / "checkout")
        quiet = COMPLETE + 'shell_environment_policy={inherit="none"}\nfeatures.apps=false\n'
        keys = ("credential_export", "auth_refresh")
        generic = "config-1: Configuration contains fields outside reader coverage; their values were withheld."
        for selected in (False, True):
            for settings, inline in (((), None), (keys[:1], None), (keys[1:], None), (keys, None),
                                     (keys, "{}"), (keys[:1], '"private-arg"'), (keys[1:], '"private-arg"')):
                with self.subTest(selected=selected, settings=settings, inline=inline):
                    text = quiet + ('model_provider="amazon-bedrock"\n' if selected else "")
                    text += '[model_providers.amazon-bedrock.aws]\nregion="us-west-2"\n'
                    for key in settings:
                        if inline is None:
                            text += f'[model_providers.amazon-bedrock.aws.{key}]\ncommand="private-{key}"\nargs=["private-arg"]\n'
                        else:
                            text += f'{key}={inline}\n'
                    path = str(self.config(text))
                    human = run_checkout(checkout, "--config", path, cwd=self.root)
                    machine = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                    expected = [generic] if selected else []
                    for key in settings:
                        label = f"aws.{key}"
                        expected.append(f"config-1: Model-provider setting {label} is for a credential command. Stay-safe did not check its value.")
                        self.assertIn(f"**Not checked: a model provider's `{label}`.** This setting is for a credential command. "
                                      "Stay-safe did not check its value.\n\n"
                                      f"*What to do:* Find `{label}` under `[model_providers.<name>]` and review its value. "
                                      "If it specifies a command, check that you trust it.\n\n*File `config-1`*",
                                      section(human.stdout, "Not checked"))
                    report = json.loads(machine.stdout)
                    self.assertCountEqual(report["inspection_gaps"], expected)
                    self.assertEqual(report["risks"], [])
                    self.assertEqual(section(human.stdout, "Not checked").count("**Not checked:"), len(expected))
                    for run in (human, machine):
                        self.assertEqual((run.returncode, run.stderr), (2, EXPLANATION) if expected else (0, ""))
                        for private in ("private-arg", "private-auth_refresh", "private-credential_export"):
                            self.assertNotIn(private, run.stdout)
        auth = self.config(quiet + '[model_providers.corp.auth]\ncommand="private-export"\n')
        control = run_checkout(checkout, "--config", str(auth), cwd=self.root)
        self.assertEqual(control.returncode, 2)
        self.assertIn("a model provider's sign-in command", section(control.stdout, "Not checked"))

        malformed = self.config(quiet + '[model_providers.corp]\naws=false\n', "bad.toml")
        other = self.config(quiet + '[model_providers.first.aws.credential_export]\n'
                            '[model_providers.second.aws.auth_refresh]\n')
        args = ("--config", str(malformed), "--config", str(other))
        report = run_checkout(checkout, *args, "--format", "json", cwd=self.root)
        self.assertEqual(report.returncode, 2)
        self.assertCountEqual(json.loads(report.stdout)["inspection_gaps"], [
            "config-1: aws must be a table.",
            "config-2: Model-provider setting aws.auth_refresh is for a credential command. Stay-safe did not check its value.",
            "config-2: Model-provider setting aws.credential_export is for a credential command. Stay-safe did not check its value."])
        output = section(run_checkout(checkout, *args, cwd=self.root).stdout, "Not checked")
        self.assertIn("**Not checked: your `aws` settings.**", output)

    def test_app_tool_ai_reviewer_is_named_and_explains_policy_limits(self):
        checkout = copy_checkout(self.root / "checkout")
        base = COMPLETE + '[apps.calendar.tools."events/read"]\n'
        field = 'apps.calendar.tools."events/read".approvals_reviewer'
        named = (f"config-1: {field} requests AI review if this tool needs approval. "
                 "A policy can require human review. The effective reviewer was not checked.")
        generic = "config-1: tools contains fields outside reader coverage; their values were withheld."
        wording = ("If this tool needs approval, your file asks Codex to have an AI reviewer approve or deny "
                   "the request. Your organization can limit who may review requests. For example, if its policy "
                   "allows only human review, Codex may ask you to decide. Stay-safe can’t tell from this file "
                   "which policy applies to your run.")
        unknown = 'future_field="private-test-value"\n'
        for settings, expected in (
            ('approvals_reviewer="auto_review"', [named]),
            ('approvals_reviewer="guardian_subagent"', [named]),
            (unknown + 'approvals_reviewer="auto_review"', [named, generic]),
            (unknown, [generic]),
            ('approvals_reviewer="user"', []),
            (unknown + 'approvals_reviewer="user"', [generic]),
            ('approvals_reviewer="private-test-value"', [generic]),
            ('approvals_reviewer=["private-test-value"]', [generic]),
            ("", []),
        ):
            with self.subTest(settings=settings):
                path = str(self.config(base + settings))
                machine = run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root)
                human = run_checkout(checkout, "--config", path, "--format", "markdown", cwd=self.root)
                self.assertCountEqual(json.loads(machine.stdout)["inspection_gaps"], expected)
                unchecked = section(human.stdout, "Not checked")
                self.assertEqual(f"**Not checked: `{field}`.** {wording}" in unchecked, named in expected)
                self.assertEqual("Codex added this tool setting in 0.172.0." in unchecked, named in expected)
                self.assertEqual("some `tools` settings" in unchecked, generic in expected)
                for run in (machine, human):
                    self.assertEqual((run.returncode, run.stderr), (2, EXPLANATION) if expected else (0, ""))
                    self.assertNotIn("private-test-value", run.stdout)

    def test_app_auto_reviewer_is_named_as_unchecked(self):
        app = COMPLETE + 'shell_environment_policy={inherit="none"}\n[apps.calendar]\ndefault_tools_approval_mode="prompt"\n'
        gap = ("config-1: App approvals_reviewer is not evaluated; Codex may let a reviewer decide an app's tool calls "
               "instead of asking you.")
        cases = [(app + 'approvals_reviewer="auto_review"\n', [gap]),
                 (app + 'approvals_reviewer="guardian_subagent"\n', [gap]),
                 (app.replace("[apps.calendar]", '[apps._default]\napprovals_reviewer="auto_review"\n[apps.calendar]'), [gap]),
                 (app + 'approvals_reviewer="user"\n', []),
                 (app, [])]
        checkout = copy_checkout(self.root / "checkout")
        for text, expected in cases:
            with self.subTest(config=text):
                path = str(self.config(text))
                human = run_checkout(checkout, "--config", path, cwd=self.root)
                report = json.loads(run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root).stdout)
                self.assertEqual(report["inspection_gaps"], expected)
                self.assertEqual((human.returncode, human.stderr), (2, EXPLANATION) if expected else (0, ""))
                if expected:
                    self.assertIn("**Not checked: an app's approval reviewer.**", section(human.stdout, "Not checked"))

    def test_removing_an_app_reviewer_can_leave_the_default_reviewer_in_place(self):
        base = COMPLETE + 'shell_environment_policy={inherit="none"}\n[apps._default]\napprovals_reviewer="auto_review"\n'
        app = '[apps.calendar]\ndefault_tools_approval_mode="prompt"\n'
        advice = ("Check the reviewer on the App and on `apps._default`. If you remove the App's override, the App can "
                  "still inherit automatic review from `apps._default`.")
        gap = ("config-1: App approvals_reviewer is not evaluated; Codex may let a reviewer decide an app's tool calls "
               "instead of asking you.")
        checkout = copy_checkout(self.root / "checkout")
        overrides = ('[apps.calendar.links.account]\napprovals_reviewer="user"\n'
                     '[apps.calendar.tools.read]\napprovals_reviewer="user"\n')
        account_gap = "config-1: Per-account app policy is not evaluated; account identifiers were withheld."
        for name, text, expected in (("before", base + app + 'approvals_reviewer="auto_review"\n', [gap]),
                                     ("after", base + app, [gap]),
                                     ("specific", base + app + overrides, sorted([gap, account_gap]))):
            with self.subTest(run=name):
                path = str(self.config(text, f"{name}.toml"))
                human = run_checkout(checkout, "--config", path, cwd=self.root)
                report = json.loads(run_checkout(checkout, "--config", path, "--format", "json", cwd=self.root).stdout)
                self.assertEqual(report["inspection_gaps"], expected)
                self.assertEqual((human.returncode, human.stderr), (2, EXPLANATION))
                unchecked = section(human.stdout, "Not checked")
                self.assertIn("**Not checked: an app's approval reviewer.**", unchecked)
                self.assertIn("Check the tool and linked account first.", unchecked)
                self.assertIn(advice, unchecked)
                self.assertNotIn("main reviewer", human.stdout)

    def test_reports_with_gaps_explain_exit_two_on_stderr_only(self):
        checkout = copy_checkout(self.root / "checkout")
        private = self.config('private_key = "secret-value"\n', "private-input-name.toml")
        for args in (["--format", "markdown"], ["--format", "json"], ["--save"]):
            with self.subTest(args=args):
                run = run_checkout(checkout, "--config", str(private), *args, cwd=self.root)
                self.assertEqual((run.returncode, run.stderr), (2, EXPLANATION))
                self.assertNotIn(EXPLANATION.strip(), run.stdout)
                for secret in (str(private), "private-input-name", "secret-value"):
                    self.assertNotIn(secret, run.stdout + run.stderr)
                if "json" in args:
                    self.assertTrue(json.loads(run.stdout)["inspection_gaps"])
                else:
                    self.assertIn("## Not checked", run.stdout)

    def test_complete_reports_and_invalid_arguments_do_not_get_the_explanation(self):
        checkout = copy_checkout(self.root / "checkout")
        config = self.config(COMPLETE)
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                run = run_checkout(checkout, "--config", str(config), "--format", format_name, cwd=self.root)
                self.assertEqual((run.returncode, run.stderr), (0, ""))
        for args, expected in ((["--unknown"], "Invalid arguments. Use --help.\n" + FEEDBACK),
                               (["--format", "json", "--save"], "--save can't be combined with --format json. Use --help.\n" + FEEDBACK)):
            with self.subTest(args=args):
                run = run_checkout(checkout, *args, cwd=self.root)
                self.assertEqual((run.returncode, run.stdout, run.stderr), (2, "", expected))

    def test_report_is_flushed_before_the_explanation_is_written(self):
        config = self.config("")
        events = []

        class Output(io.StringIO):
            def flush(self):
                events.append(("flushed", self.getvalue()))

        class Errors(io.StringIO):
            def write(self, text):
                events.append(("stderr", text))
                return super().write(text)

        with patch("sys.stdout", Output()), patch("sys.stderr", Errors()):
            status = main(["--config", str(config), "--format", "json"])
        self.assertEqual(status, 2)
        self.assertEqual([kind for kind, text in events], ["flushed", "stderr"])
        self.assertTrue(json.loads(events[0][1])["inspection_gaps"])
        self.assertEqual(events[1][1], EXPLANATION)
