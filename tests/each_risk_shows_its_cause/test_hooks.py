from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase

# Expected results come from Codex at 086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a, not from the reader.
# A `type = "command"` handler with a nonempty command becomes a command Codex can run
# (codex-rs/hooks/src/engine/discovery.rs#L650-L727). A matcher only selects events
# (codex-rs/hooks/src/engine/matcher.rs#L32-L40), and `timeout`, `async`, `statusMessage` and
# `commandWindows` are handler options (codex-rs/protocol/src/hooks.rs#L140-L188).
# Codex runs every group and every handler in it (discovery.rs#L632, #L650), so a command group counts
# wherever it sits. A group's fields other than `matcher` and `hooks` are ignored, since `MatcherGroup`
# does not deny unknown fields (protocol/src/hooks.rs#L140-L146).
# `hooks.state` holds trust and enablement (discovery.rs#L917-L923, #L1000-L1027), which stay-safe
# does not inspect, so the risk stays whatever it says. HASH matches no hook, so Codex reads an entry
# with it as modified, not trusted (discovery.rs#L1011-L1013).
# The handler's `type` picks its variant, which ignores fields it lacks, such as `command` on `prompt`
# (hooks.rs#L140-L188). Codex skips `prompt` and `agent` handlers (discovery.rs#L782-L801), an
# `mcp_tool` handler calls a tool on an MCP server (#L729-L781), and an empty command is skipped
# (#L665-L671).

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
