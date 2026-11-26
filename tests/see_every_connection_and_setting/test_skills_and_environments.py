from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import unittest
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import INCOMPLETE
from tests.support import ConfigCase

CONFIG = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
SKILL = '---\nname: private-skill\ndescription: private-description\n---\n'
ENVIRONMENTS = '[[environments]]\nid = "private-env"\nprogram = "private-program"\nargs = ["private-arg"]\n'
SKILLS_GAP = 'Codex home: skills holds Codex skills that were not inspected.'
SKILLS_FAILURE = ('Codex home: Could not check the skills folder. '
                  'Check that you can open skills in your Codex folder.')
ENV_GAP = 'Codex home: environments.toml exists and was not inspected.'
ENV_FAILURE = ('Codex home: Could not check environments.toml. '
               'Check that you can open environments.toml in your Codex folder.')
ENV_NOT_FILE = 'Codex home: environments.toml is not a file; Codex fails to read it.'
PRIVATE = ('private-skill', 'private-description', 'private-env', 'private-program', 'private-arg')


class SkillsAndEnvironmentsTests(ConfigCase):
    def home(self, name, skills=(), config=True):
        home = self.root / name / '.codex'
        home.mkdir(parents=True)
        if config:
            (home / 'config.toml').write_text(CONFIG)
        for path in skills:
            target = home / 'skills' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(SKILL)
        return home

    def run_report(self, home, args=(), env=None, fmt='json'):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env or {'CODEX_HOME': str(home)}, clear=True), \
                redirect_stdout(out), redirect_stderr(err):
            code = main(['--format', fmt, *args])
        self.assertEqual(err.getvalue(), INCOMPLETE if code == 2 else "")
        text = out.getvalue()
        for private in PRIVATE:
            self.assertNotIn(private, text)
        return code, (json.loads(text)['inspection_gaps'] if fmt == 'json' else text)


    def test_a_skill_in_the_skills_folder_gives_the_gap_and_exits_2(self):
        deep = '/'.join(f'd{n}' for n in range(1, 7)) + '/SKILL.md'
        cases = [('one skill', ['deploy/SKILL.md']),
                 ('several skills', ['deploy/SKILL.md', 'review/SKILL.md']),
                 ('skill in a group folder', ['team/deploy/SKILL.md']),
                 ('SKILL.md directly in skills', ['SKILL.md']),
                 ('six folders down', [deep]),
                 ('beside Codex system skills', ['.system/imagegen/SKILL.md', 'deploy/SKILL.md'])]
        for kind, skills in cases:
            with self.subTest(kind=kind):
                self.assertEqual(self.run_report(self.home(kind.replace(' ', '-'), skills)), (2, [SKILLS_GAP]))
        with self.subTest(kind='skill folder reached through a symlink'):
            home = self.home('symlinked-folder', [])
            target = self.root / 'outside-skill'
            target.mkdir()
            (target / 'SKILL.md').write_text(SKILL)
            (home / 'skills').mkdir()
            (home / 'skills' / 'linked').symlink_to(target, target_is_directory=True)
            self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))
        with self.subTest(kind='skills itself a symlink to a folder'):
            home = self.home('symlinked-root', [])
            target = self.root / 'outside-skills'
            (target / 'deploy').mkdir(parents=True)
            (target / 'deploy' / 'SKILL.md').write_text(SKILL)
            (home / 'skills').symlink_to(target, target_is_directory=True)
            self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))
        with self.subTest(kind='a longer link to a skill folder beside its shorter route'):
            home = self.home('two-routes', ['team/deploy/SKILL.md'])
            deep = home / 'skills' / 'a' / 'b' / 'c' / 'd' / 'e'
            deep.mkdir(parents=True)
            (deep / 'link').symlink_to(home / 'skills' / 'team', target_is_directory=True)
            real = os.listdir
            with patch('os.listdir', lambda path: sorted(real(path))):
                self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))
        with self.subTest(kind='CODEX_HOME unset'):
            home = self.home('unset', ['deploy/SKILL.md'])
            self.assertEqual(self.run_report(home, env={'HOME': str(home.parent)}), (2, [SKILLS_GAP]))
        with self.subTest(kind='no config.toml'):
            code, gaps = self.run_report(self.home('no-config', ['deploy/SKILL.md'], config=False))
            self.assertEqual(code, 2)
            self.assertIn(SKILLS_GAP, gaps)
        with self.subTest(kind='markdown'):
            code, text = self.run_report(self.home('markdown', ['deploy/SKILL.md']), fmt='markdown')
            self.assertEqual(code, 2)
            self.assertIn('**Not checked: your Codex skills.**', text)
            self.assertIn('Review the skills in `skills` yourself.', text)

    def test_skills_folder_without_a_skill_gives_no_gap(self):
        seven = '/'.join(f'd{n}' for n in range(1, 8)) + '/SKILL.md'
        cases = [('no skills folder', None), ('empty skills folder', []),
                 ('only Codex system skills', ['.system/imagegen/SKILL.md', '.system/.codex-system-skills.marker']),
                 ('skill in a hidden folder', ['.private/deploy/SKILL.md']),
                 ('skill below a hidden folder', ['team/.old/deploy/SKILL.md']),
                 ('other files only', ['deploy/README.md', 'deploy/skill.md', 'notes.txt']),
                 ('seven folders down', [seven])]
        for kind, skills in cases:
            with self.subTest(kind=kind):
                home = self.home(kind.replace(' ', '-'), skills or [])
                if skills == []:
                    (home / 'skills').mkdir()
                self.assertEqual(self.run_report(home), (0, []))
        with self.subTest(kind='folder named SKILL.md'):
            home = self.home('folder-skill', [])
            (home / 'skills' / 'deploy' / 'SKILL.md').mkdir(parents=True)
            self.assertEqual(self.run_report(home), (0, []))
        with self.subTest(kind='SKILL.md is a symlink to a file'):
            home = self.home('file-link', [])
            target = self.root / 'outside-SKILL.md'
            target.write_text(SKILL)
            (home / 'skills' / 'deploy').mkdir(parents=True)
            (home / 'skills' / 'deploy' / 'SKILL.md').symlink_to(target)
            self.assertEqual(self.run_report(home), (0, []))
        with self.subTest(kind='skills is a file'):
            home = self.home('skills-file', [])
            (home / 'skills').write_text('')
            self.assertEqual(self.run_report(home), (0, []))

    def test_unlistable_skills_folder_reports_failure_without_private_details(self):
        for level in ('', '/private-group'):
            home = self.home('private-home-' + str(len(level)), ['private-group/private-skill/README.md'])
            denied_path = home / ('skills' + level)
            real = os.listdir

            def denied(path):
                if os.fspath(path) == os.fspath(denied_path):
                    raise PermissionError(13, 'private-error', str(path))
                return real(path)

            for fmt in ('json', 'markdown'):
                with self.subTest(level=level, format=fmt), patch('os.listdir', denied):
                    code, result = self.run_report(home, fmt=fmt)
                    self.assertEqual(code, 2)
                    if fmt == 'json':
                        self.assertEqual(result, [SKILLS_FAILURE])
                    else:
                        self.assertIn('**Not checked: your Codex skills.** Could not check the skills folder.', result)
                        self.assertIn('Check that you can open `skills` in your Codex folder.', result)
                    for private in (str(home), 'private-group', 'private-error'):
                        self.assertNotIn(private, result if fmt == 'markdown' else json.dumps(result))
        with self.subTest(kind='a skill found beside an unlistable folder'):
            home = self.home('found-and-denied', ['a-deploy/SKILL.md', 'private-group/private-skill/README.md'])
            denied_path = home / 'skills' / 'private-group'
            real = os.listdir
            with patch('os.listdir', lambda p: (_ for _ in ()).throw(PermissionError(13, 'x'))
                       if os.fspath(p) == os.fspath(denied_path) else real(p)):
                self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))

    def test_permission_error_on_a_linked_skills_folder_reports_failure(self):
        for where in ('skills root', 'inside skills'):
            home = self.home(where.replace(' ', '-'))
            outside = self.root / (where.replace(' ', '-') + '-outside')
            target = outside / 'private-target'
            (target / 'deploy').mkdir(parents=True)
            (target / 'deploy' / 'SKILL.md').write_text(SKILL)
            if where == 'skills root':
                (home / 'skills').symlink_to(target, target_is_directory=True)
            else:
                (home / 'skills').mkdir()
                (home / 'skills' / 'linked').symlink_to(target, target_is_directory=True)
            real_stat, real_listdir = os.stat, os.listdir
            prefix = str(outside.resolve())
            inside = lambda path: os.path.realpath(path).startswith(prefix)

            def denied_stat(path, *args, follow_symlinks=True, **kwargs):
                if follow_symlinks and inside(path):
                    raise PermissionError(13, 'private-error', str(path))
                return real_stat(path, *args, follow_symlinks=follow_symlinks, **kwargs)

            def denied_listdir(path):
                if inside(path):
                    raise PermissionError(13, 'private-error', str(path))
                return real_listdir(path)

            with self.subTest(where=where, access='readable'):
                self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))
            with self.subTest(where=where, access='denied'), patch('os.stat', denied_stat), \
                    patch('os.listdir', denied_listdir):
                code, gaps = self.run_report(home)
                self.assertEqual((code, gaps), (2, [SKILLS_FAILURE]))
                self.assertNotIn('private-target', json.dumps(gaps))
            with self.subTest(where=where, access='restored'):
                self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))

    @unittest.skipIf(os.name != 'posix' or os.geteuid() == 0, 'needs a POSIX user that file permissions apply to')
    def test_unreadable_parent_of_a_linked_skills_folder_reports_failure(self):
        home = self.home('chmod')
        parent = self.root / 'chmod-outside'
        (parent / 'target' / 'deploy').mkdir(parents=True)
        (parent / 'target' / 'deploy' / 'SKILL.md').write_text(SKILL)
        (home / 'skills').symlink_to(parent / 'target', target_is_directory=True)
        self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))
        parent.chmod(0)
        try:
            self.assertEqual(self.run_report(home), (2, [SKILLS_FAILURE]))
        finally:
            parent.chmod(0o755)
        self.assertEqual(self.run_report(home), (2, [SKILLS_GAP]))


    def test_environments_toml_gives_the_gap_and_exits_2(self):
        for kind in ['file with a program', 'empty file', 'symlink to a file', 'CODEX_HOME unset', 'no config.toml']:
            with self.subTest(kind=kind):
                name = kind.replace(' ', '-')
                home = self.home(name, config=kind != 'no config.toml')
                if kind == 'symlink to a file':
                    target = self.root / f'{name}-target.toml'
                    target.write_text(ENVIRONMENTS)
                    (home / 'environments.toml').symlink_to(target)
                else:
                    (home / 'environments.toml').write_text('' if kind == 'empty file' else ENVIRONMENTS)
                env = {'HOME': str(home.parent)} if kind == 'CODEX_HOME unset' else None
                code, gaps = self.run_report(home, env=env)
                if kind == 'no config.toml':
                    self.assertEqual(code, 2)
                    self.assertIn(ENV_GAP, gaps)
                else:
                    self.assertEqual((code, gaps), (2, [ENV_GAP]))
        with self.subTest(kind='markdown'):
            home = self.home('markdown')
            (home / 'environments.toml').write_text(ENVIRONMENTS)
            code, text = self.run_report(home, fmt='markdown')
            self.assertEqual(code, 2)
            self.assertIn('**Not checked: your `environments.toml` file.**', text)
            self.assertIn('Review the environments in `environments.toml` yourself.', text)

    def test_codex_home_without_an_environments_toml_file_gives_no_such_gap(self):
        for kind in ['no environments.toml', 'broken symlink']:
            with self.subTest(kind=kind):
                home = self.home(kind.replace(' ', '-'))
                if kind == 'broken symlink':
                    (home / 'environments.toml').symlink_to(self.root / 'missing.toml')
                self.assertEqual(self.run_report(home), (0, []))

    def test_environments_toml_that_is_not_a_file_gives_its_own_gap(self):
        for kind in ['folder', 'symlink to a folder']:
            with self.subTest(kind=kind):
                home = self.home(kind.replace(' ', '-'))
                if kind == 'folder':
                    (home / 'environments.toml').mkdir()
                else:
                    (self.root / 'env-folder').mkdir()
                    (home / 'environments.toml').symlink_to(self.root / 'env-folder', target_is_directory=True)
                self.assertEqual(self.run_report(home), (2, [ENV_NOT_FILE]))
        code, text = self.run_report(home, fmt='markdown')
        self.assertIn("Your Codex folder has an `environments.toml` that isn't a regular file", text)

    def test_unstattable_environments_toml_reports_failure_without_private_details(self):
        home = self.home('private-env-home')
        (home / 'environments.toml').write_text(ENVIRONMENTS)
        denied_path = home / 'environments.toml'
        real = os.stat

        def denied(path, *args, **kwargs):
            if os.fspath(path) == os.fspath(denied_path):
                raise PermissionError(13, 'private-error', str(path))
            return real(path, *args, **kwargs)

        for fmt in ('json', 'markdown'):
            with self.subTest(format=fmt), patch('os.stat', denied):
                code, result = self.run_report(home, fmt=fmt)
                self.assertEqual(code, 2)
                if fmt == 'json':
                    self.assertEqual(result, [ENV_FAILURE])
                else:
                    self.assertIn('**Not checked: your `environments.toml` file.** Could not check it.', result)
                    self.assertIn('Check that you can open `environments.toml` in your Codex folder.', result)
                for private in (str(home), 'private-error'):
                    self.assertNotIn(private, result if fmt == 'markdown' else json.dumps(result))


    def test_skills_and_environments_toml_each_give_their_own_gap(self):
        home = self.home('both', ['deploy/SKILL.md'])
        (home / 'environments.toml').write_text(ENVIRONMENTS)
        self.assertEqual(self.run_report(home), (2, [SKILLS_GAP, ENV_GAP]))

    def test_runs_with_file_arguments_do_not_look_for_skills_or_environments_toml(self):
        home = self.home('both-args', ['deploy/SKILL.md'])
        (home / 'environments.toml').write_text(ENVIRONMENTS)
        without = self.home('neither-args')
        config = self.config(CONFIG)
        rules = self.config('prefix_rule(pattern=["git", "status"], decision="allow")\n', 'default.rules')
        for args in [['--config', str(config)], ['--rules', str(rules)], ['--config', str(config), '--rules', str(rules)]]:
            with self.subTest(args=args[0::2]):
                result = self.run_report(home, args)
                self.assertEqual(result, self.run_report(without, args))
                self.assertNotIn(SKILLS_GAP, result[1])
                self.assertNotIn(ENV_GAP, result[1])
