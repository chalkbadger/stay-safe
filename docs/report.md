# Reading the report

The [default terminal view](../contracts/claims.md#reads_plain_terminal_report-i-can-read-the-default-terminal-report-without-markdown-formatting-and-see-how-to-save-a-formatted-page) uses plain text.
Use `--format markdown` for Markdown or `--save` for a formatted HTML page.

## The parts of a report

The report opens with a count of findings and of things stay-safe could not check.
An introduction follows: the files stay-safe read, the number of findings in each
group, and the number of parts it could not verify. Then a numbered list gives every
finding's title under its group's heading, in [the order of findings](#the-order-of-findings),
and one line gives the count of things not checked. When stay-safe read more than
one file, each list line ends with its file label, such as `config-2`. In Markdown and on
the saved page, a list line links to its detailed finding; in the terminal, look for
the same number, such as `Finding 3`.
The detailed findings come next, in the list's order. Each finding says what it means for you, how it has gone wrong in reported incidents
and what to do, then ends with one line giving its rule ID, entry ID and configured
values. What to do gives a lower-friction option where the
[meanings table](../harnesses/codex.md) backs one, a stricter one, and how to change it; some
findings add a Check that changes nothing. Each thing not checked says what is missing, why and what to do, followed by
its source label, such as `config-1`, when it has one. Then come your setup in plain
words, links to the rules and meanings sources, and what the report can't see, with a
link to the [full scope](#full-scope). The JSON report (`--format json`) keeps the catalog, full scope
and fingerprints in their original form.

## The order of findings

Each rule belongs to one group, fixed by what the rule's condition removes, as its
cited incidents show. The list and the detailed findings follow the rows below from
top to bottom; inside a rule, findings follow the order of the files, then the
setting name. A group with no findings is left out. The order is not a score, and
the JSON report keeps its own order.

| Group | Heading in the report | Rule | Reported incidents |
| --- | --- | --- | --- |
| 1 | Nothing stands between a mistaken or injected instruction and your computer | `unrestricted_filesystem` | [I1](../incidents.md#i1-home-directory-deleted-by-rm--rf), [I3](../incidents.md#i3-windows-drive-wiped) |
| 1 | Nothing stands between a mistaken or injected instruction and your computer | `commands_without_prompts` | [I2](../incidents.md#i2-home-directory-added-to-a-delete-command), [I3](../incidents.md#i3-windows-drive-wiped), [I24](../incidents.md#i24-driver-update-followed-by-boot-and-network-failures) |
| 1 | Nothing stands between a mistaken or injected instruction and your computer | `saved_approval` | [I26](../incidents.md#i26-saved-command-approval-persisted-across-sessions-and-workspaces) |
| 2 | Harm is limited to one channel or service | `destructive_tools` | [I7](../incidents.md#i7-production-volumes-deleted-with-a-found-token), [I8](../incidents.md#i8-database-changes-after-an-order-to-stop) |
| 2 | Harm is limited to one channel or service | `network_access` | [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I21](../incidents.md#i21-issue-content-steered-an-agent-toward-workflow-secrets) |
| 2 | Harm is limited to one channel or service | `environment_inheritance` | [I23](../incidents.md#i23-production-tables-dropped-by-a-dev-only-migration-command) |
| 2 | Harm is limited to one channel or service | `automatic_tools` | [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I20](../incidents.md#i20-injected-text-turned-off-approvals) |
| 3 | Something else has to be tampered with first | `configured_program` | [I13](../incidents.md#i13-repository-settings-run-commands-on-collaborators-machines), [I14](../incidents.md#i14-readme-injection-bypassed-a-command-allowlist), [I19](../incidents.md#i19-worm-persisted-through-agent-startup-hooks) |
| Not ranked | Based on Codex's source code and not yet seen in a live run, so stay-safe has no basis to rank these. That does not make them minor. | `self_described_tools` | [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I21](../incidents.md#i21-issue-content-steered-an-agent-toward-workflow-secrets) |

## Entry IDs

Entry IDs are configuration keys, such as `mcp_servers.github`, prefixed with
`config-1`, `config-2`, and so on in the order of `--config` arguments.
In the text and Markdown reports, files found automatically are named by where Codex keeps them,
such as `~/.codex/config.toml` or `$CODEX_HOME/config.toml`, never by your own folder.
Saved approvals use `rules-1:prefix_rule.N`, where N is the physical line number
in the selected rules file.

## The commit, and release archives

A last line names the stay-safe commit and
report format. In a release zip, which has no Git history, the commit is read from
`stay_safe/release.txt`, which GitHub fills in when it builds the zip, and is marked
"(release archive)".

## Configuration names

Configuration names, such as server, app, tool and provider names, are shown as
written, and a name can itself be private, such as `mcp_servers.acme-merger`.
Review them before sharing the report.

## Where the claims come from

[stay-safe's claims](../contracts/claims.md) state, one by one, what you notice when using
stay-safe; under each claim, each line names the test that proves it. The
[Codex meanings table](../harnesses/codex.md) gives each interpreted setting, its source and
status. Each risk rule in `stay_safe/rules.py` cites [reported incidents](../incidents.md).

## Full scope

The report's "What this report can't see" section summarizes these limits. In full
("the catalog" is the JSON report's name for Your setup):

- Selected files are independent snapshots; other rules files are not read or merged.
- Rules inspection lists saved-format approval candidates, one-line allow records whose syntax context and current effect are not checked; other lines, including prompt and forbidden rules that may override a candidate, make the check incomplete.
- CLI flags, profile selection, trusted project layers, managed policies and runtime overrides are not inspected.
- Connection reachability, authentication, active tools and effective permissions are not tested.
- Source links point to the reported commit; whether that commit exists in the published GitHub repository is not checked.
- The catalog contains configured entries, documented defaults and source-status observations; account, endpoint, environment, saved approval command (except a first word on stay-safe's program list) and other command and argument values are withheld.
- Configuration names in the report, such as server, app, tool and provider names, are shown as written and should be reviewed before sharing.
- Local modifications to the checkout or unzipped release are not checked; the JSON report's `tool_revision` and `rules_revision` fingerprints identify the files that ran.
