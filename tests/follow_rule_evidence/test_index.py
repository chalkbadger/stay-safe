import copy
import json
import re
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from stay_safe.report import inspect, render
from stay_safe.rules import RULES
from tests.support import ConfigCase, ROOT

REPO = 'https://github.com/chalkbadger/stay-safe'
REVISION = '1234567890abcdef1234567890abcdef12345678'
CODEX = '/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/'
NOTES = {
    'network_access': {'rules': ['unrestricted_filesystem'], 'incidents': ['I15', 'I21'], 'external': []},
    'commands_without_prompts': {'rules': [], 'incidents': ['I2', 'I3'], 'external': [
        ('/chalkbadger/stay-safe/issues/141', ''),
        (CODEX + 'core/src/exec_policy.rs', 'L897-L925'),
        (CODEX + 'shell-command/src/command_safety/is_dangerous_command.rs', '')]},
}
FIELDS = ('- Settings:', '- Incidents:', '- Citations support:', '- Challenges:', '- [Challenge this rule](')


class RuleIndexTests(ConfigCase):
    def test_index_matches_rules_incidents_and_resolvable_links(self):
        index = ROOT / 'docs/rules.md'
        self.assertTrue(index.is_file(), 'The rule index is missing')
        self.assertTrue((ROOT / '.github/ISSUE_TEMPLATE/challenge.yml').is_file(), 'Challenge form is missing')
        form = json.loads((ROOT / '.github/ISSUE_TEMPLATE/challenge.yml').read_text())
        self.assertEqual(form.get('labels'), ['challenge'])
        finding = [field for field in form['body'] if field.get('id') == 'finding']
        self.assertEqual(len(finding), 1, 'The index prefills the finding field')
        self.assertEqual((finding[0]['type'], finding[0]['validations']['required']), ('textarea', True))
        parts = re.split(r'^## (.+)\n', index.read_text(), flags=re.M)
        ids = parts[1::2]
        self.assertCountEqual(ids, [rule.id for rule in RULES])
        sections = dict(zip(ids, parts[2::2]))
        meanings = (ROOT / 'harnesses/codex.md').read_text().splitlines()
        for rule in RULES:
            with self.subTest(rule=rule.id):
                section = sections[rule.id]
                bullets = [line for line in section.splitlines() if line.startswith('- ')]
                fields = [next((f for f in FIELDS if line.startswith(f)), line) for line in bullets]
                expected = [f for f in FIELDS if rule.id in NOTES or f != '- Citations support:']
                self.assertEqual(fields, expected, 'Bullet fields in ' + rule.id)
                incidents = next(line for line in bullets if line.startswith('- Incidents:'))
                cited = dict(re.findall(r'\[(I\d+)\]\(([^)\n]+)\)', incidents))
                self.assertCountEqual(re.findall(r'\[(I\d+)\]\(', incidents), rule.incidents)
                note_sources = []
                if rule.id in NOTES:
                    note = next(line for line in bullets if line.startswith('- Citations support:'))
                    links = re.findall(r'\[([^\]\n]+)\]\(([^)\n]+)\)', note)
                    self.assertCountEqual([text for text, link in links if re.fullmatch(r'I\d+', text)],
                                          NOTES[rule.id]['incidents'])
                    for text, link in links:
                        if re.fullmatch(r'I\d+', text):
                            self.assertEqual(link, cited[text], 'Note links its incident as cited')
                    self.assertCountEqual([link for _, link in links if link.startswith('#')],
                                          ['#' + name for name in NOTES[rule.id]['rules']])
                    for name in NOTES[rule.id]['rules']:
                        self.assertIn(f'[`{name}`](#{name})', note)
                        self.assertIn(name, ids)
                    note_sources = NOTES[rule.id]['external']
                if rule.id != 'saved_approval':
                    settings = next(line for line in section.splitlines() if line.startswith('- Settings:'))
                    rows = {line.split('|')[1].strip(' `') for line in meanings
                            if line.startswith('| `') and 'Rules:' in line
                            and f'`{rule.id}`' in line.split('Rules:')[1].split('Gap:')[0]}
                    self.assertEqual(set(re.findall(r'`([^`]+)`', settings)), rows)

                links = re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', section)
                self.assertEqual(len(links), section.count(']('), 'Malformed link in ' + rule.id)
                self.assertTrue(any(link.startswith('../harnesses/codex.md') for link in links))
                external = []
                for link in links:
                    target = urlsplit(link)
                    if target.scheme:
                        self.assertEqual((target.scheme, target.netloc), ('https', 'github.com'))
                        if target.path.startswith('/chalkbadger/stay-safe/issues') and target.query:
                            external.append((target.path, parse_qs(target.query)))
                            self.assertEqual(target.fragment, '')
                        else:
                            self.assertIn((target.path, target.fragment), note_sources, link)
                            external.append((target.path, target.fragment))
                        continue
                    file = (index.parent / target.path).resolve() if target.path else index.resolve()
                    self.assertTrue(file.is_relative_to(ROOT.resolve()) and file.is_file(), link)
                    if target.fragment:
                        headings = re.findall(r'^#+ (.+)$', file.read_text(), re.M)
                        anchors = [re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-') for h in headings]
                        self.assertIn(target.fragment, anchors, link)
                self.assertCountEqual(external, [
                    ('/chalkbadger/stay-safe/issues', {'q': [
                        f'is:issue label:challenge {rule.id} in:title,body']}),
                    ('/chalkbadger/stay-safe/issues/new', {
                        'template': ['challenge.yml'], 'finding': ['Rule ' + rule.id]}),
                ] + note_sources)

    def test_saved_approval_links_to_both_incident_entries_in_the_report_and_index(self):
        rules = self.config('prefix_rule(pattern=["synthetic"], decision="allow")\n', 'default.rules')
        report = inspect([], rules_path=rules)
        revision = report['provenance']['source_revision']
        output = render(report, 'markdown')
        index = (ROOT / 'docs/rules.md').read_text().split('## saved_approval\n', 1)[1].split('\n## ', 1)[0]
        for incident, anchor in (
                ('I26', 'i26-saved-command-approval-persisted-across-sessions-and-workspaces'),
                ('I30', 'i30-railway-credentials-printed-in-a-claude-code-transcript')):
            with self.subTest(incident=incident):
                target = f'incidents.md#{anchor}'
                self.assertIn(f'[{incident}]({REPO}/blob/{revision}/{target})', output)
                self.assertIn(f'[{incident}](../{target})', index)

    def test_readable_rule_links_follow_revision_and_unknown_stays_plain(self):
        config = self.config('approval_policy="never"\nsandbox_mode="danger-full-access"\n'
                             'notify=["private-command"]\n[mcp_servers.example]\nurl="https://example.invalid"\n'
                             '[apps.files]\ndefault_tools_approval_mode="approve"\n')
        network = self.config('approval_policy="on-request"\nsandbox_mode="workspace-write"\n'
                              '[sandbox_workspace_write]\nnetwork_access=true\n', 'network.toml')
        rules = self.config('prefix_rule(pattern=["synthetic"], decision="allow")\n', 'default.rules')
        for revision in (REVISION, None):
            with self.subTest(revision=revision), patch('stay_safe.report.identify', return_value={
                    'source_revision': revision, 'source_status': 'checkout commit' if revision else None,
                    'tool_revision': 'test', 'rules_revision': 'test', 'local_modifications': 'not checked'}):
                report = inspect([config, network], rules_path=rules)
                self.assertEqual({risk['rule'] for risk in report['risks']}, {
                    'saved_approval', 'commands_without_prompts', 'unrestricted_filesystem', 'configured_program',
                    'automatic_tools', 'destructive_tools', 'network_access', 'self_described_tools',
                    'environment_inheritance'})
                before = copy.deepcopy(report)
                for format_name in ('markdown', 'html', 'plain'):
                    output = render(report, format_name)
                    for risk in report['risks']:
                        rule = risk['rule']
                        url = f'{REPO}/blob/{revision}/docs/rules.md#{rule}'
                        if revision:
                            expected = {'markdown': f'Rule [`{rule}`]({url}) ·',
                                        'html': f'Rule <a href="{url}"><code>{rule}</code></a> ·',
                                        'plain': f'Rule {rule} ({url}) ·'}[format_name]
                        else:
                            expected = {'markdown': f'Rule `{rule}` ·',
                                        'html': f'Rule <code>{rule}</code> ·',
                                        'plain': f'Rule {rule} ·'}[format_name]
                            self.assertNotIn('docs/rules.md#', output)
                        self.assertIn(expected, output)
                self.assertEqual(report, before)
                self.assertEqual(json.loads(render(report, 'json')), before)
