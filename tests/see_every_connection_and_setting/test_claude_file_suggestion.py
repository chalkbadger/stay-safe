import json

from tests.support import ConfigCase

VALID = {"fileSuggestion": {"type": "command", "command": "~/seed/file-index.sh"}}
EXPECTED = [
    (None, {"fileSuggestion": [["command withheld"], True]}),
    ("user", {"fileSuggestion": [["command withheld"], True]}),
    ("project", {"fileSuggestion": [["command withheld", "project settings"], True]}),
]
INVALID = [
    ("fileSuggestion", [], "fileSuggestion needs a JSON object with a type field and a command field."),
    ("fileSuggestion", {"command": "seed"}, 'fileSuggestion.type must be "command".'),
    ("fileSuggestion", {"type": "static", "command": "seed"}, 'fileSuggestion.type must be "command".'),
    ("fileSuggestion", {"type": "command"}, "fileSuggestion.command is missing."),
    ("fileSuggestion", {"type": "command", "command": 7}, "fileSuggestion.command must be text."),
    ("fileSuggestion", {"type": "command", "command": "  "}, "fileSuggestion.command is blank."),
]


def read_file(*args, **kwargs):
    from stay_safe import claude
    return claude.read_file(*args, **kwargs)


class ClaudeFileSuggestionTests(ConfigCase):
    def read(self, settings, scope=None):
        path = self.config(json.dumps({"permissions": {"defaultMode": "default"}, **settings}), "settings.json")
        return read_file(path, "settings-1", **({"scope": scope} if scope else {}))

    def programs(self, entries):
        return {entry["name"]: [entry["observations"], entry["facts"].get("configured_program")]
                for entry in entries if entry["kind"] == "program"}

    def test_file_suggestion_is_listed_with_its_command_withheld(self):
        for scope, expected in EXPECTED:
            with self.subTest(scope=scope):
                entries, gaps = self.read(VALID, scope)
                self.assertEqual(self.programs(entries), expected)
                self.assertEqual(gaps, [])
                self.assertNotIn("seed", json.dumps([entries, gaps]))

        entries, gaps = self.read({**VALID, "disableAllHooks": True}, "user")
        self.assertEqual(self.programs(entries), {"fileSuggestion": [["command withheld", "disableAllHooks is true in this file"], False]})

    def test_malformed_file_suggestion_names_the_setting(self):
        for name, value, message in INVALID:
            with self.subTest(name=name, value=value):
                entries, gaps = self.read({name: value})
                self.assertEqual(gaps, [f"settings-1: {message}"])
                self.assertEqual(self.programs(entries), {})
                self.assertNotIn("seed", json.dumps([entries, gaps]))
