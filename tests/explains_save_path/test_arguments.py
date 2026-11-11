"""Issue #19: a destination after --save is an error, not an inspected or written path."""
from contextlib import redirect_stderr, redirect_stdout
import io
import subprocess
import sys
import unittest
from unittest.mock import patch

from stay_safe.cli import main
from tests.support import ROOT

MESSAGE = "--save takes no path. It saves stay-safe-report.html in the stay-safe folder.\n"
PRIVATE = "/private/customer-token/report.html"


class SavePathTests(unittest.TestCase):
    def test_save_path_explains_the_supported_form_without_echoing_the_path(self):
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--save", PRIVATE],
                             cwd=ROOT, env={}, capture_output=True, text=True, timeout=10)
        self.assertEqual((run.returncode, run.stdout, run.stderr), (2, "", MESSAGE))

    def test_save_path_stops_before_discovery_inspection_or_save(self):
        for args in (["--save", PRIVATE], ["--config", PRIVATE, "--save", "report.html"]):
            with self.subTest(args=args), patch("stay_safe.cli.codex_home") as home, \
                    patch("stay_safe.cli.inspect") as inspect, patch("stay_safe.cli.save") as save, \
                    redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as stopped:
                    main(args)
                self.assertEqual((stopped.exception.code, out.getvalue(), err.getvalue()), (2, "", MESSAGE))
                home.assert_not_called()
                inspect.assert_not_called()
                save.assert_not_called()

    def test_other_invalid_arguments_keep_the_generic_message(self):
        for args in ([PRIVATE], ["--save", "--unknown"], ["--save", "--config"],
                     ["--save", "--format", "invalid"]):
            with self.subTest(args=args), redirect_stdout(io.StringIO()) as out, \
                    redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as stopped:
                    main(args)
                self.assertEqual((stopped.exception.code, out.getvalue(), err.getvalue()),
                                 (2, "", "Invalid arguments. Use --help.\n"))
