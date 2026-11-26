import re

from .claude import (AUTO_APPROVAL_UNSET, AUTO_MODE_GAP, HTTP, UNKNOWN_EVENT, UNREAD_ENABLE, decides, read_file,
                     resolve, runs)
from .provenance import GAP, REPOSITORY, fingerprints, identify, source_link
from .rules import evaluate

HARNESS = "Claude Code"
SCOPE = [
    "Discovery reads the user settings file and `.claude/settings.json` in the current folder. You can also select "
    "settings files with --config. Account files, `.claude/settings.local.json`, `.mcp.json`, managed settings, "
    "extension folders and command-line flags are outside this check.",
    "Files are independent snapshots; Claude Code combines allow rules from every settings file it loads.",
    "Ask and deny rules, which Claude Code checks before allow rules, are not inspected.",
    "Commands, addresses, paths and other values in rules and settings are withheld, except a first word on "
    "stay-safe's program list.",
]
WHAT = {
    ("commands_without_prompts", None):
        "Set `permissions.defaultMode` to `default` to stop requesting bypass in this file. "
        "Review any separate allow rules for actions you want to approve yourself.",
    ("saved_approval", "broad: every command"):
        "Remove this rule and allow only the commands you run often, for example `Bash(npm run test *)`.",
    ("saved_approval", None):
        "Check that this rule covers only the commands you meant, and remove it if you no longer need it.",
    ("network_access", "every address"):
        "Remove this rule to stop allowing every fetch through this entry.",
    ("network_access", "every domain"):
        "Remove the wildcard rule to withdraw its all-domain allowance.",
    ("network_access", None):
        "Check that you trust the domains this rule covers, and remove the rule if you no longer need it.",
    ("configured_program", None):
        "Keep it if you trust the command it runs. Stricter: remove the setting if you don't use it.",
    ("network_access", HTTP):
        "Keep it if you trust the address. Stricter: remove the HTTP hook, or set `allowedHttpHookUrls` to the "
        "addresses you trust.",
}
HEADLINES = {
    ("commands_without_prompts", None):
        "This file selects bypassPermissions, which can skip permission prompts. "
        "From v2.1.257, project and project-local settings cannot enable this mode.",
    ("saved_approval", "broad: every command"): "This file has an allow rule for every Bash command.",
    ("saved_approval", None): "This file has an allow rule for matching Bash commands.",
    ("network_access", "every address"): "This file has a WebFetch allow rule for every web address.",
    ("network_access", "every domain"):
        "This wildcard covers every WebFetch domain from Claude Code v2.1.172. From v2.1.186 it also adds every "
        "host to the sandbox network allowlist.",
    ("network_access", None): "This file has a WebFetch allow rule for matching domains.",
    ("configured_program", None): "This file's `{name}` setting runs a command on your computer.",
    ("network_access", HTTP): "This file has an HTTP hook that sends hook data to a web address.",
}
TRUST = (" Claude Code runs {} from a project's settings in a `claude -p` run, or when you trusted a parent folder "
         "whose trust extends to this folder, without asking you to trust this folder.")
WHY = {
    "commands_without_prompts": "If this mode applies, injected or mistaken instructions could make Claude Code "
                                "run code you didn't want.",
    "saved_approval": "An allow rule can cover more than the command you remember. A rule for a program you use to "
                      "download a file can cover uploads too. Sandbox restrictions still apply when the command runs sandboxed.",
    "network_access": "Injected instructions could send your private data out in a request.",
    "configured_program": "If that command or this file were changed, Claude Code could run code you didn't intend.",
    ("network_access", HTTP): "Claude Code sends each matching event's details, such as commands, file paths and "
                              "prompts, to that address without asking you.",
}
GROUP_LABELS = ("Shell commands and permission mode", "Network access", "Programs Claude Code starts")
NOTE = ("*Before you change anything:* Claude Code combines settings from several files, and a `--permission-mode` "
        "flag or managed settings can override yours. Change the file named in each finding, then run stay-safe again.")
NOT_CHECKED = ("stay-safe reads only Claude Code settings whose meaning it has checked against Claude Code's docs, and "
               "it skips anything it can't read or check rather than guess. Each item says what to do.")
GAPS = {
    "permissions.defaultMode is absent; Claude Code's built-in mode depends on how it starts and its version, so it "
    "was not inferred.": (
        "**Not checked: which permission mode Claude Code starts in.** Your settings don't set "
        "`permissions.defaultMode`, so Claude Code uses its built-in mode, which depends on its version and how you "
        "start it.",
        "Set `permissions.defaultMode` to the mode you want, such as `default`, so the report can check it."),
    AUTO_MODE_GAP: (
        "**Not checked: auto mode.** Claude Code accepts `auto` in user settings (usually `~/.claude/settings.json`) "
        "and ignores `auto` in project and project-local settings. When this mode applies, a classifier decides "
        "which actions may run without asking. stay-safe can't assess those decisions.",
        "If this is your user settings file, set `permissions.defaultMode` to `default` to stop requesting auto "
        "mode here. Review any Bash allow rules for commands you want to approve yourself."),
    "permissions.defaultMode is unsupported or invalid; its value was withheld.": (
        "**Not checked: `permissions.defaultMode`.** Its value isn't one stay-safe recognizes.",
        "Set it to one of the modes in Claude Code's permission docs."),
    "permissions.allow contains rules for tools outside reader coverage; they were not evaluated.": (
        "**Not checked: some allow rules.** Rules for tools other than `Bash` and `WebFetch`, such as MCP tools, "
        "weren't evaluated.",
        "Review `permissions.allow` yourself."),
    "permissions.allow is not a list; its rules were not evaluated.": (
        "**Not checked: `permissions.allow`.** It isn't a list.",
        "Review `permissions.allow` yourself."),
    "permissions contains fields outside reader coverage; their values were withheld.": (
        "**Not checked: other `permissions` settings,** such as extra directories Claude Code may reach.",
        "Review the `permissions` block yourself."),
    "sandbox contains fields outside reader coverage; their values were withheld.": (
        "**Not checked: other `sandbox` settings,** such as commands excluded from the sandbox or allowed domains.",
        "Review the `sandbox` block yourself."),
    "sandbox.enabled has an invalid boolean; its behavior is unknown.": (
        "**Not checked: `sandbox.enabled`.** It isn't `true` or `false`.", "Set it to `true` or `false`."),
    "permissions must be a table.": (
        "**Not checked: `permissions`.** It isn't a JSON object.", "Review the `permissions` block yourself."),
    "sandbox must be a table.": (
        "**Not checked: `sandbox`.** It isn't a JSON object.", "Review the `sandbox` block yourself."),
    "Settings file exceeds the 1 MiB size limit.": (
        "**Not checked: the settings file.** It is larger than 1 MiB.", "Check the file yourself."),
    "Settings file is missing, unreadable, a symlink, or not a JSON object; raw errors were withheld.": (
        "**Not checked: the settings file.** stay-safe couldn't read it as a JSON object. It doesn't follow symlinks.",
        "Check that the file exists, is readable and holds a JSON object, or pass its target with `--config`."),
    UNREAD_ENABLE: (
        "**Not checked: whether hooks stay off.** `disableAllHooks` turns them off in the files read, but "
        "`.claude/settings.local.json`, managed settings and `--settings` can set it back to `false`.",
        "Look for `disableAllHooks` in those."),
    UNKNOWN_EVENT: (
        "**Not checked: a hook event.** An event name under `hooks` isn't one Claude Code documents, so its hooks "
        "weren't read. The name is withheld.",
        "Review the `hooks` block yourself."),
    "allowedHttpHookUrls is not a list of URL patterns; it was not evaluated.": (
        "**Not checked: `allowedHttpHookUrls`.** It isn't a list of URL patterns.",
        "Review `allowedHttpHookUrls` yourself."),
    "disableAllHooks has an invalid boolean; its behavior is unknown.": (
        "**Not checked: `disableAllHooks`.** It isn't `true` or `false`, so stay-safe treats your hooks as on.",
        "Set it to `true` or `false`."),
    "hooks is not an object of hook events; its hooks were not evaluated.": (
        "**Not checked: `hooks`.** It isn't a JSON object of hook events.", "Review the `hooks` block yourself."),
    "hooks contains an event that is not a list of matcher groups; it was not evaluated.": (
        "**Not checked: a hook event.** An event under `hooks` isn't a list of matcher groups.",
        "Review the `hooks` block yourself."),
    "hooks contains a matcher group without a list of handlers; it was not evaluated.": (
        "**Not checked: a group of hooks.** A matcher group under `hooks` has no `hooks` list.",
        "Review the `hooks` block yourself."),
    "hooks contains a handler that is not a valid hook; it was not evaluated.": (
        "**Not checked: a hook.** A hook isn't an object with a known `type`, or its command is empty.",
        "Review the `hooks` block yourself."),
    "hooks contains MCP tool hooks, which call a tool on an MCP server without asking you; that server was not "
    "evaluated.": (
        "**Not checked: MCP tool hooks.** They call a tool on an MCP server without asking you, and stay-safe doesn't "
        "read MCP servers yet.",
        "Check which server and tool each `mcp_tool` hook calls, and remove the hook if you don't trust them."),
    "The project's .claude folder could not be checked; its settings were not inspected.": (
        "**Not checked: the project's `.claude` folder.** stay-safe couldn't check it, so a project settings file "
        "may not have been inspected.",
        "Check that `.claude/settings.json` is readable, or pass it with `--config`."),
}
UNKNOWN = ("**Not checked:** {}", "Review this part of your setup yourself.")
WORDS = {"default": "`default` (asks before most actions)", "manual": "`manual` (asks before most actions)",
         "acceptEdits": "`acceptEdits` (accepts file edits without asking)", "plan": "`plan` (doesn't edit files)",
         "auto": "`auto` (a classifier decides what runs without asking)",
         "dontAsk": "`dontAsk` (refuses anything that would ask)",
         "bypassPermissions": "`bypassPermissions` (skips permission prompts)",
         "false (default)": "off (Claude Code's default)", "true": "on", "false": "off", "absent": "none found",
         "broad: every command": "every command", "every address": "every address",
         "addresses withheld": "some addresses (left out)"}


def inspect(paths, *, discovered=False, gaps=(), scopes=()):
    entries, gaps, sources_read = [], list(gaps), []
    scopes = list(scopes) + [None] * (len(paths) - len(scopes))
    hashes = fingerprints()
    provenance = identify(hashes=hashes)
    for index, path in enumerate(paths, 1):
        found, missing = read_file(path, f"settings-{index}", discovered=discovered, sources_read=sources_read,
                                   scope=scopes[index - 1])
        entries.extend(found)
        gaps.extend(missing)
    gaps.extend(resolve(entries, discovered))
    risks = evaluate(entries)
    revision = provenance["source_revision"]
    by_id = {entry["id"]: entry for entry in entries}
    for risk in risks:
        entry = by_id[risk["entry"]]
        risk["configured_evidence"] = list(entry["observations"])
        risk["explanation"] = hook_headline(risk["rule"], entry["facts"]) if entry["kind"] == "hook" else headline(risk)
        if risk["rule"] == "commands_without_prompts":
            risk["explanation"] += sandbox_mode_change(entry["source"], by_id, gaps)
        risk["rule_source"] = source_link(revision, "stay_safe/rules.py")
        risk["interpretation_source"] = source_link(revision, "harnesses/claude-code.md")
    from .report import INCIDENT_STATUS, incident_links
    try:
        links = incident_links(revision=revision)
    except (OSError, UnicodeError):
        links = {}
    cited = sorted({i for risk in risks for i in risk["incidents"]}, key=lambda i: int(i[1:]))
    if any(identifier not in links for identifier in cited):
        gaps.append("Committed incident citations are incomplete; source links are unavailable.")
    gaps.extend(f"Incomplete fingerprint: {name} could not be read." for name, value in hashes.items() if value is None)
    if revision is None:
        gaps.append(GAP)
    return {"format_version": 3, "harness": HARNESS, "provenance": provenance, "scope": list(SCOPE),
            "file_inspection": "incomplete" if gaps else "complete for supported fields", "sources_read": sources_read,
            "catalog": [{k: v for k, v in entry.items() if k != "facts"} for entry in entries],
            "_hooks": {entry["id"]: {key: entry["facts"][key] for key in ("handlers", "allowlist", "project")}
                       for entry in entries if entry["kind"] == "hook"},
            "risks": risks, "incident_status": INCIDENT_STATUS,
            "incident_links": {i: links[i] for i in cited if links.get(i)}, "inspection_gaps": gaps}


def heading_id(heading):
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def scope(risk):
    return next((value for value in risk["configured_evidence"]
                 if value in ("broad: every command", "every address", "every domain", HTTP)), None)


def place(record):
    return f"`{record['event']}` (matcher group {record['group']}, hook {record['position']})"


def subject(record):
    return f"The `{record['event']}` hook at matcher group {record['group']}, hook {record['position']}"


def where(record):
    return f"hook {record['position']} of matcher group {record['group']} under `hooks.{record['event']}`"


def series(items, last):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + last + items[-1]


def hook_headline(rule, facts):
    records = facts["handlers"]
    running = [record for record in records if runs(record)]
    places = series([f"on {place(record)}" for record in running], " and ")
    if rule == "configured_program":
        count = "a command hook" if len(running) == 1 else f"{len(running)} command hooks"
        lead = f"This file's `hooks` setting runs {count} on your computer: {places}."
    else:
        count = "an HTTP hook" if len(running) == 1 else f"{len(running)} HTTP hooks"
        lead = f"This file's `hooks` setting has {count} set to send hook data to a web address: {places}."
    for record in records:
        if decides(record):
            lead += f" {subject(record)} can also approve tool calls without asking you and change what they do."
        if record["background"]:
            lead += f" {subject(record)} runs in the background, so it can't block, approve or rewrite the call."
        if record["if_state"] == "filters":
            lead += f" {subject(record)} runs only for tool calls that match its `if` rule."
        if record["if_state"] == "never_runs":
            lead += f" {subject(record)} has an `if` rule on an event without tool calls, so it never runs."
    if facts["allowlist"]:
        lead += (" `allowedHttpHookUrls` is set, so Claude Code sends only if the address matches it; stay-safe didn't "
                 "check whether it does.")
    if facts["project"]:
        lead += TRUST.format("it" if len(running) == 1 else "them")
    return lead


def headline(risk):
    observations = risk["configured_evidence"]
    lead = HEADLINES[risk["rule"], scope(risk)].format(name=risk["entry"].partition(":")[2])
    overrides = [key for key in ("deny", "ask") if f"{key} rules present" in observations]
    if overrides:
        effect = {"deny": "block this action", "ask": "require approval"}
        effects = " or ".join(effect[key] for key in overrides)
        lead += f" This file also has {' and '.join(overrides)} rules that could {effects}. Their matches were not checked."
    return lead


def sandbox_mode_change(source, entries, gaps):
    enabled = entries.get(f"{source}:sandbox.enabled")
    if not enabled or enabled["observations"] != ["true"]:
        return ""
    auto = entries.get(f"{source}:sandbox.autoAllowBashIfSandboxed")
    if auto is None:
        if f"{source}: {AUTO_APPROVAL_UNSET}" in gaps:
            return (" This file omits sandbox.autoAllowBashIfSandboxed. After switching to default, eligible "
                    "sandboxed Bash commands can still run without a prompt before v2.1.324. From v2.1.324, "
                    "the default uses regular permission checks.")
        return (" This file has an invalid sandbox.autoAllowBashIfSandboxed value. Check this setting before "
                "relying on the mode change for Bash approval.")
    if auto["observations"] == ["true"]:
        return (" Changing the mode to default leaves sandbox.autoAllowBashIfSandboxed set to true, so eligible "
                "sandboxed Bash commands can still run without a prompt. Set that sandbox option to false to use "
                "regular permission checks.")
    return ""


def hook_advice(rule, details, path):
    running = [record for record in details["handlers"] if runs(record)]
    places = [where(record) for record in running]
    ask = (f"ask Claude Code: \"Show me {places[0]} in {path} and remove only that hook; show only what you "
           "change.\"")
    if len(places) == 1:
        change = f"*Change it:* in {path}, remove {places[0]}, or {ask}"
    else:
        change = f"*Change it:* in {path}, remove only the hook you don't want: {series(places, ', or ')}. Or {ask}"
    owner = "this hook's" if len(running) == 1 else "each hook's"
    what = WHAT[rule, HTTP if rule == "network_access" else None]
    if rule == "network_access":
        check = (f"*Check:* In {path}, {owner} `url` is the address it sends to. Find out who controls it before you "
                 "trust it.")
        if details["allowlist"]:
            what = ("Keep it if you trust the address. Stricter: remove the HTTP hook, or check that "
                    "`allowedHttpHookUrls` lists only addresses you trust.")
    else:
        if not any(record["exec"] for record in running):
            target = f"{owner} `command` is what it runs"
        elif len(running) == 1:
            target = "this hook's `command` and its `args` list are what it runs, so a script can be named in either"
        else:
            target = ("each hook's `command` is what it runs, and for a hook with `args`, its `args` list too, so a "
                      "script can be named in either")
        check = (f"*Check:* In {path}, {target}. If it runs a script file, check that file too: changes to the script "
                 f"don't show in {path}. Find out who wrote them before you trust them.")
    if details["project"]:
        check += " In a git repository, `git log -p -- .claude/` shows who changed the settings and scripts there."
    why = WHY[rule, HTTP] if rule == "network_access" else WHY[rule]
    return what, change, check, why


def finding(risk, path, number, details=None):
    from .report import FINDINGS
    rule = risk["rule"]
    what = WHAT[rule, scope(risk)]
    why = WHY.get((rule, scope(risk)), WHY[rule])
    if details is not None:
        what, change, check, why = hook_advice(rule, details, path)
    elif rule == "commands_without_prompts":
        change = (f"*Change it:* `permissions.defaultMode` in {path}, or ask Claude Code: \"Edit {path} to set "
                  f"`permissions.defaultMode` to `default`; show only what you change.\"")
        check = (f"*Check:* Look for `defaultMode` under `permissions` in {path}. A `--permission-mode` flag or "
                 "managed settings can still choose another mode.")
    else:
        change = (f"*Change it:* rule {number} of `permissions.allow` in {path}, or ask Claude Code: \"Show me rule "
                  f"{number} of `permissions.allow` in {path} and remove it; show only what you change.\"")
        check = f"*Check:* Look at `permissions.allow` in {path}."
    return (f"**{risk['explanation']}** {why}", FINDINGS[rule]["how"],
            "\n\n".join([f"*What to do:* {what}", change, check]))


def gap(text, files, entries, gaps):
    source, separator, message = text.partition(": ")
    if not (separator and source.startswith("settings-")):
        source, message = None, text
    lead_step = GAPS.get(message)
    if lead_step is None and message.startswith("Settings outside reader coverage were not evaluated: "):
        names = message.removeprefix("Settings outside reader coverage were not evaluated: ").removesuffix(".")
        lead_step = (f"**Not checked: other settings.** stay-safe doesn't yet read these settings: {names}.",
                     "Review them yourself; settings such as `apiKeyHelper` and `statusLine` can run programs, "
                     "and `env` can pass values to them.")
    if lead_step is None and message.startswith("Claude Code home: ") and message.endswith(
            ("no Claude Code files were inspected.", "only the project's .claude/settings.json was inspected.")):
        lead_step = (f"**Not checked: Claude Code.** {message.removeprefix('Claude Code home: ')}",
                     "Check that Claude Code is installed, or select a settings file with `--config`.")
    lead, step = lead_step or (UNKNOWN[0].format(message), UNKNOWN[1])
    if message == AUTO_MODE_GAP:
        step += sandbox_mode_change(source, entries, gaps)
    return f"{lead}\n\n*What to do:* {step}" + (f"\n\n*File `{files.get(source, source)}`*" if source else "")


def setup_line(entry):
    keys = entry["name"].split(".")
    words = [WORDS.get(o, f"starts with `{o[9:]}`" if o.startswith("program: ") else o.removeprefix("tool: "))
             for o in entry["observations"]]
    if keys[:2] == ["permissions", "allow"]:
        tool, rest = words[0], words[1:]
        return f"- Allow rule {keys[2]}: `{tool}`" + (f", {', '.join(rest)}" if rest else " (details left out)")
    label = {"permissions.defaultMode": "Permission mode", "sandbox.enabled": "Sandbox",
             "sandbox.autoAllowBashIfSandboxed": "Auto-allow sandboxed Bash commands",
             "settings": "Settings file"}.get(entry["name"], f"`{entry['name']}`")
    return f"- {label}: {', '.join(words)}"


def markdown(report, files=None):
    from .report import PLACE, count, made_by, ordered
    files = {source: path for source, path in (files or {}).items() if path is not None}
    risks, gaps = ordered(report["risks"]), report["inspection_gaps"]
    sources = report["sources_read"]
    lines = [f"# {HARNESS} configuration diagnostic", "",
             f"{count(len(risks), 'finding', 'findings')}, {count(len(gaps), 'thing', 'things')} not checked.", ""]
    if sources:
        names = ", ".join(f"`{files.get(s) or s}`" for s in sources)
        lines += [f"stay-safe read your Claude Code settings ({names}). This report describes what "
                  f"{'that file says' if len(sources) == 1 else 'those files say'}, without running Claude Code.", ""]
    else:
        lines += ["stay-safe read no Claude Code settings file. See Not checked for the reason.", ""]
    blocks, titles = [], []
    for number, risk in enumerate(risks, 1):
        source, _, name = risk["entry"].partition(":")
        path = f"`{files[source]}`" if source in files else f"`<{source}>`"
        lead, how, step = finding(risk, path, name.rsplit(".", 1)[-1], report.get("_hooks", {}).get(risk["entry"]))
        titles.append(lead[2:].split("**", 1)[0] if lead.startswith("**") else lead)
        citations = ", ".join(f"[{i}]({report['incident_links'][i]})" if i in report["incident_links"] else i
                              for i in risk["incidents"])
        rule = f"`{risk['rule']}`"
        url = source_link(report["provenance"]["source_revision"], f"docs/rules.md#{risk['rule']}")
        if url:
            rule = f"[{rule}]({url})"
        blocks.append("\n\n".join([
            f"### {HARNESS} finding {number}", lead,
            f"*How it has gone wrong:* {how} {citations} ({report['incident_status']}).", step,
            f"*Rule {rule} · setting `{risk['entry']}` = `{'; '.join(risk['configured_evidence'])}`*"]))
    group = None
    for number, (risk, title) in enumerate(zip(risks, titles), 1):
        if PLACE[risk["rule"]][0] != group:
            group = PLACE[risk["rule"]][0]
            if number > 1:
                lines.append("")
            lines += [f"**{GROUP_LABELS[group]}**", ""]
        lines.append(f"{number}. [{title}](#{heading_id(f'{HARNESS} finding {number}')})")
    if risks:
        lines.append("")
    if gaps:
        lines += [f"{count(len(gaps), 'thing', 'things')} not checked: see [Not checked]"
                  f"(#{heading_id(f'{HARNESS} not checked')}).", ""]
    lines += [f"## {HARNESS} findings", ""]
    if risks:
        lines += [NOTE, "", "\n\n---\n\n".join(blocks), ""]
    else:
        lines += ["None of stay-safe's rules matched your Claude Code settings. That doesn't mean your setup is safe: "
                  "see what stay-safe didn't check and what this report can't see, below.", ""]
    lines += [f"## {HARNESS} not checked", ""]
    if gaps:
        by_id = {entry["id"]: entry for entry in report["catalog"]}
        lines += [NOT_CHECKED, "", "\n\n---\n\n".join(gap(text, files, by_id, gaps) for text in gaps), ""]
    else:
        lines += ["stay-safe checked every Claude Code setting it supports in the files it read.", ""]
    lines += [f"## {HARNESS} setup", ""]
    groups = {}
    for entry in report["catalog"]:
        groups.setdefault(entry["source"], []).append(setup_line(entry))
    for source, entries in groups.items():
        where = f"`{files[source]}` (`{source}`)" if source in files else f"`{source}`, the file you passed with `--config`"
        lines += [f"**Settings file {where}**", *entries, ""]
    if not groups:
        lines += ["stay-safe found no settings to list.", ""]
    revision = report["provenance"]["source_revision"]
    meanings = source_link(revision, "harnesses/claude-code.md")
    lines += [f"## {HARNESS} sources", "",
              f"- [What each Claude Code setting means, with official evidence]({meanings}) (`harnesses/claude-code.md`)"
              if meanings else "Source links are left out because stay-safe couldn't tell which commit it's running from.",
              "", f"## What the {HARNESS} report can't see", ""]
    lines += [f"- {line}" for line in SCOPE]
    lines += ["", "---", "",
              f"Made by stay-safe {made_by(report['provenance']) if meanings else '(commit unknown)'} · report format "
              f"{report['format_version']} · [Report a problem or suggest an idea]({REPOSITORY}/issues/new/choose)"]
    return "\n".join(lines) + "\n"
