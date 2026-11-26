import json

from tests.support import ConfigCase

VALID = {"sshHostCommands": [{"id": "seed-id", "name": "seed-name", "command": "seed-dev create"}]}
EXPECTED = [
    (None, {"sshHostCommands": [["command withheld", "Claude Desktop reads `sshHostCommands` from your user settings or from a managed file or policy on your computer."], True]}),
    ("user", {"sshHostCommands": [["command withheld"], True]}),
    ("project", {"sshHostCommands": [["Claude Desktop ignores `sshHostCommands` in `.claude/settings.json`."], False]}),
]
INVALID = [
    ("sshHostCommands", [{"id": "unit", "name": "Unit"}],
     "Connection 1 in sshHostCommands is missing command. Add the program and arguments that print the SSH host."),
    ("sshHostCommands", [{'id': 'seed', 'name': 'seed', 'command': ''}], "Connection 1 in sshHostCommands needs text in command. Enter the program and arguments that print the SSH host as a nonblank string."),
    ("sshHostCommands", [42], "Connection 1 in sshHostCommands must be a JSON object. Give the connection an id, a name and a command."),
    ("sshHostCommands", {}, "sshHostCommands must be a list of connection entries."),
]


def read_file(*args, **kwargs):
    from stay_safe import claude
    return claude.read_file(*args, **kwargs)


class ClaudeSshHostCommandsTests(ConfigCase):
    def read(self, settings, scope=None):
        path = self.config(json.dumps({"permissions": {"defaultMode": "default"}, **settings}), "settings.json")
        return read_file(path, "settings-1", **({"scope": scope} if scope else {}))

    def programs(self, entries):
        return {entry["name"]: [entry["observations"], entry["facts"].get("configured_program")]
                for entry in entries if entry["kind"] == "program"}

    def test_ssh_host_commands_is_listed_with_its_command_withheld(self):
        for scope, expected in EXPECTED:
            with self.subTest(scope=scope):
                entries, gaps = self.read(VALID, scope)
                self.assertEqual(self.programs(entries), expected)
                self.assertEqual(gaps, [])
                self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_malformed_ssh_host_commands_names_the_setting(self):
        for name, value, message in INVALID:
            with self.subTest(name=name, value=value):
                entries, gaps = self.read({name: value})
                self.assertEqual(gaps, [f"settings-1: {message}"])
                self.assertEqual(self.programs(entries), {})
                self.assertNotIn("seed", json.dumps([entries, gaps]))

    def test_invalid_and_duplicate_connection_fields_are_reported_by_position(self):
        connections = [{"id": identifier, "name": label, "command": "secret-marker"}
                       for identifier, label in [("same", "first"), ("same", "second"),
                                                 ("bad id", "third"), ("four", "too long" * 30),
                                                 ("five", "line\nbreak")]]
        entries, gaps = self.read({"sshHostCommands": connections})
        self.assertEqual(self.programs(entries), {})
        self.assertEqual(len(gaps), 5)
        for position, problem in enumerate(["shares an id", "shares an id", "has an invalid id",
                                            "has an invalid name", "has an invalid name"], 1):
            self.assertTrue(any(f"Connection {position} in sshHostCommands {problem}" in gap for gap in gaps))
        self.assertNotIn("secret-marker", json.dumps([entries, gaps]))
