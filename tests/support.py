import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# The file name archived issue #106 fixes for the saved report.
REPORT = "stay-safe-report.html"
# A commit the copied checkout's .git/HEAD names, so its report has source and incident links.
COPY_REVISION = "0123456789abcdef0123456789abcdef01234567"
# Saved approval words that do not look like names: key-like words, an email, a path, a flag,
# words with a space, newline or `|`, an 81-character word, `..` and an empty word.
HARD_WORDS = ['sk-private-secret', 'ghp_private-secret', 'github_pat_private-secret', 'alice@example.com',
              '/private/path', '--private-flag', 'private value', 'private\nvalue', 'private|value', 'x' * 81, '..', '']
# The program names a saved approval's first word may show, copied from archived issue #89.
PROGRAMS = ('git gh npm npx pnpm yarn node python python3 pip pip3 uv cargo go make docker kubectl curl wget ssh '
            'bash sh rm mv cp chmod').split()
# First words close to a listed name that must stay withheld: a path, another case, a longer or shorter name,
# surrounding space and a version suffix.
NEAR_PROGRAMS = ['/usr/bin/git', './git', 'Git', 'GIT', 'gitk', 'git-lfs', 'r', ' git', 'git ', 'python3.12']

# Synthetic configurations shared by the findings and setup checks. Hooks use the layout Codex writes: each matcher
# group's handlers as `[[hooks.<Event>.hooks]]` sections (openai/codex 086ccc8 protocol/src/hooks.rs L140-L145). Every rule, and every kind of entry a rule can name: an MCP server, an MCP server's tool, an app, an app's tool,
# a hook event, notify, the approval, sandbox and environment settings, and a saved approval.
FIRST = """approval_policy = "never"
sandbox_mode = "danger-full-access"
notify = ["seed-notify-program", "seed-notify-arg"]

[mcp_servers.github]
command = "seed-github-command"

[mcp_servers.search]
url = "https://seed-search-host.example/mcp"
default_tools_approval_mode = "approve"

[mcp_servers."team.wiki"]
url = "https://seed-wiki-host.example/mcp"

[mcp_servers.docs]
url = "https://seed-docs-host.example/mcp"
default_tools_approval_mode = "prompt"

[mcp_servers.docs.tools.publish]
approval_mode = "approve"

[mcp_servers.docs.tools.lookup]
approval_mode = "writes"

[apps.calendar]
default_tools_approval_mode = "approve"

[apps.drive]

[apps.files]
default_tools_enabled = false
default_tools_approval_mode = "prompt"

[apps.files.tools.delete]
enabled = true
approval_mode = "approve"

[apps.files.tools.read]
enabled = true
approval_mode = "auto"

[[hooks.PreToolUse]]
matcher = "Bash"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "seed-hook-command"
"""
SECOND = """approval_policy = "on-request"
sandbox_mode = "workspace-write"
shell_environment_policy = { inherit = "core" }

[sandbox_workspace_write]
network_access = true
"""


def section(report, heading):
    """Return the body of a Markdown report section, without its heading or the following section."""
    _, found, body = report.partition(f"\n## {heading}\n\n")
    if not found:
        raise AssertionError(f"The report has no {heading!r} section.")
    return body.split("\n\n## ", 1)[0].strip("\n")


def full_scope(root=ROOT):
    """The Full scope section of a checkout's docs/report.md, which the Markdown report links (archived issue #137)."""
    guide = root / "docs" / "report.md"
    if not guide.is_file():
        raise AssertionError(f"{guide} is missing, so the report's full-scope link has no target.")
    return section(guide.read_text(encoding="utf-8"), "Full scope")


def items(body):
    """Split a Findings or Not checked section into its items, which a horizontal rule separates."""
    return [item for item in body.split("\n\n---\n\n") if item]


# The Findings section opens with one shared note on changing settings when it lists any finding (archived issue #119,
# re-review of archived PR #129 at 29d5a8c, F15); tests/findings_say_what_to_do/test_what_to_do.py checks its text.
NOTE_LABEL = "*Before you change anything:*"


def finding_items(report):
    """The items of a report's Findings section, after its shared note."""
    body = section(report, "Findings")
    if body.startswith(NOTE_LABEL):
        body = body.split("\n\n", 1)[1]
    return items(body)


# The line under "Not checked" when it lists anything (reading check, 2026-11-09).
# Not every item is a setting to review, so the line points to each item's own step (re-review F26).
NOT_CHECKED_INTRO = ("stay-safe reads only settings whose meaning it has checked against Codex, and it skips anything it "
                     "can't read or check rather than guess. Each item says what to do.")


def gap_items(report):
    """The items of a report's Not checked section, after the line that explains why they are skipped."""
    body = section(report, "Not checked")
    if not body.startswith(NOT_CHECKED_INTRO + "\n\n"):
        raise AssertionError("The Not checked section must start with its explanation:\n" + body[:300])
    return items(body[len(NOT_CHECKED_INTRO) + 2:])


# The ChatGPT Apps connection a configuration without `features.apps = false` names: harnesses/codex.md
# row `features.apps` `omitted`, from Codex's default (archived issue #121).
CHATGPT_APPS = ["ChatGPT Apps", "exists only if Codex is signed in with ChatGPT, which is not checked",
                "features.apps = false turns it off"]


class ConfigCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        system = patch('stay_safe.cli.SYSTEM', self.root / 'no-system-folder')
        system.start()
        self.addCleanup(system.stop)

    def require_no_system_folder(self):
        # A default run in a subprocess reads the real /etc/codex, which the patch above cannot reach.
        if Path('/etc/codex').exists():
            self.fail('/etc/codex exists and this subprocess default run reads it; run without /etc/codex.')

    def config(self, text, name="config.toml"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path


def copy_checkout(destination):
    """Copy the files a run reads into a new checkout whose .git/HEAD names COPY_REVISION; return its root.

    Runs that may save a report use a copy, so they never replace a report in the checkout under test.
    """
    destination.mkdir(parents=True)
    shutil.copytree(ROOT / "stay_safe", destination / "stay_safe", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("incidents.md", "harnesses/codex.md"):
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination / name)
    (destination / ".git").mkdir()
    (destination / ".git" / "HEAD").write_text(COPY_REVISION + "\n", encoding="utf-8")
    return destination


def run_checkout(checkout, *args, cwd, env=None, user=None):
    """Run the copied checkout's diagnostic with Python's bytecode cache off, so Python itself writes nothing."""
    return subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=cwd,
                          env={**(env or {}), "PYTHONPATH": str(checkout)}, user=user,
                          text=True, capture_output=True, timeout=10)


def tree_state(*roots):
    """Every path under the roots, with its type, permissions and contents (symlinks are not followed)."""
    state = {}
    for root in roots:
        for path in [root, *root.rglob("*")]:
            info = os.stat(path, follow_symlinks=False)
            data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
            state[str(path)] = (info.st_mode, data)
    return state


# One distinct seed per sensitive field. "<", ">", "&" and "'" make the HTML-escaped form differ from
# the raw one, so a value leaked through the Markdown table escaping is still found.
SEEDS = {
    "provider name": "seed-provider-name <Alice's & Bob's>",
    "MCP host": "seed-mcp-host.example",
    "command": "seed-command-<&>",
    "args": "seed-args-'&'",
    "env": "seed-env-<'&'>",
    "headers": "seed-headers-<&>",
    "URL credentials": "seed-url-user",
    "URL query": "seed-url-query",
    "provider endpoint": "seed-provider-host.example",
    "provider token": "seed-provider-token-<&>",
    "notify": "seed-notify-<&>",
    "notify args": "seed-notify-args/private-helper.py-<'&'>",
    "disabled server URL": "seed-disabled-host.example",
    "disabled server headers": "seed-disabled-headers-<&>",
}

# A config file that puts each seed where stay-safe reads a private value.
SEEDED = f"""approval_policy = "never"
sandbox_mode = "read-only"
notify = ["{SEEDS['notify']}", "{SEEDS['notify args']}"]

[mcp_servers.local]
command = "{SEEDS['command']}"
args = ["{SEEDS['args']}"]
env = {{ TOKEN = "{SEEDS['env']}" }}

[mcp_servers.remote]
url = "https://{SEEDS['URL credentials']}@{SEEDS['MCP host']}/mcp?token={SEEDS['URL query']}"
http_headers = {{ Authorization = "{SEEDS['headers']}" }}

[mcp_servers.disabled]
url = "https://{SEEDS['disabled server URL']}/mcp"
enabled = false
http_headers = {{ Authorization = "{SEEDS['disabled server headers']}" }}

[model_providers.internal]
name = "{SEEDS['provider name']}"
base_url = "https://{SEEDS['provider endpoint']}"
experimental_bearer_token = "{SEEDS['provider token']}"
"""


class ReportRuns:
    """CLI runs and report reading shared by tests in several claims' folders."""

    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, "-m", "stay_safe", *args], cwd=ROOT,
                              env=env, text=True, capture_output=True, timeout=10)

    def scope_and_setup(self, run, format_name):
        """Return what a CLI run says it can't see (JSON: its scope) and its settings grouped by file label."""
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        if format_name == "json":
            report = json.loads(run.stdout)
            groups = {}
            for entry in report["catalog"]:
                groups.setdefault(entry["source"], []).append(entry["id"])
            return report["scope"], groups
        cant_see = [line.removeprefix("- ") for line in section(run.stdout, "What this report can't see").splitlines()
                    if line.startswith("- ")]
        groups = {}
        for group in section(run.stdout, "Your setup").split("\n\n"):
            heading, *lines = group.splitlines()
            groups[heading.split("`")[1]] = [line.removeprefix("- ") for line in lines]
        return cant_see, groups

# Issue #18 specifies this stderr text independently of the implementation.
INCOMPLETE = "Inspection incomplete (exit 2). See the report for what wasn't checked.\n"
