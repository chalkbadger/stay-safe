import json
import re
import subprocess
import sys

from html import escape

from stay_safe import codex_rules

from tests.support import INCOMPLETE
from tests.support import (ConfigCase, HARD_WORDS, NEAR_PROGRAMS, PROGRAMS, REPORT, ROOT, copy_checkout,
                           gap_items, run_checkout, section)
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text


class ShareableRulesTests(ConfigCase):
    def test_shown_program_names_are_the_list_in_the_meanings_document(self):
        text = (ROOT / "harnesses/codex.md").read_text(encoding="utf-8")
        section = text.split("## Saved approval records", 1)[1].split("\n## ", 1)[0]
        listed = re.findall(r"(?m)^`([a-z0-9 ]+)`$", section)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].split(), list(codex_rules.PROGRAMS))
        self.assertEqual(listed[0].split(), PROGRAMS)

    def test_invalid_json_escape_does_not_disclose_private_source(self):
        path = self.config(r'prefix_rule(pattern=["curl", "private\qvalue"], decision="allow")', 'warning.rules')
        gap = 'rules-1: Rules contain lines that are not inspected.'
        try:
            json.loads(r'["curl", "private\qvalue"]')
        except ValueError as error:
            raw_error = str(error)
        for fmt in ['markdown', 'json']:
            with self.subTest(format=fmt):
                run = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--rules', str(path), '--format', fmt],
                                     cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                if fmt == 'json':
                    report = json.loads(run.stdout)
                    self.assertEqual((report['catalog'], report['risks'], report['inspection_gaps']), ([], [], [gap]))
                else:
                    self.assertEqual(gap_items(run.stdout), [gap_text(gap)])
                for leaked in ('private', raw_error.split(':')[0], str(path)):
                    self.assertNotIn(leaked, run.stdout)

    def test_no_saved_approval_word_other_than_a_listed_first_word_appears_in_any_output(self):
        private = [
            ['deploy', 'Hunter2Secret', 'acct12345'],
            ['vaultlogin', '123e4567-e89b-12d3-a456-426614174000'],
            ['notifybot', 'xoxb-20481-93710-QWxPz7KkLm'],
            ['backupctl'],
            ['git', 'Hunter2Secret'],
        ] + [['curl', word] for word in HARD_WORDS]
        near = [['deploy', 'git'], ['deploy', 'rm', 'curl']] + [[word, 'status'] for word in NEAR_PROGRAMS]
        approvals = private + near
        placeholders = [[word if i == 0 and word in PROGRAMS else f'w{n}x{i}' for i, word in enumerate(words)]
                        for n, words in enumerate(approvals)]
        ids = [f'rules-1:prefix_rule.{line}' for line in range(1, len(approvals) + 1)]
        (self.root / 'placeholders').mkdir()
        paths = [self.config(''.join(f'prefix_rule(pattern={json.dumps(words)}, decision="allow")\n'
                                     for words in rows), name)
                 for rows, name in [(approvals, 'private-source.rules'),
                                    (placeholders, 'placeholders/private-source.rules')]]
        for fmt in ['markdown', 'json']:
            with self.subTest(format=fmt):
                runs = [subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--rules', str(path), '--format', fmt],
                                       cwd=ROOT, capture_output=True, text=True, timeout=10) for path in paths]
                run = runs[0]
                self.assertEqual(run.stderr, INCOMPLETE if run.returncode == 2 else "")
                for entry in ids:
                    self.assertIn(entry, run.stdout)
                if fmt == 'json':
                    report = json.loads(run.stdout)
                    self.assertEqual([(e['id'], e['kind']) for e in report['catalog']],
                                     [(entry, 'saved approval') for entry in ids])
                    self.assertEqual([(r['rule'], r['entry']) for r in report['risks']],
                                     [('saved_approval', entry) for entry in ids])
                for word in [word for words in private for word in words if word and word not in PROGRAMS]:
                    self.assertNotIn(word, run.stdout)
                    self.assertNotIn(json.dumps(word)[1:-1], run.stdout)
                self.assertNotIn(str(paths[0]), run.stdout)
                self.assertEqual(run.stdout, runs[1].stdout)
        checkout = copy_checkout(self.root / 'checkout')
        outputs = []
        for path in paths:
            run = run_checkout(checkout, '--rules', str(path), '--save', cwd=self.root)
            self.assertEqual((run.returncode, run.stderr), (0, ''))
            outputs.append((run.stdout, (checkout / REPORT).read_text(encoding='utf-8')))
        output_text, page = outputs[0]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(output_text.count('**A saved approval on line '), len(approvals))
        for entry in ids:
            self.assertIn(entry, page)
        for output in (output_text, page):
            for word in [word for words in private for word in words if word and word not in PROGRAMS]:
                for form in (word, json.dumps(word)[1:-1], escape(word, quote=True), escape(word, quote=False)):
                    self.assertNotIn(form, output)
            self.assertNotIn(str(paths[0]), output)
