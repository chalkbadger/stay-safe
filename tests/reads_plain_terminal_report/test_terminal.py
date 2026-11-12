import errno
import io
import json
import os
import pty
import subprocess
import sys
from unittest.mock import patch

from stay_safe import cli
from stay_safe.report import inspect, render
from tests.support import ConfigCase, ROOT, SEEDED, SEEDS, INCOMPLETE

HINT = "Use --save to save a formatted HTML report.\n"


class TerminalTests(ConfigCase):
    def terminal(self, *args):
        master, slave = pty.openpty()
        try:
            # Capture stderr separately: only stdout determines the display.
            child = subprocess.Popen([sys.executable, '-B', '-m', 'stay_safe', *args], cwd=ROOT,
                                     stdout=slave, stderr=subprocess.PIPE)
            os.close(slave)
            slave = None
            # Drain the terminal concurrently with the child to avoid filling its buffer.
            import threading
            output = []
            def read():
                while True:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            return
                        raise
                    if not chunk:
                        return
                    output.append(chunk)
            reader = threading.Thread(target=read)
            reader.start()
            try:
                _, stderr = child.communicate(timeout=10)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
                reader.join(timeout=10)
            self.assertFalse(reader.is_alive())
            return child.returncode, b''.join(output).decode().replace('\r\n', '\n'), stderr.decode()
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)

    def test_terminal_default_is_plain_with_links_and_private_values_withheld(self):
        path = self.config(SEEDED)
        status, output, errors = self.terminal('--config', str(path))
        self.assertEqual(status, 0)
        self.assertEqual(errors, HINT)
        self.assertTrue(output.startswith('Codex configuration diagnostic\n\n'))
        headings = ['Findings', 'Not checked', 'Your setup', 'Sources', "What this report can't see"]
        positions = [output.index('\n' + heading + '\n') for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('What to do:', output)
        self.assertIn('Approval: never', output)
        self.assertIn('MCP server local: on', output)
        self.assertIn('https://github.com/chalkbadger/stay-safe/', output)
        for marker in ('## ', '**', '`', ']('):
            self.assertNotIn(marker, output)
        for secret in SEEDS.values():
            self.assertNotIn(secret, output + errors)

    def test_explicit_formats_and_redirected_output_stay_unchanged(self):
        path = self.config('approval_policy = "never"\nsandbox_mode = "read-only"\n')
        for format_name in ('markdown', 'json'):
            with self.subTest(format=format_name):
                status, terminal, errors = self.terminal('--config', str(path), '--format', format_name)
                piped = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--config', str(path),
                                        '--format', format_name], cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertEqual((status, errors), (0, ''))
                self.assertEqual(terminal, piped.stdout)
                if format_name == 'markdown':
                    self.assertTrue(terminal.startswith('# Codex configuration diagnostic\n'))
                else:
                    self.assertEqual(json.loads(terminal)['inspection_gaps'], [])
        default = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--config', str(path)],
                                 cwd=ROOT, capture_output=True, text=True, timeout=10)
        explicit = subprocess.run([sys.executable, '-B', '-m', 'stay_safe', '--config', str(path), '--format', 'markdown'],
                                  cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual((default.returncode, default.stdout, default.stderr),
                         (explicit.returncode, explicit.stdout, ''))

    def test_literal_names_survive_in_findings_advice_setup_and_evidence(self):
        name = 'team_wiki.v2-qa'
        path = self.config('approval_policy = "never"\nsandbox_mode = "read-only"\n'
                           + '[mcp_servers.' + json.dumps(name) + ']\ncommand = "private-command"\n')
        _, output, _ = self.terminal('--config', str(path))
        self.assertIn('Your ' + name + ' MCP server', output)
        self.assertIn('MCP server ' + name + ':', output)
        self.assertIn('Change it: under [mcp_servers.' + json.dumps(name) + ']', output)
        self.assertIn('Rule configured_program · setting config-1:mcp_servers.' + json.dumps(name) + ' = configured enabled;', output)
        self.assertIn('Sandbox: read-only', output)
        self.assertNotIn('private-command', output)

    def test_save_keeps_html_and_suppresses_hint_even_when_save_fails(self):
        path = self.config('approval_policy = "never"\nsandbox_mode = "read-only"\n')
        expected = render(inspect([path]), 'html')
        for saved in (self.root / 'report.html', None):
            with self.subTest(saved=saved), patch('stay_safe.cli.save', return_value=saved) as save:
                out, err = io.StringIO(), io.StringIO()
                with patch.object(out, 'isatty', return_value=True), patch('sys.stdout', out), patch('sys.stderr', err):
                    self.assertEqual(cli.main(['--config', str(path), '--save']), 0)
                save.assert_called_once_with(expected)
                self.assertTrue(out.getvalue().startswith('Codex configuration diagnostic\n'))
                self.assertNotIn(HINT, out.getvalue() + err.getvalue())
                if saved:
                    self.assertIn('Saved the formatted report.', out.getvalue())
                    self.assertEqual(err.getvalue(), '')
                else:
                    self.assertEqual(err.getvalue(), cli.NOT_SAVED)

    def test_incomplete_exit_and_hint_follow_the_flushed_report(self):
        path = self.config('approval_policy = "never"\n')
        events = []
        class Output(io.StringIO):
            def isatty(self):
                return True
            def flush(self):
                events.append('flushed')
        class Error(io.StringIO):
            def write(self, value):
                events.append(value)
                return super().write(value)
        out, err = Output(), Error()
        with patch('sys.stdout', out), patch('sys.stderr', err):
            self.assertEqual(cli.main(['--config', str(path)]), 2)
        self.assertIn('Not checked: your sandbox setting.', out.getvalue())
        self.assertEqual(err.getvalue(), HINT + INCOMPLETE)
        self.assertLess(events.index('flushed'), events.index(HINT))
