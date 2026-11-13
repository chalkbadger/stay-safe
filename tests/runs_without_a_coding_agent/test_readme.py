import re
import subprocess
import sys
import unittest

from tests.support import ROOT, finding_items

# The test configuration the README's sample finding is copied from (archived issue #137).
SAMPLE = ROOT / "tests" / "runs_without_a_coding_agent" / "sample.toml"
# Links in a finding name the commit that made the report; a copied sample keeps the commit of its own run.
# The README links a release tag, which outlives any one commit; the report links its commit.
COMMIT_LINK = re.compile(r"https://github\.com/chalkbadger/stay-safe/blob/(?:[0-9a-f]{40}|v[0-9]+\.[0-9]+\.[0-9]+)/")


def commands(text):
    """Every non-blank line inside fenced code blocks, in reading order."""
    found, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif fenced and line.strip():
            found.append(line.strip())
    return found


def first_quote(text):
    """The README's first block quote without its `>` marks, or an empty string when it has none."""
    quote, started = [], False
    for line in text.splitlines():
        if line.startswith(">"):
            started = True
            quote.append(line[2:] if line.startswith("> ") else line[1:])
        elif started:
            break
    return "\n".join(quote)


class ReadmeTests(unittest.TestCase):
    def test_readme_leads_with_agent_prompt_and_keeps_manual_release_commands(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        sections = re.findall(r"^## (.+)$", readme, re.MULTILINE)
        self.assertEqual(sections[0], "Start here")
        self.assertIn("Run it yourself", sections)
        intro, manual = readme.split("## Run it yourself", 1)
        first_fence = re.search(r"```(\w*)\n(.*?)```", intro, re.DOTALL)
        self.assertIsNotNone(first_fence)
        self.assertEqual(first_fence[1], "text")
        self.assertIn("https://github.com/chalkbadger/stay-safe/blob/main/docs/usage.md#first-run", first_fence[2])
        manual = manual.split("\n## ", 1)[0]
        first = commands(manual)[:3]
        self.assertRegex(first[0], r"^git clone --branch v\d+\.\d+\.\d+ https://github\.com/chalkbadger/stay-safe\.git$")
        self.assertEqual(first[1:], ["cd stay-safe", "python3 -m stay_safe"])

    def test_sample_finding_is_what_stay_safe_prints_for_its_test_configuration(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("(tests/runs_without_a_coding_agent/sample.toml)", readme)
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(SAMPLE)], cwd=ROOT, env={},
                             text=True, capture_output=True, timeout=10)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        sample = COMMIT_LINK.sub("<commit>/", first_quote(readme))
        self.assertEqual([sample], [COMMIT_LINK.sub("<commit>/", item) for item in finding_items(run.stdout)])
