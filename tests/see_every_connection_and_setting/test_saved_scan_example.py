import re
import subprocess
import unittest

from tests.support import ROOT


class SavedScanExampleTests(unittest.TestCase):
    def test_published_example_pairs_the_flag_with_the_selected_snapshot(self):
        guide = (ROOT / "docs/report.md").read_text()
        section = guide.partition("## Entry IDs\n")[2].partition("\n## ")[0]
        example = re.search(r"```sh\n(.*?)\n```", section, re.S)
        self.assertIsNotNone(example, "The Entry IDs section needs the runnable saved-scan example")
        result = subprocess.run(["sh", "-e"], input=example[1], cwd=ROOT,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "team.api | prompt_injection_tool_desc | tool approval: approve\n", ""))
