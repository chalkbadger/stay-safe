import json

from tests.support import ConfigCase, agent_home, run_home

VALID = {"awsAuthRefresh": "seed-aws-sso", "awsCredentialExport": "seed-aws-export", "gcpAuthRefresh": "seed-gcloud", "otelHeadersHelper": "/seed/otel-headers"}
INVALID = {"awsAuthRefresh": "  ", "awsCredentialExport": 1, "gcpAuthRefresh": None, "otelHeadersHelper": {"cmd": "seed"}}


def read_file(*args, **kwargs):
    from stay_safe import claude
    return claude.read_file(*args, **kwargs)


class ClaudeCloudHelpersTests(ConfigCase):
    def read(self, settings, scope=None):
        path = self.config(json.dumps({"permissions": {"defaultMode": "default"}, **settings}), "settings.json")
        return read_file(path, "settings-1", **({"scope": scope} if scope else {}))

    def programs(self, entries):
        return {entry["name"]: [entry["observations"], entry["facts"].get("configured_program")]
                for entry in entries if entry["kind"] == "program"}

    def test_each_helper_is_listed_with_its_command_withheld(self):
        for scope in (None, "user", "project"):
            observations = ["command withheld", "project settings"] if scope == "project" else ["command withheld"]
            expected = {name: [observations, True] for name in VALID}
            with self.subTest(scope=scope):
                entries, gaps = self.read(VALID, scope)
                self.assertEqual(self.programs(entries), expected)
                self.assertEqual(gaps, [])
                self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_invalid_helper_value_names_the_setting(self):
        home = agent_home(self.root, claude=json.dumps(INVALID))
        run = run_home(home, "--agent", "claude")
        for name, value in INVALID.items():
            with self.subTest(name=name):
                entries, gaps = self.read({name: value})
                if name == "awsAuthRefresh":
                    message = f"{name} is blank. There is no command to check."
                    reason = "The value is blank. There is no command to check."
                else:
                    message = f"{name} has a non-text value. Claude Code expects a command written as text."
                    reason = "The value is not text. Claude Code expects a command written as text."
                self.assertEqual(gaps, [f"settings-1: {message}"])
                self.assertEqual(self.programs(entries), {})
                self.assertIn(f"**Not checked: `{name}`.** {reason}", run.stdout)
                self.assertIn(f"Set `{name}` to the command you want Claude Code to run, or remove the setting.", run.stdout)
                self.assertNotIn("seed", json.dumps([entries, gaps]) + run.stdout)
