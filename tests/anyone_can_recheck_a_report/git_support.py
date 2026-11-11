"""Shared Git fixtures for the tests that a report can be rechecked. Git metadata: https://git-scm.com/docs/gitrepository-layout"""
import shutil
import subprocess
import sys

from tests.support import ConfigCase, ROOT


class GitCase(ConfigCase):
    def git(self, root, *args):
        return subprocess.check_output(["git", "-c", "user.name=Fixture", "-c",
                                        "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", *args],
                                       cwd=root, text=True, stderr=subprocess.PIPE, timeout=10).strip()

    def checkout(self, name="checkout"):
        """Copy this checkout's files into a new repository with one commit."""
        target = self.root / name
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.git(target, "init", "-b", "main")
        self.git(target, "add", ".")
        self.git(target, "commit", "-m", "Fixture baseline")
        return target

    def run_cli(self, checkout, config, format_name="json"):
        return subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(config), "--format", format_name],
                              cwd=checkout, text=True, capture_output=True, timeout=10)
