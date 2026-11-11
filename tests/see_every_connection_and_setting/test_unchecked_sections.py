"""Issue #9's bounded names and literal trusted-declaration count, not live trust."""
import builtins
import io
import json
import os
import subprocess
import sys
from unittest.mock import patch

from stay_safe.codex import Reader
from stay_safe.report import inspect
from tests.support import ConfigCase, ROOT


BASE = {'approval_policy': 'on-request', 'sandbox_mode': 'read-only'}
UNKNOWN = 'Configuration contains fields outside reader coverage; their values were withheld.'
INCOMPLETE = 'projects contains malformed or unsupported data; its declarations could not be fully assessed.'


def count_message(n):
    return f'projects contains {n} recognized trusted declarations; project settings were not inspected.'


class UncheckedSectionsTests(ConfigCase):
    def test_only_recognized_unchecked_sections_are_named_and_preferences_stay_ignored(self):
        for section in ('plugins', 'marketplaces', 'desktop'):
            for value in ({'private-key': 'private-value'}, {}, False):
                with self.subTest(section=section, value=value):
                    entries, gaps = Reader('config-1').read(BASE | {section: value})
                    self.assertEqual(gaps, [f'config-1: Unchecked section {section}; its settings were not evaluated.'])
                    self.assertEqual(entries, Reader('config-1').read(BASE)[0])
        self.assertEqual(Reader('config-1').read(BASE | {'tui': {'private-key': 'secret'}})[1], [])
        self.assertEqual(Reader('config-1').read(BASE | {'private-arbitrary-key': 'secret'})[1],
                         ['config-1: ' + UNKNOWN])

    def test_project_counts_distinguish_zero_invalid_and_partial_declarations(self):
        cases = [
            ({}, 0, False),
            ({'/private/one': {'trust_level': 'untrusted'}}, 0, False),
            ({'/private/one': {'trust_level': 'trusted'}, '/private/two': {'trust_level': 'trusted'}}, 2, False),
            (False, None, True),
            ([], None, True),
            ({'/private/one': False}, 0, True),
            ({'/private/one': {}}, 0, True),
            ({'/private/one': {'trust_level': True}}, 0, True),
            ({'/private/one': {'trust_level': 'Trusted'}}, 0, True),
            ({'/private/one': {'trust_level': 'future'}}, 0, True),
            ({'/private/one': {'trust_level': 'trusted', 'private-extra': 'secret'}}, 1, True),
            ({'/private/one': {'trust_level': 'trusted'}, '/private/two': {'trust_level': 'future'}}, 1, True),
        ]
        for projects, count, incomplete in cases:
            with self.subTest(projects=projects):
                entries, gaps = Reader('config-1').read(BASE | {'projects': projects})
                expected = ([count_message(count)] if count is not None else []) + ([INCOMPLETE] if incomplete else [])
                self.assertEqual(gaps, sorted('config-1: ' + x for x in expected))
                self.assertEqual(entries, Reader('config-1').read(BASE)[0])
        self.assertEqual(Reader('config-1').read(BASE)[1], [])

    def test_both_formats_keep_file_counts_findings_and_private_identifiers_withheld(self):
        one = self.config('''approval_policy = "on-request"
sandbox_mode = "read-only"
private_arbitrary_key = "private-value"
[plugins.private_plugin]
private_nested_key = "private-value"
[marketplaces.private_marketplace]
source = "/private/source"
[desktop]
private_nested_key = "private-value"
[projects."/private/one"]
trust_level = "trusted"
[projects."/private/two"]
trust_level = "future-private-value"
''')
        two = self.config('''approval_policy = "on-request"
sandbox_mode = "read-only"
[projects."/private/three"]
trust_level = "untrusted"
''', 'second.toml')
        expected = sorted('config-1: ' + x for x in [UNKNOWN, INCOMPLETE, count_message(1),
            *[f'Unchecked section {s}; its settings were not evaluated.' for s in ('plugins', 'marketplaces', 'desktop')]])
        expected += ['config-2: ' + count_message(0)]
        reports = {}
        for fmt in ('json', 'markdown'):
            run = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--config', str(one), '--config', str(two),
                                  '--format', fmt], cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 2)
            reports[fmt] = run.stdout
            for private in ('private_arbitrary_key', 'private_nested_key', 'private_plugin', 'private_marketplace',
                            'private-value', 'future-private-value', '/private/', str(self.root)):
                self.assertNotIn(private, run.stdout + run.stderr)
        parsed = json.loads(reports['json'])
        self.assertEqual(parsed['inspection_gaps'], expected)
        self.assertEqual([r['rule'] for r in parsed['risks']], ['environment_inheritance', 'environment_inheritance'])
        for s in ('plugins', 'marketplaces', 'desktop'):
            self.assertIn(f'**Not checked: `{s}`.** Its settings were not evaluated.', reports['markdown'])
        self.assertIn('Projects marked as trusted in your file: 1.', reports['markdown'])
        self.assertIn('Projects marked as trusted in your file: 0.', reports['markdown'])
        self.assertIn('The project declarations could not be fully assessed.', reports['markdown'])
        self.assertIn('*File `config-1`*', reports['markdown'])
        self.assertIn('*File `config-2`*', reports['markdown'])
        self.assertIn('environment variables', reports['markdown'])

    def test_referenced_project_directories_are_not_accessed(self):
        project = self.root / 'private-project'
        project.mkdir()
        (project / '.codex').mkdir()
        target = project / '.codex' / 'config.toml'
        target.write_text('sandbox_mode = "danger-full-access"')
        config = self.config('approval_policy = "on-request"\nsandbox_mode = "read-only"\n'
                             f'[projects.{json.dumps(str(project))}]\ntrust_level = "trusted"\n')
        accesses = []
        def watch(original):
            def observed(path, *args, **kwargs):
                if isinstance(path, (str, bytes, os.PathLike)):
                    p = os.fsdecode(path)
                    if p == str(project) or p.startswith(str(project) + '/'):
                        accesses.append(p)
                return original(path, *args, **kwargs)
            return observed
        from contextlib import ExitStack
        with ExitStack() as stack:
            for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open'), (os, 'stat'), (os, 'lstat'),
                                 (os, 'listdir'), (os, 'scandir')):
                stack.enter_context(patch.object(module, name, watch(getattr(module, name))))
            os.stat(project)
            self.assertEqual(accesses, [str(project)])
            accesses.clear()
            result = inspect([config])
        self.assertEqual(accesses, [])
        self.assertIn('config-1: ' + count_message(1), result['inspection_gaps'])
        self.assertNotIn('unrestricted_filesystem', [r['rule'] for r in result['risks']])
