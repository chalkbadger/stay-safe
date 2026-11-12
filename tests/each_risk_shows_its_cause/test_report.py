import json
import re
import shutil
import subprocess
import sys

from tests.see_every_connection_and_setting.test_config import FIXTURE
from tests.findings_say_what_to_do.test_what_to_do import commands
from tests.support import INCOMPLETE
from tests.support import finding_items, CHATGPT_APPS, ConfigCase, ROOT, items, section, gap_items
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text
from stay_safe.provenance import identify


CITATION_GAP = "Committed incident citations are incomplete; source links are unavailable."
# The Markdown lead for this rule (archived issue #105); tests/findings_say_what_to_do/test_plain_findings.py covers every rule.
RISK = ("**With these settings, Codex runs commands without asking you.** It won't ask before any command it's allowed to "
        "run, so injected or mistaken instructions could make it run code you didn't want.\n\n"
        "*How it has gone wrong:* Agents running commands without approval have run a delete command aimed at a home "
        "directory and wiped a drive. Another user reported an automatic driver update while getting help with GPU performance. {} (reported, not verified).\n\n"
        + commands("read-only").replace("{", "{{").replace("}", "}}") + "\n\n"
        "*Rule `commands_without_prompts` · setting `config-1:approval_policy` = `never`*")
# The catalog of that configuration in Markdown's "Your setup" (archived issue #105, reading check).
SETUP = [
    "**Config file `config-1`**: the first file you passed with `--config`. Codex reads settings from config files "
    "like this.",
    "- Approval: `never` (doesn't ask before commands)",
    "- ChatGPT Apps connection: an MCP connection to ChatGPT, only when Codex is signed in with ChatGPT (stay-safe "
    "doesn't check sign-in), `features.apps = false` turns it off",
    "- Sandbox: `read-only` (commands can't write files)",
    "- Environment for commands: none passed on (you set this), `ignore_default_excludes` true (default)",
]
REVISION = "a" * 40
SOURCE = "https://github.com/chalkbadger/stay-safe/blob/" + REVISION + "/"


class RiskOutputTests(ConfigCase):
    def checkout(self):
        """A disposable copy of the package whose incidents.md each test may break."""
        checkout = self.root / "checkout"
        shutil.copytree(ROOT / "stay_safe", checkout / "stay_safe",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "harnesses", checkout / "harnesses")
        (checkout / ".git").mkdir()
        (checkout / ".git/HEAD").write_text(REVISION, encoding="utf-8")
        return checkout

    def test_cli_reports_missing_incident_citation_and_preserves_safe_data(self):
        checkout = self.checkout()
        revision = REVISION
        source = SOURCE
        # Only this disposable copy has an intentionally incomplete incident catalog.
        (checkout / "incidents.md").write_text(
            "# Reported incidents\n\nEach entry is reported, not verified.\n\n## I2. Synthetic retained incident\n",
            encoding="utf-8")
        path = self.config('approval_policy="never"\nsandbox_mode="read-only"\nshell_environment_policy={inherit="none"}')
        before = path.read_bytes()
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(path)],
                             cwd=checkout, text=True, capture_output=True, timeout=10)
        self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
        self.assertEqual(run.stdout.splitlines()[2], "1 finding, 1 thing not checked.")
        self.assertEqual(section(run.stdout, "Your setup").splitlines(), SETUP)
        self.assertEqual(finding_items(run.stdout), [
            RISK.format(f"[I2]({source}incidents.md#i2-synthetic-retained-incident), I3, I24")])
        self.assertIn(f"]({source}stay_safe/rules.py)", section(run.stdout, "Sources"))
        self.assertEqual(gap_items(run.stdout), [gap_text(CITATION_GAP)])
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn(str(path), run.stdout)

    def test_unreadable_or_invalid_utf8_incidents_keep_findings_and_add_the_citation_gap(self):
        config = self.config('approval_policy="never"\nsandbox_mode="read-only"\nshell_environment_policy={inherit="none"}')
        catalog = [("config-1:approval_policy", "permission", ["never"]), ("config-1:features.apps", "MCP server", CHATGPT_APPS),
                   ("config-1:sandbox_mode", "permission", ["read-only"]),
                   ("config-1:shell_environment_policy", "permission", ["inherit: none (explicit)", "ignore_default_excludes: true (default)"])]
        for name, gaps in [("unreadable", [CITATION_GAP, "Incomplete fingerprint: incidents.md could not be read."]),
                           ("invalid-utf8", [CITATION_GAP])]:
            checkout = self.checkout()
            if name == "unreadable":
                (checkout / "incidents.md").mkdir()  # reading a directory raises OSError on every platform
            else:
                (checkout / "incidents.md").write_bytes(b"# Reported incidents\n\n## I2. \xff\n")
            for format_name in ("markdown", "json"):
                with self.subTest(incidents=name, format=format_name):
                    run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(config),
                                          "--format", format_name], cwd=checkout, text=True,
                                         capture_output=True, timeout=10)
                    self.assertEqual((run.returncode, run.stderr), (2, INCOMPLETE))
                    if format_name == "json":
                        report = json.loads(run.stdout)
                        self.assertEqual([(e["id"], e["kind"], e["observations"]) for e in report["catalog"]], catalog)
                        self.assertEqual([(r["rule"], r["entry"], r["incidents"], r["rule_source"]) for r in report["risks"]], [
                            ("commands_without_prompts", "config-1:approval_policy", ["I2", "I3", "I24"], SOURCE + "stay_safe/rules.py")])
                        self.assertEqual((report["incident_links"], report["inspection_gaps"]), ({}, gaps))
                    else:
                        self.assertEqual(section(run.stdout, "Your setup").splitlines(), SETUP)
                        self.assertEqual(finding_items(run.stdout), [
                            RISK.format("I2, I3, I24")])
                        self.assertEqual(gap_items(run.stdout), [gap_text(gap) for gap in gaps])
            shutil.rmtree(checkout)

    def test_cli_risks_have_expected_entries_incidents_and_status_in_both_formats(self):
        expected = [
            ("commands_without_prompts", "config-1:approval_policy", ["I2", "I3", "I24"]),
            ("self_described_tools", "config-1:apps.calendar", ["I15", "I21"]),
            ("configured_program", "config-1:mcp_servers.git", ["I13", "I14", "I19"]),
            ("configured_program", "config-1:notify", ["I13", "I14", "I19"]),
            ("environment_inheritance", "config-1:shell_environment_policy", ["I23"]),
        ]
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                run = subprocess.run([sys.executable, "-m", "stay_safe", "--config", str(FIXTURE),
                                      "--format", format_name], cwd=ROOT, text=True,
                                     capture_output=True, timeout=10)
                self.assertEqual((run.returncode, run.stderr), (0, ""))
                if format_name == "json":
                    report = json.loads(run.stdout)
                    actual = [(r["rule"], r["entry"], r["incidents"]) for r in report["risks"]]
                    self.assertEqual(report["incident_status"], "reported, not verified")
                    self.assertEqual(set(report["incident_links"]), {"I2", "I3", "I13", "I14", "I15", "I19", "I21", "I23", "I24"})
                    explanation = next(r["explanation"] for r in report["risks"] if r["rule"] == "self_described_tools")
                    self.assertIn("Documented in source, not yet observed", explanation)
                    self.assertIn("server-declared hints", explanation)
                    self.assertIn("auto and writes use server-declared hints for tool approval", explanation)
                    for identifier, url in report["incident_links"].items():
                        self.assertTrue(url.startswith("https://github.com/chalkbadger/stay-safe/blob/" + identify()["source_revision"] + "/incidents.md#" + identifier.lower() + "-"))
                else:
                    actual = []
                    for paragraph in finding_items(run.stdout):
                        lines = paragraph.split("\n\n")
                        trace = re.fullmatch(r"\*Rule `(\w+)` · setting `(.+?)` = .+\*", lines[-1])
                        incidents = re.fullmatch(r"\*How it has gone wrong:\* .+? (\[I\d.+) \(reported, not verified\)\.", lines[1])
                        self.assertIsNotNone(trace, lines[-1])
                        self.assertIsNotNone(incidents, lines[1])
                        rule, entry = trace.groups()
                        citations = incidents[1]
                        self.assertEqual("Based on Codex's source code, not yet seen in a live run." in lines[0],
                                         rule == "self_described_tools")
                        actual.append((rule, entry, re.findall(r"\[(I\d+)\]\(https://github.com/chalkbadger/stay-safe/blob/[0-9a-f]{40}/incidents.md#[^)]+\)", citations)))
                self.assertEqual(actual, expected)
