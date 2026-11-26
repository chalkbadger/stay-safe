import json
import os
import re
import stat

from .codex import MAX_BYTES, Reader, exclude_account_files, open_input
from .codex_rules import PROGRAMS

MODES = {"default", "manual", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"}
PERMISSIONS = {"allow", "ask", "deny", "defaultMode"}
SANDBOX = {"enabled", "autoAllowBashIfSandboxed"}
PREFERENCES = {"$schema", "model", "theme", "language", "verbose", "outputStyle", "editorMode", "tui", "viewMode",
               "alwaysThinkingEnabled", "effortLevel", "autoUpdatesChannel", "cleanupPeriodDays", "timeFormat",
               "timeZone", "prefersReducedMotion", "showTurnDuration", "terminalProgressBarEnabled",
               "spinnerTipsEnabled", "autoCompactEnabled", "fastMode", "feedbackSurveyRate", "spellcheck",
               "syntaxHighlightingDisabled", "vimInsertModeRemaps", "keybindingFlavor", "maxProseWidth",
               "showThinkingSummaries", "autoScrollEnabled", "copyOnSelect", "emojiCompletionEnabled"}
NAMED = {"additionalDirectories", "agent", "allowedMcpServers", "apiKeyHelper",
         "deniedMcpServers", "disableAllHooks", "disableAutoMode", "disabledMcpjsonServers",
         "enableAllProjectMcpServers", "enabledMcpjsonServers", "enabledPlugins", "env", "extraKnownMarketplaces",
         "hooks", "pluginConfigs", "processWrapper", "skipAutoPermissionPrompt",
         "skipDangerousModePermissionPrompt", "sshConfigs", "sshHostCommands", "statusLine", "worktree"}
HOOK_FIELDS = {"command": ("command",), "http": ("url",), "mcp_tool": ("server", "tool"), "prompt": ("prompt",),
               "agent": ("prompt",)}
DECISION_EVENTS = {"PreToolUse", "PermissionRequest"}
TOOL_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "PermissionDenied"}
HOOK_EVENTS = {"SessionStart", "Setup", "UserPromptSubmit", "UserPromptExpansion", "PreToolUse", "PermissionRequest",
               "PermissionDenied", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "Notification",
               "MessageDisplay", "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted", "Stop", "StopFailure",
               "TeammateIdle", "InstructionsLoaded", "ConfigChange", "CwdChanged", "DirectoryAdded", "FileChanged",
               "WorktreeCreate", "WorktreeRemove", "PreCompact", "PostCompact", "PreModelSwitch", "PostModelSwitch",
               "Elicitation", "ElicitationResult", "SessionEnd"}
HELPER_USE = {
    "apiKeyHelper": "to get the credential it sends with model requests",
    "awsAuthRefresh": "when the AWS credential check fails",
    "awsCredentialExport": "at session start and on each AWS credential reload",
    "gcpAuthRefresh": "when Google Cloud credentials expire or cannot be loaded",
    "otelHeadersHelper": "at startup and periodically to generate telemetry headers",
}
WORKSPACE_COMMANDS = {"statusLine": "draw the status line", "fileSuggestion": "suggest files when you type `@`"}
COMMAND_OBJECT = "{} needs a JSON object with a type field and a command field."
COMMAND_TYPE = '{}.type must be "command".'
COMMAND_MISSING = "{}.command is missing."
COMMAND_NON_TEXT = "{}.command must be text."
COMMAND_BLANK = "{}.command is blank."
COMMAND_DISABLE_SOURCE = "disableAllHooks is true in "
COMMAND_SUPPRESSED = ("The settings checked set disableAllHooks to true. The {} command can still run if a "
                      "higher-priority setting changes disableAllHooks to false. Check .claude/settings.local.json, "
                      "any --settings used to start Claude Code, and your organization's managed settings. "
                      "Managed settings can also supply their own command.")
SSH_CONFIG_SCOPE = "Only connection IDs in sshConfigs were checked for conflicts with sshHostCommands."
SSH_HOOKS_GAP = ("disableAllHooks is set to true. That setting can prevent Claude Desktop from running "
                 "your SSH connection commands.")
SSH_FIELDS = {"id": "the connection identifier", "name": "the display name",
              "command": "the program and arguments that print the SSH host"}
LOCAL_COMMAND_SCOPE = {"sshHostCommands": "Claude Desktop reads `sshHostCommands` from your user settings or from a managed file or policy on your computer.",
                       "processWrapper": "Claude Code uses `processWrapper` only in user or managed settings."}
PROGRAM_SETTINGS = {"hooks", "disableAllHooks", "allowedHttpHookUrls", *HELPER_USE, *WORKSPACE_COMMANDS, *LOCAL_COMMAND_SCOPE}
COMMAND = "command withheld"
DISABLED = "turned off by disableAllHooks in this file"
UNREAD_ENABLE = ("disableAllHooks turns off the hooks found, but .claude/settings.local.json, managed settings and "
                 "--settings were not read and could turn them back on.")
PROJECT = "project settings"
HTTP = "HTTP hook"
ADDRESS = "address withheld"
HEADS = {"command": [COMMAND], "http": [HTTP, ADDRESS], "prompt": ["prompt hook; prompt withheld"],
         "agent": ["agent hook; prompt withheld"], "mcp_tool": ["MCP tool hook; server and tool withheld"]}
KINDS = ("command", "http", "prompt", "agent", "mcp_tool")
FACTS = {"command": "configured_program", "http": "network_access"}
DECIDES = "can approve or change tool calls"
EXEC = "exec form; arguments withheld"
FILTERED = "runs only for matching tool calls; if rule withheld"
NEVER = "never runs: if is set on an event without tool calls"
BACKGROUND = "runs in the background; can't approve or block"
BLOCKS = "can block the call or let it continue"
READS = "can read and search files"
NORMAL_FLOW = "leaves the decision to the normal flow"
SKIPPED = "skipped: Claude Code doesn't run agent hooks on PermissionRequest"
ALLOWLIST = "allowedHttpHookUrls is set; whether this address matches was not checked"
INVALID_FLAG = "not true or false"
MCP_GAP = ("hooks contains MCP tool hooks, which call a tool on an MCP server without asking you; that server was not "
           "evaluated.")
UNKNOWN_EVENT = ("hooks contains an event Claude Code doesn't document; its name was withheld and its hooks were not "
                 "evaluated.")
RULE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)(?:\((.*)\))?", re.DOTALL)
UNREADABLE = "Settings file is missing, unreadable, a symlink, or not a JSON object; raw errors were withheld."


AUTO_MODE_GAP = ("permissions.defaultMode is auto. Claude Code ignores auto in project and project-local settings. "
                 "Where auto applies, the classifier's decisions are not assessed.")
AUTO_APPROVAL_UNSET = ("sandbox.autoAllowBashIfSandboxed is unset. Its default changed from true to false in "
                      "v2.1.324. Check your Claude Code version to determine how sandboxed Bash approvals work.")


class SettingsReader(Reader):
    scope = None

    def read(self, data):
        self.permissions(data.get("permissions", {}))
        self.sandbox(data.get("sandbox", {}))
        self.programs(data)
        resolve(self.entries, False)
        others = set(data) - {"permissions", "sandbox"} - PREFERENCES - PROGRAM_SETTINGS
        if ("sshConfigs" in others and self.scope != "project" and isinstance(data.get("sshHostCommands"), list)
                and isinstance(data["sshConfigs"], list)):
            others.remove("sshConfigs")
            self.gap(SSH_CONFIG_SCOPE)
        if others:
            names = sorted(others & NAMED)
            if others - NAMED:
                names.append("other fields whose names were withheld")
            listed = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
            self.gap(f"Settings outside reader coverage were not evaluated: {listed}.")
        return self.entries, sorted(self.gaps)

    def permissions(self, value):
        table = self.table(value, "permissions")
        self.unknown(table, PERMISSIONS, "permissions")
        mode = table.get("defaultMode")
        if "defaultMode" not in table:
            if self.scope != "project":
                self.gap("permissions.defaultMode is absent; Claude Code's built-in mode depends on how it starts "
                         "and its version, so it was not inferred.")
        elif not isinstance(mode, str) or mode not in MODES:
            self.gap("permissions.defaultMode is unsupported or invalid; its value was withheld.")
        else:
            self.add(["permissions", "defaultMode"], "setting", [mode],
                     {"commands_without_prompts": mode == "bypassPermissions"})
            if mode == "auto":
                self.gap(AUTO_MODE_GAP)
        overrides = []
        for key in ("deny", "ask"):
            value = table.get(key, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                self.gap(f"permissions.{key} must be a list of rule strings. Its rules were not evaluated.")
            elif value:
                overrides.append(f"{key} rules present")
                self.gap(f"permissions.{key} contains rules that can take precedence over allow. "
                         "Their matches were not checked.")
        rules = table.get("allow", [])
        if not isinstance(rules, list):
            self.gap("permissions.allow is not a list; its rules were not evaluated.")
            rules = []
        for number, rule in enumerate(rules, 1):
            self.allow(number, rule, overrides)

    def allow(self, number, rule, overrides):
        found = RULE.fullmatch(rule) if isinstance(rule, str) else None
        keys = ["permissions", "allow", str(number)]
        if found and found[1] == "Bash":
            spec = (found[2] or "").strip()
            if spec in ("", "*"):
                self.add(keys, "allow rule", ["tool: Bash", "broad: every command", *overrides], {"saved_approval": True})
                return
            first = re.split(r"[\s:]", spec, maxsplit=1)[0]
            observations = ["tool: Bash"]
            if first in PROGRAMS:
                observations.append(f"program: {first}")
            self.add(keys, "allow rule", [*observations, *overrides], {"saved_approval": True})
        elif found and found[1] == "WebFetch":
            spec = found[2]
            if spec is None:
                scope = "every address"
            elif spec == "domain:*":
                scope = "every domain"
            elif spec.startswith("domain:") and spec[7:]:
                scope = "addresses withheld"
            else:
                self.gap("permissions.allow contains an unsupported WebFetch specifier. Its value was withheld.")
                return
            self.add(keys, "allow rule", ["tool: WebFetch", scope, *overrides], {"network_access": True})
        else:
            self.gap("permissions.allow contains rules for tools outside reader coverage; they were not evaluated.")

    def programs(self, data):
        if "disableAllHooks" in data:
            value = self.boolean(data, "disableAllHooks", False, "disableAllHooks")
            flag = "invalid" if value is None else value
            self.add(["disableAllHooks"], "setting", [], {"disable_all_hooks": flag})
        if "allowedHttpHookUrls" in data:
            patterns = data["allowedHttpHookUrls"]
            if isinstance(patterns, list) and all(isinstance(item, str) for item in patterns):
                self.add(["allowedHttpHookUrls"], "setting", ["set; patterns withheld"], {"http_allowlist": True})
            else:
                self.gap("allowedHttpHookUrls is not a list of URL patterns; it was not evaluated.")
        self.commands(data)
        if "hooks" not in data:
            return
        records = self.handlers(data["hooks"])
        for kind in KINDS:
            found = [record for record in records if record["kind"] == kind]
            if found:
                name = ["hooks"] if kind == "command" else ["hooks", kind]
                facts = {"kind": kind, "handlers": found, "project": self.scope == "project"}
                if kind in FACTS:
                    facts[FACTS[kind]] = False
                self.add(name, "hook", [], facts)

    def commands(self, data):
        for name in WORKSPACE_COMMANDS:
            if name not in data:
                continue
            value = data[name]
            if not isinstance(value, dict):
                problem = COMMAND_OBJECT
            elif value.get("type") != "command":
                problem = COMMAND_TYPE
            elif "command" not in value:
                problem = COMMAND_MISSING
            elif not isinstance(value["command"], str):
                problem = COMMAND_NON_TEXT
            elif not value["command"].strip():
                problem = COMMAND_BLANK
            else:
                problem = None
            if problem:
                self.gap(problem.format(name))
                continue
            self.add([name], "program", [], {"configured_program": True, "project": self.scope == "project"})
        if "sshHostCommands" in data:
            self.ssh_host_commands(data["sshHostCommands"], data.get("sshConfigs"), data.get("disableAllHooks") is True)
        for name in (*HELPER_USE, "processWrapper"):
            if name not in data:
                continue
            if name in LOCAL_COMMAND_SCOPE and self.scope == "project":
                self.add([name], "program", ["Claude Code ignores `processWrapper` in `.claude/settings.json`."], {"configured_program": False})
                continue
            value = data[name]
            if not isinstance(value, str):
                self.gap(f"{name} has a non-text value. Claude Code expects a command written as text.")
                continue
            if not value.strip():
                self.gap(f"{name} is blank. There is no command to check.")
                continue
            observations = [COMMAND] + ([PROJECT] if self.scope == "project" else [])
            if name in LOCAL_COMMAND_SCOPE and self.scope is None:
                observations.append(LOCAL_COMMAND_SCOPE[name])
            self.add([name], "program", observations, {"configured_program": True})

    def ssh_host_commands(self, value, ssh_configs, hooks_disabled):
        name = "sshHostCommands"
        if self.scope == "project":
            self.add([name], "program", ["Claude Desktop ignores `sshHostCommands` in `.claude/settings.json`."], {"configured_program": False})
            return
        if not isinstance(value, list):
            self.gap("sshHostCommands must be a list of connection entries.")
            return
        reserved = {entry["id"] for entry in ssh_configs if isinstance(entry, dict) and nonempty(entry.get("id"))
                    } if isinstance(ssh_configs, list) else set()
        configured = []
        invalid = []
        counts = {}
        for entry in value:
            if isinstance(entry, dict) and nonempty(entry.get("id")):
                identifier = entry["id"]
                counts[identifier] = counts.get(identifier, 0) + 1
        for position, entry in enumerate(value, 1):
            subject = f"Connection {position} in sshHostCommands"
            if not isinstance(entry, dict):
                invalid.append(position)
                self.gap(f"{subject} must be a JSON object. Give the connection an id, a name and a command.")
                continue
            problems = []
            for field, meaning in SSH_FIELDS.items():
                if field not in entry:
                    problems.append(f"is missing {field}. Add {meaning}.")
                elif not nonempty(entry[field]):
                    problems.append(f"needs text in {field}. Enter {meaning} as a nonblank string.")
            identifier = entry.get("id")
            if nonempty(identifier):
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", identifier):
                    problems.append("has an invalid id. Use up to 64 ASCII letters, digits, dots, underscores or "
                                    "hyphens, starting with a letter or digit.")
                elif counts[identifier] > 1:
                    problems.append("shares an id with another connection. Give each connection a unique id.")
                if identifier in reserved:
                    problems.append("uses an ID already present in sshConfigs. Give the connection a unique ID.")
            label = entry.get("name")
            if nonempty(label) and (len(label) > 200 or label.splitlines() != [label]):
                problems.append("has an invalid name. Use one line of up to 200 characters for the display name.")
            for problem in problems:
                self.gap(f"{subject} {problem}")
            if problems:
                invalid.append(position)
            else:
                configured.append(position)
        if configured:
            observations = [COMMAND]
            if hooks_disabled:
                observations.append("disableAllHooks is true in this file")
                self.gap(SSH_HOOKS_GAP)
            if self.scope is None:
                observations.append(LOCAL_COMMAND_SCOPE[name])
            facts = {"configured_program": not hooks_disabled}
            if invalid:
                facts["ssh_configured_positions"] = configured
                facts["ssh_invalid_positions"] = invalid
            self.add([name], "program", observations, facts)

    def handlers(self, value):
        if not isinstance(value, dict):
            self.gap("hooks is not an object of hook events; its hooks were not evaluated.")
            return []
        found = []
        for event, groups in value.items():
            if event not in HOOK_EVENTS:
                self.gap(UNKNOWN_EVENT)
                continue
            if not isinstance(groups, list):
                self.gap("hooks contains an event that is not a list of matcher groups; it was not evaluated.")
                continue
            for group, entry in enumerate(groups, 1):
                handlers = entry.get("hooks") if isinstance(entry, dict) else None
                if not isinstance(handlers, list):
                    self.gap("hooks contains a matcher group without a list of handlers; it was not evaluated.")
                    continue
                for position, handler in enumerate(handlers, 1):
                    if valid_handler(handler):
                        found.append(handler_record(event, group, position, handler))
                    else:
                        self.gap("hooks contains a handler that is not a valid hook; it was not evaluated.")
        return found

    def sandbox(self, value):
        if not isinstance(value, dict):
            self.gap("sandbox must be a table.")
            return
        self.unknown(value, SANDBOX, "sandbox")
        enabled = self.boolean(value, "enabled", False, "sandbox.enabled")
        if enabled is not None and ("enabled" in value or self.scope != "project"):
            label = str(enabled).lower() if "enabled" in value else "false (default)"
            self.add(["sandbox", "enabled"], "setting", [label])
        key = "autoAllowBashIfSandboxed"
        if key in value:
            auto = self.boolean(value, key, None, f"sandbox.{key}")
            if auto is not None:
                self.add(["sandbox", key], "setting", [str(auto).lower()])
        elif enabled:
            self.gap(AUTO_APPROVAL_UNSET)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def invalid_json_constant(token):
    raise ValueError("Invalid JSON number")


def valid_handler(handler):
    kind = handler.get("type") if isinstance(handler, dict) else None
    field = HOOK_FIELDS.get(kind) if isinstance(kind, str) else None
    if field is None or not all(nonempty(handler.get(name)) for name in field):
        return False
    if "if" in handler and not nonempty(handler["if"]):
        return False
    if "args" not in handler:
        return True
    args = handler["args"]
    return kind == "command" and isinstance(args, list) and all(isinstance(item, str) for item in args)


def handler_record(event, group, position, handler):
    kind = handler["type"]
    if "if" not in handler:
        condition = "none"
    else:
        condition = "filters" if event in TOOL_EVENTS else "never_runs"
    background = kind == "command" and (handler.get("async") is True or handler.get("asyncRewake") is True)
    return {"event": event, "group": group, "position": position, "kind": kind, "background": background,
            "if_state": condition, "exec": "args" in handler}


def runs(record):
    return record["if_state"] != "never_runs" and not (record["kind"] == "agent"
                                                       and record["event"] == "PermissionRequest")


def decides(record):
    return (runs(record) and record["kind"] in FACTS and not record["background"]
            and record["event"] in DECISION_EVENTS)


def handler_note(record):
    notes = [f"{record['event']}: matcher group {record['group']}, hook {record['position']}"]
    notes += [EXEC] if record["exec"] else []
    notes += {"filters": [FILTERED], "never_runs": [NEVER]}.get(record["if_state"], [])
    notes += [BACKGROUND] if record["background"] else []
    notes += [DECIDES] if decides(record) else []
    if record["kind"] in ("prompt", "agent"):
        if record["event"] == "PermissionRequest":
            notes.append(SKIPPED if record["kind"] == "agent" else NORMAL_FLOW)
        elif record["event"] == "PreToolUse":
            notes.append(BLOCKS)
        if record["kind"] == "agent" and runs(record):
            notes.append(READS)
    return "; ".join(notes)


def resolve(entries, discovered):
    programs = [entry for entry in entries if entry["kind"] == "program"
                and (entry["name"] in HELPER_USE or entry["name"] in WORKSPACE_COMMANDS)]
    winners = {entry["name"]: entry["source"] for entry in programs} if discovered else {}
    flags = [entry for entry in entries if "disable_all_hooks" in entry["facts"]]
    lists = {entry["source"] for entry in entries if entry["facts"].get("http_allowlist")}
    for flag in flags:
        value = flag["facts"]["disable_all_hooks"]
        flag["observations"] = [INVALID_FLAG if value == "invalid" else str(value).lower()]
        if discovered and flag is not flags[-1] and value != flags[-1]["facts"]["disable_all_hooks"]:
            flag["observations"].append(f"overridden by {flags[-1]['source']}")
    gaps, disabled_any = [], False
    for entry in entries:
        facts = entry["facts"]
        name, source = entry["name"], entry["source"]
        workspace_command = entry["kind"] == "program" and name in WORKSPACE_COMMANDS
        if workspace_command:
            entry["observations"] = [COMMAND] + ([PROJECT] if facts["project"] else [])
            facts["configured_program"] = True
        if name in winners and source != winners[name]:
            entry["observations"].append(f"overridden by {winners[name]}")
            facts["configured_program"] = False
            continue
        if "handlers" not in facts and not workspace_command:
            continue
        scoped = flags if discovered else [flag for flag in flags if flag["source"] == source]
        winner = scoped[-1] if scoped else None
        disabled = winner is not None and winner["facts"]["disable_all_hooks"] is True
        if workspace_command:
            if disabled:
                facts["configured_program"] = False
                location = "this file" if source == winner["source"] else winner["source"]
                entry["observations"].append(COMMAND_DISABLE_SOURCE + location)
                if discovered:
                    gaps.append(COMMAND_SUPPRESSED.format(name))
            continue
        active = not disabled and any(runs(record) for record in facts["handlers"])
        if facts["kind"] in FACTS:
            facts[FACTS[facts["kind"]]] = active
        facts["allowlist"] = facts["kind"] == "http" and bool(entry["source"] in lists or discovered and lists)
        observations = list(HEADS[facts["kind"]]) + ([ALLOWLIST] if facts["allowlist"] else [])
        observations += [handler_note(record) for record in facts["handlers"]]
        if disabled:
            disabled_any = True
            observations.append(DISABLED if winner["source"] == entry["source"]
                                else f"turned off by disableAllHooks in {winner['source']}")
        observations += [PROJECT] if facts["project"] else []
        entry["observations"] = observations
        if facts["kind"] == "mcp_tool" and active:
            gaps.append(f"{entry['source']}: {MCP_GAP}")
    if discovered and disabled_any:
        gaps.append(UNREAD_ENABLE)
    return gaps


@exclude_account_files
def read_file(path, source, *, discovered=False, sources_read=None, scope=None):
    reader = SettingsReader(source)
    reader.scope = scope
    try:
        fd = open_input(path)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("not a regular file")
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            reader.gap("Settings file exceeds the 1 MiB size limit.")
            return [], sorted(reader.gaps)
        data = json.loads(content.decode("utf-8"), parse_constant=invalid_json_constant)
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except FileNotFoundError:
        if not discovered:
            reader.gap(UNREADABLE)
            return [], sorted(reader.gaps)
        reader.add(["settings"], "settings file", ["absent"])
        return reader.read({})
    except (OSError, RecursionError, ValueError):
        reader.gap(UNREADABLE)
        return [], sorted(reader.gaps)
    if sources_read is not None:
        sources_read.append(source)
    return reader.read(data)
