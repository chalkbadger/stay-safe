"""The report opens with an introduction and a numbered findings list, before the detailed findings (issue #82).

The expected sentences, group headings and rule order below are written from issue #82. Finding titles are the
bold headlines contracts/claims.md [findings_say_what_to_do] already fixes. A link in the Markdown report reaches a
heading by the anchor GitHub generates for it: lower case, punctuation removed, spaces replaced with hyphens
(https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links).
"""

from html.parser import HTMLParser
import json
import re
import subprocess
import sys

from stay_safe.report import inspect, render
from tests.support import INCOMPLETE, ROOT, ConfigCase, section

GROUP_1 = "**Nothing stands between a mistaken or injected instruction and your computer**"
GROUP_2 = "**Harm is limited to one channel or service**"
GROUP_3 = "**Something else has to be tampered with first**"
NOT_RANKED = ("**Based on Codex's source code and not yet seen in a live run, so stay-safe has no basis to rank these. "
              "That does not make them minor.**")
LEAD_IN = "Here are the findings for you to review, with actionable advice."
NO_FINDINGS = ("None of stay-safe's rules matched your settings. That doesn't mean your setup is safe: "
               "see what stay-safe didn't check and what this report can't see, below.")

SANDBOX_OFF = "Your config turns off Codex's sandbox."
NO_PROMPTS = "With these settings, Codex runs commands without asking you."
ENVIRONMENT = "With these settings, commands Codex runs get your environment variables."
SEARCH_APPROVE = "Your `search` MCP server's tool approval mode is `approve`."
GITHUB_PROGRAM = "Your `github` MCP server can start a program on your computer."
GITHUB_HINTS = "Your `github` MCP server uses server hints for tool approval."
NOTIFY_PROGRAM = "Your `notify` setting can start a program on your computer."

# One finding in group 3 and one not ranked; with nothing else set, the file has no gaps.
QUIET = 'approval_policy = "on-request"\nsandbox_mode = "read-only"\nshell_environment_policy = { inherit = "none" }\n'
# Findings from every group; `profile` adds one thing not checked.
EVERY_GROUP = """approval_policy = "never"
sandbox_mode = "danger-full-access"
profile = "work"

[mcp_servers.github]
command = "seed-command"

[mcp_servers.search]
url = "https://seed-host.example/mcp"
default_tools_approval_mode = "approve"
"""
# The rules of group 2 that EVERY_GROUP lacks, each on two settings or files.
CHANNELS = QUIET.replace("read-only", "workspace-write") + """
[sandbox_workspace_write]
network_access = true

[apps.files]
default_tools_approval_mode = "prompt"

[apps.calendar]
default_tools_approval_mode = "prompt"
"""
# Saved approvals on lines 2 and 10: as text "10" sorts before "2", as line numbers after it.
APPROVALS = ('\nprefix_rule(pattern=["git", "status"], decision="allow")\n' + "\n" * 7
             + 'prefix_rule(pattern=["curl"], decision="allow")\n')
SANDBOX_ONLY = QUIET.replace("read-only", "danger-full-access")


def overview(report):
    """The paragraphs between the title and the Findings section."""
    head, found, _ = report.partition("\n\n## Findings\n\n")
    if not found:
        raise AssertionError("The report has no Findings section.")
    return head.split("\n\n")[1:]


def listed(report):
    """The findings list: (group heading, number, text after the number) for each line, in order."""
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
    """The detailed findings in order: (number, headline, rule, entry), read from each finding's own lines."""
    body = section(report, "Findings")
    found = []
    for item in body.split("\n\n---\n\n"):
        number = re.search(r"^### Finding (\d+)\n\n\*\*(.+?)\*\* ", item, re.MULTILINE)
        trace = re.search(r"\n\n\*Rule `([a-z_]+)` · (?:setting|rules entry) `(.+?)` = ", item)
        found.append((int(number[1]) if number else None, number[2] if number else None,
                      trace[1] if trace else None, trace[2] if trace else None))
    return found


def anchor(heading):
    """The anchor GitHub gives a heading (see the module docstring)."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


class Targets(HTMLParser):
    """A saved page's links (overview_links: those before the first id), its elements with an id, and the text
    that follows each id up to the next one."""

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
    def report(self, *texts, rules=None):
        paths = [self.config(text, f"config-{index}.toml") for index, text in enumerate(texts, 1)]
        return inspect(paths, rules_path=self.config(rules, "selected.rules") if rules is not None else None)

    def test_every_finding_is_listed_once_in_the_documented_order_with_its_number_on_its_details(self):
        report = self.report(EVERY_GROUP)
        markdown = render(report, "markdown")
        self.assertEqual(len(report["risks"]), 6)
        paragraphs = overview(markdown)
        self.assertIn(LEAD_IN, paragraphs)
        self.assertEqual(paragraphs[paragraphs.index(LEAD_IN) + 1:], [
            GROUP_1,
            f"1. [{SANDBOX_OFF}](#finding-1)\n2. [{NO_PROMPTS}](#finding-2)",
            GROUP_2,
            f"3. [{ENVIRONMENT}](#finding-3)\n4. [{SEARCH_APPROVE}](#finding-4)",
            GROUP_3,
            f"5. [{GITHUB_PROGRAM}](#finding-5)",
            NOT_RANKED,
            f"6. [{GITHUB_HINTS}](#finding-6)",
            "1 thing not checked: see [Not checked](#not-checked)."])
        self.assertEqual(details(markdown), [
            (1, SANDBOX_OFF, "unrestricted_filesystem", "config-1:sandbox_mode"),
            (2, NO_PROMPTS, "commands_without_prompts", "config-1:approval_policy"),
            (3, ENVIRONMENT, "environment_inheritance", "config-1:shell_environment_policy"),
            (4, SEARCH_APPROVE, "automatic_tools", "config-1:mcp_servers.search"),
            (5, GITHUB_PROGRAM, "configured_program", "config-1:mcp_servers.github"),
            (6, GITHUB_HINTS, "self_described_tools", "config-1:mcp_servers.github")])
        # In the terminal the number is the route: the same lines without Markdown, and no link target.
        plain = render(report, "plain")
        for line in (GROUP_1.strip("*"), "1. " + SANDBOX_OFF, "4. Your search MCP server's tool approval mode is approve.",
                     NOT_RANKED.strip("*"), "6. Your github MCP server uses server hints for tool approval.",
                     "1 thing not checked: see Not checked.", "Finding 1", "Finding 6"):
            self.assertIn(f"\n{line}\n", plain)
        self.assertLess(plain.index("\n6. Your github"), plain.index("\nFinding 1\n"))
        self.assertNotIn("#finding", plain)
        self.assertNotIn("#not-checked", plain)

    def test_every_rule_follows_its_group_then_rule_then_file_then_setting_order(self):
        markdown = render(self.report(EVERY_GROUP, CHANNELS, CHANNELS, rules=APPROVALS), "markdown")
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
            ("automatic_tools", "config-1:mcp_servers.search"),
            ("configured_program", "config-1:mcp_servers.github"),
            ("self_described_tools", "config-1:mcp_servers.github")]
        found = details(markdown)
        self.assertEqual([(rule, entry) for _, _, rule, entry in found], expected)
        self.assertEqual([number for number, *_ in found], list(range(1, 15)))
        headings = [GROUP_1] * 4 + [GROUP_2] * 8 + [GROUP_3, NOT_RANKED]
        self.assertEqual(listed(markdown), [
            (heading, number, f"[{headline}](#finding-{number}) (`{entry.split(':')[0]}`)")
            for heading, (number, headline, _, entry) in zip(headings, found)])

    def test_a_group_1_finding_is_listed_before_a_group_3_finding_that_precedes_it_in_the_config(self):
        report = self.report('notify = ["seed-notify"]\n' + SANDBOX_ONLY)
        # The condition: the JSON report, which keeps its order, has the group 3 finding first.
        self.assertEqual([(risk["rule"], risk["entry"]) for risk in report["risks"]],
                         [("configured_program", "config-1:notify"), ("unrestricted_filesystem", "config-1:sandbox_mode")])
        markdown = render(report, "markdown")
        self.assertEqual(listed(markdown), [(GROUP_1, 1, f"[{SANDBOX_OFF}](#finding-1)"),
                                            (GROUP_3, 2, f"[{NOTIFY_PROGRAM}](#finding-2)")])
        self.assertEqual(details(markdown), [(1, SANDBOX_OFF, "unrestricted_filesystem", "config-1:sandbox_mode"),
                                             (2, NOTIFY_PROGRAM, "configured_program", "config-1:notify")])

    def test_a_self_described_tools_finding_is_listed_under_not_ranked_with_its_reason_only(self):
        # `auto`, left as the default or set, and `writes` each give the rule, on a server and on a tool.
        markdown = render(self.report(QUIET + '[mcp_servers.github]\nurl = "https://seed-host.example/mcp"\n'
                                      '[mcp_servers.github.tools.search]\napproval_mode = "writes"\n'
                                      '[mcp_servers.files]\ncommand = "seed-command"\n'), "markdown")
        self.assertEqual(listed(markdown), [
            (GROUP_3, 1, f"[{GITHUB_PROGRAM.replace('github', 'files')}](#finding-1)"),
            (NOT_RANKED, 2, f"[{GITHUB_HINTS.replace('github', 'files')}](#finding-2)"),
            (NOT_RANKED, 3, f"[{GITHUB_HINTS}](#finding-3)"),
            (NOT_RANKED, 4, "[The `search` tool of your `github` MCP server uses server hints for tool approval.]"
                            "(#finding-4)")])
        self.assertEqual([(number, rule) for number, _, rule, _ in details(markdown)],
                         [(1, "configured_program"), (2, "self_described_tools"), (3, "self_described_tools"),
                          (4, "self_described_tools")])
        paragraphs = overview(markdown)
        self.assertEqual(paragraphs.count(NOT_RANKED), 1)
        self.assertEqual(paragraphs[paragraphs.index(NOT_RANKED) + 1].count("\n"), 2)

    def test_two_files_with_the_same_title_keep_their_labels_and_each_link_reaches_its_own_finding(self):
        report = self.report(SANDBOX_ONLY, SANDBOX_ONLY)
        markdown = render(report, "markdown")
        self.assertEqual(listed(markdown), [(GROUP_1, 1, f"[{SANDBOX_OFF}](#finding-1) (`config-1`)"),
                                            (GROUP_1, 2, f"[{SANDBOX_OFF}](#finding-2) (`config-2`)")])
        # Markdown: each link's target is the anchor of one heading, and the finding under it is that file's.
        body = section(markdown, "Findings")
        for number in (1, 2):
            heading = f"Finding {number}"
            self.assertEqual(anchor(heading), f"finding-{number}")
            self.assertEqual(body.count(f"### {heading}\n"), 1)
            finding = body.split(f"### {heading}\n\n", 1)[1].split("\n\n---\n\n", 1)[0]
            self.assertTrue(finding.startswith(f"**{SANDBOX_OFF}** "), finding)
            self.assertIn(f"*Rule `unrestricted_filesystem` · setting `config-{number}:sandbox_mode` = ", finding)
        self.assertEqual(anchor("Not checked"), "not-checked")
        self.assertEqual(markdown.count("\n## Not checked\n"), 1)
        # Saved page: each link's target is one element's id, and the finding that follows it is that file's.
        page = Targets(render(report, "html"))
        self.assertEqual([link for link in page.links if link.startswith("#")],
                         ["#finding-1", "#finding-2", "#not-checked"])
        for target in ("finding-1", "finding-2", "not-checked"):
            self.assertEqual(page.ids.count(target), 1)
        self.assertLess(page.ids.index("finding-1"), page.ids.index("finding-2"))
        self.assertLess(page.ids.index("finding-2"), page.ids.index("not-checked"))
        for number in (1, 2):
            self.assertIn(f"config-{number}:sandbox_mode", page.text[f"finding-{number}"])
            self.assertNotIn(f"config-{3 - number}:sandbox_mode", page.text[f"finding-{number}"])
        self.assertTrue(page.text["not-checked"].startswith("Not checked"))
        # One file, one title: no label (the first test shows the whole line).
        self.assertEqual(listed(render(self.report(SANDBOX_ONLY), "markdown")),
                         [(GROUP_1, 1, f"[{SANDBOX_OFF}](#finding-1)")])

    def test_groups_3_and_not_ranked_only_give_the_files_read_and_one_sentence_for_each_of_those_groups(self):
        # A default run, as in the issue's example: both files exist where Codex keeps them.
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

    def test_no_findings_show_the_first_and_third_paragraphs_and_the_not_safe_sentence_without_a_list(self):
        markdown = render(self.report(QUIET + 'profile = "work"\n'), "markdown")
        self.assertEqual(markdown.split("\n\n## Not checked\n", 1)[0].split("\n\n"), [
            "# Codex configuration diagnostic",
            "0 findings, 1 thing not checked.",
            "stay-safe read one file: your Codex settings (`config-1`). This report describes what that file says, "
            "without running any tests in Codex.",
            "1 part of your setup could not be verified because it is missing from that file or outside what "
            "stay-safe covers. stay-safe flagged it for you to review.",
            "## Findings",
            NO_FINDINGS])
        self.assertNotIn("#finding", markdown)
        self.assertNotIn("#not-checked", markdown)
        plain = render(self.report(QUIET + 'profile = "work"\n'), "plain")
        self.assertIn("\nstay-safe read one file: your Codex settings (config-1). This report describes what that "
                      "file says, without running any tests in Codex.\n", plain)
        self.assertNotIn("risky setting", plain)
        self.assertNotIn(LEAD_IN, plain)

    def test_a_selected_file_that_could_not_be_read_is_not_named_among_the_files_read(self):
        report = inspect([self.config(QUIET, "read.toml"), self.root / "missing.toml"],
                         rules_path=self.root / "missing.rules")
        self.assertEqual(len(report["inspection_gaps"]), 2)
        self.assertEqual(overview(render(report, "markdown")), [
            "0 findings, 2 things not checked.",
            "stay-safe read one file: your Codex settings (`config-1`). This report describes what that file says, "
            "without running any tests in Codex.",
            "2 parts of your setup could not be verified because they are missing from that file or outside what "
            "stay-safe covers. stay-safe flagged them for you to review."])

    def test_names_with_markdown_or_html_characters_are_escaped_in_the_list_and_links_stay_https_or_own(self):
        # Codex's own names cannot hold these characters today (stay_safe/codex.py NAME), so this sets entry
        # names on a report, as tests/share_without_exposing_secrets/test_page.py does.
        names = ["<b>bold</b>", "*x*", "[x](javascript:alert(1))", "a](https://example.com/)[b", "<script>alert(1)</script>",
                 "tick`[y](https://example.com/)"]
        report = self.report(QUIET + "".join(f'[mcp_servers.s{index}]\ncommand = "seed-command"\n'
                                             for index in range(len(names))))
        programs = [risk for risk in report["risks"] if risk["rule"] == "configured_program"]
        self.assertEqual(len(programs), len(names))
        for risk, name in zip(programs, names):
            risk["entry"] = f"config-1:mcp_servers.{json.dumps(name)}"
        markdown, plain, html = (render(report, name) for name in ("markdown", "plain", "html"))
        # A name is code text inside its line's one link. A backtick would end code text early, so a name with
        # one is written with character references instead.
        written = [f"`{name}`" for name in names[:5]] + [
            "tick&#96;&#91;y&#93;&#40;https&#58;&#47;&#47;example&#46;com&#47;&#41;"]
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
        own = [f"#finding-{number}" for number in range(1, len(report["risks"]) + 1)] + ["#not-checked"]
        # The list and the line after it hold exactly the links to the page's own findings and Not checked section.
        self.assertEqual(page.overview_links, own)
        self.assertEqual([link for link in page.links if not link.startswith("https://")], own)
        for link in own:
            self.assertEqual(page.ids.count(link[1:]), 1)

    def test_the_report_guide_lists_each_group_with_its_rules_in_order_and_their_incidents(self):
        guide = (ROOT / "docs" / "report.md").read_text(encoding="utf-8")
        rows = [[cell.strip() for cell in line.strip("|").split("|")]
                for line in section(guide, "The order of findings").splitlines() if line.startswith("| ")]
        self.assertEqual(rows[0], ["Group", "Heading in the report", "Rule", "Reported incidents"])
        # Groups, headings and rule order from issue #82; each rule's incidents from stay_safe/rules.py.
        self.assertEqual([[row[0], row[1], row[2], re.findall(r"\[(I\d+)\]\(\.\./incidents\.md#", row[3])]
                          for row in rows[2:]], [
            ["1", GROUP_1.strip("*"), "`unrestricted_filesystem`", ["I1", "I3"]],
            ["1", GROUP_1.strip("*"), "`commands_without_prompts`", ["I2", "I3", "I24"]],
            ["1", GROUP_1.strip("*"), "`saved_approval`", ["I26"]],
            ["2", GROUP_2.strip("*"), "`destructive_tools`", ["I7", "I8"]],
            ["2", GROUP_2.strip("*"), "`network_access`", ["I15", "I21"]],
            ["2", GROUP_2.strip("*"), "`environment_inheritance`", ["I23"]],
            ["2", GROUP_2.strip("*"), "`automatic_tools`", ["I15", "I20"]],
            ["3", GROUP_3.strip("*"), "`configured_program`", ["I13", "I14", "I19"]],
            ["Not ranked", NOT_RANKED.strip("*"), "`self_described_tools`", ["I15", "I21"]]])


class UnchangedTests(ConfigCase):
    """These hold before and after issue #82: they also pass on the commit the change starts from."""

    def test_the_json_report_keeps_its_order_and_identities_and_the_exit_status_follows_gaps_only(self):
        quiet = self.config('notify = ["seed-notify"]\n' + SANDBOX_ONLY, "quiet.toml")
        gap = self.config('notify = ["seed-notify"]\n' + SANDBOX_ONLY + 'profile = "work"\n', "gap.toml")
        for path, status, gaps in ((quiet, 0, []), (gap, 2, ["config-1: Profiles are outside reader coverage; a selected "
                                                           "profile can override the reported settings."])):
            with self.subTest(status=status):
                runs = [subprocess.run([sys.executable, "-B", "-m", "stay_safe", "--config", str(path), "--format", name],
                                       cwd=ROOT, env={}, text=True, capture_output=True, timeout=10)
                        for name in ("json", "markdown")]
                self.assertEqual([(run.returncode, run.stderr) for run in runs],
                                 [(status, INCOMPLETE if status else "")] * 2)
                report = json.loads(runs[0].stdout)
                self.assertEqual(sorted(report), ["catalog", "file_inspection", "format_version", "harness",
                                                  "incident_links", "incident_status", "inspection_gaps", "provenance",
                                                  "risks", "scope"])
                self.assertEqual(report["format_version"], 3)
                self.assertEqual([(risk["rule"], risk["entry"], risk["incidents"]) for risk in report["risks"]],
                                 [("configured_program", "config-1:notify", ["I13", "I14", "I19"]),
                                  ("unrestricted_filesystem", "config-1:sandbox_mode", ["I1", "I3"])])
                self.assertEqual(sorted(report["risks"][0]), ["configured_evidence", "entry", "explanation", "incidents",
                                                              "interpretation_source", "rule", "rule_source"])
                self.assertEqual(report["inspection_gaps"], gaps)
                revision = report["provenance"]["source_revision"]
                source = f"https://github.com/chalkbadger/stay-safe/blob/{revision}/"
                self.assertEqual(section(runs[1].stdout, "Sources"), "\n".join([
                    f"- [How each finding's rule is defined]({source}stay_safe/rules.py) (`stay_safe/rules.py`)",
                    f"- [What each Codex setting means, with official evidence]({source}harnesses/codex.md) "
                    "(`harnesses/codex.md`)"]))
                self.assertTrue(runs[1].stdout.endswith(
                    f"Made by stay-safe `{revision[:7]}` · report format 3 · [Report a problem or suggest an idea]"
                    "(https://github.com/chalkbadger/stay-safe/issues/new/choose)\n"))
                if not gaps:
                    self.assertEqual(section(runs[1].stdout, "Not checked"),
                                     "stay-safe checked every setting it supports in the files it read. "
                                     "What this report can't see, below, still applies.")
