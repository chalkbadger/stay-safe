"""Names on the saved page are shown as written, never as markup or links.

Page and markdown_view, which read the page and the Markdown report, live with the other saved-page checks in
tests/nothing_in_my_setup_changes/test_page.py.
"""

import json

from stay_safe.report import inspect, render
from tests.nothing_in_my_setup_changes.test_page import Page, markdown_view
from tests.see_every_connection_and_setting.test_report_order import AFTER
from tests.support import ConfigCase


class SavedPageNameTests(ConfigCase):
    def test_names_with_html_characters_are_shown_as_written_not_as_markup(self):
        # Codex's own names cannot hold these characters today (stay_safe/codex.py NAME); the page must still
        # show any name as text, so this sets entry names directly on a report.
        report = inspect([self.config(AFTER)])
        names = ["<script>alert(1)</script>", "a&amp;b <img src=x onerror=alert(1)>", "it's \"quoted\"",
                 "[x](javascript:alert(1))", "[y](data:text/html,<b>z</b>)", "*x*"]
        report["catalog"] += [{"id": f"config-1:{name}", "source": "config-1", "name": name, "kind": "MCP server",
                               "observations": [name]} for name in names]
        report["risks"][1]["entry"] = "config-1:mcp_servers.<b>"
        markdown, page = render(report, "markdown"), render(report, "html")
        parsed = Page(page)
        self.assertEqual(parsed.view(), markdown_view(markdown))
        self.assertEqual([tag for tag, _ in parsed.tags if tag in {"script", "img", "b"}], [])
        self.assertEqual([href for href in parsed.links if not href.startswith("https://")], [])
        text = " ".join(parsed.view()["words"])
        for name in names:
            self.assertIn(" ".join(name.split()), text)
        self.assertIn("config-1:mcp_servers.<b>", parsed.view()["code"])
        self.assertEqual(json.loads(render(report, "json"))["catalog"][-1]["name"], names[-1])
