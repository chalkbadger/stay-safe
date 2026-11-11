from stay_safe.provenance import identify
from tests.anyone_can_recheck_a_report.git_support import GitCase


class LayoutTests(GitCase):
    def repository(self):
        repo = self.root / "repo"
        repo.mkdir()
        self.git(repo, "init", "-b", "main")
        self.commit(repo, "main start")
        return repo

    def commit(self, root, message):
        self.git(root, "commit", "--allow-empty", "-m", message)
        return self.git(root, "rev-parse", "HEAD")

    def assert_reports_git_head(self, root, seen):
        """The reported commit is what `git rev-parse HEAD` reports, and differs from every earlier layout's."""
        expected = self.git(root, "rev-parse", "HEAD")
        self.assertNotIn(expected, seen)
        seen.append(expected)
        self.assertEqual(identify(root)["source_revision"], expected)

    def test_each_layout_reports_its_own_commit_as_git_does(self):
        """Packed-only, loose, detached and worktree heads, each on a distinct commit, match `git rev-parse HEAD`."""
        repo, seen = self.repository(), []
        packed_main = self.git(repo, "rev-parse", "HEAD")

        self.git(repo, "checkout", "-b", "packed")
        self.commit(repo, "packed")
        self.git(repo, "pack-refs", "--all", "--prune")
        self.assertFalse((repo / ".git/refs/heads/packed").exists())
        self.assert_reports_git_head(repo, seen)

        self.git(repo, "checkout", "main")
        self.commit(repo, "loose main")
        self.assertIn(packed_main + " refs/heads/main", (repo / ".git/packed-refs").read_text())
        self.assertTrue((repo / ".git/refs/heads/main").is_file())
        self.assert_reports_git_head(repo, seen)

        self.git(repo, "checkout", "--detach")
        self.commit(repo, "detached")
        self.assertNotIn("ref:", (repo / ".git/HEAD").read_text())
        self.assert_reports_git_head(repo, seen)

        worktree = self.root / "worktree"
        self.git(repo, "worktree", "add", "-b", "colleague", str(worktree))
        self.commit(worktree, "worktree loose")
        self.assertTrue((worktree / ".git").is_file())
        self.assertTrue((repo / ".git/refs/heads/colleague").is_file())
        self.assert_reports_git_head(worktree, seen)

        self.commit(worktree, "worktree packed")
        self.git(worktree, "pack-refs", "--all", "--prune")
        self.assertFalse((repo / ".git/refs/heads/colleague").exists())
        self.assert_reports_git_head(worktree, seen)
        self.assertEqual(identify(repo)["source_revision"], self.git(repo, "rev-parse", "HEAD"))
