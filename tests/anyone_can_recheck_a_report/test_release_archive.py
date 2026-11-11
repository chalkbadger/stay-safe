"""Runs from an unzipped release archive (archived issue #132).

The archives are built with `git archive`, which applies the `export-subst` attribute and replaces
`$Format:%H$` with the archived commit (git 2.43.0: https://git-scm.com/docs/gitattributes/2.43.0#_export_subst).
Whether GitHub's zips do the same is a recorded run in the PR, not something these tests show. The expected
commit is read from Git, never from stay-safe.
"""
import json
import subprocess
import sys
import zipfile

from stay_safe.provenance import identify
from tests.support import section
from tests.anyone_can_recheck_a_report.git_support import GitCase

REVISION_FILE = "stay_safe/release.txt"
SECRET = "private-secret-value"


class ReleaseArchiveTests(GitCase):
    def archive(self):
        """Commit this checkout's files, zip that commit with `git archive` and unzip it; return (copy, commit, repo)."""
        checkout = self.checkout()
        commit = self.git(checkout, "rev-parse", "HEAD")
        zipped = self.root / "release.zip"
        self.git(checkout, "archive", "--format=zip", "--prefix=stay-safe-test/", "-o", str(zipped), "HEAD")
        with zipfile.ZipFile(zipped) as archive:
            archive.extractall(self.root / "unzipped")
        copy = self.root / "unzipped" / "stay-safe-test"
        self.assertFalse((copy / ".git").exists())
        return copy, commit, checkout

    def run_default(self, copy, format_name):
        """Run `python3 -m stay_safe` in the copy with a synthetic home whose Codex config sets both settings."""
        self.require_no_system_folder()
        home = self.root / "home"
        (home / ".codex").mkdir(parents=True, exist_ok=True)
        (home / ".codex" / "config.toml").write_text('approval_policy="never"\nsandbox_mode="read-only"\n',
                                                     encoding="utf-8")
        return subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--format", format_name], cwd=copy,
                              env={"HOME": str(home), "CODEX_HOME": str(home / ".codex")},
                              text=True, capture_output=True, timeout=10)

    def test_unzipped_archive_reports_archived_commit_and_links_in_both_formats(self):
        """A run from a `git archive` zip names the archived commit and links rules, meanings and incidents at it."""
        copy, commit, _ = self.archive()
        prefix = "https://github.com/chalkbadger/stay-safe/blob/" + commit + "/"
        run = self.run_default(copy, "json")
        report = json.loads(run.stdout)
        self.assertEqual((report["provenance"]["source_revision"], report["provenance"]["source_status"],
                          report["provenance"]["local_modifications"]),
                         (commit, "release archive commit", "not checked"))
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        self.assertEqual(report["inspection_gaps"], [])
        risk, = [r for r in report["risks"] if r["rule"] == "commands_without_prompts"]
        self.assertEqual((risk["rule_source"], risk["interpretation_source"]),
                         (prefix + "stay_safe/rules.py", prefix + "harnesses/codex.md"))
        self.assertTrue(report["incident_links"])
        for identifier, link in report["incident_links"].items():
            self.assertTrue(link.startswith(prefix + "incidents.md#" + identifier.lower() + "-"), link)
        run = self.run_default(copy, "markdown")
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        self.assertIn(f"\nMade by stay-safe `{commit[:7]}` (release archive) · report format 3 · ", run.stdout)
        self.assertIn(f"\n[Full scope of this report]({prefix}docs/report.md#full-scope)\n", run.stdout)
        sources = section(run.stdout, "Sources")
        self.assertIn(f"({prefix}stay_safe/rules.py)", sources)
        self.assertIn(f"({prefix}harnesses/codex.md)", sources)
        for link in report["incident_links"].values():
            self.assertIn(f"]({link})", run.stdout)
        self.assertTrue(run.stdout.splitlines()[2].endswith(", 0 things not checked."), run.stdout.splitlines()[2])
        self.assertNotIn("/blob/main/", run.stdout)

    def test_placeholder_or_malformed_revision_file_gives_revision_unknown(self):
        """A copy whose revision file still holds the committed placeholder, or anything but one full commit hash,
        is unknown, and the value is never shown."""
        copy, commit, _ = self.archive()
        cases = {
            # The placeholder `git archive` substitutes (https://git-scm.com/docs/gitattributes/2.43.0#_export_subst).
            "placeholder": "$Format:%H$\n",
            "absent": None,
            "empty": "",
            "non-hex": SECRET.ljust(40, "x") + "\n",
            "39 hex": commit[:39] + "\n",
            "41 hex": commit + "a\n",
            "uppercase hex": commit.upper() + "\n",
            "all zeros": "0" * 40 + "\n",
            "hex then text": commit + " " + SECRET + "\n",
            "two lines": commit + "\n" + SECRET + "\n",
            "invalid UTF-8": b"\xff" + commit.encode(),
        }
        for label, value in cases.items():
            with self.subTest(label):
                path = copy / REVISION_FILE
                path.unlink(missing_ok=True)
                if isinstance(value, bytes):
                    path.write_bytes(value)
                elif value is not None:
                    path.write_text(value, encoding="utf-8")
                result = identify(copy)
                self.assertEqual((result["source_revision"], result["source_status"]), (None, "revision unknown"))
                self.assertNotIn(SECRET, json.dumps(result))

    def test_git_checkout_uses_git_and_ignores_revision_file(self):
        """In a Git checkout, a `.git` folder or a `git worktree` whose `.git` is a file, the commit comes from Git;
        a commit written into the revision file is not used, even when Git's metadata is unreadable."""
        checkout = self.checkout()
        commit = self.git(checkout, "rev-parse", "HEAD")
        self.git(checkout, "commit", "--allow-empty", "-m", "Second commit")
        other = self.git(checkout, "rev-parse", "HEAD")
        self.git(checkout, "reset", "-q", "--hard", commit)
        self.assertNotEqual(other, commit)
        worktree = self.root / "worktree"
        self.git(checkout, "worktree", "add", "-q", "-b", "linked", str(worktree), commit)
        self.assertTrue((worktree / ".git").is_file())
        for label, root in (("git folder", checkout), ("worktree", worktree)):
            with self.subTest(label):
                (root / REVISION_FILE).write_text(other + "\n", encoding="utf-8")
                result = identify(root)
                self.assertEqual((result["source_revision"], result["source_status"], result["local_modifications"]),
                                 (commit, "checkout commit", "not checked"))
        # Unreadable metadata: a worktree whose .git file points to a missing folder, and a folder without HEAD.
        (worktree / ".git").write_text("gitdir: " + str(self.root / "missing-gitdir") + "\n", encoding="utf-8")
        (checkout / ".git" / "HEAD").unlink()
        for label, root in (("worktree with a broken pointer", worktree), ("git folder without HEAD", checkout)):
            with self.subTest(label):
                result = identify(root)
                self.assertEqual((result["source_revision"], result["source_status"]), (None, "revision unknown"))
