import json

from stay_safe.report import inspect, render
from tests.nothing_in_my_setup_changes.test_page import Page, markdown_view
from tests.overview_lists_findings_first.test_report_layout import AFTER
from tests.support import ConfigCase


class SavedPageNameTests(ConfigCase):
    def test_names_with_html_characters_are_shown_as_written_not_as_markup(self):
        report = inspect([self.config(AFTER)])
        names = ["<script>alert(1)</script>", "a&amp;b <img src=x onerror=alert(1)>", "it's \"quoted\"",
                 "[x](javascript:alert(1))", "[y](data:text/html,<b>z</b>)", "*x*", "[x](#other)"]
        report["catalog"] += [{"id": f"config-1:{name}", "source": "config-1", "name": name, "kind": "MCP server",
                               "observations": [name]} for name in names]
        report["risks"][1]["entry"] = "config-1:mcp_servers.<b>"
        markdown, page = render(report, "markdown"), render(report, "html")
        parsed = Page(page)
        self.assertNotIn("#other", parsed.links)
        self.assertEqual(parsed.view(), markdown_view(markdown))
        self.assertEqual([tag for tag, _ in parsed.tags if tag in {"script", "img", "b"}], [])
        self.assertEqual([href for href in parsed.links if not href.startswith("https://")],
                         ["#finding-1", "#finding-2", "#finding-3", "#finding-4", "#not-checked"])
        text = " ".join(parsed.view()["words"])
        for name in names:
            self.assertIn(" ".join(name.split()), text)
        self.assertIn("config-1:mcp_servers.<b>", parsed.view()["code"])
        self.assertEqual(json.loads(render(report, "json"))["catalog"][-1]["name"], names[-1])
