import hashlib
import subprocess

from stay_safe.provenance import identify
from tests.anyone_can_recheck_a_report.git_support import GitCase

# Full ref names as `HEAD` could hold them. Expected acceptance comes from `git check-ref-format`, run below.
NAMES = (
    "refs/heads/main", "refs/heads/feature+review", "refs/heads/über", "refs/heads/日本", "refs/tags/v1.0",
    "refs/heads/a.b", "refs/heads/x@y", "refs/heads/@", "refs/heads/{x}", "refs/heads/a!b", "refs/heads/a.lockx",
    "refs/heads/team/topic", "refs/heads/a#b", "refs/heads/a,b", "refs/heads/a'b", "refs/heads/a\"b",
    "refs/../../x", "refs/heads/../../../x", "refs/heads/a..b", "refs/heads/.hidden", "refs/heads/x/.y",
    "refs/heads/x.lock", "refs/heads/x.lock/y", "refs/heads/x.", "refs/heads/x/", "refs/heads//x",
    "refs/heads/a b", "refs/heads/a~b", "refs/heads/a^b", "refs/heads/a:b", "refs/heads/a?b", "refs/heads/a*b",
    "refs/heads/a[b", "refs/heads/a\\b", "refs/heads/a@{b", "refs/heads/a\tb", "refs/heads/a\nb",
    "refs/heads/a\x01b", "refs/heads/a\x1fb", "refs/heads/a\x7fb",
)


class RefNameTests(GitCase):
    def git_accepts(self, name):
        run = subprocess.run(["git", "check-ref-format", name], capture_output=True, timeout=10)
        self.assertIn(run.returncode, (0, 1), run.stderr)
        return run.returncode == 0

    def test_ref_names_are_accepted_exactly_as_git_check_ref_format_decides(self):
        """A HEAD naming an existing ref reports its commit only when `git check-ref-format` accepts the name."""
        decisions = {name: self.git_accepts(name) for name in NAMES}
        self.assertTrue(decisions["refs/heads/feature+review"] and decisions["refs/heads/über"])
        self.assertEqual(set(decisions.values()), {True, False})
        for index, (name, accepted) in enumerate(decisions.items()):
            with self.subTest(name=name, git_accepts=accepted):
                root = self.root / f"case-{index}"
                gitdir = root / ".git"
                gitdir.mkdir(parents=True)
                (gitdir / "HEAD").write_text(f"ref: {name}\n", encoding="utf-8")
                commit = hashlib.sha1(name.encode()).hexdigest()
                ref = gitdir / name  # refs/../../x lands outside .git, so only the name check can refuse it.
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_text(commit + "\n", encoding="utf-8")
                self.assertEqual(identify(root)["source_revision"], commit if accepted else None)
