from html import escape, unescape
import json
from pathlib import Path
import re

from .codex import (APP_TOOL_REVIEWER_GAP, APPROVALS, EMPTY_PROFILES, EXCLUDED_ACCOUNT, INLINE_MCP_VALUES, INLINE_PROFILE_OVERRIDE,
                    INVALID_APPROVAL, INVALID_BOOLEAN, INVALID_MCP_MAP, INVALID_PROFILE_SELECTOR, LEGACY_PROFILE_SELECTOR,
                    LEGACY_PROFILE_TABLES, PROFILE_LOADER_VERSION, ROOT_HOME_UNKNOWN, ROOTS_NO_WORKSPACE, ROOTS_SCOPE,
                    WORKSPACE_HOME, WORKSPACE_HOME_UNKNOWN, WORKSPACE_UNKNOWN, read_file)
from .codex_rules import other_files, read_file as read_rules
from .rules import SANDBOX_OFF_EXPLANATION, evaluate
from .provenance import GAP, REPOSITORY, fingerprints, identify, source_link, resource

INCIDENTS = resource("incidents.md")
INCIDENT_STATUS = "reported, not verified"
APPROVAL_OPTIONS = ", ".join(f'`"{mode}"`' for mode in APPROVALS[:-1]) + f' or `"{APPROVALS[-1]}"`'


def incident_links(path=INCIDENTS, revision=None):
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
    "CLI flags, profile selection, trusted project layers, managed policies and runtime overrides are not inspected. "
    "A separately selected profile file can override the main config.",
    "Connection reachability, authentication, active tools and effective permissions are not tested.",
    "Source links point to the reported commit; whether that commit exists in the published GitHub repository is not checked.",
    "The catalog contains configured entries, documented defaults and source-status observations; account, endpoint, environment, saved approval command (except a first word on stay-safe's program list) and other command and argument values are withheld.",
    "Configuration names in the report, such as server, app, tool and provider names, "
    "are shown as written and should be reviewed before sharing.",
]


def inspect(paths, *, rules_path=None, discovered=False, gaps=(), workspace=None):
    entries, gaps = [], list(gaps)
    hashes = fingerprints()
    provenance = identify(hashes=hashes)
    for index, path in enumerate(paths, 1):
        found, missing = read_file(path, f"config-{index}", discovered=discovered, workspace=workspace)
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


PROGRAM = "If that program or your config file were tampered with, it could run code you didn't intend."
AUTOMATIC = "Untrusted tool content could lead to unwanted actions."
DESTRUCTIVE = "A mistaken operation could change or delete data in the connected service."
SOURCE_ONLY = "Based on Codex's source code, not yet seen in a live run."
INJECTION = ("Instructions hidden in public GitHub issues and issue comments could take over agents that read them.")
FINDINGS = {
    "saved_approval": {
        "headline": "A saved approval on line {line} of your rules file says matching commands may run outside the "
                    "sandbox without asking you.",
        "why": "It covers every command that starts with its saved words. A rule that asks first or forbids the "
               "command can override it, and stay-safe doesn't check whether one does.",
        "how": "A Codex user reported that a saved approval for `curl` let later `curl` commands run without asking, "
               "even after restarting in another workspace. A Claude Code user reported that a broad Railway "
               "approval let a command print secrets into the transcript while commands to release a new version "
               "stayed blocked."},
    "commands_without_prompts": {
        "headline": "With these settings, Codex runs commands without asking you.",
        "why": "It won't ask before any command it's allowed to run, so injected or mistaken instructions could make "
               "it run code you didn't want.",
        "how": "Agents running commands without approval have run a delete command aimed at a home directory "
               "and wiped a drive. Another user reported an automatic driver update while getting help with GPU performance."},
    "unrestricted_filesystem": {
        "headline": "Your config turns off Codex’s sandbox.",
        "why": SANDBOX_OFF_EXPLANATION,
        "how": "Agents have deleted a home directory and wiped a whole drive with one mistaken delete command. "
               "A Claude Code user reported losing SSH keys and cloud credentials when a PowerShell cleanup "
               "deleted files in their home directory. GitHub Copilot was tricked into editing its own approval "
               "settings. Intruders changed project settings that Claude Code used at startup."},
    "writable_project_settings": {
        "headline": "Your config lists the project's `.codex` directory as writable.",
        "why": "A sandboxed command could change project settings that a later trusted Codex run uses.",
        "how": "Injected text got GitHub Copilot to change its approval settings. In another report, intruders "
               "changed project settings that Claude Code used at startup."},
    "configured_program": {
        "headline": "{Subject} can start a program on your computer.",
        "why": PROGRAM,
        "how": "Flaws in other agents let repository settings run commands on collaborators' machines, and a worm "
               "wrote itself into an agent's settings so its code ran at every start. Google reported that intruders "
               "changed project settings so Claude Code would download a backdoor at startup."},
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
AUTOMATIC_GROUP = {
    "what": "Set `default_tools_approval_mode = \"writes\"` (uses server hints){allowlist}. "
            "Stricter: `default_tools_approval_mode = \"prompt\"`.",
    "allowlist": ", or list only the tools you use in `enabled_tools`",
    "where": "under `[{table}]`",
    "ask": "Edit {file} to set `default_tools_approval_mode = \"writes\"` for my `{name}` {kind}"}
LABELS_GROUP = {
    "what": "Set `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for tools you trust"
            "{allowlist}. Stricter: `default_tools_approval_mode = \"prompt\"` for every tool.",
    "allowlist": ", or list only the tools you use in `enabled_tools`",
    "where": "under `[{table}]`, with each trusted tool's `approval_mode` under `[{table}.tools.<tool>]`",
    "ask": "Edit {file} so my `{name}` {kind} uses `default_tools_approval_mode = \"prompt\"` with `approval_mode = \"approve\"` only for these tools I trust: <tool names>"}
KEEP_SANDBOX = "Edit {file} to set `approval_policy = \"on-request\"` without changing `sandbox_mode`"
PROFILE_CHECK = "Review `default_permissions` in {profile} and any profile it names."
COMMANDS_CHECK = "Look for `approval_policy` and `sandbox_mode` in {where}."
ASK_FOR_BLOCKED = "If you want Codex to ask before running some commands it currently blocks, choose "
ORDINARY_STILL_RUN = "Ordinary commands can still run inside the sandbox without asking you."
APPROVAL_ONLY = "`approval_policy` " + TOP
COMMANDS = {
    "profile": {
        "what": ASK_FOR_BLOCKED + '`approval_policy = "on-request"`. ' + ORDINARY_STILL_RUN +
                " For read-only access, check that any profile you use blocks writes. Even then, " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": "{mode_note}" + PROFILE_CHECK},
    "read-only": {
        "what": ASK_FOR_BLOCKED + "`approval_policy = \"on-request\"` and keep `sandbox_mode = \"read-only\"` "
                "(commands still can't write files). " + ORDINARY_STILL_RUN + " But " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    "workspace-write": {
        "what": ASK_FOR_BLOCKED + "`approval_policy = \"on-request\"` and keep `sandbox_mode = \"workspace-write\"` "
                "(commands can still write in your workspace). " + ORDINARY_STILL_RUN + " Stricter: also "
                "`sandbox_mode = \"read-only\"` (commands can't write files). Either way, " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    "other": {
        "what": ASK_FOR_BLOCKED + "`approval_policy = \"on-request\"` without loosening the "
                "`sandbox_mode = \"{value}\"` in `{label}`. " + ORDINARY_STILL_RUN + " But " + SAVED_STILL,
        "where": APPROVAL_ONLY, "ask": KEEP_SANDBOX, "check": COMMANDS_CHECK},
    "full-on-request": {
        "what": "Set `sandbox_mode = \"workspace-write\"` and keep `approval_policy = \"on-request\"` (commands can write "
                "in your workspace and in any extra folders in `writable_roots`, so review that list). "
                + ORDINARY_STILL_RUN + " Stricter: `sandbox_mode = \"read-only\"` "
                "(commands can't write files). Either way, " + SAVED_STILL,
        "where": "`sandbox_mode` " + TOP,
        "ask": "Edit {file} to set `sandbox_mode = \"workspace-write\"` without changing `approval_policy`",
        "check": COMMANDS_CHECK},
    "full-on-request-read-only": {
        "what": "Set `sandbox_mode = \"read-only\"`, as `{label}` does, and keep `approval_policy = \"on-request\"` "
                "(commands can't write files). " + ORDINARY_STILL_RUN + " But " + SAVED_STILL,
        "where": "`sandbox_mode` " + TOP,
        "ask": "Edit {file} to set `sandbox_mode = \"read-only\"` without changing `approval_policy`",
        "check": COMMANDS_CHECK},
    None: {
        "what": ASK_FOR_BLOCKED + "`approval_policy = \"on-request\"` with `sandbox_mode = \"workspace-write\"` "
                "(commands can write in your workspace and in any extra folders in `writable_roots`, so review that "
                "list). " + ORDINARY_STILL_RUN + " Stricter: `sandbox_mode = \"read-only\"` "
                "(commands can't write files). Either way, " + SAVED_STILL,
        "where": TOP,
        "ask": "Edit {file} to set `approval_policy = \"on-request\"` and `sandbox_mode = \"workspace-write\"`",
        "check": COMMANDS_CHECK}}
SANDBOX = {
    "read-only": {
        "what": "Set `sandbox_mode = \"read-only\"`, as `{label}` does (commands can't write files).",
        "where": TOP, "ask": "Edit {file} to set `sandbox_mode = \"read-only\"`"},
    None: {
        "what": "Set `sandbox_mode = \"workspace-write\"` (commands can write in your workspace and in any extra "
                "folders in `writable_roots`, so review that list). Stricter: "
                "`sandbox_mode = \"read-only\"` (commands can't write files).",
        "where": TOP, "ask": "Edit {file} to set `sandbox_mode = \"workspace-write\"`"}}
FULL_ACCESS_TOOLS = {
    "read-only": {
        "what": "Set `sandbox_mode = \"read-only\"`, as `{label}` does (each server's and app's tool approval mode then "
                "applies, Codex refuses calls that need approval instead of asking, and commands can't write files).",
        "where": "`sandbox_mode` " + TOP,
        "ask": "Edit {file} to set `sandbox_mode = \"read-only\"` without changing `approval_policy`"},
    None: {
        "what": "Set `sandbox_mode = \"workspace-write\"` (each server's and app's tool approval mode then applies, and "
                "Codex refuses calls that need approval instead of asking), and review any extra folders in "
                "`writable_roots`. Stricter: `sandbox_mode = \"read-only\"` "
                "(commands can't write files).",
        "where": "`sandbox_mode` " + TOP,
        "ask": "Edit {file} to set `sandbox_mode = \"workspace-write\"` without changing `approval_policy`"}}
FULL_ACCESS_HEADLINES = {
    "commands_without_prompts": ("With these settings, Codex runs most commands without asking you.",
                                 "With `sandbox_mode = \"danger-full-access\"`, ordinary commands can run without "
                                 "asking, including ones that delete or change files. For commands without a matching "
                                 "rule, Codex asks first only if it flags the command as dangerous, such as a forced "
                                 "`rm`."),
    "automatic_tools": ("With these settings, Codex can use MCP server and app tools without asking you.",
                        "`approval_policy = \"never\"` with `sandbox_mode = \"danger-full-access\"` can allow MCP "
                        "server and app tools to run without asking you, even when a tool's approval mode requests "
                        "approval. " + AUTOMATIC)}
ADVICE = {
    ("commands_without_prompts", "approval_policy", 1): COMMANDS,
    ("automatic_tools", "approval_policy", 1): FULL_ACCESS_TOOLS,
    ("unrestricted_filesystem", "sandbox_mode", 1): SANDBOX,
    ("configured_program", "mcp_servers", 2): {
        "what": "Keep it if you trust the program it starts. Stricter: `enabled = false`; if nothing you use stops "
                "working, leave it off.",
        "where": "under `[{table}]`",
        "ask": "Edit {file} to set `enabled = false` for my `{name}` MCP server",
        "check": "Under `[{table}]` in {where}, the program is `command` with its `args` (or `http_headers_helper`); "
                 "for a launcher such as `npx`, `uvx`, `docker`, `node` or `python`, what runs is named in `args`. Find "
                 "out who publishes it before you trust it."},
    ("configured_program", "notify", 1): {
        "what": "Keep it if you trust the program it starts. Stricter: remove `notify` if you don't need notifications.",
        "where": "delete the `notify` setting, including any lines its list continues on",
        "ask": "Edit {file} to remove the `notify` setting",
        "check": "In {where}, the first item in the `notify` list is the program it starts; for a launcher such as "
                 "`node` or `npx`, the next items name what runs. Find out who publishes it before you trust it."},
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
    ("writable_project_settings", "sandbox_workspace_write", 2): {
        "what": "Remove the project's `.codex` directory from `writable_roots`. You can keep the workspace writable.",
        "where": "under `[sandbox_workspace_write]`, remove each entry for that directory",
        "ask": "Edit {file} to remove the selected project's `.codex` directory from `writable_roots`, "
               "keeping the other entries",
        "check": "Rerun stay-safe with the same `--workspace` and config selection."},
    ("network_access", "sandbox_workspace_write", 2): {
        "what": "Set `network_access = false` unless commands need the network.",
        "where": "under `[sandbox_workspace_write]`",
        "ask": "Edit {file} to set `network_access = false` under `[sandbox_workspace_write]`"},
    ("environment_inheritance", "shell_environment_policy", 1): {
        "what": "Set `inherit = \"core\"` (commands get only core variables, such as `HOME` and `PATH`, plus any you "
                "list under `set`). Stricter: `inherit = \"none\"` (no inherited variables).",
        "where": "under `[shell_environment_policy]` (inside its `{{ }}` if it's on one line)",
        "ask": "Edit {file} to set `inherit = \"core\"` under `[shell_environment_policy]`",
        "check": "In a terminal like the one you start Codex from, run "
                 "`awk 'BEGIN {{ for (name in ENVIRON) print name }}'` to list the names of your environment variables "
                 "without their values, and look for names that suggest credentials."},
    ("saved_approval", "prefix_rule", 2): {
        "what": "Replace it with a rule whose `pattern` has more words (it then covers only the commands you meant), "
                "for example `[\"git\", \"status\"]` instead of `[\"git\"]`. Stricter: delete line {line}.",
        "where": "on line {line}, add the next words of the command you meant to the `pattern` list",
        "ask": "Edit {file} to replace line {line} with a rule that allows only <the command you meant>",
        "check": "Open {where} and read line {line}: its `pattern` lists the words a command must start with."},
}
TEMPLATE_HEADLINES = {
    "automatic_tools": "Apps your config doesn't name use tool approval mode `approve`, set in `apps._default`.",
    "destructive_tools": "Apps your config doesn't name have tools that can change or delete data turned on, set in "
                         "`apps._default`."}
TEMPLATE_ADVICE = {
    "automatic_tools": {
        "what": "Set `default_tools_approval_mode = \"writes\"` (uses server hints). Stricter: "
                "`default_tools_approval_mode = \"prompt\"`. Apps you name without their own mode change too.",
        "where": "under `[apps._default]`",
        "ask": "Edit {file} to set `default_tools_approval_mode = \"writes\"` under `[apps._default]`"},
    "destructive_tools": {
        "what": "Set `destructive_enabled = false` (tools marked as not destructive stay on; tools marked destructive, "
                "or not marked, turn off). Stricter: `enabled = false` (apps your config doesn't name turn off; apps "
                "you name stay on).",
        "where": "under `[apps._default]`",
        "ask": "Edit {file} to set `destructive_enabled = false` under `[apps._default]`"}}
KINDS = {"mcp_servers": "MCP server", "apps": "app"}
STRICTNESS = ("read-only", "workspace-write")


def sandbox_context(report, files):
    sources = {entry["source"] for entry in report["catalog"] if entry["source"].startswith("config-")}
    gaps = {}
    for text in report["inspection_gaps"]:
        source, _, message = text.partition(": ")
        gaps.setdefault(source, set()).add(message)
    sources |= {source for source in gaps if source.startswith("config-")}
    own = {entry["source"]: entry["observations"][0] for entry in report["catalog"]
           if entry["name"] == "sandbox_mode" and entry["observations"]}
    full = {entry["source"]: entry["observations"][0] for entry in report["catalog"]
            if entry["name"] == "approval_policy" and len(entry["observations"]) == 2
            and entry["observations"][1].startswith("with danger-full-access")}
    profiles = [source for source, messages in gaps.items()
                if "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown." in messages
                or ("Named permission profiles are outside reader coverage; sandbox settings are not "
                    "effective-permission evidence." in messages
                    and "sandbox_mode is absent; the reader does not infer its effective value." not in messages
                    and "sandbox_mode is unsupported or invalid; its value was withheld." not in messages
                    and source not in own)]
    profile_files = ", ".join(f"`{files.get(source, source)}`" for source in sorted(profiles, key=source_order))
    context = {}
    for source in sources:
        others = sorted((int(other.split("-")[1]), other) for other, value in own.items()
                        if other != source and value == "read-only")
        context[source] = {"sandbox": own.get(source), "profile": profile_files, "full_access": full.get(source),
                           "other": ("read-only", others[0][1]) if others else None}
    return context


def pick_spec(spec, context):
    if spec is COMMANDS:
        if context.get("full_access") == "on-request":
            return COMMANDS["full-on-request-read-only" if context.get("other") else "full-on-request"]
        if context.get("profile"):
            return COMMANDS["profile"]
        if context.get("sandbox") in STRICTNESS:
            return COMMANDS[context["sandbox"]]
        return COMMANDS["other"] if context.get("other") else COMMANDS[None]
    if spec is SANDBOX or spec is FULL_ACCESS_TOOLS:
        return spec["read-only"] if context.get("other") else spec[None]
    return spec


def advice(risk, files, contexts):
    source, _, name = risk["entry"].partition(":")
    keys = parts(name)
    spec = (TEMPLATE_ADVICE.get(risk["rule"]) if keys == ["apps", "_default"]
            else ADVICE.get((risk["rule"], keys[0], len(keys))))
    if spec is None or (keys[0] == "prefix_rule" and not keys[1].isdigit()):
        return None
    context = contexts.get(source, {})
    spec = pick_spec(spec, context)
    path = files.get(source)
    other = context.get("other") or ("", "")
    mode = context.get("sandbox")
    fields = {"file": f"`{path}`" if path else f"`<{source}>`", "where": f"`{path}`" if path else f"`<{source}>`",
              "table": name, "name": keys[1] if len(keys) > 1 else "", "tool": keys[3] if len(keys) == 4 else "",
              "kind": KINDS.get(keys[0], ""), "line": keys[1] if len(keys) > 1 else "",
              "allowlist": spec.get("allowlist", "") if keys[0] == "mcp_servers" else "",
              "value": other[0], "label": other[1], "profile": context.get("profile", ""),
              "mode_note": f"This file sets `sandbox_mode` to `{mode}`. " if mode else ""}
    fill = lambda text: text.format(**fields)
    paragraphs = [f"*What to do:* {fill(spec['what'])}",
                  f"*Change it:* {fill(spec['where'])}, or ask Codex: \"{fill(spec['ask'])}; show only what you change.\""]
    if "check" in spec:
        paragraphs.append(f"*Check:* {fill(spec['check'])}")
    return "\n\n".join(paragraphs)


def note(report, files):
    passed = any(risk["entry"].split(":", 1)[0] not in files for risk in report["risks"])
    return NOTE.format(placeholders=PLACEHOLDERS if passed else "")


WITHHELD = "The value is left out of this report."
EXTRA_FOLDERS = "Some may be outside your workspace. Their paths are withheld."
REVIEW_ROOTS = ("Review each folder in `writable_roots` and remove any that commands shouldn't change, "
                "such as the Docker socket (`/var/run/docker.sock`).")
GAPS = {
    INLINE_MCP_VALUES: "**Not checked: inline values in `{label}`.** stay-safe did not check these entries for credentials.",
    INVALID_MCP_MAP: "**Codex cannot load this configuration.** `{label}` must be a table of strings.",
    "Unchecked section {label}; its settings were not evaluated.":
        "**Not checked: `{label}`.** Its settings were not evaluated.",
    "projects contains {label} recognized trusted declarations; project settings were not inspected.":
        "**Not checked: project settings.** Projects marked as trusted in your file: {label}. "
        "Their settings were not inspected.",
    "projects contains malformed or unsupported data; its declarations could not be fully assessed.":
        "**Not checked: some project declarations.** The project declarations could not be fully assessed. "
        "Some data is malformed or unsupported, so a reported count covers only recognized declarations.",
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
    ROOTS_NO_WORKSPACE: "**Not checked: extra writable folders.** Your config lists folders commands may write. "
                        f"{EXTRA_FOLDERS} Supply `--workspace DIR` to check for a direct grant to the project's `.codex`.",
    ROOTS_SCOPE: f"**Not checked: other effects of extra writable folders.** {EXTRA_FOLDERS} The project settings "
                 "check covers a direct grant to `.codex`. It leaves other relative paths, aliases and the folders' "
                 "contents unchecked.",
    ROOT_HOME_UNKNOWN: "**Not checked: home-relative writable folders.** The file uses `~` or `~/`, "
                       "but `HOME` does not give an absolute path for the comparison.",
    WORKSPACE_UNKNOWN: "**Not checked: the project settings directory.** A path component is a symlink, "
                       "is not a directory, or could not be checked.",
    WORKSPACE_HOME_UNKNOWN: "**Not checked: the project settings directory.** The user Codex home is unknown "
                            "or has an unresolved path or alias.",
    WORKSPACE_HOME: "**Not checked: user Codex home.** Codex treats this folder as its user configuration folder.",
    "sandbox_workspace_write.writable_roots is invalid; its value was withheld.":
        "**Not checked: extra folders commands can write to.** Your `writable_roots` isn't a list of folder "
        f"paths, so stay-safe can't tell where commands can write. {WITHHELD}",
    "sandbox_mode is unsupported or invalid; its value was withheld.":
        "**Not checked: your sandbox setting.** Your `sandbox_mode` value isn't one stay-safe supports, so it "
        f"can't tell what commands Codex runs are allowed to do. {WITHHELD}",
    "Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.":
        "**Not checked: your permission profiles.** Stay-safe doesn't check permission profiles or what commands "
        "they allow.",
    "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.":
        "**Not checked: which sandbox Codex uses.** Your config file sets both `default_permissions` and "
        "`sandbox_mode`, so stay-safe can't tell which one Codex uses.",
    LEGACY_PROFILE_SELECTOR:
        f"**This file uses an old way to select a profile.** Codex {PROFILE_LOADER_VERSION} stops if "
        "`profile` is in the configuration it uses at startup. It ignores this setting in project configuration. "
        f"{INLINE_PROFILE_OVERRIDE}",
    LEGACY_PROFILE_TABLES:
        "**This file defines a profile but doesn’t select it.** If this is your main `config.toml` and you "
        f"start Codex {PROFILE_LOADER_VERSION} with `--profile` and a name defined here, the matching table stops "
        "Codex from loading. Starting with a name this file doesn’t define does not trigger that conflict. "
        f"{INLINE_PROFILE_OVERRIDE}",
    INVALID_PROFILE_SELECTOR:
        "**`profile` isn’t a quoted name.** Codex expects a string here. It ignores this setting in project "
        "configuration.",
    EMPTY_PROFILES:
        "**Not checked: profile selection.** The `profiles` table is empty. It defines no names that could "
        "conflict with a startup profile.",
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
    "Codex cannot load this configuration because stdio MCP server {label} sets http_headers_helper.":
        "**Codex can't load this configuration.** The `{label}` server uses `command` (stdio). "
        "Codex accepts `http_headers_helper` only on HTTP servers.",
    "Per-account app policy is not evaluated; account identifiers were withheld.":
        "**Not checked: per-account app settings.** An app has per-account settings (`links`), which stay-safe "
        "doesn't assess. Account identifiers are left out of this report.",
    "App approvals_reviewer is not evaluated; Codex may let a reviewer decide an app's tool calls instead of asking you.":
        "**Not checked: an app's approval reviewer.** An app sets `approvals_reviewer` (in `[apps.<name>]` or "
        "`[apps._default]`), which can let a reviewer such as automatic review decide its tool calls instead of "
        "asking you. stay-safe doesn't assess it.",
    APP_TOOL_REVIEWER_GAP:
        "**Not checked: `{label}`.** If this tool needs approval, your file asks Codex to have an AI reviewer "
        "approve or deny the request. Your organization can limit who may review requests. For example, if its "
        "policy allows only human review, Codex may ask you to decide. Stay-safe can’t tell from this file "
        "which policy applies to your run.",
    INVALID_APPROVAL: f"**{INVALID_APPROVAL}** Findings for other entries describe settings written in the file.",
    INVALID_BOOLEAN:
        "**Codex cannot load this configuration file.** `{label}` must be `true` or `false` without quotes. "
        "Findings for other entries describe settings written in the file.",
    "Model-provider command-backed authentication is outside reader coverage.":
        "**Not checked: a model provider's sign-in command.** A model provider gets its credentials by running a "
        "command (`auth`), which stay-safe doesn't assess.",
    "Model-provider setting {label} is for a credential command. Stay-safe did not check its value.":
        "**Not checked: a model provider's `{label}`.** This setting is for a credential command. Stay-safe did not check its value.",
    "otel.headers_helper is for a command that supplies telemetry headers. Stay-safe did not check its value.":
        "**Not checked: `otel.headers_helper`.** This setting is for a command that supplies telemetry headers. "
        "Stay-safe did not check its value.",
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
    "Codex home: skills holds Codex skills that were not inspected.":
        "**Not checked: your Codex skills.** Your Codex folder has skills in `skills`, which stay-safe doesn't read.",
    "Codex home: Could not check the skills folder. Check that you can open skills in your Codex folder.":
        "**Not checked: your Codex skills.** Could not check the skills folder.",
    "Codex home: environments.toml exists and was not inspected.":
        "**Not checked: your `environments.toml` file.** Your Codex folder has an `environments.toml` file, which "
        "stay-safe doesn't read.",
    "Codex home: Could not check environments.toml. Check that you can open environments.toml in your Codex folder.":
        "**Not checked: your `environments.toml` file.** Could not check it.",
    "Codex home: environments.toml is not a file; Codex fails to read it.":
        "**Not checked: your `environments.toml` file.** Your Codex folder has an `environments.toml` that isn't a "
        "regular file, such as a folder. Codex reports an error when it tries to read it.",
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
ABSENT = {
    "approval_policy is absent; the reader does not infer its effective value.":
        "**Not checked: your approval setting.** stay-safe found no Codex config file, so it can't tell whether "
        "Codex asks before running commands.",
    "sandbox_mode is absent; the reader does not infer its effective value.":
        "**Not checked: your sandbox setting.** stay-safe found no Codex config file, so it can't tell what "
        "commands Codex runs are allowed to do.",
}
STEPS = {
    INLINE_MCP_VALUES: "Review the entries for credentials in your own configuration file.",
    INVALID_MCP_MAP: "Give each entry in `{label}` a quoted string value, or remove the setting.",
    "Unchecked section {label}; its settings were not evaluated.":
        "Review the `{label}` section in your selected file yourself.",
    "projects contains {label} recognized trusted declarations; project settings were not inspected.":
        "Review the `projects` section in your selected file and the settings for projects you trust.",
    "projects contains malformed or unsupported data; its declarations could not be fully assessed.":
        "Check each entry in the `projects` section of your selected file yourself.",
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
    ROOTS_NO_WORKSPACE: REVIEW_ROOTS,
    ROOTS_SCOPE: REVIEW_ROOTS,
    ROOT_HOME_UNKNOWN: "Check these entries locally or rerun with `HOME` set to the absolute path of the "
                       "intended user's home.",
    WORKSPACE_UNKNOWN: "Use the project's direct directory path and check the listed roots locally.",
    WORKSPACE_HOME_UNKNOWN: "Check the path to your Codex home and the workspace locally.",
    WORKSPACE_HOME: "Select the project directory with `--workspace` to check its settings.",
    "sandbox_workspace_write.writable_roots is invalid; its value was withheld.": "Make `writable_roots` a list of folder paths, or remove it.",
    "sandbox_mode is unsupported or invalid; its value was withheld.":
        "Set it to `\"read-only\"`, `\"workspace-write\"` or `\"danger-full-access\"`.",
    "Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.":
        "Review your permission profiles yourself; findings about this file's sandbox may not apply.",
    "default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.":
        "Keep only one of `default_permissions` and `sandbox_mode`, then run stay-safe again.",
    LEGACY_PROFILE_SELECTOR:
        "Remove the `profile` setting. To use a user profile named `work`, move the settings inside "
        "`[profiles.work]` in your main config into `work.config.toml` in your Codex folder. Remove the old table and start Codex "
        "with `--profile work`. Then run stay-safe with `--config` and the path to that file to check its settings.",
    LEGACY_PROFILE_TABLES:
        "If you want to use one of these profiles, move its settings into a separate file in your Codex folder "
        "and remove the matching table from the main config. For example, use `work.config.toml` with "
        "`--profile work`.",
    INVALID_PROFILE_SELECTOR:
        "Remove the `profile` setting. To choose a profile, use a separate profile file and select it with "
        "`--profile`.",
    EMPTY_PROFILES:
        "If you start Codex with `--profile`, review the separate profile file you select.",
    "shell_environment_policy.inherit is unsupported or invalid; its value was withheld.":
        "Set `inherit` to `\"all\"`, `\"core\"` or `\"none\"`.",
    "shell_environment_policy.ignore_default_excludes has an invalid boolean; its behavior is unknown.":
        "Set `ignore_default_excludes` to `true` or `false`.",
    "Configuration contains fields outside reader coverage; their values were withheld.":
        "Review those settings yourself; stay-safe didn't evaluate them.",
    "profiles must be a table.":
        "Remove the malformed `profiles` value. If you want to use a profile, put its settings in a separate "
        "profile file in your Codex folder.",
    "{label} must be a table.": "Rewrite it as a group of settings, then run stay-safe again.",
    "{label} contains fields outside reader coverage; their values were withheld.":
        "Review the other settings under `{label}` yourself; stay-safe didn't evaluate them.",
    "{label} has an invalid boolean; its behavior is unknown.": "Set it to `true` or `false`.",
    "{label} contains a name that cannot be included in a shareable report.":
        "Review that entry yourself, since it isn't in this report.",
    "{label} contains an entry that is not a table.": "Rewrite it as a group of settings, then run stay-safe again.",
    "A tool approval mode is unsupported or invalid; its value was withheld.":
        f'Set it to {APPROVAL_OPTIONS}; use `"prompt"` to request approval.',
    "A per-tool approval mode is unsupported or invalid; its value was withheld.":
        f'Set it to {APPROVAL_OPTIONS}; use `"prompt"` to request approval.',
    "A tool allow/deny list contains a name that cannot be included in a shareable report.":
        "Review the full list in your config file yourself.",
    "A tool allow/deny list is invalid; tool availability is unknown.":
        "Make `enabled_tools` and `disabled_tools` lists of tool names.",
    "An MCP transport is missing, conflicting or invalid.": "Give the server either a `command` or a `url`, not both.",
    "An MCP header-helper command is invalid; its value was withheld.":
        "Set `http_headers_helper` to the command you mean to run, or remove it.",
    "Codex cannot load this configuration because stdio MCP server {label} sets http_headers_helper.":
        "To keep using stdio, remove `http_headers_helper` from this server's settings.",
    "Per-account app policy is not evaluated; account identifiers were withheld.":
        "Review those per-account settings yourself.",
    "App approvals_reviewer is not evaluated; Codex may let a reviewer decide an app's tool calls instead of asking you.":
        "Check the tool and linked account first. "
        "Check the reviewer on the App and on `apps._default`. If you remove the App's override, the App can still "
        "inherit automatic review from `apps._default`.",
    APP_TOOL_REVIEWER_GAP:
        "Codex added this tool setting in 0.172.0. Check which reviewers your organization allows and whether "
        "it requires AI review for your model.",
    INVALID_APPROVAL: f"Set `{{label}}` to {APPROVAL_OPTIONS}.",
    INVALID_BOOLEAN:
        "Set `{label}` to `true` or `false` without quotes.",
    "Model-provider command-backed authentication is outside reader coverage.":
        "Review that command yourself; stay-safe doesn't check it.",
    "Model-provider setting {label} is for a credential command. Stay-safe did not check its value.":
        "Find `{label}` under `[model_providers.<name>]` and review its value. If it specifies a command, check that you trust it.",
    "otel.headers_helper is for a command that supplies telemetry headers. Stay-safe did not check its value.":
        "Review `otel.headers_helper`. If it specifies a command, check that you trust it.",
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
    "Codex home: skills holds Codex skills that were not inspected.": "Review the skills in `skills` yourself.",
    "Codex home: Could not check the skills folder. Check that you can open skills in your Codex folder.":
        "Check that you can open `skills` in your Codex folder.",
    "Codex home: environments.toml exists and was not inspected.":
        "Review the environments in `environments.toml` yourself.",
    "Codex home: Could not check environments.toml. Check that you can open environments.toml in your Codex folder.":
        "Check that you can open `environments.toml` in your Codex folder.",
    "Codex home: environments.toml is not a file; Codex fails to read it.":
        "Replace `environments.toml` in your Codex folder with the file you meant, or remove it.",
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
    if message in table:
        return table[message]
    for key, text in table.items():
        if "{label}" in key:
            found = re.fullmatch(re.escape(key).replace(r"\{label\}", r'([\w./"*-]+)'), message)
            if found:
                return text.replace("{label}", found[1])
    return None


def parts(name):
    return [json.loads(p) if p.startswith('"') else p for p in re.findall(r'"(?:[^"\\]|\\.)*"|[^."]+', name)]


SUBJECTS = {("mcp_servers", 2): "your {0} MCP server", ("mcp_servers", 4): "the {1} tool of your {0} MCP server",
            ("apps", 2): "your {0} app", ("apps", 4): "the {1} tool of your {0} app",
            ("hooks", 2): "your {0} hooks", ("notify", 1): "your `notify` setting"}


def finding(risk, files=None, contexts=None):
    keys = parts(risk["entry"].split(":", 1)[1])
    shape = (keys[0], len(keys))
    subject = SUBJECTS.get(shape, "").format(*[f"`{key}`" for key in keys[1::2]])
    plain = FINDINGS.get(risk["rule"])
    if plain is None:
        return None
    pick = lambda text: (text.get(keys[0]) if isinstance(text, dict)
                         else text[len(keys) == 4] if isinstance(text, tuple) else text)
    headline, why, step = pick(plain["headline"]), pick(plain["why"]), advice(risk, files or {}, contexts or {})
    if keys == ["apps", "_default"]:
        headline = TEMPLATE_HEADLINES.get(risk["rule"], headline)
    source = risk["entry"].split(":", 1)[0]
    full_access = (contexts or {}).get(source, {}).get("full_access")
    if keys == ["approval_policy"] and (risk["rule"], full_access) in {("commands_without_prompts", "on-request"),
                                                                      ("automatic_tools", "never")}:
        headline, why = FULL_ACCESS_HEADLINES[risk["rule"]]
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


def gap(text, absent, files, contexts=None):
    source, separator, message = text.partition(": ")
    if not (separator and re.fullmatch(r"(config|rules)-\d+", source)):
        source, message = None, text
    if source in absent and message in ABSENT:
        lead, step = ABSENT[message], ABSENT_STEPS[message]
    else:
        lead, step = lookup(GAPS, message), lookup(STEPS, message)
    if (message == "sandbox_mode is absent; the reader does not infer its effective value."
            and contexts and contexts.get(source, {}).get("profile")):
        step = PROFILE_CHECK.format(profile=contexts[source]["profile"])
    if lead is None or step is None:
        lead, step = UNKNOWN_GAP[0].format(cell(message)), UNKNOWN_GAP[1]
    return f"{lead}\n\n*What to do:* {step}" + (f"\n\n*File `{files.get(source, source)}`*" if source else "")


SETUP_LABELS = {("approval_policy",): "Approval", ("sandbox_mode",): "Sandbox",
                ("sandbox_workspace_write", "network_access"): "Network access for commands",
                ("sandbox_workspace_write", "writable_roots"): "Extra writable folders",
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
    "ChatGPT Apps": "an MCP connection to ChatGPT",
    "exists only if Codex is signed in with ChatGPT, which is not checked":
        "only when Codex is signed in with ChatGPT (stay-safe doesn't check sign-in)",
    "disabled by features.apps = false": "off (`features.apps = false`)",
    "features.apps = false turns it off": "`features.apps = false` turns it off",
    "applies to apps not named in this file": "applies to apps your file doesn't name",
    "broad: one-token prefix": "covers every use of that program",
    "never": "`never` (doesn't ask before commands)", "on-request": "`on-request` (Codex can ask before commands)",
    "with danger-full-access, ordinary commands can run without asking":
        "but with `danger-full-access` ordinary commands can run without asking",
    "with danger-full-access, MCP and app tool calls can run without asking":
        "and with `danger-full-access` MCP server and app tools can run without asking",
    "read-only": "`read-only` (commands can't write files)",
    "workspace-write": "`workspace-write` (commands can write in your workspace)",
    "danger-full-access": "`danger-full-access` (no sandbox)",
}
INHERIT = {"all": "all variables passed on", "core": "only core variables passed on", "none": "none passed on"}
ORIGIN = {"explicit": "you set this", "default": "default"}


def setup_words(keys, observation):
    if keys == ["web_search"]:
        return f"`{observation}`"
    if keys == ["apps", "_default"] and observation == "disabled":
        return "off (this doesn't turn off your named apps)"
    if observation in SETUP_WORDS:
        return SETUP_WORDS[observation]
    found = re.fullmatch(r"tool approval: (\w+)( \(default\))?", observation)
    if found and found[1] in APPROVALS:
        mode = f"`{found[1]}`"
        return f"tool approval left at the default, {mode}" if found[2] else f"tool approval {mode}"
    found = re.fullmatch(r"apps not named in this file: destructive tools (enabled|disabled) by (.+)", observation)
    if found:
        origin = "Codex default" if found[2] == "Codex default" else f"set by `{found[2]}`"
        return f"apps your file doesn't name have tools that change or delete data {'on' if found[1] == 'enabled' else 'off'} ({origin})"
    if observation == "apps not named in this file: disabled by apps._default.enabled":
        return "apps your file doesn't name are off (`apps._default.enabled`)"
    if observation == "apps not named in this file: destructive tools unknown":
        return "unknown whether apps your file doesn't name have tools that change or delete data on (`apps._default.destructive_enabled` is invalid)"
    if observation == "apps not named in this file: settings unknown":
        return "unknown what apps your file doesn't name are allowed to do (`apps._default` is invalid)"
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
    label = f"`{provenance['source_revision'][:7]}`"
    return label + " (release archive)" if provenance["source_status"] == "release archive commit" else label


GROUPS = (
    ("Nothing stands between a mistaken or injected instruction and your computer",
     ("lets commands reach your whole computer unchecked", "let commands reach your whole computer unchecked"),
     ("unrestricted_filesystem", "commands_without_prompts", "saved_approval")),
    ("Network access, credentials, and connected tools",
     ("is about network access, credentials, or connected tools",
      "are about network access, credentials, or connected tools"),
     ("destructive_tools", "network_access", "environment_inheritance", "automatic_tools")),
    ("Something else has to be tampered with first",
     ("matters only if something else is tampered with first", "matter only if something else is tampered with first"),
     ("configured_program",)),
    ("Based on Codex's source code and not yet seen in a live run, so stay-safe has no basis to rank these. "
     "That does not make them minor.",
     ("rests on Codex's source code alone", "rest on Codex's source code alone"),
     ("self_described_tools", "writable_project_settings")),
)
PLACE = {rule: (group, position) for group, (_, _, rules) in enumerate(GROUPS) for position, rule in enumerate(rules)}
NUMBERS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
READ = {"config": "your Codex settings", "rules": "your saved approvals"}
LEAD_IN = "Here are the findings for you to review, with actionable advice."
TARGET = "Finding {}"


def source_order(source):
    kind, _, number = source.partition("-")
    return ({"config": 0, "rules": 1}.get(kind, 2), int(number) if number.isdigit() else 0, source)


def ordered(risks):
    def key(risk):
        source, _, name = risk["entry"].partition(":")
        return (*PLACE[risk["rule"]], source_order(source),
                [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in parts(name)])
    return sorted(risks, key=key)


def files_read(report, files):
    absent = {entry["source"] for entry in report["catalog"] if entry["kind"] in ("configuration file", "rules file")}
    listed = {entry["source"] for entry in report["catalog"]}
    refused = {text.partition(": ")[0] for text in report["inspection_gaps"]
               if text.partition(": ")[2].startswith(("Rules input ", "Selected rules input ", EXCLUDED_ACCOUNT))}
    sources = {source for source in listed | set(files) | {text.partition(": ")[0] for text in report["inspection_gaps"]}
               if re.fullmatch(r"(config|rules)-\d+", source)}
    return sorted((source for source in sources - absent - refused
                   if source.startswith("rules-") or source in listed), key=source_order)


def introduction(report, files, read):
    risks, gaps = report["risks"], report["inspection_gaps"]
    paragraphs = []
    if read:
        names = []
        for kind, description in READ.items():
            labels = [f"`{files.get(source) or source}`" for source in read if source.startswith(kind + "-")]
            if labels:
                joined = ", ".join(labels[:-1]) + (" and " if labels[:-1] else "") + labels[-1]
                names.append(f"{description} ({joined})")
        number = NUMBERS[len(read) - 1] if len(read) <= len(NUMBERS) else str(len(read))
        paragraphs.append(
            f"stay-safe read {number} {'file' if len(read) == 1 else 'files'}: "
            f"{', '.join(names[:-1])}{' and ' if names[:-1] else ''}{names[-1]}. This report describes what "
            f"{'that file says' if len(read) == 1 else 'those files say'}, without running any tests in Codex.")
    else:
        paragraphs.append("stay-safe could not read any configuration files. See Not checked for the reason.")
    if ("rules-1" in read and files.get("rules-1") is None
            and not any(entry["source"] == "rules-1" for entry in report["catalog"])
            and not any(gap.startswith("rules-1: ") for gap in gaps)):
        paragraphs.append("Your rules file contains no saved approvals.")
    if risks:
        sentences = [f"stay-safe found {count(len(risks), 'risky setting', 'risky settings')}."]
        for group, (_, (one, several), _) in enumerate(GROUPS):
            number = sum(PLACE[risk["rule"]][0] == group for risk in risks)
            if number:
                sentences.append(f"{number} {one if number == 1 else several}.")
        paragraphs.append(" ".join(sentences))
    if gaps:
        one, those = len(gaps) == 1, "that file" if len(read) == 1 else "those files"
        reason = (f" because {'it is' if one else 'they are'} missing from {those} or outside what stay-safe covers"
                  if read else "")
        paragraphs.append(
            f"{count(len(gaps), 'part', 'parts')} of your setup could not be verified{reason}. "
            f"stay-safe flagged {'it' if one else 'them'} for you to review.")
    if risks:
        paragraphs.append(LEAD_IN)
    return paragraphs


def findings_list(report, risks, titles, labelled):
    paragraphs, group = [], None
    for number, (risk, title) in enumerate(zip(risks, titles), 1):
        if PLACE[risk["rule"]][0] != group:
            group = PLACE[risk["rule"]][0]
            paragraphs += [f"**{GROUPS[group][0]}**", ""]
        label = f" (`{risk['entry'].partition(':')[0]}`)" if labelled else ""
        paragraphs[-1] += ("\n" if paragraphs[-1] else "") + f"{number}. [{title}](#{anchor(TARGET.format(number))}){label}"
    if report["inspection_gaps"]:
        paragraphs.append(f"{count(len(report['inspection_gaps']), 'thing', 'things')} not checked: "
                          "see [Not checked](#not-checked).")
    return paragraphs


def markdown(report, files=None):
    if report.get("harness") == "Claude Code":
        from .claude_report import markdown as claude_markdown
        return claude_markdown(report, files)
    files = files or {}
    risks, gaps = ordered(report["risks"]), report["inspection_gaps"]
    read = files_read(report, files)
    lines = ["# Codex configuration diagnostic", "",
             f"{count(len(risks), 'finding', 'findings')}, {count(len(gaps), 'thing', 'things')} not checked.", ""]
    for paragraph in introduction(report, files, read):
        lines += [paragraph, ""]
    files = {source: path for source, path in files.items() if path is not None}
    blocks, titles = [], []
    contexts = sandbox_context(report, files)
    for number, risk in enumerate(risks, 1):
        citations = ", ".join(f"[{i}]({report['incident_links'][i]})" if i in report["incident_links"] else i for i in risk["incidents"])
        lead, how, step = finding(risk, files, contexts) or (risk["explanation"], "See the cited incidents.",
                                                   "*What to do:* Review this setting yourself.")
        kind = "rules entry" if risk["entry"].startswith("rules-") else "setting"
        headline = re.search(r"^\*\*(.+?)\*\* ", lead)
        titles.append(headline[1] if headline else lead)
        rule = f"`{risk['rule']}`"
        rule_url = source_link(report["provenance"]["source_revision"], f"docs/rules.md#{risk['rule']}")
        if rule_url:
            rule = f"[{rule}]({rule_url})"
        blocks.append("\n\n".join([
            f"### {TARGET.format(number)}",
            lead,
            f"*How it has gone wrong:* {how} {citations} ({report['incident_status']}).",
            step,
            f"*Rule {rule} · {kind} `{risk['entry']}` = `{'; '.join(risk['configured_evidence'])}`*"]))
    if risks:
        for paragraph in findings_list(report, risks, titles, len(read) > 1):
            lines += [paragraph, ""]
    lines += ["## Findings", ""]
    if risks:
        lines += [note(report, files), "", "\n\n---\n\n".join(blocks), ""]
    else:
        lines += ["None of stay-safe's rules matched your settings. That doesn't mean your setup is safe: "
                  "see what stay-safe didn't check and what this report can't see, below.", ""]
    lines += ["## Not checked", ""]
    absent = {entry["source"] for entry in report["catalog"] if entry["kind"] == "configuration file"}
    if gaps:
        lines += [NOT_CHECKED, "", "\n\n---\n\n".join(gap(text, absent, files, contexts) for text in gaps), ""]
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
              "- Settings you choose in the app or with command-line flags can override your config. "
              "Check how you start Codex. If you select a separate profile file with `--profile`, "
              "that file can override your main config. Run stay-safe with `--config` and the path "
              "to that file to inspect it separately.",
              "- Whether connections work, or what Codex actually allows when it runs: stay-safe only reads files; it "
              "doesn't start Codex or contact any service. Watch what Codex asks before it acts.",
              "- Private values such as commands, addresses and tokens are left out, but names like `github` are "
              "shown as written: names can identify a project or a person, so check them before sharing."]
    if len(set(groups) - missing) > 1:
        lines.append("- These files are read as separate snapshots, not combined: Codex may apply several of them "
                     "together, so a setting in one can change what another allows.")
    guide = source_link(revision, "docs/report.md")
    lines += ["", f"[Full scope of this report]({guide}#full-scope)" if guide
              else "Full scope of this report: see the Full scope section of stay-safe's docs/report.md.",
              "", "---", "",
              f"Made by stay-safe {made_by(report['provenance']) if guide else '(commit unknown)'} · report format "
              f"{report['format_version']} · [Report a problem or suggest an idea]({REPOSITORY}/issues/new/choose)"]
    return "\n".join(lines) + "\n"


INLINE = re.compile(r"`([^`\n]*)`|\[((?:`[^`\n]*`|[^\]`\n])*)\]\((https://[^)\s]*|#finding-\d+|#not-checked|#claude-code-finding-\d+|#claude-code-not-checked)\)|\*\*|\*")
NUMBERED = re.compile(r"(\d+)\. (.*)")
STYLE = """body { font-family: system-ui, sans-serif; line-height: 1.5; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; }
p, li { overflow-wrap: anywhere; }
code { font-family: ui-monospace, monospace; font-size: 0.95em; }
hr { border: 0; border-top: 1px solid; margin: 1.5rem 0; }"""


def anchor(heading):
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def text(value):
    return escape(unescape(value), quote=False)


def inline(line):
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
            out.append(f'<a href="{escape(found[3], quote=True)}">{inline(found[2])}</a>')
        position = found.end()
    out.append(text(line[position:]))
    out.extend(f"</{t}>" for t in reversed(open_tags))
    return "".join(out)


def page(report, files=None, text=None, title=None):
    body = []
    text = markdown(report, files) if text is None else text
    title = title or text.split("\n", 1)[0].removeprefix("# ")
    for block in text.rstrip("\n").split("\n\n"):
        if block.startswith("# "):
            body.append(f"<h1>{inline(block[2:])}</h1>")
        elif block.startswith("## "):
            body.append(f'<h2 id="{escape(anchor(block[3:]), quote=True)}">{inline(block[3:])}</h2>')
        elif block.startswith("### "):
            body.append(f'<h3 id="{escape(anchor(block[4:]), quote=True)}">{inline(block[4:])}</h3>')
        elif block == "---":
            body.append("<hr>")
        else:
            runs = []
            for line in block.split("\n"):
                listed = "ul" if line.startswith("- ") else "ol" if NUMBERED.fullmatch(line) else None
                if runs and runs[-1][0] == listed:
                    runs[-1][1].append(line)
                else:
                    runs.append((listed, [line]))
            for listed, lines in runs:
                if listed == "ul":
                    body.append("<ul>\n" + "\n".join(f"<li>{inline(line[2:])}</li>" for line in lines) + "\n</ul>")
                elif listed == "ol":
                    body.append(f'<ol start="{NUMBERED.fullmatch(lines[0])[1]}">\n'
                                + "\n".join(f"<li>{inline(NUMBERED.fullmatch(line)[2])}</li>" for line in lines)
                                + "\n</ol>")
                else:
                    body.append("<p>" + "<br>\n".join(inline(line) for line in lines) + "</p>")
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{escape(title, quote=False)}</title>\n<style>\n{STYLE}\n</style>\n</head>\n<body>\n"
            + "\n".join(body) + "\n</body>\n</html>\n")


def plain(report, files=None):
    def words(line):
        pieces, position = [], 0
        for found in INLINE.finditer(line):
            pieces.append(unescape(line[position:found.start()]))
            if found[1] is not None:
                pieces.append(found[1])
            elif found[2] is not None:
                pieces.append(words(found[2]) + ("" if found[3].startswith("#") else f" ({found[3]})"))
            position = found.end()
        pieces.append(unescape(line[position:]))
        return "".join(pieces)

    lines = []
    for line in markdown(report, files).splitlines():
        if line == "---":
            continue
        line = line.removeprefix("### ").removeprefix("## ").removeprefix("# ")
        if line.startswith("- "):
            line = "• " + line[2:]
        lines.append(words(line))
    return "\n".join(lines) + "\n"


def public(report):
    return {key: value for key, value in report.items() if not key.startswith("_")}


def render(report, format_name="markdown", files=None):
    if format_name == "json":
        return json.dumps(public(report), ensure_ascii=True, indent=2) + "\n"
    if format_name == "plain":
        return plain(report, files)
    if format_name == "html":
        return page(report, files)
    return markdown(report, files)


def render_all(runs, format_name="markdown"):
    if len(runs) == 1:
        return render(runs[0][0], format_name, runs[0][1])
    if format_name == "json":
        return json.dumps({"reports": [public(report) for report, _ in runs]}, ensure_ascii=True, indent=2) + "\n"
    if format_name == "html":
        text = "\n".join(markdown(report, files) for report, files in runs)
        return page(None, text=text, title=" and ".join(report["harness"] for report, _ in runs)
                    + " configuration diagnostic")
    return "\n".join(render(report, format_name, files) for report, files in runs)
