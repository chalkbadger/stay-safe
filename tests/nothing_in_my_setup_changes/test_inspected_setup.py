import os

from tests.see_every_connection_and_setting.test_config import FIXTURE
from tests.support import ConfigCase, copy_checkout, run_checkout


class InspectedSetupTests(ConfigCase):
    def snapshot(self, *trees):
        return sorted(str(p) for tree in trees for p in tree.rglob("*"))

    def state(self, path):
        info = os.stat(path, follow_symlinks=False)
        return path.read_bytes(), info.st_mode, info.st_mtime_ns

    def test_inspection_leaves_inspected_files_unchanged_and_adds_no_files(self):
        home, work = self.root / "home", self.root / "work"
        work.mkdir()
        (home / "selected").mkdir(parents=True)
        config = home / "selected" / "config.toml"
        config.write_bytes(FIXTURE.read_bytes())
        rules = home / "selected" / "default.rules"
        rules.write_text('prefix_rule(pattern=["git", "status"], decision="allow")\n', encoding="utf-8")
        for path in (config, rules):
            path.chmod(0o640)
            os.utime(path, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
        # The checkout is outside the home and working directories; with --save it gains its report file.
        checkout = copy_checkout(self.root / "checkout")
        env = {"HOME": str(home)}
        self.require_no_system_folder()  # the absent-default cases are default runs
        cases = [
            ("explicit config", ["--config", str(config)], [config], 0, "\n- MCP server `lookup`: on,"),
            ("rules file", ["--rules", str(rules)], [rules], 0, "rules-1:prefix_rule.1"),
            ("absent default", [], [], 2, "\n- Config file: none found,"),
            ("explicit config, saved", ["--config", str(config), "--save"], [config], 0, "\nSaved the formatted report. Open it with: "),
            ("rules file, saved", ["--rules", str(rules), "--save"], [rules], 0, "\nSaved the formatted report. Open it with: "),
            ("absent default, saved", ["--save"], [], 2, "\nSaved the formatted report. Open it with: "),
        ]
        for name, args, inspected, status, expected in cases:
            with self.subTest(input=name):
                tree, files = self.snapshot(home, work), [self.state(p) for p in inspected]
                run = run_checkout(checkout, *args, cwd=work, env=env)
                self.assertEqual((run.returncode, run.stderr), (status, ""))
                self.assertIn(expected, run.stdout)
                self.assertEqual([self.state(p) for p in inspected], files)
                self.assertEqual(self.snapshot(home, work), tree)
