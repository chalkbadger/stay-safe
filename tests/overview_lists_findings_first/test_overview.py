from html.parser import HTMLParser
import json
import re
import subprocess
import sys

from stay_safe.report import inspect, render
from tests.support import SELECTOR_GAP
from tests.support import without_rule_links
from tests.support import INCOMPLETE, REPORT, ROOT, ConfigCase, copy_checkout, run_checkout, section

GROUP_1 = "**Nothing stands between a mistaken or injected instruction and your computer**"
GROUP_2 = "**Network access, credentials, and connected tools**"
GROUP_3 = "**Something else has to be tampered with first**"
NOT_RANKED = ("**Based on Codex's source code and not yet seen in a live run, so stay-safe has no basis to rank these. "
              "That does not make them minor.**")
LEAD_IN = "Here are the findings for you to review, with actionable advice."
NO_FINDINGS = ("None of stay-safe's rules matched your settings. That doesn't mean your setup is safe: "
               "see what stay-safe didn't check and what this report can't see, below.")

SANDBOX_OFF = "Your config turns off Codex’s sandbox."

QUIET = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\nshell_environment_policy = { inherit = "none" }\n'
EVERY_GROUP = """approval_policy = "never"
sandbox_mode = "danger-full-access"
profile = "work"

[mcp_servers.github]
command = "seed-command"

[mcp_servers.search]
url = "https://seed-host.example/mcp"
default_tools_approval_mode = "approve"
"""
CHANNELS = QUIET.replace("read-only", "workspace-write") + """
[sandbox_workspace_write]
network_access = true

[apps.files]
default_tools_approval_mode = "prompt"

[apps.calendar]
default_tools_approval_mode = "prompt"
"""
APPROVALS = ('\nprefix_rule(pattern=["git", "status"], decision="allow")\n' + "\n" * 7
             + 'prefix_rule(pattern=["curl"], decision="allow")\n')
SANDBOX_ONLY = QUIET.replace("read-only", "danger-full-access")
MOST_COMMANDS = "With these settings, Codex runs most commands without asking you."


def overview(report):
    head, found, _ = report.partition("\n\n## Findings\n\n")
    if not found:
        raise AssertionError("The report has no Findings section.")
    return head.split("\n\n")[1:]


def listed(report):
    lines, heading = [], None
    for paragraph in overview(report):
        if paragraph.startswith("**"):
            heading = paragraph
            continue
        for line in paragraph.split("\n"):
            found = re.fullmatch(r"(\d+)\. (.+)", line)
            if found:
                lines.append((heading, int(found[1]), found[2]))
    return lines


def details(report):
    body = section(without_rule_links(report), "Findings")
    found = []
    for item in body.split("\n\n---\n\n"):
        number = re.search(r"^### Finding (\d+)\n\n\*\*(.+?)\*\* ", item, re.MULTILINE)
        trace = re.search(r"\n\n\*Rule `([a-z_]+)` · (?:setting|rules entry) `(.+?)` = ", item)
        found.append((int(number[1]) if number else None, number[2] if number else None,
                      trace[1] if trace else None, trace[2] if trace else None))
    return found


class Targets(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links, self.overview_links, self.ids, self.text, self.tags, self.words = [], [], [], {}, [], []
        self.current = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attributes = dict(attrs)
        if "href" in attributes:
            self.links.append(attributes["href"])
            if self.current is None:
                self.overview_links.append(attributes["href"])
        if "id" in attributes:
            self.current = attributes["id"]
            self.ids.append(self.current)
            self.text[self.current] = ""

    def handle_data(self, data):
        self.words.append(data)
        if self.current is not None:
            self.text[self.current] += data


class OverviewTests(ConfigCase):
    def test_claude_finding_groups_keep_numbered_lists_in_markdown_and_html(self):
        path = self.config(json.dumps({"permissions": {"defaultMode": "default",
                                                      "allow": ["Bash", "Bash(git status)", "WebFetch"]}}))
        checkout = copy_checkout(self.root / "checkout")
        run = run_checkout(checkout, "--agent", "claude", "--config", str(path), "--format", "markdown",
                           "--save", cwd=checkout)
        self.assertEqual(run.returncode, 0)
        self.assertRegex(run.stdout, r"(?m)^2\. .*\n\n\*\*Network access\*\*\n\n3\. ")
        page = (checkout / REPORT).read_text()
        self.assertEqual(re.findall(r'<ol start="(\d+)">', page), ["1", "3"])

    def report(self, *texts, rules=None):
        paths = [self.config(text, f"config-{index}.toml") for index, text in enumerate(texts, 1)]
        return inspect(paths, rules_path=self.config(rules, "selected.rules") if rules is not None else None)

    def test_every_finding_appears_once_in_policy_order_with_matching_details(self):
        report = self.report(EVERY_GROUP, CHANNELS, CHANNELS, rules=APPROVALS)
        markdown = render(report, "markdown")
        expected = [
            ("unrestricted_filesystem", "config-1:sandbox_mode"),
            ("commands_without_prompts", "config-1:approval_policy"),
            ("saved_approval", "rules-1:prefix_rule.2"),
            ("saved_approval", "rules-1:prefix_rule.10"),
            ("destructive_tools", "config-2:apps.calendar"),
            ("destructive_tools", "config-2:apps.files"),
            ("destructive_tools", "config-3:apps.calendar"),
            ("destructive_tools", "config-3:apps.files"),
            ("network_access", "config-2:sandbox_workspace_write.network_access"),
            ("network_access", "config-3:sandbox_workspace_write.network_access"),
            ("environment_inheritance", "config-1:shell_environment_policy"),
            ("automatic_tools", "config-1:approval_policy"),
            ("automatic_tools", "config-1:mcp_servers.search"),
            ("configured_program", "config-1:mcp_servers.github"),
            ("self_described_tools", "config-1:mcp_servers.github")]
        found = details(markdown)
        self.assertEqual([(rule, entry) for _, _, rule, entry in found], expected)
        self.assertEqual([number for number, *_ in found], list(range(1, 16)))
        headings = [GROUP_1] * 4 + [GROUP_2] * 9 + [GROUP_3, NOT_RANKED]
        self.assertEqual(listed(markdown), [
            (heading, number, f"[{headline}](#finding-{number}) (`{entry.split(':')[0]}`)")
            for heading, (number, headline, _, entry) in zip(headings, found)])
        plain = render(report, "plain")
        for number, headline, _, entry in found:
            line = f"{number}. {headline.replace('`', '')} ({entry.split(':')[0]})"
            self.assertEqual(plain.count("\n" + line + "\n"), 1)
            self.assertEqual(plain.count(f"\nFinding {number}\n"), 1)
        self.assertLess(plain.index("\n14. "), plain.index("\nFinding 1\n"))
        self.assertNotIn("#finding", plain)

    def test_two_files_with_the_same_title_keep_their_labels_and_each_link_reaches_its_own_finding(self):
        report = self.report(SANDBOX_ONLY, SANDBOX_ONLY)
        markdown = render(report, "markdown")
        self.assertEqual(listed(markdown), [(GROUP_1, 1, f"[{SANDBOX_OFF}](#finding-1) (`config-1`)"),
                                            (GROUP_1, 2, f"[{SANDBOX_OFF}](#finding-2) (`config-2`)"),
                                            (GROUP_1, 3, f"[{MOST_COMMANDS}](#finding-3) (`config-1`)"),
                                            (GROUP_1, 4, f"[{MOST_COMMANDS}](#finding-4) (`config-2`)")])
        body = section(markdown, "Findings")
        for number in (1, 2):
            heading = f"Finding {number}"
            self.assertEqual(body.count(f"### {heading}\n"), 1)
            finding = body.split(f"### {heading}\n\n", 1)[1].split("\n\n---\n\n", 1)[0]
            self.assertTrue(finding.startswith(f"**{SANDBOX_OFF}** "), finding)
            self.assertIn(f"*Rule `unrestricted_filesystem` · setting `config-{number}:sandbox_mode` = ", without_rule_links(finding))
        self.assertEqual(markdown.count("\n## Not checked\n"), 1)
        page = Targets(render(report, "html"))
        self.assertEqual([link for link in page.links if link.startswith("#")],
                         ["#finding-1", "#finding-2", "#finding-3", "#finding-4"])
        for target in ("finding-1", "finding-2", "not-checked"):
            self.assertEqual(page.ids.count(target), 1)
        self.assertLess(page.ids.index("finding-1"), page.ids.index("finding-2"))
        self.assertLess(page.ids.index("finding-2"), page.ids.index("not-checked"))
        for number in (1, 2):
            self.assertIn(f"config-{number}:sandbox_mode", page.text[f"finding-{number}"])
            self.assertNotIn(f"config-{3 - number}:sandbox_mode", page.text[f"finding-{number}"])
        self.assertTrue(page.text["not-checked"].startswith("Not checked"))
        self.assertEqual(listed(render(self.report(SANDBOX_ONLY), "markdown")),
                         [(GROUP_1, 1, f"[{SANDBOX_OFF}](#finding-1)"),
                          (GROUP_1, 2, f"[{MOST_COMMANDS}](#finding-2)")])

    def test_network_credentials_and_tools_group_uses_topic_and_count(self):
        network = QUIET.replace("read-only", "workspace-write") + "[sandbox_workspace_write]\nnetwork_access = true\n"
        cases = [
            (SANDBOX_ONLY, None),
            (network, "1 is about"),
            (network.replace('inherit = "none"', 'inherit = "all"'), "2 are about"),
        ]
        topic = "network access, credentials, or connected tools"
        for config, count_phrase in cases:
            report = self.report(config)
            for fmt in ("plain", "markdown", "html"):
                with self.subTest(count_phrase=count_phrase, fmt=fmt):
                    text = render(report, fmt)
                    if fmt == "html":
                        text = " ".join(Targets(text).words)
                    heading = GROUP_2.strip("*")
                    if count_phrase is None:
                        self.assertNotIn(heading, text)
                        self.assertNotIn(topic, text)
                    else:
                        self.assertIn(heading, text)
                        self.assertIn(f"{count_phrase} {topic}.", text)

    def test_representative_introduction_explains_results_and_limits(self):
        self.require_no_system_folder()
        home = self.root / "home"
        (home / ".codex" / "rules").mkdir(parents=True)
        (home / ".codex" / "config.toml").write_text(
            QUIET + 'profile = "work"\nfuture_setting = 1\nnotify = ["seed-notify"]\n'
            '[mcp_servers.github]\ncommand = "seed-command"\n', encoding="utf-8")
        (home / ".codex" / "rules" / "default.rules").write_text("# no saved approvals yet\n", encoding="utf-8")
        runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--format", name], cwd=ROOT,
                               env={"HOME": str(home)}, text=True, capture_output=True, timeout=10)
                for name in ("json", "markdown")]
        self.assertEqual([(run.returncode, run.stderr) for run in runs], [(2, INCOMPLETE)] * 2)
        report = json.loads(runs[0].stdout)
        self.assertEqual(sorted(risk["rule"] for risk in report["risks"]),
                         ["configured_program", "configured_program", "self_described_tools"])
        self.assertEqual(len(report["inspection_gaps"]), 2)
        self.assertEqual(overview(runs[1].stdout)[:5], [
            "3 findings, 2 things not checked.",
            "stay-safe read two files: your Codex settings (`~/.codex/config.toml`) and your saved approvals "
            "(`~/.codex/rules/default.rules`). This report describes what those files say, without running any tests "
            "in Codex.",
            "stay-safe found 3 risky settings. 2 matter only if something else is tampered with first. "
            "1 rests on Codex's source code alone.",
            "2 parts of your setup could not be verified because they are missing from those files or outside what "
            "stay-safe covers. stay-safe flagged them for you to review.",
            LEAD_IN])
        self.assertEqual([heading for heading, *_ in listed(runs[1].stdout)], [GROUP_3, GROUP_3, NOT_RANKED])

    def test_no_findings_does_not_imply_safety_or_hide_incomplete_checks(self):
        report = self.report(QUIET + 'profile = "work"\n')
        markdown = render(report, "markdown")
        self.assertIn(NO_FINDINGS, section(markdown, "Findings"))
        self.assertIn("1 thing not checked", "\n".join(overview(markdown)))
        self.assertIn("This file uses an old way to select a profile.", section(markdown, "Not checked"))
        self.assertEqual(listed(markdown), [])
        self.assertNotIn("#finding", markdown)
        plain = render(report, "plain")
        self.assertIn(NO_FINDINGS, plain)
        self.assertNotIn("risky setting", plain)

    def test_overview_names_only_read_files_and_keeps_inspection_gaps_visible(self):
        read = self.config(SANDBOX_ONLY, "read.toml")
        other = self.config(QUIET, "other.toml")
        missing = self.root / "missing.toml"
        invalid = self.config("[broken", "invalid.toml")
        cases = [([read, other], None, ["config-1", "config-2"], 0),
                 ([read, missing], self.root / "missing.rules", ["config-1"], 2),
                 ([missing], None, [], 1), ([invalid], None, [], 1)]
        for paths, rules, labels, gaps in cases:
            with self.subTest(paths=paths, rules=rules):
                report = inspect(paths, rules_path=rules)
                markdown = render(report, "markdown")
                intro = "\n".join(overview(markdown))
                read_lines = [line for line in intro.splitlines() if line.startswith("stay-safe read ")]
                if labels:
                    self.assertEqual(len(read_lines), 1)
                    self.assertEqual(re.findall(r"`([^`]+)`", read_lines[0]), labels)
                    self.assertIn("without running any tests in Codex", read_lines[0])
                else:
                    self.assertEqual(read_lines, [])
                    self.assertIn("could not read any configuration files", intro)
                    self.assertIn("Not checked", intro)
                    self.assertNotIn("those files", intro)
                if gaps:
                    self.assertRegex(intro, rf"{gaps} parts? of your setup could not be verified")
                    self.assertIn("**Not checked:", section(markdown, "Not checked"))
                    if report["risks"]:
                        page = Targets(render(report, "html"))
                        self.assertIn("#not-checked", page.overview_links)
                        self.assertEqual(page.ids.count("not-checked"), 1)
                        self.assertIn("Not checked", page.text["not-checked"])
                else:
                    self.assertNotIn("could not be verified", intro)
                    self.assertNotIn("flagged", intro)
                    self.assertNotIn("not checked:", intro)

    def test_names_with_markdown_or_html_characters_are_escaped_in_the_list_and_links_stay_https_or_own(self):
        names = ["<b>bold</b>", "*x*", "[x](javascript:alert(1))", "a](https://example.com/)[b", "<script>alert(1)</script>"]
        report = self.report(QUIET + "".join(f'[mcp_servers.s{index}]\ncommand = "seed-command"\n'
                                             for index in range(len(names))))
        programs = [risk for risk in report["risks"] if risk["rule"] == "configured_program"]
        self.assertEqual(len(programs), len(names))
        for risk, name in zip(programs, names):
            risk["entry"] = f"config-1:mcp_servers.{json.dumps(name)}"
        markdown, plain, html = (render(report, name) for name in ("markdown", "plain", "html"))
        written = [f"`{name}`" for name in names]
        lines = [(number, text) for heading, number, text in listed(markdown) if heading == GROUP_3]
        self.assertCountEqual([re.sub(r"\(#finding-(\d+)\)$", "", text) for _, text in lines],
                              [f"[Your {name} MCP server can start a program on your computer.]" for name in written])
        for number, text in lines:
            self.assertTrue(text.endswith(f"](#finding-{number})"), text)
        page = Targets(html)
        for name in names:
            sentence = f"Your {name} MCP server can start a program on your computer."
            self.assertIn(sentence, "".join(page.words))
            self.assertRegex(plain, r"\n\d+\. " + re.escape(sentence) + r"\n")
        self.assertEqual([tag for tag in page.tags if tag in {"script", "b", "img"}], [])
        own = [f"#finding-{number}" for number in range(1, len(report["risks"]) + 1)]
        self.assertEqual(page.overview_links, own)
        self.assertEqual([link for link in page.links if not link.startswith("https://")], own)
        for link in own:
            self.assertEqual(page.ids.count(link[1:]), 1)


class UnchangedTests(ConfigCase):
    def test_overview_order_does_not_change_json_or_exit_status(self):
        for suffix, status in (("", 0), ('profile = "work"\n', 2)):
            with self.subTest(status=status):
                path = self.config('notify = ["seed-notify"]\n' + SANDBOX_ONLY + suffix)
                runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(path), "--format", name],
                                       cwd=ROOT, env={}, text=True, capture_output=True, timeout=10)
                        for name in ("json", "markdown")]
                self.assertEqual([(run.returncode, run.stderr) for run in runs],
                                 [(status, INCOMPLETE if status else "")] * 2)
                report = json.loads(runs[0].stdout)
                self.assertEqual([(risk["rule"], risk["entry"]) for risk in report["risks"]],
                                 [("commands_without_prompts", "config-1:approval_policy"),
                                  ("configured_program", "config-1:notify"),
                                  ("unrestricted_filesystem", "config-1:sandbox_mode")])
                self.assertEqual([(rule, entry) for _, _, rule, entry in details(runs[1].stdout)],
                                 [("unrestricted_filesystem", "config-1:sandbox_mode"),
                                  ("commands_without_prompts", "config-1:approval_policy"),
                                  ("configured_program", "config-1:notify")])
                self.assertEqual(report["inspection_gaps"], [] if status == 0 else [
                    "config-1: " + SELECTOR_GAP])
