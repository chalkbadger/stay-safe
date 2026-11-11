"""Codex plugins in plugins/cache in the Codex home, in a run with no file arguments (archived issue #116).

Expected results follow openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a:
- The plugin cache is `plugins/cache` in the Codex home (core-plugin-common/src/installed.rs L11;
  core-plugins/src/store.rs L87-L88), and a plugin installs to `<marketplace>/<plugin>/<version>` there
  (store.rs L112-L120).
- A plugin's active version is a directory inside `<marketplace>/<plugin>`; with none, there is no plugin
  to load (installed.rs L47-L68).
The unreadable result and next step follow issue #41; discovery semantics stay unchanged.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import INCOMPLETE
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
        self.assertEqual(err.getvalue(), INCOMPLETE if code == 2 else "")
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

    def test_unlistable_cache_reports_failure_without_private_details(self):
        failure = ('Codex home: Could not check the plugin cache. '
                   'Check that you can open plugins/cache in your Codex folder.')
        for level in ('', '/private-market', '/private-market/private-plugin'):
            home = self.home('private-home-' + str(len(level)),
                             ['plugins/cache/private-market/private-plugin'])
            denied_path = home / ('plugins/cache' + level)
            real = os.listdir

            def denied(path):
                if path == denied_path:
                    raise PermissionError(13, 'private-error', str(path))
                return real(path)

            for fmt in ('json', 'markdown'):
                with self.subTest(level=level, format=fmt):
                    out, err = io.StringIO(), io.StringIO()
                    with patch.dict(os.environ, {'CODEX_HOME': str(home)}, clear=True), \
                            patch('os.listdir', denied), redirect_stdout(out), redirect_stderr(err):
                        code = main(['--format', fmt])
                    self.assertEqual(code, 2)
                    self.assertEqual(err.getvalue(), INCOMPLETE)
                    text = out.getvalue()
                    if fmt == 'json':
                        report = json.loads(text)
                        self.assertEqual(report['inspection_gaps'], [failure])
                        self.assertEqual([risk['rule'] for risk in report['risks']], ['environment_inheritance'])
                    else:
                        self.assertIn('Could not check the plugin cache.', text)
                        self.assertIn('Check that you can open `plugins/cache` in your Codex folder.', text)
                        self.assertIn('environment_inheritance', text)
                        self.assertNotIn('Your Codex folder has plugins', text)
                    for private in (str(home), 'private-market', 'private-plugin', 'private-error'):
                        self.assertNotIn(private, text + err.getvalue())
        home = self.home('cache-file', ['plugins'])
        (home / 'plugins' / 'cache').write_text('')
        self.assertEqual(self.run_report(home), (2, [failure]))

    def test_runs_with_file_arguments_give_no_plugins_cache_gap(self):
        home = self.home('plugins', ['plugins/cache/openai-curated/github/1.0.0'])
        config = self.config(CONFIG)
        rules = self.config('prefix_rule(pattern=["git", "status"], decision="allow")\n', 'default.rules')
        without = self.home('no-plugins')
        for args in [['--config', str(config)], ['--rules', str(rules)], ['--config', str(config), '--rules', str(rules)]]:
            with self.subTest(args=args[0::2]):
                # The same as with no plugins.
                self.assertEqual(self.run_report(home, args), self.run_report(without, args))
