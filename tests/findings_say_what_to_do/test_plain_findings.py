"""Each Markdown finding leads with what it means for you, how it has gone wrong and what to do, then keeps its ids
and labels on one trace line (archived issue #105 and its reading check).

The expected headlines and sentences below were written from the issue's After example and from each rule's
meaning in stay_safe/rules.py and harnesses/codex.md, not copied from the report. The headline, in bold, is one
sentence that stands alone (archived issue #106 lists it on its own).
"""

import json
import subprocess
import sys

from tests.support import finding_items, FIRST, SECOND, ConfigCase, ROOT, items, section

PROGRAM = "If that program or your config file were tampered with, it could run code you didn't intend."
AUTOMATIC = 'Untrusted tool content could lead to unwanted actions.'
DESTRUCTIVE = "A mistaken operation could change or delete data in the connected service."
SOURCE_ONLY = "Based on Codex's source code, not yet seen in a live run."
GROUP_HINTS = '`auto` and `writes` use hints supplied by the server. ' + SOURCE_ONLY
TOOL_HINTS = GROUP_HINTS
# Rule -> one sentence on its cited incidents, from incidents.md (reading check, 2026-11-09).
HOW = {
    "saved_approval": "A Codex user reported that a saved approval for `curl` let later `curl` commands run without "
                      "asking, even after restarting in another workspace.",
    "commands_without_prompts": "Agents running commands without approval have run a delete command aimed at a home "
                                "directory, wiped a drive and updated drivers when asked only to diagnose.",
    "unrestricted_filesystem": "Agents have deleted a home directory and wiped a whole drive with one mistaken delete "
                               "command.",
    "configured_program": "Flaws in other agents let repository settings run commands on collaborators' machines, "
                          "and a worm wrote itself into an agent's settings so its code ran at every start.",
    "automatic_tools": "Hidden instructions in public GitHub issues could take over agents using a GitHub MCP server, "
                       "and injected text got another agent to turn off its own approvals.",
    "destructive_tools": "Agents have deleted production data with a token they found, and changed a database after "
                         "being told to stop.",
    "network_access": "Instructions hidden in public GitHub issues and issue comments could take over agents that "
                      "read them.",
    "self_described_tools": "Instructions hidden in public GitHub issues and issue comments could take over agents "
                            "that read them.",
    "environment_inheritance": "An agent that could read a production database URL dropped all 22 production tables "
                               "with a migration command.",
}

RULES = 'prefix_rule(pattern=["git", "seed-rule-word"], decision="allow")\n'
SEEDS = ["seed-notify-program", "seed-notify-arg", "seed-github-command", "seed-search-host", "seed-wiki-host",
         "seed-docs-host", "seed-hook-command", "seed-rule-word"]

# (rule, entry) -> headline and why. The What to do part is checked in tests/findings_say_what_to_do/test_what_to_do.py.
EXPECTED = {
    ("commands_without_prompts", "config-1:approval_policy"):
        "**With these settings, Codex runs commands without asking you.** It won't ask before any command it's "
        "allowed to run, so injected or mistaken instructions could make it run code you didn't want.",
    ("automatic_tools", "config-1:apps.calendar"):
        f"**Your `calendar` app's tool approval mode is `approve`.** {AUTOMATIC}",
    ("destructive_tools", "config-1:apps.calendar"):
        f"**Your `calendar` app's tools that can change or delete data are turned on.** {DESTRUCTIVE}",
    ("destructive_tools", "config-1:apps.drive"):
        f"**Your `drive` app's tools that can change or delete data are turned on.** {DESTRUCTIVE}",
    ("self_described_tools", "config-1:apps.drive"):
        f"**Your `drive` app uses server hints for tool approval.** {GROUP_HINTS}",
    ("automatic_tools", "config-1:apps.files.tools.delete"):
        f"**The `delete` tool of your `files` app has approval mode `approve`.** {AUTOMATIC}",
    ("destructive_tools", "config-1:apps.files.tools.delete"):
        f"**The `delete` tool of your `files` app is turned on, even if it can change or delete data.** {DESTRUCTIVE}",
    ("destructive_tools", "config-1:apps.files.tools.read"):
        f"**The `read` tool of your `files` app is turned on, even if it can change or delete data.** {DESTRUCTIVE}",
    ("self_described_tools", "config-1:apps.files.tools.read"):
        f"**The `read` tool of your `files` app uses server hints for tool approval.** {TOOL_HINTS}",
    ("configured_program", "config-1:hooks.PreToolUse"):
        f"**Your `PreToolUse` hooks can start a program on your computer.** {PROGRAM}",
    ("self_described_tools", "config-1:mcp_servers.docs.tools.lookup"):
        f"**The `lookup` tool of your `docs` MCP server uses server hints for tool approval.** {TOOL_HINTS}",
    ("automatic_tools", "config-1:mcp_servers.docs.tools.publish"):
        f"**The `publish` tool of your `docs` MCP server has approval mode `approve`.** {AUTOMATIC}",
    ("configured_program", "config-1:mcp_servers.github"):
        f"**Your `github` MCP server can start a program on your computer.** {PROGRAM}",
    ("self_described_tools", "config-1:mcp_servers.github"):
        f"**Your `github` MCP server uses server hints for tool approval.** {GROUP_HINTS}",
    ("automatic_tools", "config-1:mcp_servers.search"):
        f"**Your `search` MCP server's tool approval mode is `approve`.** {AUTOMATIC}",
    ("self_described_tools", 'config-1:mcp_servers."team.wiki"'):
        f"**Your `team.wiki` MCP server uses server hints for tool approval.** {GROUP_HINTS}",
    ("configured_program", "config-1:notify"):
        f"**Your `notify` setting can start a program on your computer.** {PROGRAM}",
    ("unrestricted_filesystem", "config-1:sandbox_mode"):
        "**Your config turns off Codex's sandbox.** Commands Codex runs aren't limited to your project, so a "
        "mistaken command could damage files elsewhere on your computer.",
    ("environment_inheritance", "config-1:shell_environment_policy"):
        "**With these settings, commands Codex runs get your environment variables.** They start with the "
        "environment Codex was launched with, apart from a few Codex launch variables. Credentials in it could be "
        "misused, even if Codex filters out some variable names.",
    ("network_access", "config-2:sandbox_workspace_write.network_access"):
        "**With these settings, commands Codex runs can use the network.** Your sandbox allows network access, so "
        "injected instructions could send your private data to an outside service.",
    ("saved_approval", "rules-1:prefix_rule.1"):
        "**A saved approval on line 1 of your rules file says matching commands may run outside the sandbox "
        "without asking you.** It covers every command that starts with its saved words. A rule that asks first or "
        "forbids the command can override it, and stay-safe doesn't check whether one does.",
}
ALL_RULES = {"saved_approval", "commands_without_prompts", "unrestricted_filesystem", "configured_program",
             "automatic_tools", "destructive_tools", "network_access", "self_described_tools",
             "environment_inheritance"}


class PlainFindingTests(ConfigCase):
    def run_cli(self, *args):
        run = subprocess.run([sys.executable, "-B", "-m", "stay_safe", *args], cwd=ROOT, env={},
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(run.stderr, "")
        return run

    def test_each_finding_leads_with_its_meaning_then_incidents_next_step_and_trace_and_sources_close_the_report(self):
        args = ["--config", str(self.config(FIRST, "first.toml")), "--config", str(self.config(SECOND, "second.toml")),
                "--rules", str(self.config(RULES, "selected.rules"))]
        report = json.loads(self.run_cli(*args, "--format", "json").stdout)
        markdown = self.run_cli(*args).stdout
        self.assertEqual({r["rule"] for r in report["risks"]}, ALL_RULES)
        self.assertCountEqual([(r["rule"], r["entry"]) for r in report["risks"]], EXPECTED)
        self.assertTrue(report["incident_links"], "This checkout must link its incidents for the links to be checked.")
        expected = []
        for risk in report["risks"]:
            if risk["rule"] == "automatic_tools":
                self.assertEqual(risk["explanation"], "Tool approval mode is approve; untrusted tool content "
                                 "could lead to unwanted operations.")
            lead = EXPECTED[(risk["rule"], risk["entry"])]
            citations = ", ".join(f"[{i}]({report['incident_links'][i]})" for i in risk["incidents"])
            kind = "rules entry" if risk["entry"].startswith("rules-") else "setting"
            # Each part is its own paragraph, with italic labels and an italic trace line (reading check, layout).
            expected.append([
                lead,
                f"*How it has gone wrong:* {HOW[risk['rule']]} {citations} (reported, not verified).",
                f"*Rule `{risk['rule']}` · {kind} `{risk['entry']}` = `{'; '.join(risk['configured_evidence'])}`*",
            ])
        found = [item.split("\n\n") for item in finding_items(markdown)]
        # What to do sits between the incidents and the trace line; its content is risk_trace evidence (archived issue #119).
        self.assertEqual([paragraphs[:2] + paragraphs[-1:] for paragraphs in found], expected)
        for paragraphs in found:
            self.assertTrue(paragraphs[2].startswith("*What to do:*"), paragraphs[2])
        rules, meanings = {(r["rule_source"], r["interpretation_source"]) for r in report["risks"]}.pop()
        self.assertEqual(section(markdown, "Sources"),
                         f"- [How each finding's rule is defined]({rules}) (`stay_safe/rules.py`)\n"
                         f"- [What each Codex setting means, with official evidence]({meanings}) (`harnesses/codex.md`)")
        for seed in SEEDS:
            self.assertNotIn(seed, markdown)
