from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase

# The gap messages state a 1 MiB limit; this value is fixed here, not imported.
LIMIT = 1024 * 1024
CONFIG = b'approval_policy="never"\nsandbox_mode="read-only"\n'
RULES = b'prefix_rule(pattern=["git", "status"], decision="allow")\n'


class SizeLimitTests(ConfigCase):
    def padded(self, name, content, size, padding):
        path = self.root / name
        count, rest = divmod(size - len(content), len(padding))
        path.write_bytes(content + padding * count + b' ' * rest)
        self.assertEqual(path.stat().st_size, size)
        return path

    def test_configuration_of_exactly_one_mebibyte_is_read(self):
        report = inspect([self.padded('config.toml', CONFIG, LIMIT, b' ')])
        self.assertEqual(report['inspection_gaps'], [])
        self.assertEqual([(e['name'], e['observations']) for e in report['catalog']], [
            ('approval_policy', ['never']),
            ('features.apps', CHATGPT_APPS),
            ('sandbox_mode', ['read-only']),
            ('shell_environment_policy', ['inherit: all (default)', 'ignore_default_excludes: true (default)']),
        ])
        self.assertEqual([r['rule'] for r in report['risks']], ['commands_without_prompts', 'environment_inheritance'])

    def test_configuration_one_byte_over_is_a_size_gap_without_partial_assessment(self):
        report = inspect([self.padded('config.toml', CONFIG + b'#', LIMIT + 1, 'é'.encode())])
        self.assertEqual(report['inspection_gaps'], ['config-1: Input exceeds the 1 MiB size limit.'])
        self.assertEqual((report['catalog'], report['risks']), ([], []))

    def test_rules_of_exactly_one_mebibyte_are_read(self):
        report = inspect([], rules_path=self.padded('default.rules', RULES, LIMIT, b'\n'))
        self.assertEqual(report['inspection_gaps'], [])
        self.assertEqual([(e['id'], e['observations']) for e in report['catalog']], [
            ('rules-1:prefix_rule.1', ['program: git', 'tokens: 2']),
        ])
        self.assertEqual([r['rule'] for r in report['risks']], ['saved_approval'])

    def test_rules_one_byte_over_are_a_size_gap_without_partial_assessment(self):
        report = inspect([], rules_path=self.padded('default.rules', RULES + b'#', LIMIT + 1, 'é'.encode()))
        self.assertEqual(report['inspection_gaps'], ['rules-1: Rules input exceeds the 1 MiB size limit.'])
        self.assertEqual((report['catalog'], report['risks']), ([], []))
