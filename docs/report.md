# Reading the report

The default terminal view uses plain text.
Use `--format markdown` for Markdown or `--save` for a formatted HTML page.

## The parts of a report

The report opens with a count of findings and of things stay-safe could not check.
An introduction follows: the files stay-safe read, the number of findings in each
group, and the number of parts it could not verify. Then a numbered list gives every
finding's title under its group's heading, in [the order of findings](#the-order-of-findings),
and, when checks are incomplete, one line gives the count of things not checked. When stay-safe read more than
one file, each list line ends with its file label, such as `config-2`. In a Markdown file rendered with heading anchors and on
the saved page, a list line links to its detailed finding. GitHub issue and PR comments
may omit heading anchors, so pasted reports use the matching finding numbers there.
In the terminal, look for the same number, such as `Finding 3`.
See [how the introduction reports an empty or comment-only file passed to `--rules`](../contracts/claims.md#understand_inspection_limits-i-can-tell-what-the-report-establishes-and-what-needs-further-checking).
When stay-safe cannot read any selected file, the introduction points to Not checked for the reason. Multiple config labels share one description.
The detailed findings come next, in the list's order. Each finding says what it means for you, how it has gone wrong in reported incidents
and what to do, then ends with one line giving its rule ID, entry ID and configured
values. What to do gives a lower-friction option where the
[meanings table](../harnesses/codex.md) backs one, a stricter one, and how to change it; some
findings add a Check that changes nothing. Each thing not checked says what is missing, why and what to do, followed by
its source label, such as `config-1`, when it has one. Then come your setup in plain
words, links to the rules and meanings sources, and what the report can't see, with a
link to the [full scope](#full-scope). The JSON report (`--format json`) keeps the catalog, full scope
and fingerprints in their original form.

## Example finding

This is the full finding from the [README example](../README.md), including the
change suggested for that configuration.

> **With these settings, Codex runs commands without asking you.** It won't ask before any command it's allowed to run, so injected or mistaken instructions could make it run code you didn't want.
>
> *How it has gone wrong:* Agents running commands without approval have run a delete command aimed at a home directory and wiped a drive. Another user reported an automatic driver update while getting help with GPU performance. [I2](https://github.com/chalkbadger/stay-safe/blob/v0.2.4/incidents.md#i2-home-directory-added-to-a-delete-command), [I3](https://github.com/chalkbadger/stay-safe/blob/v0.2.4/incidents.md#i3-windows-drive-wiped), [I24](https://github.com/chalkbadger/stay-safe/blob/v0.2.4/incidents.md#i24-driver-update-followed-by-boot-and-network-failures) (reported, not verified).
>
> *What to do:* If you want Codex to ask before running some commands it currently blocks, choose `approval_policy = "on-request"` and keep `sandbox_mode = "read-only"` (commands still can't write files). Ordinary commands can still run inside the sandbox without asking you. But commands a saved approval allows still run outside the sandbox.
>
> *Change it:* `approval_policy` near the top of the file, before any `[section]`, or ask Codex: "Edit `<config-1>` to set `approval_policy = "on-request"` without changing `sandbox_mode`; show only what you change."
>
> *Check:* Look for `approval_policy` and `sandbox_mode` in `<config-1>`.
>
> *Rule `commands_without_prompts` · setting `config-1:approval_policy` = `never`*

## The order of findings

Each rule belongs to one group, fixed by what the rule's condition removes, as its
cited incidents show. The list and the detailed findings follow the rows below from
top to bottom; inside a rule, findings follow the order of the files, then the
setting name. A group with no findings is left out. The order is not a score, and
the JSON report keeps its own order.

| Group | Heading in the report | Rule | Reported incidents |
| --- | --- | --- | --- |
| 1 | Nothing stands between a mistaken or injected instruction and your computer | `unrestricted_filesystem` | [I1](../incidents.md#i1-home-directory-deleted-by-rm--rf), [I3](../incidents.md#i3-windows-drive-wiped), [I32](../incidents.md#i32-powershell-cleanup-deleted-files-in-the-home-directory), [I20](../incidents.md#i20-injected-text-turned-off-approvals), [I33](../incidents.md#i33-intruders-changed-claude-code-project-settings-to-download-a-backdoor) |
| 1 | Nothing stands between a mistaken or injected instruction and your computer | `commands_without_prompts` | [I2](../incidents.md#i2-home-directory-added-to-a-delete-command), [I3](../incidents.md#i3-windows-drive-wiped), [I24](../incidents.md#i24-driver-update-followed-by-boot-and-network-failures) |
| 1 | Nothing stands between a mistaken or injected instruction and your computer | `saved_approval` | [I26](../incidents.md#i26-saved-command-approval-persisted-across-sessions-and-workspaces), [I30](../incidents.md#i30-railway-credentials-printed-in-a-claude-code-transcript) |
| 2 | Network access, credentials, and connected tools | `destructive_tools` | [I7](../incidents.md#i7-production-volumes-deleted-with-a-found-token), [I8](../incidents.md#i8-database-changes-after-an-order-to-stop) |
| 2 | Network access, credentials, and connected tools | `network_access` | [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I21](../incidents.md#i21-issue-content-steered-an-agent-toward-workflow-secrets) |
| 2 | Network access, credentials, and connected tools | `environment_inheritance` | [I23](../incidents.md#i23-production-tables-dropped-by-a-dev-only-migration-command) |
| 2 | Network access, credentials, and connected tools | `automatic_tools` | [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I20](../incidents.md#i20-injected-text-turned-off-approvals) |
| 3 | Something else has to be tampered with first | `configured_program` | [I13](../incidents.md#i13-repository-settings-run-commands-on-collaborators-machines), [I14](../incidents.md#i14-readme-injection-bypassed-a-command-allowlist), [I19](../incidents.md#i19-worm-persisted-through-agent-startup-hooks), [I33](../incidents.md#i33-intruders-changed-claude-code-project-settings-to-download-a-backdoor) |
| Not ranked | Based on Codex's source code and not yet seen in a live run, so stay-safe has no basis to rank these. That does not make them minor. | `self_described_tools`<br>`writable_project_settings` | [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I21](../incidents.md#i21-issue-content-steered-an-agent-toward-workflow-secrets)<br>[I20](../incidents.md#i20-injected-text-turned-off-approvals), [I33](../incidents.md#i33-intruders-changed-claude-code-project-settings-to-download-a-backdoor) |

## Entry IDs

Entry IDs are configuration keys, such as `mcp_servers.github`, prefixed with
`config-1`, `config-2`, and so on in the order of `--config` arguments.
In the text and Markdown reports, files found automatically are named by where Codex keeps them,
such as `~/.codex/config.toml` or `$CODEX_HOME/config.toml`, never by your own folder.
Saved approvals use `rules-1:prefix_rule.N`, where N is the physical line number
in the selected rules file.

### A saved tool-description flag

This synthetic [Snyk Agent Scan v0.7.1 fixture](../tests/see_every_connection_and_setting/pairing/saved-scan.json)
flags a tool description on `team.api` in `approve.toml`. Run this example from the
checkout root. Both Codex files name that server. Select `config-2` because
`approve.toml` is the second `--config`. The quotes in the entry ID keep the
dotted server name together. [Scanner JSON reference, read 2026-11-24](https://github.com/snyk/agent-scan/blob/a85612713593ab8beb1c0b6964eee954c1a498b0/docs/json-output.md#agent-scan-v06-and-later)

```sh
python3 - <<'PY'
import json
import subprocess
import sys
from pathlib import Path

samples = Path("tests/see_every_connection_and_setting/pairing")
saved = json.loads((samples / "saved-scan.json").read_text())
server, = saved["scan_path_responses"][0]["server_risks"]
report = json.loads(subprocess.check_output([
    sys.executable, "-m", "stay_safe", "--format", "json",
    "--config", samples / "prompt.toml", "--config", samples / "approve.toml",
]))
key = "config-2:mcp_servers." + json.dumps(server["name"])
entry, = (row for row in report["catalog"] if row["id"] == key)
approval, = (item for item in entry["observations"] if item.startswith("tool approval: "))
flag = "prompt_injection_tool_desc"
if flag in server["risk_indexes"]:
    print(server["name"], flag, approval, sep=" | ")
PY
```

The output is `team.api | prompt_injection_tool_desc | tool approval: approve`.
Review the flagged description alongside the server’s configured default when
deciding whether to change that setting.
[Challenge this description](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&title=Challenge%3A%20Snyk%20Agent%20Scan%20v0.7.1&disputed-claim=Snyk%20Agent%20Scan%20v0.7.1%20reports%20a%20tool-description%20flag%20in%20server_risks%5B%5D.risk_indexes.prompt_injection_tool_desc.)

## The commit, and release archives

A last line names the stay-safe commit and
report format. In a release zip, which has no Git history, the commit is read from
`stay_safe/release.txt`, which GitHub fills in when it builds the zip, and is marked
"(release archive)".

stay-safe reads the commit from Git's own files ([repository layout](https://git-scm.com/docs/gitrepository-layout))
without running Git. It follows a symbolic `HEAD` only to a ref name that
[`git check-ref-format`](https://git-scm.com/docs/git-check-ref-format) accepts. Git trims only ASCII whitespace
when it reads `HEAD` ([Git 2.43.0](https://github.com/git/git/blob/564d0252ca632e0264ed670534a51d18a689ef5d/refs/files-backend.c#L456)),
so other control characters stay in the name. `git archive` fills in `release.txt` through its
[`export-subst` attribute](https://git-scm.com/docs/gitattributes/2.43.0#_export_subst), which replaces
`$Format:%H$` with the commit.

## Configuration names

Configuration names, such as server, app, tool and provider names, are shown as
written, and a name can itself be private, such as `mcp_servers.acme-merger`.
Review them before sharing the report.

## Where the claims come from

Each claim links to tests of Stay Safe's behavior.
The [rule index](rules.md) links each warning to its evidence and challenges.
For evidence behind a warning, the [Codex meanings table](../harnesses/codex.md) gives sources and evidence status;
[incident reports](../incidents.md) describe the cases behind risk rules.
Passing software tests does not prove your live setup safe. See [Full scope](#full-scope) for the inspection limits.

### Understanding configuration findings

- [Settings and saved approvals](../contracts/claims.md#see_every_connection_and_setting-i-see-supported-settings-and-saved-approvals-from-my-files-with-defaults-identified)
- [Inspection limits](../contracts/claims.md#understand_inspection_limits-i-can-tell-what-the-report-establishes-and-what-needs-further-checking)
- [Evidence behind warnings](../contracts/claims.md#each_risk_shows_its_cause-each-warning-identifies-the-setting-and-evidence-behind-it)
- [Advice for findings](../contracts/claims.md#findings_say_what_to_do-each-finding-explains-what-is-wrong-and-what-i-can-do)

### Using and trusting the tool

- [Running without a coding agent](../contracts/claims.md#runs_without_a_coding_agent-i-can-run-stay-safe-without-an-agent-and-get-guidance-if-my-python-is-too-old)
- [Reading the report](../contracts/claims.md#overview_lists_findings_first-i-can-scan-the-report-and-reach-each-findings-details)
- [Privacy when sharing](../contracts/claims.md#share_without_exposing_secrets-my-report-withholds-commands-addresses-tokens-and-environment-values-names-need-checking-before-sharing)
- [Leaving your setup unchanged](../contracts/claims.md#nothing_in_my_setup_changes-running-stay-safe-leaves-my-setup-unchanged-saving-writes-only-the-report)
- [Reproducing a report](../contracts/claims.md#anyone_can_recheck_a_report-i-can-identify-the-code-that-made-a-report-and-reproduce-it-from-the-same-files)
- [Feedback and challenges](../contracts/claims.md#find_feedback-i-can-report-a-problem-suggest-an-idea-or-challenge-a-finding-without-sharing-private-files)

## Full scope

The report's "What this report can't see" section summarizes these limits. In full
("the catalog" is the JSON report's name for Your setup):

- Selected files are independent snapshots; other rules files are not read or merged.
- Rules inspection lists saved-format approval candidates, one-line allow records whose syntax context and current effect are not checked; other lines, including prompt and forbidden rules that may override a candidate, make the check incomplete.
- CLI flags, profile selection, trusted project layers, managed policies and runtime overrides are not inspected. A separately selected profile file can override the main config.
- Connection reachability, authentication, active tools and effective permissions are not tested.
- Source links point to the reported commit; whether that commit exists in the published GitHub repository is not checked.
- The catalog contains configured entries, documented defaults and source-status observations; account, endpoint, environment, saved approval command (except a first word on stay-safe's program list) and other command and argument values are withheld.
- Configuration names in the report, such as server, app, tool and provider names, are shown as written and should be reviewed before sharing.
- Local modifications to the checkout or unzipped release are not checked; the JSON report's `tool_revision` and `rules_revision` fingerprints identify the files that ran.
