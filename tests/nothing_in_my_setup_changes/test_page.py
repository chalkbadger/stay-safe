"""The saved page holds the Markdown report's content and loads nothing (archived issue #106).

The Markdown report is the reference: each check reads the page with Python's HTML parser and compares what a
browser would show with what the Markdown report says, read with the Markdown rules in markdown_view below.
"""

from html import unescape
from html.parser import HTMLParser
import re

from tests.see_every_connection_and_setting.test_report_order import AFTER
from tests.support import FIRST, SECOND, ConfigCase, REPORT, copy_checkout, run_checkout
from tests.findings_say_what_to_do.test_plain_findings import EXPECTED, RULES
from tests.see_every_connection_and_setting.test_plain_gaps import PLAIN

# What the page may contain: document structure, text elements and links (HTML Living Standard element index,
# https://html.spec.whatwg.org/multipage/indices.html#elements-3). None of these runs code or loads a resource;
# an `a` element navigates only when clicked, and its target must be https.
ALLOWED = {"html": {"lang"}, "head": set(), "meta": {"charset", "http-equiv", "content", "name"}, "title": set(),
           "style": set(), "body": set(), "h1": set(), "h2": set(), "hr": set(), "p": set(), "br": set(),
           "strong": set(), "em": set(), "code": set(), "a": {"href"}, "ul": set(), "li": set()}
# A second layer: the page tells the browser to load nothing and allow only its own inline style.
POLICY = "default-src 'none'; style-src 'unsafe-inline'"
# Elements with no end tag (https://html.spec.whatwg.org/multipage/syntax.html#void-elements).
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Phrasing elements, which do not separate words (https://html.spec.whatwg.org/multipage/dom.html#phrasing-content).
INLINE = {"a", "abbr", "b", "code", "em", "i", "kbd", "mark", "q", "s", "samp", "small", "span", "strong", "sub",
          "sup", "u", "var"}
# A word that stands for a horizontal rule in both readings; text can't produce it.
RULE = "\x00rule"
LINK = re.compile(r"\[([^\]\n]*)\]\((https://[^)\s]*)\)")


class Page(HTMLParser):
    """What a browser shows from a page's body, and every tag and attribute in the page."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.words, self.links, self.strong, self.em, self.code, self.tags, self.styles = [], [], [], [], [], [], []
        self.open, self.body = [], False
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))
        self.body = self.body or tag == "body"
        if tag not in VOID:
            self.open.append([tag, ""])
        if tag == "a":
            self.links.append(dict(attrs).get("href"))
        if tag not in INLINE:
            self.words.append(f" {RULE} " if tag == "hr" else " ")

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, attrs))
        self.words.append(f" {RULE} " if tag == "hr" else " ")

    def handle_endtag(self, tag):
        if tag not in INLINE:
            self.words.append(" ")
        while self.open:
            name, text = self.open.pop()
            if self.open:
                self.open[-1][1] += text
            if name == "strong":
                self.strong.append(text)
            elif name == "em":
                self.em.append(text)
            elif name == "code":
                self.code.append(text)
            if name == tag:
                break

    def handle_data(self, data):
        if self.open and self.open[-1][0] == "style":
            self.styles.append(data)
        if self.body:
            self.words.append(data)
            if self.open:
                self.open[-1][1] += data

    def view(self):
        return {"words": "".join(self.words).split(), "links": self.links, "strong": self.strong, "em": self.em,
                "code": self.code}


def markdown_view(text):
    """The words, link targets, bold, italic and code text a Markdown previewer shows for the report.

    Headings (`#`) and list items (`- `) are block markers, not words; a horizontal rule (`---`) is the word RULE.
    Code spans come first, as in Markdown: their text is kept as written, and `**` (bold), `*` (italic), links and
    entities such as &#124; are read only outside them.
    """
    words, links, strong, em, code = [], [], [], [], []
    for line in text.splitlines():
        if line == "---":
            words.append(RULE)
            continue
        line = re.sub(r"^(#+|-) ", "", line)
        spans = []

        def hold(found):
            spans.append(found[1])
            return f"\x01{len(spans) - 1}\x02"

        outside = re.sub(r"`([^`\n]*)`", hold, line)
        code += spans
        restore = lambda value: re.sub(r"\x01(\d+)\x02", lambda found: spans[int(found[1])], value)
        links += [m[2] for m in LINK.finditer(outside)]
        outside = LINK.sub(lambda m: m[1], outside)
        strong += [restore(unescape(s)) for s in re.findall(r"\*\*(.+?)\*\*", outside)]
        single = outside.replace("**", "")
        em += [restore(unescape(s)) for s in re.findall(r"\*(.+?)\*", single)]
        words += restore(unescape(single.replace("*", ""))).split()
    return {"words": words, "links": links, "strong": strong, "em": em, "code": code}


class SavedPageTests(ConfigCase):
    def saved(self, *texts, rules=None):
        checkout = copy_checkout(self.root / "checkout")
        work = self.root / "work"
        work.mkdir()
        args = [a for i, t in enumerate(texts) for a in ("--config", str(self.config(t, f"config-{i}.toml")))]
        if rules:
            args += ["--rules", str(self.config(rules, "selected.rules"))]
        markdown = run_checkout(checkout, *args, cwd=work)
        saved = run_checkout(checkout, *args, "--save", cwd=work)
        self.assertEqual((saved.returncode, saved.stderr), (markdown.returncode, markdown.stderr))
        return markdown.stdout, (checkout / REPORT).read_text(encoding="utf-8")

    def test_saved_page_shows_the_markdown_reports_words_links_bold_and_code_text(self):
        # Every rule, every kind of entry, gaps with and without a source label, and source and incident links.
        markdown, page = self.saved(FIRST, SECOND, AFTER, rules=RULES)
        expected = markdown_view(markdown)
        self.assertIn("https://github.com/chalkbadger/stay-safe/blob/0123456789abcdef0123456789abcdef01234567/"
                      "incidents.md#i13-repository-settings-run-commands-on-collaborators-machines", expected["links"])
        github = EXPECTED[("configured_program", "config-1:mcp_servers.github")]
        self.assertIn(re.match(r"\*\*(.+?)\*\*", github)[1].replace("`", ""), expected["strong"])
        profiles = PLAIN["Profiles are outside reader coverage; a selected profile can override the reported settings."]
        self.assertIn(re.match(r"\*\*(.+?)\*\*", profiles)[1], expected["strong"])
        self.assertIn("How it has gone wrong:", expected["em"])
        self.assertIn("https://github.com/chalkbadger/stay-safe/issues/new/choose", expected["links"])
        self.assertEqual(Page(page).view(), expected)

    def test_found_file_labels_and_name_placeholders_show_as_text(self):
        # A default run names found files `~/.codex/...` or `$CODEX_HOME/...` (archived issue #105), and Your setup's note on left-out
        # values shows `[mcp_servers.<name>]`; on the page each must be code text, not markup or the expanded folder.
        # Both Codex homes are temporary folders, so plugin discovery never reads the real home. One has a plugin in
        # plugins/cache and an invalid features.apps (two gaps); the other leaves features.apps out, which names
        # the ChatGPT Apps connection (archived PR #118, archived issue #121).
        self.require_no_system_folder()
        checkout = copy_checkout(self.root / "checkout")
        home, codex_home, work = self.root / "home", self.root / "codex-home", self.root / "work"
        work.mkdir()
        base = 'approval_policy = "never"\n[mcp_servers.github]\ncommand = "x"\n'
        (home / ".codex" / "plugins" / "cache" / "market" / "plugin" / "1.0").mkdir(parents=True)
        (home / ".codex" / "config.toml").write_text('features = { apps = "yes" }\n' + base)
        codex_home.mkdir()
        (codex_home / "config.toml").write_text(base)
        cases = [({"HOME": str(home)}, "~/.codex"), ({"HOME": str(home), "CODEX_HOME": str(codex_home)}, "$CODEX_HOME")]
        expected = {"~/.codex": [PLAIN[m] for m in ("Codex home: plugins/cache holds Codex plugins that were not inspected.",
                                                    "features.apps has an invalid boolean; its behavior is unknown.")],
                    "$CODEX_HOME": ["ChatGPT Apps connection:"]}
        for env, label in cases:
            with self.subTest(label=label):
                markdown = run_checkout(checkout, cwd=work, env=env)
                saved = run_checkout(checkout, "--save", cwd=work, env=env)
                self.assertEqual((saved.returncode, saved.stderr), (markdown.returncode, markdown.stderr))
                page = (checkout / REPORT).read_text(encoding="utf-8")
                parsed = Page(page)
                self.assertEqual(parsed.view(), markdown_view(markdown.stdout))
                for code in (f"{label}/config.toml", f"{label}/rules/default.rules", "[mcp_servers.<name>]"):
                    self.assertIn(code, parsed.view()["code"])
                for lead in expected[label]:
                    if lead.startswith("**"):
                        self.assertIn(re.match(r"\*\*(.+?)\*\*", lead)[1].replace("`", ""), parsed.view()["strong"])
                    else:
                        self.assertIn(lead, " ".join(parsed.view()["words"]))
                self.assertNotIn("name", [tag for tag, _ in parsed.tags])
                for folder in (str(home), str(codex_home)):
                    self.assertNotIn(folder, page)

    def test_saved_page_has_no_script_and_loads_nothing_from_outside_the_file(self):
        _, page = self.saved(FIRST, SECOND, AFTER, rules=RULES)
        parsed = Page(page)
        self.assertTrue(page.startswith("<!DOCTYPE html>"))
        for tag, attrs in parsed.tags:
            with self.subTest(tag=tag, attrs=attrs):
                self.assertIn(tag, ALLOWED)
                self.assertLessEqual({name for name, _ in attrs}, ALLOWED[tag])
                for name, value in attrs:
                    if name == "href":
                        self.assertRegex(value, r"^https://")
                    if tag == "meta" and name == "http-equiv":
                        # HTML matches http-equiv values case-insensitively; attribute order doesn't matter.
                        self.assertEqual((value.lower(), dict(attrs).get("content")), ("content-security-policy", POLICY))
        self.assertEqual([dict(a).get("content") for t, a in parsed.tags
                          if t == "meta" and (dict(a).get("http-equiv") or "").lower() == "content-security-policy"],
                         [POLICY])
        for style in parsed.styles:
            self.assertNotRegex(style.lower(), r"url\(|@import|expression\(")
