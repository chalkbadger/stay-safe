import json

from tests.support import ConfigCase

VALID = {"processWrapper": "/seed/corp-launcher --flag"}
EXPECTED = [
    (None, {"processWrapper": [["command withheld", "Claude Code uses `processWrapper` only in user or managed settings."], True]}),
    ("user", {"processWrapper": [["command withheld"], True]}),
    ("project", {"processWrapper": [["Claude Code ignores `processWrapper` in `.claude/settings.json`."], False]}),
]
INVALID = [
    ("processWrapper", '', "processWrapper is blank. There is no command to check."),
    ("processWrapper", [], "processWrapper has a non-text value. Claude Code expects a command written as text."),
]


def read_file(*args, **kwargs):
    from stay_safe import claude
    return claude.read_file(*args, **kwargs)


class ClaudeProcessWrapperTests(ConfigCase):
    def read(self, settings, scope=None):
        path = self.config(json.dumps({"permissions": {"defaultMode": "default"}, **settings}), "settings.json")
        return read_file(path, "settings-1", **({"scope": scope} if scope else {}))

    def programs(self, entries):
        return {entry["name"]: [entry["observations"], entry["facts"].get("configured_program")]
                for entry in entries if entry["kind"] == "program"}

    def test_process_wrapper_is_listed_with_its_command_withheld(self):
        for scope, expected in EXPECTED:
            with self.subTest(scope=scope):
                entries, gaps = self.read(VALID, scope)
                self.assertEqual(self.programs(entries), expected)
                self.assertEqual(gaps, [])
                self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_malformed_process_wrapper_names_the_setting(self):
        for name, value, message in INVALID:
            with self.subTest(name=name, value=value):
                entries, gaps = self.read({name: value})
                self.assertEqual(gaps, [f"settings-1: {message}"])
                self.assertEqual(self.programs(entries), {})
                self.assertNotIn("seed", json.dumps([entries, gaps]))
