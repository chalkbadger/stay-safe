import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

FEEDBACK = "Report a problem or suggest an idea: https://github.com/chalkbadger/stay-safe/issues/new/choose\n"

INLINE_OVERRIDE = ("On versions that support inline profiles, settings in the selected table can override "
                   "your top-level settings.")
SELECTOR_GAP = ("Codex 0.172.0 rejects a top-level profile selector in the configuration it uses at startup. "
                f"It ignores this setting in project configuration. {INLINE_OVERRIDE}")
TABLES_GAP = ("Legacy profile tables do not select a profile. If this is the base user config, "
              f"starting Codex 0.172.0 with a matching --profile name stops configuration loading. {INLINE_OVERRIDE}")

ROOT = Path(__file__).resolve().parents[1]
_TEST_HOME = tempfile.TemporaryDirectory()
os.environ["HOME"] = _TEST_HOME.name
for variable in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
    os.environ.pop(variable, None)
REPORT = "stay-safe-report.html"
COPY_REVISION = "0123456789abcdef0123456789abcdef01234567"
HARD_WORDS = ['sk-private-secret', 'ghp_private-secret', 'github_pat_private-secret', 'alice@example.com',
              '/private/path', '--private-flag', 'private value', 'private\nvalue', 'private|value', 'x' * 81, '..', '']
PROGRAMS = ('git gh npm npx pnpm yarn node python python3 pip pip3 uv cargo go make docker kubectl curl wget ssh '
            'bash sh rm mv cp chmod').split()
NEAR_PROGRAMS = ['/usr/bin/git', './git', 'Git', 'GIT', 'gitk', 'git-lfs', 'r', ' git', 'git ', 'python3.12']

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
    _, found, body = report.partition(f"\n## {heading}\n\n")
    if not found:
        raise AssertionError(f"The report has no {heading!r} section.")
    return body.split("\n\n## ", 1)[0].strip("\n")


def full_scope(root=ROOT):
    guide = root / "docs" / "report.md"
    if not guide.is_file():
        raise AssertionError(f"{guide} is missing, so the report's full-scope link has no target.")
    return section(guide.read_text(encoding="utf-8"), "Full scope")


def items(body):
    return [item for item in body.split("\n\n---\n\n") if item]


NOTE_LABEL = "*Before you change anything:*"


FINDING_HEADING = re.compile(r"### Finding \d+\n\n")


def without_rule_links(text):
    url = r'https://github\.com/chalkbadger/stay-safe/blob/[0-9a-f]{40}/docs/rules\.md#[a-z_]+'
    text = re.sub(r'(?<=Rule )\[(`[^`]+`)\]\(' + url + r'\)', r'\1', text)
    return re.sub(r'(?<=Rule )([a-z_]+) \(' + url + r'\)', r'\1', text)


def finding_items(report):
    body = section(without_rule_links(report), "Findings")
    if body.startswith(NOTE_LABEL):
        body = body.split("\n\n", 1)[1]
    found = items(body)
    for item in found:
        if not FINDING_HEADING.match(item):
            raise AssertionError("A finding must open with its numbered heading:\n" + item[:300])
    return [FINDING_HEADING.sub("", item, count=1) for item in found]


NOT_CHECKED_INTRO = ("stay-safe reads only settings whose meaning it has checked against Codex, and it skips anything it "
                     "can't read or check rather than guess. Each item says what to do.")


def gap_items(report):
    body = section(report, "Not checked")
    if not body.startswith(NOT_CHECKED_INTRO + "\n\n"):
        raise AssertionError("The Not checked section must start with its explanation:\n" + body[:300])
    return items(body[len(NOT_CHECKED_INTRO) + 2:])


CHATGPT_APPS = ["ChatGPT Apps", "exists only if Codex is signed in with ChatGPT, which is not checked",
                "features.apps = false turns it off", "apps not named in this file: destructive tools enabled by Codex default"]


class ConfigCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        system = patch('stay_safe.cli.SYSTEM', self.root / 'no-system-folder')
        system.start()
        self.addCleanup(system.stop)

    def require_no_system_folder(self):
        if Path('/etc/codex').exists():
            self.fail('/etc/codex exists and this subprocess default run reads it; run without /etc/codex.')

    def config(self, text, name="config.toml"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path


def copy_checkout(destination):
    destination.mkdir(parents=True)
    shutil.copytree(ROOT / "stay_safe", destination / "stay_safe", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("incidents.md", "harnesses/codex.md", "harnesses/claude-code.md"):
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination / name)
    (destination / ".git").mkdir()
    (destination / ".git" / "HEAD").write_text(COPY_REVISION + "\n", encoding="utf-8")
    return destination


def run_checkout(checkout, *args, cwd, env=None, user=None):
    return subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=cwd,
                          env={**(env or {}), "PYTHONPATH": str(checkout)}, user=user,
                          text=True, capture_output=True, timeout=10)


def tree_state(*roots):
    state = {}
    for root in roots:
        for path in [root, *root.rglob("*")]:
            info = os.stat(path, follow_symlinks=False)
            data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
            state[str(path)] = (info.st_mode, data)
    return state


SEEDS = {
    "provider name": "seed-provider-name <Alice's & Bob's>",
    "MCP host": "seed-mcp-host.example",
    "command": "seed-command-<&>",
    "args": "seed-args-'&'",
    "env key": "PrivateInlineEnvKey",
    "header key": "PrivateInlineHeaderKey",
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

SEEDED = f"""approval_policy = "never"
sandbox_mode = "read-only"
notify = ["{SEEDS['notify']}", "{SEEDS['notify args']}"]

[mcp_servers.local]
command = "{SEEDS['command']}"
args = ["{SEEDS['args']}"]
env = {{ {SEEDS['env key']} = "{SEEDS['env']}" }}

[mcp_servers.remote]
url = "https://{SEEDS['URL credentials']}@{SEEDS['MCP host']}/mcp?token={SEEDS['URL query']}"
http_headers = {{ {SEEDS['header key']} = "{SEEDS['headers']}" }}

[mcp_servers.disabled]
url = "https://{SEEDS['disabled server URL']}/mcp"
enabled = false
http_headers = {{ {SEEDS['header key']} = "{SEEDS['disabled server headers']}" }}

[model_providers.internal]
name = "{SEEDS['provider name']}"
base_url = "https://{SEEDS['provider endpoint']}"
experimental_bearer_token = "{SEEDS['provider token']}"
"""


class ReportRuns:
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, "-m", "stay_safe", *args], cwd=ROOT,
                              env=env, text=True, capture_output=True, timeout=10)

    def scope_and_setup(self, run, format_name):
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

INCOMPLETE = "Inspection incomplete (exit 2). See the report for what wasn't checked.\n"


def agent_home(root, codex=None, claude=None):
    home = root / "home"
    home.mkdir(exist_ok=True)
    if codex is not None:
        (home / ".codex").mkdir()
        (home / ".codex" / "config.toml").write_text(codex, encoding="utf-8")
    if claude is not None:
        (home / ".claude").mkdir()
        (home / ".claude" / "settings.json").write_text(claude, encoding="utf-8")
    return home


def run_home(home, *args, cwd=None, **env):
    return subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=cwd or home,
                          env={"HOME": str(home), "PYTHONPATH": str(ROOT), **env},
                          text=True, capture_output=True, timeout=10)
