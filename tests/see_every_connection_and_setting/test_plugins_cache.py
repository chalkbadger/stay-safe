"""Codex plugins in plugins/cache in the Codex home, in a run with no file arguments (archived issue #116).

Expected results follow openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a:
- The plugin cache is `plugins/cache` in the Codex home (core-plugin-common/src/installed.rs L11;
  core-plugins/src/store.rs L87-L88), and a plugin installs to `<marketplace>/<plugin>/<version>` there
  (store.rs L112-L120).
- A plugin's active version is a directory inside `<marketplace>/<plugin>`; with none, there is no plugin
  to load (installed.rs L47-L68).
The gap text and the unlistable case follow the issue: it names plugins/cache as not inspected.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ConfigCase

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
GAP = 'Codex home: plugins/cache holds Codex plugins that were not inspected.'


class PluginsCacheTests(ConfigCase):
    def home(self, name, folders=()):
        # A clean Codex home: with nothing in plugins/cache the run has no gaps and exits 0.
        home = self.root / name
        home.mkdir()
        (home / 'config.toml').write_text(CONFIG)
        for folder in folders:
            (home / folder).mkdir(parents=True)
        return home

    def run_report(self, home, args=()):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'CODEX_HOME': str(home)}, clear=True), \
                redirect_stdout(out), redirect_stderr(err):
            code = main(['--format', 'json', *args])
        self.assertEqual(err.getvalue(), '')
        return code, json.loads(out.getvalue())['inspection_gaps']

    def test_version_folder_gives_the_gap_and_exits_2(self):
        github = 'plugins/cache/openai-curated/github/1.0.0'
        other, same = 'plugins/cache/acme/empty', 'plugins/cache/openai-curated/figma'  # plugin folders with no version
        cases = [('one plugin', [github]),
                 ('several plugins', [github, 'plugins/cache/openai-curated/github/local', 'plugins/cache/acme/linear/2.1.0']),
                 ('no version in another marketplace, made first', [other, github]),
                 ('no version in another marketplace, made last', [github, other]),
                 ('no version in the same marketplace, made first', [same, github]),
                 ('no version in the same marketplace, made last', [github, same])]
        for kind, folders in cases:
            with self.subTest(kind=kind):
                self.assertEqual(self.run_report(self.home(kind.replace(' ', '-'), folders)), (2, [GAP]))
        with self.subTest(kind='no config.toml'):
            # Plugins on the ChatGPT account load with no config.toml entry (the issue's Now and After).
            home = self.home('no-config', [github])
            (home / 'config.toml').unlink()
            code, gaps = self.run_report(home)
            self.assertEqual(code, 2)
            self.assertIn(GAP, gaps)

    def test_cache_without_a_version_folder_gives_no_gap(self):
        cases = [('no plugins folder', []), ('no cache', ['plugins']), ('empty cache', ['plugins/cache']),
                 ('marketplace only', ['plugins/cache/openai-curated']),
                 ('plugin only', ['plugins/cache/openai-curated/github'])]
        for kind, folders in cases:
            with self.subTest(kind=kind):
                self.assertEqual(self.run_report(self.home(kind.replace(' ', '-'), folders)), (0, []))
        with self.subTest(kind='file where a version folder would be'):
            home = self.home('file-version', ['plugins/cache/openai-curated/github'])
            (home / 'plugins' / 'cache' / 'openai-curated' / 'github' / '1.0.0').write_text('')
            self.assertEqual(self.run_report(home), (0, []))

    def test_unlistable_cache_gives_the_gap_and_exits_2(self):
        # A plugins/cache that is a file cannot be listed as a directory; this holds even for uid 0.
        home = self.home('cache-file', ['plugins'])
        (home / 'plugins' / 'cache').write_text('')
        self.assertEqual(self.run_report(home), (2, [GAP]))
        # A plugins/cache directory whose listing is denied. Only this listing is denied.
        home = self.home('cache-denied', ['plugins/cache'])
        cache = home / 'plugins' / 'cache'
        scandir, listdir = os.scandir, os.listdir

        def denied(real):
            def call(path='.'):
                if os.fspath(path) == os.fspath(cache):
                    raise PermissionError(13, 'Permission denied')
                return real(path)
            return call
        with patch('os.scandir', denied(scandir)), patch('os.listdir', denied(listdir)):
            self.assertEqual(self.run_report(home), (2, [GAP]))

    def test_runs_with_file_arguments_give_no_plugins_cache_gap(self):
        home = self.home('plugins', ['plugins/cache/openai-curated/github/1.0.0'])
        config = self.config(CONFIG)
        rules = self.config('prefix_rule(pattern=["git", "status"], decision="allow")\n', 'default.rules')
        without = self.home('no-plugins')
        for args in [['--config', str(config)], ['--rules', str(rules)], ['--config', str(config), '--rules', str(rules)]]:
            with self.subTest(args=args[0::2]):
                # The same as with no plugins.
                self.assertEqual(self.run_report(home, args), self.run_report(without, args))
