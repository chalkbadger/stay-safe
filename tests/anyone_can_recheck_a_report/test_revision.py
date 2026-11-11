import hashlib
import json
import shutil
from unittest.mock import patch

from stay_safe.provenance import identify
from stay_safe.report import inspect, render
from tests.support import full_scope, items, section, gap_items
from tests.anyone_can_recheck_a_report.git_support import GitCase
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text

GAP = "Revision unknown; checkout source links are withheld."

LINK_SCOPE = ("Source links point to the reported commit; whether that commit exists in the published "
              "GitHub repository is not checked.")


class RevisionTests(GitCase):
    def test_reports_show_expected_commit_hashes_and_evidence_in_both_formats(self):
        """Both report formats identify the code and link to its commit, never main."""
        checkout = self.checkout()
        revision = self.git(checkout, "rev-parse", "HEAD")
        config = self.config('approval_policy="on-request"\nsandbox_mode="read-only"\n[mcp_servers.docs]\nurl="https://example.invalid/mcp"')
        with patch("stay_safe.report.identify", return_value=identify(checkout)):
            report = inspect([config])
        # Every module of the package, found in the checkout rather than copied from SOURCE_FILES.
        modules = sorted(p.relative_to(checkout).as_posix() for p in (checkout / "stay_safe").glob("*.py"))
        self.assertIn("stay_safe/save.py", modules)
        paths = (*modules, "harnesses/codex.md", "incidents.md")
        hashes = {p: hashlib.sha256((checkout / p).read_bytes()).hexdigest() for p in paths}
        expected_tool = "sha256:" + hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        expected_rules = "sha256:" + hashes["stay_safe/rules.py"]
        encoded = json.loads(render(report, "json"))
        self.assertEqual(encoded["provenance"], {
            "tool_revision": expected_tool, "rules_revision": expected_rules,
            "source_revision": revision, "source_status": "checkout commit", "local_modifications": "not checked"})
        risk, = [r for r in encoded["risks"] if r["rule"] == "self_described_tools"]
        self.assertEqual((risk["rule"], risk["entry"], risk["configured_evidence"]),
                         ("self_described_tools", "config-1:mcp_servers.docs",
                          ["configured enabled", "HTTP; endpoint withheld", "tool approval: auto (default)"]))
        prefix = "https://github.com/chalkbadger/stay-safe/blob/" + revision + "/"
        self.assertEqual(risk["rule_source"], prefix + "stay_safe/rules.py")
        self.assertEqual(risk["interpretation_source"], prefix + "harnesses/codex.md")
        self.assertEqual(encoded["incident_links"]["I15"].split("#")[0], prefix + "incidents.md")
        markdown = render(report)
        for value in (f"Made by stay-safe `{revision[:7]}` · report format 3 · ",
                      f"[Full scope of this report]({prefix}docs/report.md#full-scope)",
                      risk["rule_source"], risk["interpretation_source"],
                      "Rule `self_described_tools` · setting `config-1:mcp_servers.docs` = "
                      "`configured enabled; HTTP; endpoint withheld; tool approval: auto (default)`"):
            self.assertIn(value, markdown)
        # The local-edit and published-commit limits are in the JSON report and the full scope in docs/report.md, which the
        # Markdown report links at its commit.
        self.assertIn(LINK_SCOPE, encoded["scope"])
        full = full_scope(checkout)
        self.assertIn("\n- " + LINK_SCOPE + "\n", "\n" + full + "\n")
        self.assertIn("\n- Local modifications to the checkout or unzipped release are not checked;", "\n" + full)
        self.assertNotIn("/blob/main/", markdown, "Markdown evidence links must stay at the report's commit, never moving main.")
        self.assertNotIn("/blob/main/", render(report, "json"), "JSON evidence links must stay at the report's commit, never moving main.")

    def test_local_edits_change_hashes_but_never_claim_a_clean_checkout(self):
        """Editing local files changes their fingerprints; the report does not certify an unmodified checkout."""
        checkout = self.checkout()
        original = identify(checkout)
        self.assertEqual(self.git(checkout, "status", "--porcelain"), "")
        for name in ("stay_safe/rules.py", "stay_safe/codex.py", "stay_safe/codex_rules.py", "incidents.md"):
            path = checkout / name
            before = path.read_bytes()
            path.write_bytes(before + b"\n# local edit\n")
            self.assertNotEqual(self.git(checkout, "status", "--porcelain"), "")
            changed = identify(checkout)
            self.assertEqual(changed["source_revision"], original["source_revision"])
            self.assertEqual(changed["local_modifications"], "not checked")
            self.assertEqual(changed["source_status"], "checkout commit")
            self.assertNotEqual(changed["tool_revision"], original["tool_revision"])
            if name == "stay_safe/rules.py":
                self.assertNotEqual(changed["rules_revision"], original["rules_revision"])
            path.write_bytes(before)
        self.assertEqual(identify(checkout), original)

    def test_clean_crlf_clone_retains_revision_and_cli_links(self):
        """A clone using Windows line endings reports its commit and source links, with its own fingerprints."""
        checkout = self.checkout()
        clone = self.root / "crlf"
        self.git(self.root, "clone", "--no-local", "--config", "core.autocrlf=true", str(checkout), str(clone))
        self.assertIn(b"\r\n", (clone / "stay_safe/rules.py").read_bytes())
        self.assertEqual(self.git(clone, "status", "--porcelain"), "")
        config = self.config('approval_policy="never"\nsandbox_mode="read-only"')
        run = self.run_cli(clone, config)
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        report = json.loads(run.stdout)
        expected = self.git(checkout, "rev-parse", "HEAD")
        self.assertEqual(report["provenance"]["source_revision"], expected)
        self.assertEqual(report["inspection_gaps"], [])
        self.assertIn("/blob/" + expected + "/", report["risks"][0]["rule_source"])
        self.assertNotEqual(report["provenance"]["tool_revision"], identify(checkout)["tool_revision"],
                            "Fingerprints hash working-tree bytes, so CRLF and LF checkouts of one commit differ.")

    def test_unknown_revision_cli_withholds_links_and_preserves_findings(self):
        """Without Git metadata, keep findings and fingerprints, report the gap, and omit source links."""
        checkout = self.checkout()
        config = self.config('approval_policy="never"\nsandbox_mode="read-only"')
        shutil.rmtree(checkout / ".git")
        for format_name in ("markdown", "json"):
            run = self.run_cli(checkout, config, format_name)
            self.assertEqual((run.returncode, run.stderr), (2, ""))
            self.assertIn("commands_without_prompts", run.stdout)
            self.assertNotIn("/blob/", run.stdout)
            if format_name == "json":
                report = json.loads(run.stdout)
                self.assertIsNone(report["provenance"]["source_revision"])
                self.assertIsNone(report["risks"][0]["rule_source"])
                self.assertIsNone(report["risks"][0]["interpretation_source"])
                self.assertEqual(report["incident_links"], {})
                self.assertIn(GAP, report["inspection_gaps"])
                self.assertRegex(report["provenance"]["tool_revision"], r"^sha256:[0-9a-f]{64}$")
            else:
                self.assertIn("\nMade by stay-safe (commit unknown) · report format 3 · ", run.stdout)
                self.assertIn("\nFull scope of this report: see the Full scope section of stay-safe's docs/report.md.\n", run.stdout)
                self.assertIn(gap_text(GAP), gap_items(run.stdout))
                self.assertEqual(section(run.stdout, "Sources"), "Source links are left out because stay-safe couldn't "
                                 "tell which commit it's running from.")
