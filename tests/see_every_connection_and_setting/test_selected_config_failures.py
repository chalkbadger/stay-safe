"""Issue #16: selected-file failures say which fix to try without exposing private input."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from unittest.mock import patch

from stay_safe.cli import main
from stay_safe.codex import open_input
from tests.support import ConfigCase

MISSING = 'Selected config file is missing. Check the path supplied to --config.'
SYMLINK = 'Selected config file is a symlink and was not followed. Select its target file explicitly with --config.'
UNREADABLE = 'Selected config file could not be read. Check its permissions and that it is a readable regular file.'
UTF8 = 'Selected config file is not valid UTF-8. Save a copy as UTF-8 and select it with --config.'
TOML = 'Selected config file is not valid TOML. Fix the TOML syntax locally, then run stay-safe again.'


class SelectedConfigFailureTests(ConfigCase):
    def test_each_failure_has_a_distinct_private_safe_reason_and_action_in_both_formats(self):
        good = self.config('approval_policy="never"\nsandbox_mode="read-only"', 'good.toml')
        missing = self.root / 'alice@example.com-missing.toml'
        denied = self.config('', 'alice@example.com-denied.toml')
        bad_utf8 = self.root / 'alice@example.com-encoding.toml'
        bad_utf8.write_bytes(b'# private-content-marker\n\xff')
        bad_toml = self.config('private-content-marker = "unterminated', 'alice@example.com-syntax.toml')
        linked = self.root / 'alice@example.com-link.toml'
        linked.symlink_to(good)
        dangling = self.root / 'alice@example.com-dangling.toml'
        dangling.symlink_to(missing)

        def permission_failure(path):
            if path == denied:
                raise PermissionError(13, 'private-error-marker', str(path))
            return open_input(path)

        cases = [(missing, MISSING, "file is missing"), (linked, SYMLINK, "file is a symlink"),
                 (dangling, SYMLINK, "file is a symlink"), (denied, UNREADABLE, "couldn't read"),
                 (bad_utf8, UTF8, "isn't valid UTF-8"), (bad_toml, TOML, "isn't valid TOML")]
        for path, expected, words in cases:
            for format_name in ('json', 'markdown'):
                with self.subTest(path=path.name, format=format_name):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with patch('stay_safe.codex.open_input', side_effect=permission_failure), redirect_stdout(stdout), redirect_stderr(stderr):
                        status = main(['--config', str(path), '--config', str(good), '--format', format_name])
                    text = stdout.getvalue()
                    self.assertEqual((status, stderr.getvalue()), (2, ''))
                    if format_name == 'json':
                        report = json.loads(text)
                        self.assertEqual(report['inspection_gaps'], ['config-1: ' + expected])
                        self.assertEqual({(risk['rule'], risk['entry']) for risk in report['risks']}, {
                            ('commands_without_prompts', 'config-2:approval_policy'),
                            ('environment_inheritance', 'config-2:shell_environment_policy'),
                        })
                        self.assertEqual({e['source'] for e in report['catalog']}, {'config-2'})
                    else:
                        self.assertIn(words, text)
                        self.assertIn(expected.split('. ', 1)[1], text.replace('`', ''))
                        self.assertIn('**With these settings, Codex runs commands without asking you.**', text)
                        self.assertIn('**With these settings, commands Codex runs get your environment variables.**', text)
                        self.assertIn('Rule `commands_without_prompts` · setting `config-2:approval_policy`', text)
                        self.assertIn('Rule `environment_inheritance` · setting `config-2:shell_environment_policy`', text)
                    for private in (str(self.root), 'alice@example.com', 'private-content-marker', 'private-error-marker'):
                        self.assertNotIn(private, text)
                    self.assertNotIn('readlink', text)
