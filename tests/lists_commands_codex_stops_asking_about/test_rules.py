"""Independent expectations for the saved prefix_rule format and its declared meaning.

Writer: openai/codex@086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a,
codex-rs/execpolicy/src/amend.rs::blocking_append_allow_prefix_rule.
Decision precedence: execpolicy/src/policy.rs::Evaluation::from_matches.
Sandbox bypass: core/src/exec_policy.rs::create_exec_approval_requirement_for_command_platform.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from stay_safe.cli import main
from stay_safe.codex_rules import PROGRAMS as CODE_PROGRAMS
from tests.support import INCOMPLETE
from tests.support import ConfigCase, HARD_WORDS, NEAR_PROGRAMS, PROGRAMS, ROOT, full_scope

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
ALLOW = 'prefix_rule(pattern=["curl"], decision="allow")\n'
UNSUPPORTED = 'rules-1: Rules contain lines that are not inspected.'
SCOPE = ('Rules inspection lists saved-format approval candidates, one-line allow records whose syntax context '
         'and current effect are not checked; other lines, including prompt and forbidden rules that may '
         'override a candidate, make the check incomplete.')


class SavedApprovalTests(ConfigCase):
    def run_report(self, args, status=0, format_name='json', environment=None):
        out, err = io.StringIO(), io.StringIO()
        env = {'CODEX_HOME': str(self.root), **(environment or {})}
        with patch.dict(os.environ, env), redirect_stdout(out), redirect_stderr(err):
            try:
                code = main([*args, '--format', format_name])
            except SystemExit as exc:
                code = exc.code
        self.assertEqual((code, err.getvalue()), (status, INCOMPLETE if status == 2 else ""))
        completeness = 'incomplete' if status else 'complete for supported fields'
        if format_name == 'json':
            report = json.loads(out.getvalue())
            self.assertEqual(report['file_inspection'], completeness)
            return report
        summary = out.getvalue().splitlines()[2]
        self.assertEqual(summary.endswith(', 0 things not checked.'), not status, summary)
        return out.getvalue()

    def rules(self, text=ALLOW, name='selected.rules'):
        return self.config(text, name)

    def test_saved_lines_keep_line_numbers_part_counts_and_broad_labels(self):
        path = self.rules('''# Saved declarations, not an effective-policy calculation.
prefix_rule(pattern=["git", "status"], decision="allow")
prefix_rule(pattern=["npm", "test"], decision="allow")
prefix_rule(pattern=["curl"], decision="allow")

# A repeated record keeps its own line identity.
prefix_rule(pattern=["curl"], decision="allow")
''' + ''.join('prefix_rule(pattern=' + json.dumps(['curl', word]) + ', decision="allow")\n' for word in HARD_WORDS))
        report = self.run_report(['--rules', str(path)])
        self.assertEqual([(e['id'], e['kind'], e['observations']) for e in report['catalog']], [
            ('rules-1:prefix_rule.2', 'saved approval', ['program: git', 'tokens: 2']),
            ('rules-1:prefix_rule.3', 'saved approval', ['program: npm', 'tokens: 2']),
            ('rules-1:prefix_rule.4', 'saved approval', ['program: curl', 'tokens: 1', 'broad: one-token prefix']),
            ('rules-1:prefix_rule.7', 'saved approval', ['program: curl', 'tokens: 1', 'broad: one-token prefix']),
        ] + [(f'rules-1:prefix_rule.{line}', 'saved approval', ['program: curl', 'tokens: 2'])
             for line in range(8, 20)])
        self.assertEqual([r['rule'] for r in report['risks']], ['saved_approval'] * 16)
        self.assertEqual({r['explanation'] for r in report['risks']}, {
            'A saved rule declares matching commands allowed outside the sandbox without prompting.'})
        self.assertEqual(report['inspection_gaps'], [])

    def test_only_a_first_word_exactly_on_the_program_list_is_shown(self):
        # A check of source structure: no report fixture can show that an unknown name was not added, so the
        # code's list must be exactly the decided one (no additions, removals or duplicates).
        self.assertEqual(sorted(CODE_PROGRAMS), sorted(PROGRAMS))
        # Each listed name first, with a private second word; then one-word approvals; then first words that
        # are near a listed name, and listed names after the first word.
        approvals = ([[name, 'Hunter2Secret'] for name in PROGRAMS] + [['rm'], ['backupctl']]
                     + [[word, 'status'] for word in NEAR_PROGRAMS] + [['deploy', 'git'], ['deploy', 'rm', 'curl']])
        path = self.rules(''.join(f'prefix_rule(pattern={json.dumps(words)}, decision="allow")\n'
                                  for words in approvals))
        listed = len(PROGRAMS)
        expected = ([(f'rules-1:prefix_rule.{line}', [f'program: {name}', 'tokens: 2'])
                     for line, name in enumerate(PROGRAMS, 1)]
                    + [(f'rules-1:prefix_rule.{listed + 1}', ['program: rm', 'tokens: 1', 'broad: one-token prefix']),
                       (f'rules-1:prefix_rule.{listed + 2}', ['tokens: 1', 'broad: one-token prefix'])]
                    + [(f'rules-1:prefix_rule.{line}', ['tokens: 2'])
                       for line in range(listed + 3, listed + 3 + len(NEAR_PROGRAMS) + 1)]
                    + [(f'rules-1:prefix_rule.{len(approvals)}', ['tokens: 3'])])
        report = self.run_report(['--rules', str(path)])
        self.assertEqual([(e['id'], e['observations']) for e in report['catalog']], expected)
        markdown = self.run_report(['--rules', str(path)], format_name='markdown')
        self.assertIn('\n- Saved approval, line 1: starts with `git`, 2 words\n', markdown)
        self.assertIn(f'\n- Saved approval, line {listed + 3}: 2 words\n', markdown)

    def test_scope_calls_listed_entries_candidates_with_unchecked_context_and_effect(self):
        path = self.rules('x = """\n' + ALLOW + '"""\n')
        report = self.run_report(['--rules', str(path)], status=2)
        self.assertEqual([e['id'] for e in report['catalog']], ['rules-1:prefix_rule.2'])
        self.assertIn(SCOPE, report['scope'])
        markdown = self.run_report(['--rules', str(path)], status=2, format_name='markdown')
        # Markdown links the full scope in docs/report.md at its commit, which holds this line (archived issues #105, #137).
        revision = report['provenance']['source_revision']
        self.assertIn(f'[Full scope of this report](https://github.com/chalkbadger/stay-safe/blob/{revision}/docs/report.md#full-scope)',
                      markdown)
        self.assertIn('\n- ' + SCOPE + '\n', '\n' + full_scope() + '\n')

    def test_unsupported_lines_preserve_supported_records(self):
        for statement in [
            'prefix_rule(pattern=commands, decision="allow")',
            'prefix_rule(pattern=[["git", "hg"]], decision="allow")',
            'prefix_rule(pattern=[], decision="allow")',
            'prefix_rule(pattern=[1], decision="allow")',
            'prefix_rule(pattern=["curl"])',
            'prefix_rule(pattern=["curl"], decision="unknown")',
            'prefix_rule(pattern=["curl"], decision="allow", decision="forbidden")',
            'prefix_rule(pattern=["curl"], decision="allow", justification="private-value")',
            # https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/execpolicy/src/parser.rs#L355
            'prefix_rule(pattern=["curl"], decision="allow", canonical_matching=True)',
            'prefix_rule(["curl"], "allow")',
            'prefix_rule(pattern=["cu" "rl"], decision="allow")',
            'prefix_rule(pattern=[r"curl"], decision="allow")',
            'prefix_rule(pattern=["curl"], decision=d)',
            'prefix_rule(pattern=["curl"], decision="al" "low")',
            'prefix_rule(pattern=["curl"], decision=r"allow")',
            "prefix_rule(pattern=['curl'], decision='allow')",
            'prefix_rule(decision="allow", pattern=["curl"])',
            'prefix_rule(pattern=["curl"], decision="allow") # trailing comment',
            'prefix_rule(pattern=["curl"], decision="allow")\r',
            '    prefix_rule(pattern=["curl"], decision="allow")',
            'network_rule(host="api.github.com", protocol="https", decision="allow")',
        ]:
            with self.subTest(statement=statement):
                path = self.rules(statement + '\n' + ALLOW)
                report = self.run_report(['--rules', str(path)], status=2)
                self.assertEqual([e['id'] for e in report['catalog']], ['rules-1:prefix_rule.2'])
                self.assertEqual([r['entry'] for r in report['risks']], ['rules-1:prefix_rule.2'])
                self.assertEqual(report['inspection_gaps'], [UNSUPPORTED])

    def test_broken_and_multiline_input_keeps_other_lines_without_echoing_it(self):
        for broken in ['private-secret = "unterminated', 'prefix_rule(', '\0private-secret',
                       'prefix_rule(\n    pattern=["private-secret"], decision="allow"\n)']:
            with self.subTest(broken=broken):
                path = self.rules(ALLOW + broken + '\n' + ALLOW)
                report = self.run_report(['--rules', str(path)], status=2)
                ids = ['rules-1:prefix_rule.1', f'rules-1:prefix_rule.{len(broken.splitlines()) + 2}']
                self.assertEqual([e['id'] for e in report['catalog']], ids)
                self.assertEqual([r['entry'] for r in report['risks']], ids)
                self.assertEqual(report['inspection_gaps'], [UNSUPPORTED])
                self.assertNotIn('private-secret', json.dumps(report))
                markdown = self.run_report(['--rules', str(path)], status=2, format_name='markdown')
                self.assertNotIn('private-secret', markdown)

    def test_file_selection_keeps_configuration_and_rules_independent(self):
        config = self.config(CONFIG)
        directory = self.root / 'rules'
        directory.mkdir()
        default = self.rules(ALLOW, 'rules/default.rules')
        # The default file has a one-part approval on line 1; the selected file a two-part one on line 2.
        selected = self.rules('\nprefix_rule(pattern=["git", "status"], decision="allow")')
        default_approval = ('rules-1:prefix_rule.1', ['program: curl', 'tokens: 1', 'broad: one-token prefix'])
        selected_approval = ('rules-1:prefix_rule.2', ['program: git', 'tokens: 2'])
        for args, approvals, sources in [
            ([], [default_approval], {'config-1', 'rules-1'}),
            (['--config', str(config)], [], {'config-1'}),
            (['--rules', str(selected)], [selected_approval], {'rules-1'}),
            (['--config', str(config), '--config', str(config), '--rules', str(selected)],
             [selected_approval], {'config-1', 'config-2', 'rules-1'}),
        ]:
            with self.subTest(args=args):
                report = self.run_report(args)
                self.assertEqual({e['source'] for e in report['catalog']}, sources)
                found = [(e['id'], e['observations']) for e in report['catalog'] if e['kind'] == 'saved approval']
                self.assertEqual(found, approvals)
        config.unlink()
        report = self.run_report(['--rules', str(selected)])
        self.assertEqual([r['rule'] for r in report['risks']], ['saved_approval'])
        self.assertEqual(report['inspection_gaps'], [])
        self.assertEqual(default.read_text(), ALLOW)

    def test_unset_codex_home_uses_home_dot_codex(self):
        home = self.root / '.codex'
        (home / 'rules').mkdir(parents=True)
        (home / 'config.toml').write_text(CONFIG)
        (home / 'rules/default.rules').write_text(ALLOW)
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'home', return_value=self.root):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(['--format', 'json']), 0)
        report = json.loads(out.getvalue())
        self.assertIn('rules-1:prefix_rule.1', [e['id'] for e in report['catalog']])

    def test_missing_default_is_absent_but_missing_selected_file_is_a_gap(self):
        self.config(CONFIG)
        report = self.run_report([])
        self.assertEqual([e for e in report['catalog'] if e['source'] == 'rules-1'], [{
            'id': 'rules-1:rules', 'source': 'rules-1', 'name': 'rules',
            'kind': 'rules file', 'observations': ['absent'],
        }])
        self.assertEqual(report['inspection_gaps'], [])
        report = self.run_report(['--rules', str(self.root / 'private-missing.rules')], status=2)
        self.assertEqual((report['catalog'], report['risks'], report['inspection_gaps']),
                         ([], [], ['rules-1: Selected rules input is missing; its path was withheld.']))
        self.assertNotIn('private-missing', json.dumps(report))

    def test_empty_and_comment_only_files_have_no_approval_findings(self):
        for text in ['', '# comment\n']:
            with self.subTest(text=text):
                report = self.run_report(['--rules', str(self.rules(text))])
                self.assertEqual((report['catalog'], report['risks'], report['inspection_gaps']), ([], [], []))

    def test_prompt_and_forbidden_lines_are_unsupported_beside_listed_allow_lines(self):
        for decision in ['prompt', 'forbidden']:
            for token in ['curl', '/bin/rm']:
                restrictive = ALLOW.replace('curl', token).replace('allow', decision)
                for text, ids in [(ALLOW + restrictive, ['rules-1:prefix_rule.1']),
                                  (restrictive + ALLOW, ['rules-1:prefix_rule.2']),
                                  (restrictive, [])]:
                    with self.subTest(text=text):
                        report = self.run_report(['--rules', str(self.rules(text))], status=2)
                        self.assertEqual([(e['id'], e['observations']) for e in report['catalog']],
                                         [(i, ['program: curl', 'tokens: 1', 'broad: one-token prefix'])
                                          for i in ids])
                        self.assertEqual([(r['rule'], r['entry']) for r in report['risks']],
                                         [('saved_approval', i) for i in ids])
                        self.assertEqual(report['inspection_gaps'], [UNSUPPORTED])

    def test_unreadable_nonregular_oversize_and_invalid_utf8_are_gaps(self):
        good = self.rules()
        link = self.root / 'link.rules'
        link.symlink_to(good)
        broken_link = self.root / 'broken.rules'
        broken_link.symlink_to(self.root / 'absent')
        invalid = self.root / 'invalid.rules'
        invalid.write_bytes(b'\xff')
        large = self.rules(' ' * (1024 * 1024 + 1), 'large.rules')
        for path in [link, broken_link, invalid, large, self.root]:
            with self.subTest(path=path):
                report = self.run_report(['--rules', str(path)], status=2)
                self.assertEqual((report['catalog'], report['risks']), ([], []))
        with patch('os.open', side_effect=PermissionError):
            report = self.run_report(['--rules', str(good)], status=2)
        self.assertEqual(report['catalog'], [])
        fifo = self.root / 'fifo.rules'
        os.mkfifo(fifo)
        run = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--rules', str(fifo), '--format', 'json'],
                             cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
        self.assertEqual(json.loads(run.stdout)['catalog'], [])

    def test_both_formats_repeat_and_removing_a_rule_removes_its_finding(self):
        path = self.rules(ALLOW)
        report = self.run_report(['--rules', str(path)])
        finding, = report['risks']
        self.assertEqual((finding['entry'], finding['incidents']), ('rules-1:prefix_rule.1', ['I26']))
        revision = report['provenance']['source_revision']
        self.assertEqual(finding['interpretation_source'],
                         f'https://github.com/chalkbadger/stay-safe/blob/{revision}/harnesses/codex.md')
        self.assertIn(f'/blob/{revision}/incidents.md#i26-', report['incident_links']['I26'])
        self.assertEqual(report['incident_status'], 'reported, not verified')
        for format_name in ['markdown', 'json']:
            one = self.run_report(['--rules', str(path)], format_name=format_name)
            self.assertEqual(one, self.run_report(['--rules', str(path)], format_name=format_name))
            if format_name == 'markdown':
                self.assertIn('Rule `saved_approval` · rules entry `rules-1:prefix_rule.1` = ', one)
                self.assertIn('Saved approval, line 1: starts with `curl`, 1 word, covers every use of that program', one)
                self.assertIn(report['incident_links']['I26'], one)
        path.write_text('# removed\n')
        report = self.run_report(['--rules', str(path)])
        self.assertEqual((report['catalog'], report['risks']), ([], []))
