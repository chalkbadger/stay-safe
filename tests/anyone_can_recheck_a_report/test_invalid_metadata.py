import json

from stay_safe.provenance import identify
from tests.support import items, section, gap_items
from tests.anyone_can_recheck_a_report.git_support import GitCase
from tests.see_every_connection_and_setting.test_plain_gaps import gap_text

GAP = "Revision unknown; checkout source links are withheld."

SECRET = "private-secret-value"
ZERO = "0" * 40


class InvalidMetadataTests(GitCase):
    def repository(self, name):
        """A one-commit repository whose `main` is packed only, with a commit any wrong reading would return."""
        repo = self.root / name
        repo.mkdir()
        self.git(repo, "init", "-b", "main")
        self.git(repo, "commit", "--allow-empty", "-m", "baseline")
        commit = self.git(repo, "rev-parse", "HEAD")
        self.git(repo, "pack-refs", "--all", "--prune")
        return repo, commit

    def test_rejected_names_and_bad_values_report_revision_unknown_without_contents(self):
        """Rejected names, non-hex and all-zero values in HEAD, loose refs or packed-refs, or no HEAD, give no commit and no contents."""
        cases = {
            "HEAD all zeros": {"HEAD": ZERO},
            "HEAD non-hex": {"HEAD": SECRET},
            "HEAD short hex": {"HEAD": "abc123"},
            "HEAD 41 hex": {"HEAD": "a" * 41},
            "HEAD traversal": {"HEAD": f"ref: refs/../../{SECRET}"},
            "HEAD rejected name": {"HEAD": f"ref: refs/heads/{SECRET}..x"},
            "HEAD outside refs": {"HEAD": f"ref: {SECRET}"},
            "HEAD relative path": {"HEAD": f"ref: ../../{SECRET}"},
            "HEAD absent": {"HEAD": None},
            "HEAD missing ref": {"HEAD": "ref: refs/heads/missing"},
            # Git writes HEAD as "ref: %s\n" and trims only ASCII whitespace (sane_ctype) when reading it, so it
            # keeps \x1f, and check-ref-format rejects that name. Git v2.43.0 refs/files-backend.c lines 456 and 1931,
            # strbuf.c strbuf_rtrim, ctype.c: https://github.com/git/git/blob/564d0252ca632e0264ed670534a51d18a689ef5d/refs/files-backend.c#L456
            "HEAD rejected trailing \\x1f": {"HEAD": "ref: refs/heads/a\x1f", "refs/heads/a": "{commit}"},
            "loose all zeros": {"refs/heads/main": ZERO},
            "loose non-hex": {"refs/heads/main": SECRET},
            "loose hex then text": {"refs/heads/main": "{commit} " + SECRET},
            "packed all zeros": {"packed-refs": f"{ZERO} refs/heads/main\n"},
            "packed non-hex": {"packed-refs": f"{SECRET} refs/heads/main\n"},
            "packed malformed": {"packed-refs": f"# pack-refs with: peeled\n{SECRET} refs/heads/main {SECRET}\n"
                                                f"{SECRET}\n"},
        }
        for index, (label, files) in enumerate(cases.items()):
            with self.subTest(label):
                repo, commit = self.repository(f"case-{index}")
                for name, value in files.items():
                    path = repo / ".git" / name
                    if value is None:
                        path.unlink()
                        continue
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value.format(commit=commit) + "\n", encoding="utf-8")
                result = identify(repo)
                self.assertEqual((result["source_revision"], result["source_status"]), (None, "revision unknown"))
                self.assertNotIn(SECRET, json.dumps(result))

    def test_seeded_secret_in_packed_refs_gives_status_2_without_showing_it(self):
        """A malformed packed-refs line holding a secret, beside an all-zero entry, gives revision unknown and status 2."""
        checkout = self.checkout()
        self.git(checkout, "pack-refs", "--all", "--prune")
        (checkout / ".git/packed-refs").write_text(
            f"# pack-refs with: peeled fully-peeled sorted\n{SECRET} refs/heads/main\n{ZERO} refs/heads/main\n",
            encoding="utf-8")
        config = self.config('approval_policy="never"\nsandbox_mode="read-only"')
        for format_name in ("markdown", "json"):
            with self.subTest(format_name):
                run = self.run_cli(checkout, config, format_name)
                self.assertEqual((run.returncode, run.stderr), (2, ""))
                self.assertNotIn(SECRET, run.stdout)
                self.assertNotIn(ZERO, run.stdout)
                self.assertNotIn("/blob/", run.stdout)
                self.assertIn("commands_without_prompts", run.stdout)
                if format_name == "json":
                    provenance = json.loads(run.stdout)["provenance"]
                    self.assertIn(GAP, json.loads(run.stdout)["inspection_gaps"])
                    self.assertEqual((provenance["source_revision"], provenance["source_status"]),
                                     (None, "revision unknown"))
                else:
                    self.assertIn("\nMade by stay-safe (commit unknown) · report format 3 · ", run.stdout)
                    self.assertIn(gap_text(GAP), gap_items(run.stdout))
