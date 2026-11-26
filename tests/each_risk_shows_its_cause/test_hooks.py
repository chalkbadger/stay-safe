from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase


BASE = 'approval_policy="on-request"\nsandbox_mode="read-only"\n'
CATALOG = {'approval_policy': ['on-request'], 'sandbox_mode': ['read-only'],
           'shell_environment_policy': ['inherit: all (default)', 'ignore_default_excludes: true (default)'],
           'hooks.PreToolUse': ['contents withheld'],
           'features.apps': CHATGPT_APPS}
GAPS = ['config-1: Hook execution policy is outside reader coverage.']
PROGRAM = ('configured_program', 'config-1:hooks.PreToolUse')
ENVIRONMENT = ('environment_inheritance', 'config-1:shell_environment_policy')
STATE = '[hooks.state."/home/user/private/config.toml:pre_tool_use:0:0"]\n'
HASH = 'sha256:' + '0' * 64
COMMAND = '{type="command", command="private-check"}'


class HookProgramTests(ConfigCase):
    def assert_hook(self, text, risks):
        report = inspect([self.config(BASE + text)])
        self.assertEqual([(r['rule'], r['entry']) for r in report['risks']], risks + [ENVIRONMENT])
        self.assertEqual(report['inspection_gaps'], GAPS)
        self.assertEqual({e['name']: e['observations'] for e in report['catalog']}, CATALOG)
        self.assertNotIn('private', str(report))

    def test_command_handler_reports_program_whatever_matcher_options_or_state(self):
        for text in [
            f'[[hooks.PreToolUse]]\nhooks=[{COMMAND}]\n',
            f'[[hooks.PreToolUse]]\nmatcher="shell"\nhooks=[{COMMAND}]\n',
            '[[hooks.PreToolUse]]\nhooks=[{type="command", command="private-check", timeout=30}]\n',
            '[[hooks.PreToolUse]]\nmatcher="shell"\nhooks=[{type="command", command="private-check", timeout=30, '
            'async=true, statusMessage="private-status", commandWindows="private-windows"}]\n',
            f'[[hooks.PreToolUse]]\nhooks=[{{type="prompt"}}, {COMMAND}]\n',
            f'[[hooks.PreToolUse]]\nhooks=[{{type="agent"}}]\n[[hooks.PreToolUse]]\nhooks=[{COMMAND}]\n',
            f'[[hooks.PreToolUse]]\nhooks=[{COMMAND}]\n[[hooks.PreToolUse]]\nhooks=[{{type="agent"}}]\n',
        ]:
            with self.subTest(text=text):
                self.assert_hook(text, [PROGRAM])

    def test_unknown_group_field_gives_no_gap_of_its_own(self):
        self.assert_hook(f'[[hooks.PreToolUse]]\nmatcher="shell"\nunknown_field="private-value"\nhooks=[{COMMAND}]\n',
                         [PROGRAM])

    def test_hooks_state_with_a_modified_hash_or_enablement_keeps_the_program(self):
        hook = f'[[hooks.PreToolUse]]\nmatcher="shell"\nhooks=[{COMMAND}]\n'
        for state in [f'trusted_hash="{HASH}"\n', 'enabled=true\n', f'enabled=false\ntrusted_hash="{HASH}"\n',
                      'enabled=false\n']:
            with self.subTest(state=state):
                self.assert_hook(hook + STATE + state, [PROGRAM])

    def test_prompt_agent_mcp_tool_or_empty_command_handlers_report_no_program(self):
        for handlers in [
            '{type="prompt"}',
            '{type="agent"}',
            '{type="mcp_tool", server="private-server", tool="private-tool"}',
            '{type="prompt", command="private-check"}',
            '{type="mcp_tool", server="private-server", tool="private-tool", command="private-check"}',
            '{type="command", command=""}',
            '{type="command", command="  "}',
            '{type="prompt"}, {type="agent"}, {type="mcp_tool", server="private-server", tool="private-tool"}, '
            '{type="command", command=""}',
        ]:
            with self.subTest(handlers=handlers):
                self.assert_hook(f'[[hooks.PreToolUse]]\nmatcher="shell"\nhooks=[{handlers}]\n', [])

    def test_windows_command_alone_reports_program(self):
        for handler in [
            '{type="command", command="", commandWindows="private-windows"}',
            '{type="command", command="  ", command_windows="private-windows"}',
            '{type="command", command="private-check", commandWindows=""}',
        ]:
            with self.subTest(handler=handler):
                self.assert_hook(f'[[hooks.PreToolUse]]\nhooks=[{handler}]\n', [PROGRAM])

    def test_empty_or_non_string_windows_command_reports_no_program(self):
        for handler in [
            '{type="command", command="", commandWindows=""}',
            '{type="command", command="", command_windows="  "}',
            '{type="command", command="", commandWindows=1}',
            '{type="command", command="", command_windows=["private-windows"]}',
            '{type="command", commandWindows="private-windows"}',
            '{type="prompt", commandWindows="private-windows"}',
        ]:
            with self.subTest(handler=handler):
                self.assert_hook(f'[[hooks.PreToolUse]]\nhooks=[{handler}]\n', [])
