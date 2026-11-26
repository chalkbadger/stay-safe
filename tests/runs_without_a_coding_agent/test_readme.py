import re
import shlex
import subprocess
import sys
import unittest

from tests.support import ROOT, finding_items

SAMPLE = ROOT / "tests" / "runs_without_a_coding_agent" / "sample.toml"
COMMIT_LINK = re.compile(r"https://github\.com/chalkbadger/stay-safe/blob/(?:[0-9a-f]{40}|v[0-9]+\.[0-9]+\.[0-9]+)/")


def first_quote(text):
    quote, started = [], False
    for line in text.splitlines():
        if line.startswith(">"):
            started = True
            quote.append(line[2:] if line.startswith("> ") else line[1:])
        elif started:
            break
    return "\n".join(quote)


class ReadmeTests(unittest.TestCase):
    def test_documented_clone_commands_run_the_diagnostic(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"^```[^\n]*\n(.*?)^```[ \t]*$", readme, re.MULTILINE | re.DOTALL)
        clone = [block for block in blocks if re.search(r"^git clone ", block, re.MULTILINE)]
        self.assertEqual(len(clone), 1, "The README needs one clone-and-run example")
        commands = [line.strip() for line in clone[0].splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(len(commands), 3)
        self.assertRegex(commands[0], r"^git clone --branch v\d+\.\d+\.\d+ https://github\.com/chalkbadger/stay-safe\.git$")
        self.assertEqual(shlex.split(commands[1]), ["cd", "stay-safe"])
        invocation = shlex.split(commands[2])
        self.assertEqual(invocation, ["python3", "-m", "stay_safe"])
        run = subprocess.run([sys.executable, "-B", *invocation[1:], "--config", str(SAMPLE)],
                             cwd=ROOT, env={}, text=True, capture_output=True, timeout=10)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        self.assertIn("1 finding, 0 things not checked.", run.stdout)

    def test_readme_excerpt_and_full_example_match_the_printed_finding(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("(tests/runs_without_a_coding_agent/sample.toml)", readme)
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(SAMPLE)], cwd=ROOT, env={},
                             text=True, capture_output=True, timeout=10)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        self.assertIn("(docs/report.md#example-finding)", readme)
        guide = (ROOT / "docs" / "report.md").read_text(encoding="utf-8")
        _, heading, example = guide.partition("\n## Example finding\n")
        self.assertTrue(heading)
        full = COMMIT_LINK.sub("<commit>/", first_quote(example))
        self.assertEqual([full], [COMMIT_LINK.sub("<commit>/", item) for item in finding_items(run.stdout)])
        excerpt = COMMIT_LINK.sub("<commit>/", first_quote(readme))
        self.assertEqual(excerpt, "\n\n".join(full.split("\n\n")[:2]))
