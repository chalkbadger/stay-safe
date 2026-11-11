"""A hooks.json file in the Codex home, in a run with no file arguments (archived issue #97).

Expected results follow openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a:
- hooks/src/engine/discovery.rs L176-L181 loads hooks.json from each layer's hooks folder, which for the
  User layer is the folder holding the Codex home's config.toml (config/src/state.rs L219-L243;
  config/src/loader/mod.rs L297).
- The User layer is added even when config.toml is missing: a missing file reads as an empty table
  (config/src/loader/mod.rs L617-L619) and the layer is still pushed (L328).
- The Codex home is $CODEX_HOME, or ~/.codex when CODEX_HOME is unset or empty
  (utils/home-dir/src/lib.rs L14-L16, L52-L59).
- discovery.rs `load_hooks_json` (L390-L397) loads it only when `Path::is_file` is true. Codex builds with
  Rust 1.95.0 (codex-rs/rust-toolchain.toml L2), whose `is_file` traverses symbolic links and is true only
  for a regular file (rust-lang/rust@59807616e1fa2540724bfbac14d7976d7e4a3860 library/std/src/path.rs
  L3480-L3511).
The gap text follows the issue: it names the file and says it is not inspected; its contents are not read.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
HOOKS = '{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "private-hook-program"}]}]}}\n'
GAP = 'Codex home: hooks.json exists and was not inspected.'


class HooksJsonTests(ConfigCase):
    def home(self, name, config=True):
        # As in tests/works_without_a_config_file/test_home.py: a home directory holding .codex/.
        home = self.root / name / '.codex'
        home.mkdir(parents=True)
        if config:
            (home / 'config.toml').write_text(CONFIG)
        return home

    def run_report(self, env):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), redirect_stdout(out), redirect_stderr(err):
            code = main(['--format', 'json'])
        self.assertEqual(err.getvalue(), '')
        return code, out.getvalue()

    def test_hooks_json_file_gives_a_gap_naming_it_and_exits_2(self):
        for kind in ['regular file', 'symlink to a regular file', 'CODEX_HOME unset', 'CODEX_HOME empty',
                     'no config.toml']:
            with self.subTest(kind=kind):
                name = kind.replace(' ', '-')
                home = self.home(name, config=kind != 'no config.toml')
                if kind == 'symlink to a regular file':
                    target = self.root / f'{name}-target.json'
                    target.write_text(HOOKS)
                    (home / 'hooks.json').symlink_to(target)
                else:
                    (home / 'hooks.json').write_text(HOOKS)
                env = {'CODEX_HOME': str(home)}
                if kind == 'CODEX_HOME unset':
                    env = {'HOME': str(home.parent)}
                elif kind == 'CODEX_HOME empty':
                    env = {'HOME': str(home.parent), 'CODEX_HOME': ''}
                code, out = self.run_report(env)
                report = json.loads(out)
                if kind == 'no config.toml':
                    # The missing file's own gaps belong to other claims.
                    self.assertEqual(code, 2)
                    self.assertIn(GAP, report['inspection_gaps'])
                else:
                    self.assertEqual((code, report['file_inspection'], report['inspection_gaps']),
                                     (2, 'incomplete', [GAP]))
                self.assertNotIn('private-hook-program', out)

    def test_codex_home_without_a_hooks_json_file_gives_no_such_gap(self):
        for kind in ['no hooks.json', 'directory named hooks.json']:
            with self.subTest(kind=kind):
                home = self.home(kind.replace(' ', '-'))
                if kind == 'directory named hooks.json':
                    (home / 'hooks.json').mkdir()
                code, out = self.run_report({'CODEX_HOME': str(home)})
                report = json.loads(out)
                self.assertEqual((code, report['inspection_gaps']), (0, []))
