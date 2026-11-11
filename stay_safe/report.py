"""Produce the code-only report from bounded, public observations."""

from html import escape, unescape
import json
from pathlib import Path
import re

from .codex import read_file
from .codex_rules import other_files, read_file as read_rules
from .rules import evaluate
from .provenance import GAP, REPOSITORY, fingerprints, identify, source_link

INCIDENTS = Path(__file__).resolve().parents[1] / "incidents.md"
INCIDENT_STATUS = "reported, not verified"


def incident_links(path=INCIDENTS, revision=None):
    """Derive GitHub heading anchors from the single committed incident catalog."""
    links = {}
    text = path.read_text(encoding="utf-8")
    for heading in re.findall(r"^## (I\d+\. .+)$", text, re.MULTILINE):
        identifier = heading.split(".", 1)[0]
        anchor = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        base = source_link(revision, "incidents.md")
        links[identifier] = base + "#" + anchor if base else None
    return links

SCOPE = [
    "Selected files are independent snapshots; other rules files are not read or merged.",
    "Rules inspection lists saved-format approval candidates, one-line allow records whose syntax context "
    "and current effect are not checked; other lines, including prompt and forbidden rules that may "
    "override a candidate, make the check incomplete.",
    "CLI flags, profile selection, trusted project layers, managed policies and runtime overrides are not inspected.",
    "Connection reachability, authentication, active tools and effective permissions are not tested.",
    "Source links point to the reported commit; whether that commit exists in the published GitHub repository is not checked.",
    "The catalog contains configured entries, documented defaults and source-status observations; account, endpoint, environment, saved approval command (except a first word on stay-safe's program list) and other command and argument values are withheld.",
    "Configuration names in the report, such as server, app, tool and provider names, "
    "are shown as written and should be reviewed before sharing.",
]


def inspect(paths, *, rules_path=None, discovered=False, gaps=()):
    entries, gaps = [], list(gaps)
    hashes = fingerprints()
    provenance = identify(hashes=hashes)
    for index, path in enumerate(paths, 1):
        found, missing = read_file(path, f"config-{index}", discovered=discovered)
        entries.extend(found)
        gaps.extend(missing)
    if rules_path is not None:
        found, missing = read_rules(rules_path, "rules-1", discovered=discovered)
        entries.extend(found)
        gaps.extend(missing)
        if discovered:
            gaps.extend(other_files(rules_path, "rules-1"))
    risks = evaluate(entries)
    revision = provenance["source_revision"]
    by_id = {entry["id"]: entry for entry in entries}
    for risk in risks:
        risk["configured_evidence"] = list(by_id[risk["entry"]]["observations"])
        risk["rule_source"] = source_link(revision, "stay_safe/rules.py")
        risk["interpretation_source"] = source_link(revision, "harnesses/codex.md")
    try:
        links = incident_links(revision=revision)
    except (OSError, UnicodeError):
        links = {}
    cited = sorted({identifier for risk in risks for identifier in risk["incidents"]}, key=lambda i: int(i[1:]))
    if any(identifier not in links for identifier in cited):
        gaps.append("Committed incident citations are incomplete; source links are unavailable.")
    gaps.extend(f"Incomplete fingerprint: {name} could not be read." for name, value in hashes.items() if value is None)
    if revision is None:
        gaps.append(GAP)
    return {"format_version": 3, "harness": "Codex", "provenance": provenance,
            "scope": list(SCOPE),
            "file_inspection": "incomplete" if gaps else "complete for supported fields",
            "catalog": [{k: v for k, v in entry.items() if k != "facts"} for entry in entries],
            "risks": risks, "incident_status": INCIDENT_STATUS,
            "incident_links": {identifier: links[identifier] for identifier in cited if links.get(identifier)},
            "inspection_gaps": gaps}


def cell(value):
    return escape(value, quote=True).replace("|", "&#124;").replace("\n", "&#10;")


# Plain wording for the Markdown report (archived issue #105 and its reading check). The JSON report keeps each
# rule's explanation and each gap's text; these lines say the same thing to the person whose setup it is, say how
# the rule's cited incidents went wrong and what to do, then give the ids.
PROGRAM = "If that program or your config file were tampered with, it could run code you didn't intend."
AUTOMATIC = "Untrusted tool content could lead to unwanted actions."
DESTRUCTIVE = "A mistaken operation could change or delete data in the connected service."
SOURCE_ONLY = "Based on Codex's source code, not yet seen in a live run."
INJECTION = ("Instructions hidden in public GitHub issues and issue comments could take over agents that read them.")
# Rule -> headline, why and how its cited incidents went wrong (incidents.md). A pair gives the wording for a server
# or app, then for one tool. What to do is in ADVICE, below.
FINDINGS = {
    "saved_approval": {
        "headline": "A saved approval on line {line} of your rules file says matching commands may run outside the "
                    "sandbox without asking you.",
        "why": "It covers every command that starts with its saved words. A rule that asks first or forbids the "
               "command can override it, and stay-safe doesn't check whether one does.",
        "how": "A Codex user reported that a saved approval for `curl` let later `curl` commands run without asking, "
               "even after restarting in another workspace."},
    "commands_without_prompts": {
        "headline": "With these settings, Codex runs commands without asking you.",
        "why": "It won't ask before any command it's allowed to run, so injected or mistaken instructions could make "
               "it run code you didn't want.",
        "how": "Agents running commands without approval have run a delete command aimed at a home directory, "
               "wiped a drive and updated drivers when asked only to diagnose."},
    "unrestricted_filesystem": {
        "headline": "Your config turns off Codex's sandbox.",
        "why": "Commands Codex runs aren't limited to your project, so a mistaken command could damage files "
               "elsewhere on your computer.",
        "how": "Agents have deleted a home directory and wiped a whole drive with one mistaken delete command."},
    "configured_program": {
        "headline": "{Subject} can start a program on your computer.",
        "why": PROGRAM,
        "how": "Flaws in other agents let repository settings run commands on collaborators' machines, and a worm "
               "wrote itself into an agent's settings so its code ran at every start."},
    "automatic_tools": {
        "headline": ("{Subject}'s tool approval mode is `approve`.", "{Subject} has approval mode `approve`."),
        "why": AUTOMATIC,
        "how": "Hidden instructions in public GitHub issues could take over agents using a GitHub MCP server, and "
               "injected text got another agent to turn off its own approvals."},
    "destructive_tools": {
        "headline": ("{Subject}'s tools that can change or delete data are turned on.",
                     "{Subject} is turned on, even if it can change or delete data."),
        "why": DESTRUCTIVE,
        "how": "Agents have deleted production data with a token they found, and changed a database after being told "
               "to stop."},
    "network_access": {
        "headline": "With these settings, commands Codex runs can use the network.",
        "why": "Your sandbox allows network access, so injected instructions could send your private data to an "
               "outside service.",
        "how": INJECTION},
    "self_described_tools": {
        "headline": ("{Subject} uses server hints for tool approval.", "{Subject} uses server hints for tool approval."),
        "why": '`auto` and `writes` use hints supplied by the server. ' + SOURCE_ONLY,
        "how": INJECTION},
    "environment_inheritance": {
        "headline": "With these settings, commands Codex runs get your environment variables.",
        "why": "They start with the environment Codex was launched with, apart from a few Codex launch variables. "
               "Credentials in it could be misused, even if Codex filters out some variable names.",
        "how": "An agent that could read a production database URL dropped all 22 production tables with a migration "
               "command."},
}
# What to do (archived issue #119; reviews of archived PR #129 at 143ba19 and 29d5a8c): one line with the lower-friction
# option, if the Codex meanings table (harnesses/codex.md) backs one, and its trade-off in brackets, then "Stricter:";
# one Change it line with where the setting goes and a sentence to ask Codex; and a Check that changes nothing and
# shows no values. What every finding shares is said once, in NOTE. Keyed by rule, then by the entry's first
# configuration key and number of keys, so findings can later be grouped by rule without changing this table.
# Fields: {file} and {where} name the file (a found file by where Codex keeps it, a passed file by a placeholder with
# its label, since the report withholds its path); {table} is the entry's TOML table, {name} its server, app or hook
# event, {tool} its tool, {kind} "MCP server" or "app", {line} its rules line; {value} and {label} a sandbox another
# inspected file sets.
# The note: `codex --help` (0.167.0) lists `-a, --ask-for-approval`, `-s, --sandbox`, `-p, --profile` and
# `-c, --config`, which override a file. Codex can allow or block a call without showing a prompt.
# (openai/codex 086ccc8, codex-mcp/src/mcp/mod.rs L91-L110, core/src/mcp_tool_call.rs L1691-L1698).
NOTE = ("*Before you change anything:* {placeholders}Codex reads the whole file to edit it. The app, profiles and flags "
        "such as `--ask-for-approval`, `--sandbox`, `--profile` and `-c` can override any file. Codex can allow or "
        "block a tool call without asking you. This report does not test which calls Codex allows.")
PLACEHOLDERS = ("`<config-1>` and similar labels stand for a file you passed with `--config` or `--rules`; put its "
                "path in before you paste. ")
TOP = "near the top of the file, before any `[section]`"
SAVED_STILL = "commands a saved approval allows still run outside the sandbox."
TOOL_PROMPT = {
    "what": "Set `approval_mode = \"prompt\"` for this tool.",
    "where": "under `[{table}]`",
    "ask": "Edit {file} to set `approval_mode = \"prompt\"` for the `{tool}` tool of my `{name}` {kind}"}
# Approval mode settings: harnesses/codex.md.
AUTOMATIC_GROUP = {
    "what": "Set `default_tools_approval_mode = \"writes\"` (uses server hints){allowlist}. "
            "Stricter: `default_tools_approval_mode = \"prompt\"`.",
    "allowlist": ", or list only the tools you use in `enabled_tools`",
    "where": "under `[{table}]`",
    "ask": "Edit {file} to set `default_tools_approval_mode = \"writes\"` for my `{name}` {kind}"}
# Rows: default_tools_approval_mode `prompt`, tools.*.approval_mode `approve`, enabled_tools (MCP servers only).
LABELS_GROUP = {
    "what": "Set `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for tools you trust"
            "{allowlist}. Stricter: `default_tools_approval_mode = \"prompt\"` for every tool.",
    "allowlist": ", or list only the tools you use in `enabled_tools`",
    "where": "under `[{table}]`, with each trusted tool's `approval_mode` under `[{table}.tools.<tool>]`",
    "ask": "Edit {file} so my `{name}` {kind} uses `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for these tools I trust: <tool names>"}
# Rows: approval_policy `on-request`, sandbox_mode `workspace-write` and `read-only`. The advice never suggests a
# sandbox looser than one set by the finding's file or another inspected file: `workspace-write` only when none sets
# the stricter `read-only`. With `default_permissions`, the permission profile, not `sandbox_mode`, decides
# what commands can write (openai/codex 086ccc8, core/src/config/mod.rs L2712-L2722).
KEEP_SANDBOX = "Edit {file} to set `approval_policy = \"on-request\"` without changing `sandbox_mode`"
COMMANDS_CHECK = "Look for `approval_policy` and `sandbox_mode` in {where}."
APPROVAL_ONLY = "`approval_policy` " + TOP
COMMANDS = {
    "profile": {
        "what": "Set `approval_policy = \"on-request\"` (Codex decides when to ask you first). Your `default_permissions` "
                "profile, not `sandbox_mode`, decides what commands can write; review it.",
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    "read-only": {
        "what": "Set `approval_policy = \"on-request\"` and keep `sandbox_mode = \"read-only\"` (Codex decides when to "
                "ask you first; commands still can't write files). But " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    "workspace-write": {
        "what": "Set `approval_policy = \"on-request\"` and keep `sandbox_mode = \"workspace-write\"` (Codex decides when "
                "to ask you first; commands can still write in your workspace). Stricter: also "
                "`sandbox_mode = \"read-only\"` (commands can't write files). Either way, " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    "other": {
        "what": "Set `approval_policy = \"on-request\"` (Codex decides when to ask you first) without loosening the "
                "`sandbox_mode = \"{value}\"` in `{label}`. But " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    None: {
        "what": "Set `approval_policy = \"on-request\"` with `sandbox_mode = \"workspace-write\"` (commands can write only "
                "in your workspace; Codex decides when to ask you first). Stricter: `sandbox_mode = \"read-only\"` "
                "(commands can't write files). Either way, " + SAVED_STILL,
        "where": TOP,
        "ask": "Edit {file} to set `approval_policy = \"on-request\"` and `sandbox_mode = \"workspace-write\"`",
        "check": COMMANDS_CHECK}}
# Rows: sandbox_mode `workspace-write` and `read-only`; with `read-only` in another inspected file, `workspace-write`
# would be looser, so only `read-only` is offered.
SANDBOX = {
    "read-only": {
        "what": "Set `sandbox_mode = \"read-only\"`, as `{label}` does (commands can't write files).",
        "where": TOP, "ask": "Edit {file} to set `sandbox_mode = \"read-only\"`"},
    None: {
        "what": "Set `sandbox_mode = \"workspace-write\"` (commands can write only in your workspace). Stricter: "
                "`sandbox_mode = \"read-only\"` (commands can't write files).",
        "where": TOP, "ask": "Edit {file} to set `sandbox_mode = \"workspace-write\"`"}}
ADVICE = {
    ("commands_without_prompts", "approval_policy", 1): COMMANDS,
    ("unrestricted_filesystem", "sandbox_mode", 1): SANDBOX,
    # Keeping a trusted program changes nothing; turning it off to see what breaks changes the setup, so it is the
    # stricter option, not the Check. A stdio server runs `command` with `args` (openai/codex 086ccc8,
    # config/src/mcp_types.rs L393-L397), so with a launcher or interpreter what runs is in `args`;
    # `http_headers_helper` is a program too (L411). Row mcp_servers.*.enabled `false`.
    ("configured_program", "mcp_servers", 2): {
        "what": "Keep it if you trust the program it starts. Stricter: `enabled = false`; if nothing you use stops "
                "working, leave it off.",
        "where": "under `[{table}]`",
        "ask": "Edit {file} to set `enabled = false` for my `{name}` MCP server",
        "check": "Under `[{table}]` in {where}, the program is `command` with its `args` (or `http_headers_helper`); "
                 "for a launcher such as `npx`, `uvx`, `docker`, `node` or `python`, what runs is named in `args`. Find "
                 "out who publishes it before you trust it."},
    # `notify` is a list whose first item is the program; it can continue over several lines, and Codex 0.167.0
    # refuses a file with only its first line deleted.
    ("configured_program", "notify", 1): {
        "what": "Keep it if you trust the program it starts. Stricter: remove `notify` if you don't need notifications.",
        "where": "delete the `notify` setting, including any lines its list continues on",
        "ask": "Edit {file} to remove the `notify` setting",
        "check": "In {where}, the first item in the `notify` list is the program it starts; for a launcher such as "
                 "`node` or `npx`, the next items name what runs. Find out who publishes it before you trust it."},
    # Codex writes each matcher group's handlers as `[[hooks.<Event>.hooks]]` sections (MatcherGroup, openai/codex
    # 086ccc8 protocol/src/hooks.rs L140-L145); deleting only the `[[hooks.<Event>]]` lines leaves those sections,
    # which Codex 0.167.0 refuses to load.
    ("configured_program", "hooks", 2): {
        "what": "Keep them if you trust the commands they run. Stricter: remove these hooks if you don't use them.",
        "where": "delete each `[[{table}]]` section with everything under it, including its `[[{table}.hooks]]` "
                 "sections",
        "ask": "Edit {file} to remove my `{name}` hooks",
        "check": "In {where}, each `command` in the `hooks` of `[[{table}]]`, often written as `[[{table}.hooks]]` "
                 "sections, is a command they run. Find out who publishes the program it starts before you trust it."},
    ("automatic_tools", "mcp_servers", 2): AUTOMATIC_GROUP,
    ("automatic_tools", "apps", 2): AUTOMATIC_GROUP,
    ("automatic_tools", "mcp_servers", 4): TOOL_PROMPT,
    ("automatic_tools", "apps", 4): TOOL_PROMPT,
    ("self_described_tools", "mcp_servers", 2): LABELS_GROUP,
    ("self_described_tools", "apps", 2): LABELS_GROUP,
    ("self_described_tools", "mcp_servers", 4): TOOL_PROMPT,
    ("self_described_tools", "apps", 4): TOOL_PROMPT,
    # Rows: apps.*.destructive_enabled `false inherited from _default`, apps.*.default_tools_enabled `true` (which
    # turns destructive tools back on), apps.*.enabled `false`, apps.*.tools.*.enabled `false`.
    ("destructive_tools", "apps", 2): {
        "what": "Set `destructive_enabled = false` and leave `default_tools_enabled` unset (tools the app marks as not "
                "destructive stay on; tools marked destructive, or not marked, turn off). Stricter: `enabled = false`, "
                "if you don't need the app.",
        "where": "under `[{table}]`, removing any `default_tools_enabled` line there",
        "ask": "Edit {file} to set `destructive_enabled = false` for my `{name}` app and remove its "
               "`default_tools_enabled` line if it has one"},
    ("destructive_tools", "apps", 4): {
        "what": "If you don't need this tool, set `enabled = false` for it.",
        "where": "under `[{table}]`",
        "ask": "Edit {file} to set `enabled = false` for the `{tool}` tool of my `{name}` app"},
    # Row: sandbox_workspace_write.network_access `false`. No lower-friction option has a row yet (archived issue #127).
    ("network_access", "sandbox_workspace_write", 2): {
        "what": "Set `network_access = false` unless commands need the network.",
        "where": "under `[sandbox_workspace_write]`",
        "ask": "Edit {file} to set `network_access = false` under `[sandbox_workspace_write]`"},
    # Rows: shell_environment_policy.inherit `core` and `none`. Core variables on Unix include HOME and PATH, and Codex
    # adds `set` entries after `inherit` (openai/codex 086ccc8, protocol/src/shell_environment.rs L153-L158,
    # L178-L181). The Check prints names only: `env | cut -d= -f1` would print each line of a multi-line value that
    # has no `=`, so it uses awk's ENVIRON.
    ("environment_inheritance", "shell_environment_policy", 1): {
        "what": "Set `inherit = \"core\"` (commands get only core variables, such as `HOME` and `PATH`, plus any you "
                "list under `set`). Stricter: `inherit = \"none\"` (no inherited variables).",
        "where": "under `[shell_environment_policy]` (inside its `{{ }}` if it's on one line)",
        "ask": "Edit {file} to set `inherit = \"core\"` under `[shell_environment_policy]`",
        "check": "In a terminal like the one you start Codex from, run "
                 "`awk 'BEGIN {{ for (name in ENVIRON) print name }}'` to list the names of your environment variables "
                 "without their values, and look for names that suggest credentials."},
    # Saved approval records: a record covers every command that starts with its pattern's words (openai/codex
    # 086ccc8, execpolicy/src/rule.rs L55-L72), so a pattern with more words covers fewer commands.
    ("saved_approval", "prefix_rule", 2): {
        "what": "Replace it with a rule whose `pattern` has more words (it then covers only the commands you meant), "
                "for example `[\"git\", \"status\"]` instead of `[\"git\"]`. Stricter: delete line {line}.",
        "where": "on line {line}, add the next words of the command you meant to the `pattern` list",
        "ask": "Edit {file} to replace line {line} with a rule that allows only <the command you meant>",
        "check": "Open {where} and read line {line}: its `pattern` lists the words a command must start with."},
}
KINDS = {"mcp_servers": "MCP server", "apps": "app"}
STRICTNESS = ("read-only", "workspace-write")


def sandbox_context(report):
    """For each inspected config file: the sandbox it sets, whether `default_permissions` selects a permission
    profile instead, and the first other inspected file that sets the stricter `read-only`, with its label.

    The reader reports a selected profile as the conflict gap (with `sandbox_mode`), or as the named-profile gap without
    the absent-`sandbox_mode` gap and without a `sandbox_mode` entry (stay_safe/codex.py, Reader.sandbox); unselected
    `[permissions.*]` definitions alone give the absent gap or a plain `sandbox_mode` entry."""
    sources = {entry["source"] for entry in report["catalog"] if entry["source"].startswith("config-")}
    gaps = {}
    for text in report["inspection_gaps"]:
        source, _, message = text.partition(": ")
        gaps.setdefault(source, set()).add(message)
    sources |= {source for source in gaps if source.startswith("config-")}
    own = {entry["source"]: entry["observations"][0] for entry in report["catalog"]
           if entry["name"] == "sandbox_mode" and entry["observations"]}
    context = {}
    for source in sources:
        messages = gaps.get(source, set())
        profile = ("default_permissions and sandbox_mode conflict; effective sandbox selection is unknown." in messages
                   or ("Named permission profiles are outside reader coverage; sandbox settings are not "
                       "effective-permission evidence." in messages
                       and "sandbox_mode is absent; the reader does not infer its effective value." not in messages
                       and "sandbox_mode is unsupported or invalid; its value was withheld." not in messages
                       and source not in own))
        context[source] = {"sandbox": own.get(source), "profile": profile, "other": None}
    for source in context:
        # A file that selects a profile still counts: in a later layer, an added `sandbox_mode` would replace that
        # profile (openai/codex 086ccc8, core/src/config/mod.rs L2717-L2719).
        others = sorted((int(other.split("-")[1]), other) for other, value in own.items()
                        if other != source and value == "read-only")
        context[source]["other"] = ("read-only", others[0][1]) if others else None
    return context


def pick_spec(spec, context):
    """The commands and sandbox advice depend on the sandbox the finding's file and the other files set."""
    if spec is COMMANDS:
        if context.get("profile"):
            return COMMANDS["profile"]
        if context.get("sandbox") in STRICTNESS:
            return COMMANDS[context["sandbox"]]
        return COMMANDS["other"] if context.get("other") else COMMANDS[None]
    if spec is SANDBOX:
        other = context.get("other")
        return SANDBOX["read-only"] if other else SANDBOX[None]
    return spec


def advice(risk, files, contexts):
    """A finding's What to do, Change it and Check paragraphs; None where its rule and entry have none."""
    source, _, name = risk["entry"].partition(":")
    keys = parts(name)
    spec = ADVICE.get((risk["rule"], keys[0], len(keys)))
    if spec is None or (keys[0] == "prefix_rule" and not keys[1].isdigit()):
        return None
    context = contexts.get(source, {})
    spec = pick_spec(spec, context)
    path = files.get(source)
    other = context.get("other") or ("", "")
    fields = {"file": f"`{path}`" if path else f"`<{source}>`", "where": f"`{path}`" if path else f"`<{source}>`",
              "table": name, "name": keys[1] if len(keys) > 1 else "", "tool": keys[3] if len(keys) == 4 else "",
              "kind": KINDS.get(keys[0], ""), "line": keys[1] if len(keys) > 1 else "",
              "allowlist": spec.get("allowlist", "") if keys[0] == "mcp_servers" else "",
              "value": other[0], "label": other[1]}
    fill = lambda text: text.format(**fields)
    paragraphs = [f"*What to do:* {fill(spec['what'])}",
                  f"*Change it:* {fill(spec['where'])}, or ask Codex: \"{fill(spec['ask'])}; show only what you change.\""]
    if "check" in spec:
        paragraphs.append(f"*Check:* {fill(spec['check'])}")
    return "\n\n".join(paragraphs)


def note(report, files):
    """The note before the findings; it explains placeholders only when a finding names a passed file."""
    passed = any(risk["entry"].split(":", 1)[0] not in files for risk in report["risks"])
    return NOTE.format(placeholders=PLACEHOLDERS if passed else "")


WITHHELD = "The value is left out of this report."
# JSON gap text, without its source label -> Markdown lead. {label} stands for the setting a gap names.
GAPS = {
    'Selected config file is missing. Check the path supplied to --config.':
        '**Not checked: your config file.** The selected file is missing.',
    'Selected config file is a symlink and was not followed. Select its target file explicitly with --config.':
        "**Not checked: your config file.** The selected file is a symlink, so stay-safe didn't follow it.",
    'Selected config file could not be read. Check its permissions and that it is a readable regular file.':
        "**Not checked: your config file.** stay-safe couldn't read the selected file. Error details are left out of this report.",
    'Selected config file is not valid UTF-8. Save a copy as UTF-8 and select it with --config.':
        "**Not checked: your config file.** The selected file isn't valid UTF-8. Its contents are left out of this report.",
    'Selected config file is not valid TOML. Fix the TOML syntax locally, then run stay-safe again.':
        "**Not checked: your config file.** The selected file isn't valid TOML. Parser details are left out of this report.",
    "Input is not a regular file.":
        "**Not checked: your config file.** It isn't a regular file, so stay-safe didn't read it.",
    "Input exceeds the 1 MiB size limit.":
        "**Not checked: your config file.** It's larger than 1 MiB, so stay-safe didn't read any of it.",
    "Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.":
        "**Not checked: your config file.** stay-safe couldn't read it: it's missing, unreadable, a symlink, or "
        "not valid UTF-8 TOML. Error details are left out of this report.",
    "approval_policy is absent; the reader does not infer its effective value.":
        "**Not checked: your approval setting.** `approval_policy` isn't in your config file, so stay-safe can't "
        "tell whether Codex asks before running commands.",
    "approval_policy has a known but unhandled value; its behavior is not evaluated.":
        "**Not checked: your approval setting.** stay-safe recognizes your `approval_policy` value but doesn't "
        "assess it, so it can't tell when Codex asks before running commands.",
    "approval_policy is unsupported or invalid; its value was withheld.":
        "**Not checked: your approval setting.** Your `approval_policy` value isn't one stay-safe supports, so it "
        f"can't tell whether Codex asks before running commands. {WITHHELD}",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "**Not checked: your sandbox setting.** `sandbox_mode` isn't in your config file, so stay-safe can't tell "
        "what commands Codex runs are allowed to do.",
    "sandbox_mode is unsupported or invalid; its value was withheld.":
        "**Not checked: your sandbox setting.** Your `sandbox_mode` value isn't one stay-safe supports, so it "
        f"can't tell what commands Codex runs are allowed to do. {WITHHELD}",
    "Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.":
        "**Not checked: your permission profiles.** Your config file has named permission profiles, which "
        "stay-safe doesn't read. They can change what commands are allowed to do, so your sandbox settings may "
        "not show what commands can really do.",
    "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.":
        "**Not checked: which sandbox Codex uses.** Your config file sets both `default_permissions` and "
        "`sandbox_mode`, so stay-safe can't tell which one Codex uses.",
    "Profiles are outside reader coverage; a selected profile can override the reported settings.":
        "**Not checked: your profiles.** Your config file has profiles, which stay-safe doesn't read. A profile "
        "Codex uses can override the settings in this report.",
    "shell_environment_policy.inherit is unsupported or invalid; its value was withheld.":
        "**Not checked: whether commands get your environment variables.** Your "
        f"`shell_environment_policy.inherit` value isn't one stay-safe supports. {WITHHELD}",
    "shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown.":
        "**Not checked: whether commands get your environment variables.** Your "
        "`shell_environment_policy.ignore_default_excludes` isn't true or false.",
    "Configuration contains fields outside reader coverage; their values were withheld.":
        "**Not checked: some settings in your config file.** Some settings in your config file aren't ones "
        "stay-safe reads, so it can't tell what they change. Their values are left out of this report.",
    "{label} must be a table.":
        "**Not checked: your `{label}` settings.** `{label}` isn't written as a group of settings, such as a "
        "`[section]`, so stay-safe couldn't read the settings in it.",
    "{label} contains fields outside reader coverage; their values were withheld.":
        "**Not checked: some `{label}` settings.** Some fields in `{label}` aren't ones stay-safe reads, so it "
        "can't tell what they change. Their values are left out of this report.",
    "{label} has an invalid boolean; its behavior is unknown.":
        "**Not checked: an on/off setting in `{label}`.** A setting in `{label}` that should be true or false "
        "isn't, so stay-safe can't tell what it does.",
    "{label} contains a name that cannot be included in a shareable report.":
        "**Not checked: an entry in `{label}`.** Its name looks like it could be private, such as an address or "
        "a key, so stay-safe left the entry out of this report.",
    "{label} contains an entry that is not a table.":
        "**Not checked: an entry in `{label}`.** It isn't written as a group of settings, such as a `[section]`, "
        "so stay-safe couldn't read it.",
    "A tool approval mode is unsupported or invalid; its value was withheld.":
        "**Not checked: a tool approval setting.** A `default_tools_approval_mode` value isn't one stay-safe "
        f"supports, so it can't tell when Codex asks before using those tools. {WITHHELD}",
    "A per-tool approval mode is unsupported or invalid; its value was withheld.":
        "**Not checked: a tool approval setting.** A tool's `approval_mode` value isn't one stay-safe supports, "
        f"so it can't tell when Codex asks before using that tool. {WITHHELD}",
    "A tool allow/deny list contains a name that cannot be included in a shareable report.":
        "**Not shown: a tool name in an allow or deny list.** A name in `enabled_tools` or `disabled_tools` looks "
        "like it could be private, so it's left out of this report.",
    "A tool allow/deny list is invalid; tool availability is unknown.":
        "**Not checked: which tools are available.** An `enabled_tools` or `disabled_tools` list isn't a list of "
        "names, so stay-safe can't tell which tools Codex can use.",
    "An MCP transport is missing, conflicting or invalid.":
        "**Not checked: how an MCP server connects.** An MCP server needs either a `command` or a `url`; this one "
        "has neither, both, or an invalid one, so stay-safe can't tell how it connects.",
    "An MCP header-helper command is invalid; its value was withheld.":
        "**Not checked: an MCP header-helper command.** An `http_headers_helper` value isn't a valid command, so "
        f"stay-safe didn't assess it. {WITHHELD}",
    "apps has an invalid destructive_enabled flag.":
        "**Not checked: an app's `destructive_enabled` setting.** It isn't true or false, so stay-safe can't tell "
        "whether that app's tools that change or delete data are turned on.",
    "Per-account app policy is not evaluated; account identifiers were withheld.":
        "**Not checked: per-account app settings.** An app has per-account settings (`links`), which stay-safe "
        "doesn't assess. Account identifiers are left out of this report.",
    "Model-provider command-backed authentication is outside reader coverage.":
        "**Not checked: a model provider's sign-in command.** A model provider gets its credentials by running a "
        "command (`auth`), which stay-safe doesn't assess.",
    "notify is not a command list with a nonempty program.":
        "**Not checked: your `notify` setting.** It isn't a list that starts with a program name, so stay-safe "
        "can't tell whether it starts a program.",
    "hooks contains an invalid event configuration.":
        "**Not checked: a hook event.** A hook event in your config file isn't a list, so stay-safe couldn't read "
        "its hooks.",
    "hooks contains an invalid handler group.":
        "**Not checked: a group of hooks.** A hook group in your config file isn't in the expected form, so "
        "stay-safe couldn't read the hooks in it.",
    "Hook execution policy is outside reader coverage.":
        "**Not checked: whether your hooks are trusted and turned on.** stay-safe doesn't read the settings that "
        "decide whether Codex runs your hooks, so it treats each hook command as able to run.",
    "web_search is unsupported or invalid; its value was withheld.":
        f"**Not checked: your web search setting.** Your `web_search` value isn't one stay-safe supports. {WITHHELD}",
    "Rules input is not a regular file.":
        "**Not checked: your rules file.** It isn't a regular file, so stay-safe didn't read it.",
    "Rules input exceeds the 1 MiB size limit.":
        "**Not checked: your rules file.** It's larger than 1 MiB, so stay-safe didn't read any of it.",
    "Selected rules input is missing; its path was withheld.":
        "**Not checked: your rules file.** The rules file you selected doesn't exist. Its path is left out of "
        "this report.",
    "Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.":
        "**Not checked: your rules file.** stay-safe couldn't read it: it's unreadable, a symlink, or not valid "
        "UTF-8. Error details are left out of this report.",
    "Rules contain lines that are not inspected.":
        "**Not checked: some lines in your rules file.** stay-safe reads only one-line saved approvals. Other "
        "lines, such as rules that ask first or forbid a command, could change what the listed approvals do.",
    "The rules directory cannot be listed; other rules files may exist and were not inspected.":
        "**Not checked: other rules files.** stay-safe couldn't list your `rules` folder, so there may be rules "
        "files it didn't read.",
    "Other rules files exist and were not inspected.":
        "**Not checked: other rules files.** Your `rules` folder has other `.rules` files besides "
        "`default.rules`. Codex reads them too, but stay-safe doesn't.",
    "Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; "
    "Codex would not start, so no default files were inspected.":
        "**Not checked: your Codex folder.** `CODEX_HOME` points to something that's missing, isn't a folder or "
        "can't be checked. Codex wouldn't start, so stay-safe read no files.",
    "Codex home: CODEX_HOME is unset and the home directory cannot be determined; no default files were inspected.":
        "**Not checked: your Codex folder.** `CODEX_HOME` isn't set and stay-safe couldn't find your home "
        "folder, so it read no files.",
    "Codex home: Could not check the plugin cache. Check that you can open plugins/cache in your Codex folder.":
        "**Not checked: your Codex plugins.** Could not check the plugin cache.",
    "Codex home: plugins/cache holds Codex plugins that were not inspected.":
        "**Not checked: your Codex plugins.** Your Codex folder has plugins in `plugins/cache`, which stay-safe "
        "doesn't read.",
    "features.apps has an invalid boolean; its behavior is unknown.":
        "**Not checked: the ChatGPT Apps connection.** Your `features.apps` isn't true or false, so stay-safe can't "
        "tell whether Codex adds the ChatGPT Apps connection.",
    "System config folder: /etc/codex holds Codex configuration that was not inspected.":
        "**Not checked: Codex's system folder.** `/etc/codex` holds Codex settings, hooks or rules that stay-safe "
        "doesn't read.",
    "Codex home: hooks.json exists and was not inspected.":
        "**Not checked: your `hooks.json` file.** Your Codex folder has a `hooks.json` file, which stay-safe "
        "doesn't read.",
    "Committed incident citations are incomplete; source links are unavailable.":
        "**Not checked: some cited incidents.** stay-safe couldn't find every cited incident in its incident list, "
        "so those incidents appear without links.",
    "Incomplete fingerprint: {label} could not be read.":
        "**Not checked: stay-safe's own file `{label}`.** stay-safe couldn't read it, so the fingerprint that "
        "identifies this version of stay-safe is incomplete.",
    GAP:
        "**Not checked: which version of stay-safe made this report.** stay-safe couldn't tell which commit it's "
        "running from, so links to its rules, evidence and incidents are left out.",
}
# The absent-setting gaps of a Codex config file that automatic discovery did not find.
ABSENT = {
    "approval_policy is absent; the reader does not infer its effective value.":
        "**Not checked: your approval setting.** stay-safe found no Codex config file, so it can't tell whether "
        "Codex asks before running commands.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "**Not checked: your sandbox setting.** stay-safe found no Codex config file, so it can't tell what "
        "commands Codex runs are allowed to do.",
}
# JSON gap text -> what the reader can do about it (reading check). {label} stands for the setting a gap names.
STEPS = {
    'Selected config file is missing. Check the path supplied to --config.':
        'Check the path supplied to --config.',
    'Selected config file is a symlink and was not followed. Select its target file explicitly with --config.':
        'Select its target file explicitly with --config.',
    'Selected config file could not be read. Check its permissions and that it is a readable regular file.':
        'Check its permissions and that it is a readable regular file.',
    'Selected config file is not valid UTF-8. Save a copy as UTF-8 and select it with --config.':
        'Save a copy as UTF-8 and select it with --config.',
    'Selected config file is not valid TOML. Fix the TOML syntax locally, then run stay-safe again.':
        'Fix the TOML syntax locally, then run stay-safe again.',
    "Input is not a regular file.": "Make sure the path is a regular file, then run stay-safe again.",
    "Input exceeds the 1 MiB size limit.": "Check that you selected the right file and that it's under 1 MiB.",
    "Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.":
        "Check that the file exists, is readable and is valid TOML; for a symlink, select the file it points to.",
    "approval_policy is absent; the reader does not infer its effective value.":
        "Check the approval setting wherever you run Codex (the app or the command line). To set it in a file, add "
        "`approval_policy = \"on-request\"` to your config file.",
    "approval_policy has a known but unhandled value; its behavior is not evaluated.":
        "Review this setting yourself, or switch to `\"on-request\"`, which stay-safe can assess.",
    "approval_policy is unsupported or invalid; its value was withheld.":
        "Set it to a supported value such as `\"on-request\"`.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "Check the sandbox setting wherever you run Codex (the app or the command line). To set it in a file, add "
        "`sandbox_mode = \"workspace-write\"` or `\"read-only\"` to your config file.",
    "sandbox_mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"read-only\"`, `\"workspace-write\"` or `\"danger-full-access\"`.",
    "Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.":
        "Review your permission profiles yourself; findings about this file's sandbox may not apply.",
    "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.":
        "Keep only one of `default_permissions` and `sandbox_mode`, then run stay-safe again.",
    "Profiles are outside reader coverage; a selected profile can override the reported settings.":
        "Review your profiles yourself, especially their approval and sandbox settings.",
    "shell_environment_policy.inherit is unsupported or invalid; its value was withheld.":
        "Set `inherit` to `\"all\"`, `\"core\"` or `\"none\"`.",
    "shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown.":
        "Set `ignore_default_excludes` to `true` or `false`.",
    "Configuration contains fields outside reader coverage; their values were withheld.":
        "Review those settings yourself; stay-safe didn't evaluate them.",
    "{label} must be a table.": "Rewrite it as a group of settings, then run stay-safe again.",
    "{label} contains fields outside reader coverage; their values were withheld.":
        "Review the other settings under `{label}` yourself; stay-safe didn't evaluate them.",
    "{label} has an invalid boolean; its behavior is unknown.": "Set it to `true` or `false`.",
    "{label} contains a name that cannot be included in a shareable report.":
        "Review that entry yourself, since it isn't in this report.",
    "{label} contains an entry that is not a table.": "Rewrite it as a group of settings, then run stay-safe again.",
    "A tool approval mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"auto\"`, `\"prompt\"`, `\"writes\"` or `\"approve\"`; use `\"prompt\"` to request approval.",
    "A per-tool approval mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"auto\"`, `\"prompt\"`, `\"writes\"` or `\"approve\"`; use `\"prompt\"` to request approval.",
    "A tool allow/deny list contains a name that cannot be included in a shareable report.":
        "Review the full list in your config file yourself.",
    "A tool allow/deny list is invalid; tool availability is unknown.":
        "Make `enabled_tools` and `disabled_tools` lists of tool names.",
    "An MCP transport is missing, conflicting or invalid.": "Give the server either a `command` or a `url`, not both.",
    "An MCP header-helper command is invalid; its value was withheld.":
        "Set `http_headers_helper` to the command you mean to run, or remove it.",
    "apps has an invalid destructive_enabled flag.": "Set `destructive_enabled` to `true` or `false`.",
    "Per-account app policy is not evaluated; account identifiers were withheld.":
        "Review those per-account settings yourself.",
    "Model-provider command-backed authentication is outside reader coverage.":
        "Review that command yourself; stay-safe doesn't check it.",
    "notify is not a command list with a nonempty program.":
        "Write `notify` as a list that starts with the program, or remove it.",
    "hooks contains an invalid event configuration.": "Write each hook event as a list of hook groups, or remove it.",
    "hooks contains an invalid handler group.": "Fix or remove that hook group.",
    "Hook execution policy is outside reader coverage.":
        "Check which hooks Codex trusts and has turned on, and remove any you don't use.",
    "web_search is unsupported or invalid; its value was withheld.":
        "Set it to `\"disabled\"`, `\"cached\"`, `\"indexed\"` or `\"live\"`.",
    "Rules input is not a regular file.": "Select the rules file itself with `--rules`.",
    "Rules input exceeds the 1 MiB size limit.": "Check that you selected the right rules file and that it's under 1 MiB.",
    "Selected rules input is missing; its path was withheld.": "Check the path you gave with `--rules`.",
    "Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.":
        "Check that the file is readable and valid UTF-8; for a symlink, select the file it points to.",
    "Rules contain lines that are not inspected.":
        "Review the other lines in your rules file yourself, especially rules that ask first or forbid a command.",
    "The rules directory cannot be listed; other rules files may exist and were not inspected.":
        "Check that `rules` in your Codex folder is a folder you can read, then run stay-safe again.",
    "Other rules files exist and were not inspected.":
        "Review the other `.rules` files yourself, or check one with `--rules`.",
    "Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; "
    "Codex would not start, so no default files were inspected.":
        "Point `CODEX_HOME` at your Codex folder, or unset it to use `~/.codex`.",
    "Codex home: CODEX_HOME is unset and the home directory cannot be determined; no default files were inspected.":
        "Set `HOME` or `CODEX_HOME`, or select files with `--config` and `--rules`.",
    "Codex home: hooks.json exists and was not inspected.": "Review the hooks in `hooks.json` yourself.",
    "System config folder: /etc/codex holds Codex configuration that was not inspected.":
        "Review the files in `/etc/codex` yourself.",
    "Codex home: Could not check the plugin cache. Check that you can open plugins/cache in your Codex folder.":
        "Check that you can open `plugins/cache` in your Codex folder.",
    "Codex home: plugins/cache holds Codex plugins that were not inspected.":
        "Review the plugins in `plugins/cache` yourself.",
    "features.apps has an invalid boolean; its behavior is unknown.": "Set `features.apps` to `true` or `false`.",
    "Committed incident citations are incomplete; source links are unavailable.":
        "Get a fresh copy of stay-safe so its incident list is complete.",
    "Incomplete fingerprint: {label} could not be read.": "Restore that file, for example by cloning stay-safe again.",
    GAP: "Run stay-safe from a git clone so the report can link to the exact version.",
}
# With no Codex config file found, the absent-setting follow-ups say to create one.
ABSENT_STEPS = {
    "approval_policy is absent; the reader does not infer its effective value.":
        "Check the approval setting wherever you run Codex (the app or the command line). To set it in a file, "
        "create `~/.codex/config.toml` (or `config.toml` in the folder `CODEX_HOME` names) with "
        "`approval_policy = \"on-request\"`.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "Check the sandbox setting wherever you run Codex (the app or the command line). To set it in a file, "
        "create `~/.codex/config.toml` (or `config.toml` in the folder `CODEX_HOME` names) with "
        "`sandbox_mode = \"workspace-write\"` or `\"read-only\"`.",
}
UNKNOWN_GAP = ("**Not checked:** {}", "Review this part of your setup yourself.")


def lookup(table, message):
    """The table's text for a gap message, filling in the setting a labelled message names; None if it has none."""
    if message in table:
        return table[message]
    for key, text in table.items():
        if "{label}" in key:
            found = re.fullmatch(re.escape(key).replace(r"\{label\}", r"([\w./-]+)"), message)
            if found:
                return text.replace("{label}", found[1])
    return None


def parts(name):
    """Split an entry name into its configuration keys, unquoting the ones written as JSON strings."""
    return [json.loads(p) if p.startswith('"') else p for p in re.findall(r'"(?:[^"\\]|\\.)*"|[^."]+', name)]


SUBJECTS = {("mcp_servers", 2): "your {0} MCP server", ("mcp_servers", 4): "the {1} tool of your {0} MCP server",
            ("apps", 2): "your {0} app", ("apps", 4): "the {1} tool of your {0} app",
            ("hooks", 2): "your {0} hooks", ("notify", 1): "your `notify` setting"}


def finding(risk, files=None, contexts=None):
    """The plain lead, incident summary and What to do of a finding; None where its rule or entry has no wording."""
    keys = parts(risk["entry"].split(":", 1)[1])
    shape = (keys[0], len(keys))
    subject = SUBJECTS.get(shape, "").format(*[f"`{key}`" for key in keys[1::2]])
    plain = FINDINGS.get(risk["rule"])
    if plain is None:
        return None
    pick = lambda text: (text.get(keys[0]) if isinstance(text, dict)
                         else text[len(keys) == 4] if isinstance(text, tuple) else text)
    headline, why, step = pick(plain["headline"]), pick(plain["why"]), advice(risk, files or {}, contexts or {})
    if "{line}" in headline:
        if shape != ("prefix_rule", 2):
            return None
        headline = headline.format(line=keys[1])
    if "{Subject}" in headline:
        if not subject:
            return None
        headline = headline.replace("{Subject}", subject[:1].upper() + subject[1:])
    if step is None:
        return None
    return f"**{headline}** {why}", plain["how"], step


def gap(text, absent, files):
    """A gap's paragraph; absent holds the sources whose Codex config file automatic discovery did not find, and
    files maps a source found automatically to where Codex keeps it."""
    source, separator, message = text.partition(": ")
    if not (separator and re.fullmatch(r"(config|rules)-\d+", source)):
        source, message = None, text
    if source in absent and message in ABSENT:
        lead, step = ABSENT[message], ABSENT_STEPS[message]
    else:
        lead, step = lookup(GAPS, message), lookup(STEPS, message)
    if lead is None or step is None:
        lead, step = UNKNOWN_GAP[0].format(cell(message)), UNKNOWN_GAP[1]
    # Each part is its own paragraph: single newlines would join them when the Markdown is rendered.
    return f"{lead}\n\n*What to do:* {step}" + (f"\n\n*File `{files.get(source, source)}`*" if source else "")


# "Your setup": each catalog entry as one plain line (archived issue #105, second reading-check edit).
SETUP_LABELS = {("approval_policy",): "Approval", ("sandbox_mode",): "Sandbox",
                ("sandbox_workspace_write", "network_access"): "Network access for commands",
                ("shell_environment_policy",): "Environment for commands", ("web_search",): "Web search",
                ("notify",): "Notifications", ("apps", "_default"): "Defaults for all apps (`_default`)",
                ("features", "apps"): "ChatGPT Apps connection"}
SETUP_SHAPES = {("mcp_servers", 2): "MCP server {0}", ("mcp_servers", 3, "enabled_tools"): "Allowed tools of MCP server {0}",
                ("mcp_servers", 3, "disabled_tools"): "Blocked tools of MCP server {0}",
                ("mcp_servers", 4): "Tool {1} of MCP server {0}", ("apps", 2): "App {0}", ("apps", 4): "Tool {1} of app {0}",
                ("model_providers", 2): "Model provider {0}", ("hooks", 2): "{0} hooks",
                ("prefix_rule", 2): "Saved approval, line {line}"}
SETUP_WORDS = {
    "configured enabled": "on", "disabled": "off", "enablement unknown": "on or off unknown",
    "disabled or enablement unknown": "off or unknown", "enabled even if destructive": "even if it can change or delete data",
    "default tools disabled or unknown": "tools off unless turned on one by one (or unknown)",
    "stdio; command withheld": "starts a program on your computer (command left out)",
    "HTTP; endpoint withheld": "connects over HTTP (address left out)", "transport unknown": "connection type unknown",
    "permission-profile selection is uninspected": "a permission profile may replace it (not checked)",
    "workspace-write option": "(applies in `workspace-write` mode)",
    "inactive or selection unknown": "(applies only in `workspace-write` mode, which isn't selected or is unknown)",
    "true": "on", "false": "off",
    "configured; endpoint and credentials withheld": "set up (address and credentials left out)",
    "notification command configured; command withheld": "start a program (command left out)",
    "contents withheld": "set (contents left out)", "absent": "none found",
    "no reportable configured names": "no names that can be shown", "some names withheld": "some names left out",
    "No default Codex configuration file was found. Assessed defaults: command environment and ChatGPT Apps.":
        "none found, so stay-safe assessed Codex's documented defaults (the environment of commands and the ChatGPT "
        "Apps connection)",
    # The ChatGPT Apps connection (harnesses/codex.md row `features.apps` `omitted`, archived issue #121).
    "ChatGPT Apps": "an MCP connection to ChatGPT",
    "exists only if Codex is signed in with ChatGPT, which is not checked":
        "only when Codex is signed in with ChatGPT (stay-safe doesn't check sign-in)",
    "features.apps = false turns it off": "`features.apps = false` turns it off",
    "broad: one-token prefix": "covers every use of that program",
    "never": "`never` (doesn't ask before commands)", "on-request": "`on-request` (Codex can ask before commands)",
    "read-only": "`read-only` (commands can't write files)",
    "workspace-write": "`workspace-write` (commands can write in your workspace)",
    "danger-full-access": "`danger-full-access` (no sandbox)",
}
APPROVAL_MODES = {"auto", "approve", "prompt", "writes"}
INHERIT = {"all": "all variables passed on", "core": "only core variables passed on", "none": "none passed on"}
ORIGIN = {"explicit": "you set this", "default": "default"}


def setup_words(keys, observation):
    """One observation in plain words; text without wording is shown as it is."""
    if keys == ["web_search"]:
        return f"`{observation}`"
    if keys == ["apps", "_default"] and observation == "disabled":
        return "off (this doesn't turn off your named apps)"
    if observation in SETUP_WORDS:
        return SETUP_WORDS[observation]
    found = re.fullmatch(r"tool approval: (\w+)( \(default\))?", observation)
    if found and found[1] in APPROVAL_MODES:
        mode = f"`{found[1]}`"
        return f"tool approval left at the default, {mode}" if found[2] else f"tool approval {mode}"
    found = re.fullmatch(r"destructive tools (enabled|disabled) by (.+)", observation)
    if found:
        origin = "Codex default" if found[2] == "Codex default" else f"set by `{found[2]}`"
        return f"tools that change or delete data {'on' if found[1] == 'enabled' else 'off'} ({origin})"
    found = re.fullmatch(r"configured names: (.+)", observation)
    if found:
        return ", ".join(f"`{name}`" for name in found[1].split(", "))
    found = re.fullmatch(r"program: (.+)", observation)
    if found:
        return f"starts with `{found[1]}`"
    found = re.fullmatch(r"tokens: (\d+)", observation)
    if found:
        return f"{found[1]} word" + ("" if found[1] == "1" else "s")
    found = re.fullmatch(r"inherit: (all|core|none) \((explicit|default)\)", observation)
    if found:
        return f"{INHERIT[found[1]]} ({ORIGIN[found[2]]})"
    found = re.fullmatch(r"ignore_default_excludes: (true|false) \((explicit|default)\)", observation)
    if found:
        return f"`ignore_default_excludes` {found[1]} ({ORIGIN[found[2]]})"
    return cell(observation)


def setup_line(entry):
    keys = parts(entry["name"])
    label = {"configuration file": "Config file", "rules file": "Saved approvals file"}.get(entry["kind"])
    label = label or SETUP_LABELS.get(tuple(keys))
    shape = SETUP_SHAPES.get((keys[0], len(keys))) or SETUP_SHAPES.get((keys[0], len(keys), keys[-1]))
    if label is None and shape:
        label = shape.format(*[f"`{key}`" for key in keys[1::2]], line=keys[-1])
    label = label or f"`{entry['name']}`"
    text = ""
    for observation in entry["observations"]:
        words = setup_words(keys, observation)
        text += (" " if words.startswith("(") else ", " if text else "") + words
    return f"- {label}: {text}" if text else f"- {label}"


def count(number, singular, plural):
    return f"{number} {singular if number == 1 else plural}"


NOT_CHECKED = ("stay-safe reads only settings whose meaning it has checked against Codex, and it skips anything it "
               "can't read or check rather than guess. Each item says what to do.")
WITHHELD_NOTE = ("stay-safe doesn't show commands, addresses, credentials, hook contents, tool names that look "
                 "private or the words of saved approvals, because they can hold private paths or tokens. You'll find them in the file named in "
                 "each list's heading, for example a server's command under `[mcp_servers.<name>]`.")
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
FILE_USE = {"config": "Codex reads its settings from this file.",
            "rules": "Codex saves \"don't ask again\" approvals to this file and loads them from it."}


def file_heading(source, files, missing=()):
    """A Your setup heading: where a found file lives, or which file you passed, and how Codex uses it."""
    kind = "config" if source.startswith("config-") else "rules" if source.startswith("rules-") else None
    if kind is None:
        return f"**`{source}`**"
    title = "Config file" if kind == "config" else "Rules file"
    if source in files:
        use = FILE_USE[kind]
        if kind == "config" and source in missing:
            use = "Codex reads its settings from this file when it exists."
        return f"**{title} `{files[source]}`** (`{source}`): {use}"
    if kind == "config":
        number = int(source.split("-", 1)[1])
        word = ORDINALS[number - 1] if number <= len(ORDINALS) else f"number {number}"
        return (f"**{title} `{source}`**: the {word} file you passed with `--config`. "
                "Codex reads settings from config files like this.")
    return (f"**{title} `{source}`**: the file you passed with `--rules`. "
            "Codex loads saved approvals from rules files like this.")


def made_by(provenance):
    """The short commit, marked when it came from a release archive rather than a Git checkout (archived issue #132)."""
    label = f"`{provenance['source_revision'][:7]}`"
    return label + " (release archive)" if provenance["source_status"] == "release archive commit" else label


def markdown(report, files=None):
    files = files or {}
    risks, gaps = report["risks"], report["inspection_gaps"]
    lines = ["# Codex configuration diagnostic", "",
             f"{count(len(risks), 'finding', 'findings')}, {count(len(gaps), 'thing', 'things')} not checked.",
             "", "## Findings", ""]
    blocks = []
    # The sandboxes the files set, so the advice never suggests a looser one (reviews of archived PR #129, F2 and F13).
    contexts = sandbox_context(report)
    for risk in risks:
        citations = ", ".join(f"[{i}]({report['incident_links'][i]})" if i in report["incident_links"] else i for i in risk["incidents"])
        lead, how, step = finding(risk, files, contexts) or (risk["explanation"], "See the cited incidents.",
                                                   "*What to do:* Review this setting yourself.")
        kind = "rules entry" if risk["entry"].startswith("rules-") else "setting"
        blocks.append("\n\n".join([
            lead,
            f"*How it has gone wrong:* {how} {citations} ({report['incident_status']}).",
            step,
            f"*Rule `{risk['rule']}` · {kind} `{risk['entry']}` = `{'; '.join(risk['configured_evidence'])}`*"]))
    if risks:
        lines += [note(report, files), "", "\n\n---\n\n".join(blocks), ""]
    else:
        lines += ["None of stay-safe's rules matched your settings. That doesn't mean your setup is safe: "
                  "see what stay-safe didn't check and what this report can't see, below.", ""]
    lines += ["## Not checked", ""]
    absent = {entry["source"] for entry in report["catalog"] if entry["kind"] == "configuration file"}
    if gaps:
        lines += [NOT_CHECKED, "", "\n\n---\n\n".join(gap(text, absent, files) for text in gaps), ""]
    else:
        lines += ["stay-safe checked every setting it supports in the files it read. "
                  "What this report can't see, below, still applies.", ""]
    lines += ["## Your setup", ""]
    groups = {}
    for entry in report["catalog"]:
        groups.setdefault(entry["source"], []).append(setup_line(entry))
    if any("left out" in line for entries in groups.values() for line in entries) \
            or any(entry["kind"] == "saved approval" for entry in report["catalog"]):
        lines += [WITHHELD_NOTE, ""]
    missing = {entry["source"] for entry in report["catalog"] if entry["kind"] in ("configuration file", "rules file")}
    for source, entries in groups.items():
        lines += [file_heading(source, files, missing), *entries, ""]
    if not groups:
        lines += ["stay-safe found no settings to list.", ""]
    lines.pop()
    lines += ["", "## Sources", ""]
    sources = sorted({(risk["rule_source"], risk["interpretation_source"]) for risk in risks}, key=str)
    if not risks:
        lines.append("No findings, so there are no rule sources to link.")
    elif any(rules is None for rules, _ in sources):
        lines.append("Source links are left out because stay-safe couldn't tell which commit it's running from.")
    for rules, meanings in sources:
        if rules is not None:
            lines += [f"- [How each finding's rule is defined]({rules}) (`stay_safe/rules.py`)",
                      f"- [What each Codex setting means, with official evidence]({meanings}) (`harnesses/codex.md`)"]
    revision = report["provenance"]["source_revision"]
    lines += ["", "## What this report can't see", "",
              "- Settings chosen in the app or with command-line flags, and which profile Codex uses: these can "
              "override the files listed under Your setup, and stay-safe can't see them. Check them where you start "
              "Codex, and the `profile` setting in your config file.",
              "- Whether connections work, or what Codex actually allows when it runs: stay-safe only reads files; it "
              "doesn't start Codex or contact any service. Watch what Codex asks before it acts.",
              "- Private values such as commands, addresses and tokens are left out, but names like `github` are "
              "shown as written: names can identify a project or a person, so check them before sharing."]
    # Only files that were found count: a default run always lists config-1 and rules-1 (re-review F22).
    if len(set(groups) - missing) > 1:
        lines.append("- These files are read as separate snapshots, not combined: Codex may apply several of them "
                     "together, so a setting in one can change what another allows.")
    guide = source_link(revision, "docs/report.md")
    lines += ["", f"[Full scope of this report]({guide}#full-scope)" if guide
              else "Full scope of this report: see the Full scope section of stay-safe's docs/report.md.",
              "", "---", "",
              f"Made by stay-safe {made_by(report['provenance']) if guide else '(commit unknown)'} · report format "
              f"{report['format_version']} · [challenge a finding]({REPOSITORY}/issues/new?template=challenge.yml)"]
    return "\n".join(lines) + "\n"


# The saved page is the Markdown report as a Markdown previewer shows it (archived issue #106): the same lines, read with
# the few Markdown forms markdown() writes. All text is escaped; links are kept only for https targets.
INLINE = re.compile(r"`([^`\n]*)`|\[([^\]\n]*)\]\((https://[^)\s]*)\)|\*\*|\*")
STYLE = """body { font-family: system-ui, sans-serif; line-height: 1.5; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; }
p, li { overflow-wrap: anywhere; }
code { font-family: ui-monospace, monospace; font-size: 0.95em; }
hr { border: 0; border-top: 1px solid; margin: 1.5rem 0; }"""


def text(value):
    """Markdown text outside code spans shows entities such as &#124; as their character; escape that for HTML."""
    return escape(unescape(value), quote=False)


def inline(line):
    """One line's text, code spans, https links, bold (`**`) and italic (`*`); emphasis left open closes at its end."""
    out, open_tags, position = [], [], 0

    def toggle(tag):
        if tag not in open_tags:
            out.append(f"<{tag}>")
            open_tags.append(tag)
            return
        above = open_tags[open_tags.index(tag) + 1:]
        out.extend(f"</{t}>" for t in [*reversed(above), tag])
        del open_tags[open_tags.index(tag):]
        for t in above:
            out.append(f"<{t}>")
            open_tags.append(t)

    for found in INLINE.finditer(line):
        out.append(text(line[position:found.start()]))
        if found[0] == "**":
            toggle("strong")
        elif found[0] == "*":
            toggle("em")
        elif found[0].startswith("`"):
            out.append(f"<code>{escape(found[1], quote=False)}</code>")
        else:
            out.append(f'<a href="{escape(found[3], quote=True)}">{text(found[2])}</a>')
        position = found.end()
    out.append(text(line[position:]))
    out.extend(f"</{t}>" for t in reversed(open_tags))
    return "".join(out)


def page(report, files=None):
    """Headings, horizontal rules, then paragraphs and lists: a run of `- ` lines is a list, other lines a paragraph."""
    body = []
    for block in markdown(report, files).rstrip("\n").split("\n\n"):
        if block.startswith("# "):
            body.append(f"<h1>{inline(block[2:])}</h1>")
        elif block.startswith("## "):
            body.append(f"<h2>{inline(block[3:])}</h2>")
        elif block == "---":
            body.append("<hr>")
        else:
            runs = []
            for line in block.split("\n"):
                listed = line.startswith("- ")
                if runs and runs[-1][0] == listed:
                    runs[-1][1].append(line)
                else:
                    runs.append((listed, [line]))
            for listed, lines in runs:
                if listed:
                    body.append("<ul>\n" + "\n".join(f"<li>{inline(line[2:])}</li>" for line in lines) + "\n</ul>")
                else:
                    body.append("<p>" + "<br>\n".join(inline(line) for line in lines) + "</p>")
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>Codex configuration diagnostic</title>\n<style>\n{STYLE}\n</style>\n</head>\n<body>\n"
            + "\n".join(body) + "\n</body>\n</html>\n")


def render(report, format_name="markdown", files=None):
    """files maps an automatically found source, such as config-1, to where Codex keeps it; JSON doesn't use it."""
    if format_name == "json":
        return json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if format_name == "html":
        return page(report, files)
    return markdown(report, files)
