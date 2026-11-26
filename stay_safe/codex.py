import errno
import json
import os
from pathlib import Path
from posixpath import normpath
import re
import stat
import tomllib
import unicodedata

MAX_BYTES = 1024 * 1024
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}\Z")
APPROVALS = ("auto", "prompt", "writes", "approve")
AUTO_REVIEW_VALUES = ("auto_review", "guardian_subagent")
APP_TOOL_REVIEWER_GAP = ("{label} requests AI review if this tool needs approval. "
                         "A policy can require human review. The effective reviewer was not checked.")
PROFILE_LOADER_VERSION = "0.172.0"
INLINE_PROFILE_OVERRIDE = ("On versions that support inline profiles, settings in the selected table can override "
                           "your top-level settings.")
LEGACY_PROFILE_SELECTOR = (f"Codex {PROFILE_LOADER_VERSION} rejects a top-level profile selector in the configuration "
                           f"it uses at startup. It ignores this setting in project configuration. {INLINE_PROFILE_OVERRIDE}")
LEGACY_PROFILE_TABLES = ("Legacy profile tables do not select a profile. If this is the base user config, "
                         f"starting Codex {PROFILE_LOADER_VERSION} with a matching --profile name stops configuration "
                         f"loading. {INLINE_PROFILE_OVERRIDE}")
INVALID_PROFILE_SELECTOR = "Codex expects a string for the top-level profile setting. It ignores this setting in project configuration."
EMPTY_PROFILES = "The profiles table is empty. No profile names are defined. Startup profile selection was not checked."
INVALID_APPROVAL = "Codex cannot load this configuration file because {label} is not one of " + ", ".join(APPROVALS) + "."
INVALID_BOOLEAN = "Codex cannot load this configuration file because {label} is not a boolean."
INLINE_MCP_VALUES = "{label} contains inline values. Check the entries for credentials."
INVALID_MCP_MAP = "Codex cannot load this configuration because {label} must be a table of strings."
MCP_OTHER_TRANSPORT = {
    "env": {"http_headers", "http_headers_helper", "env_http_headers", "bearer_token_env_var", "oauth", "oauth_resource", "auth", "bearer_token"},
    "http_headers": {"args", "env", "env_vars", "cwd", "bearer_token"},
}
SANDBOXES = {"read-only", "workspace-write", "danger-full-access"}
HOOKS = {"SessionStart", "SessionEnd", "PreToolUse", "PostToolUse", "UserPromptSubmit",
         "Stop", "SubagentStart", "SubagentStop", "PreCompact", "PostCompact",
         "PreModelRequest", "PostModelRequest", "PermissionRequest", "Interrupt"}
UNKNOWN = object()
EXTRA_ROOTS = ("sandbox_workspace_write.writable_roots lists extra folders commands may write, "
               "some possibly outside the workspace. Their paths are withheld. ")
ROOTS_NO_WORKSPACE = EXTRA_ROOTS + ("No --workspace was supplied to check project .codex. "
                                   "The folders' other effects were not assessed.")
ROOTS_SCOPE = EXTRA_ROOTS + ("Only a direct grant to project .codex is checked. "
                             "Aliases and other effects of extra folders are unassessed.")
ROOT_HOME_UNKNOWN = ("sandbox_workspace_write.writable_roots contains a home-relative path but HOME is missing "
                     "or is not absolute. The home-relative roots could not be compared with project .codex.")
WORKSPACE_UNKNOWN = ("The project .codex comparison depends on an unresolved path, symlink or directory "
                     "that could not be checked.")
WORKSPACE_HOME = "The selected workspace's .codex is the user Codex home, outside the project settings check."
WORKSPACE_HOME_UNKNOWN = "The project settings directory could not be distinguished from the user Codex home."
PREFERENCES = {"model", "review_model", "model_reasoning_effort", "model_reasoning_summary",
               "model_verbosity", "service_tier", "personality", "tui", "notice", "history",
               "check_for_update_on_startup", "disable_paste_burst", "hide_agent_reasoning",
               "show_raw_agent_reasoning", "suppress_unstable_features_warning"}


def config_name(parts):
    return ".".join(p if re.fullmatch(r"[A-Za-z0-9_-]+", p) else json.dumps(p) for p in parts)


def tool_tables(table):
    tools = table.get("tools", {})
    return {n: c for n, c in tools.items() if isinstance(c, dict)} if isinstance(tools, dict) else {}


def public_name(value, tool=False):
    pieces = value.split("/") if tool else [value]
    return all(bool(NAME.fullmatch(p)) and p not in {".", ".."}
               and not p.lower().startswith(("sk-", "ghp_", "github_pat_")) for p in pieces)


def app_tool_setting(table, path, key, default, errors):
    if key not in table:
        return default
    value = table[key]
    if key in ("enabled", "default_tools_enabled"):
        if type(value) is bool:
            return value
        message = INVALID_BOOLEAN
    else:
        if isinstance(value, str) and value in APPROVALS:
            return value
        message = INVALID_APPROVAL
    errors.append(message.format(label=f"{path}.{key}"))
    return UNKNOWN


def configured_root(value):
    if value == "~" or value.startswith("~/"):
        home = os.environ.get("HOME")
        if not home or not home.startswith("/"):
            return UNKNOWN
        value = str(Path(home) / value[1:].lstrip("/"))
    if not value.startswith("/"):
        return None
    return Path(normpath("/" + value.lstrip("/")))


def directory_identity(path):
    if path.anchor != "/" or ".." in path.parts:
        return UNKNOWN
    ancestor = None
    for index, component in enumerate((*reversed(path.parents), path)):
        try:
            info = component.stat(follow_symlinks=False)
        except FileNotFoundError:
            return (ancestor, "/".join(path.parts[index:])) if ancestor is not None else UNKNOWN
        except (OSError, ValueError):
            return UNKNOWN
        if not stat.S_ISDIR(info.st_mode):
            return UNKNOWN
        ancestor = (info.st_dev, info.st_ino)
    return ancestor, ""


def unresolved_home_alias(target, home):
    return (target[0] == home[0] and
            unicodedata.normalize("NFD", target[1].casefold()) == unicodedata.normalize("NFD", home[1].casefold()))


class Reader:
    def __init__(self, source, workspace=None):
        self.source = source
        self.workspace = workspace
        self.entries = []
        self.gaps = set()

    def gap(self, message):
        self.gaps.add(f"{self.source}: {message}")

    def add(self, parts, kind, observations, facts=None):
        name = config_name(parts)
        self.entries.append({"id": f"{self.source}:{name}", "source": self.source,
                             "name": name, "kind": kind, "observations": observations,
                             "facts": facts or {}})

    def table(self, value, label):
        if not isinstance(value, dict):
            self.gap(f"{label} must be a table.")
            return {}
        return value

    def unknown(self, table, known, label):
        found = bool(set(table) - known)
        if found:
            self.gap(f"{label} contains fields outside reader coverage; their values were withheld.")
        return found

    def boolean(self, table, key, default, label):
        value = table.get(key, default)
        if type(value) is not bool:
            self.gap(f"{label} has an invalid boolean; its behavior is unknown.")
            return None
        return value

    def named(self, table, label, *, include_withheld=False):
        for name, value in table.items():
            if not public_name(name, tool=label == "tools"):
                self.gap(f"{label} contains a name that cannot be included in a shareable report.")
                if not include_withheld or not isinstance(value, dict):
                    continue
                name = None
            if not isinstance(value, dict):
                self.gap(f"{label} contains an entry that is not a table.")
                continue
            yield name, value

    def approval(self, data):
        if "approval_policy" not in data:
            self.gap("approval_policy is absent; the reader does not infer its effective value.")
            return
        value = data["approval_policy"]
        if isinstance(value, str) and value in {"never", "on-request"}:
            self.add(["approval_policy"], "permission", [value],
                     {"commands_without_prompts": value == "never"})
        elif (isinstance(value, str) and value in {"untrusted", "on-failure"}
              or isinstance(value, dict) and set(value) == {"granular"}):
            self.gap("approval_policy has a known but unhandled value; its behavior is not evaluated.")
        else:
            self.gap("approval_policy is unsupported or invalid; its value was withheld.")

    def writable_roots(self, roots, selected_profile):
        if self.workspace is None:
            self.gap(ROOTS_NO_WORKSPACE)
            return
        self.gap(ROOTS_SCOPE)
        if selected_profile:
            return
        normalized = {configured_root(root) for root in roots}
        if UNKNOWN in normalized:
            self.gap(ROOT_HOME_UNKNOWN)
        target = Path(self.workspace).absolute() / ".codex"
        target_id = directory_identity(target)
        if target_id is UNKNOWN:
            self.gap(WORKSPACE_UNKNOWN)
            return
        if target not in normalized:
            return
        home = os.environ.get("CODEX_HOME")
        if not home and os.environ.get("HOME"):
            home = Path(os.environ["HOME"]) / ".codex"
        home = Path(home).absolute() if home else None
        home_id = directory_identity(home) if home is not None else UNKNOWN
        if home == target or target_id == home_id:
            self.gap(WORKSPACE_HOME)
            return
        if home_id is UNKNOWN or unresolved_home_alias(target_id, home_id):
            self.gap(WORKSPACE_HOME_UNKNOWN)
            return
        self.add(["sandbox_workspace_write", "writable_roots"], "permission",
                 ["selected workspace's .codex directory explicitly listed"],
                 {"writable_project_settings": True})

    def sandbox(self, data):
        profile = "default_permissions" in data
        if profile or "permissions" in data:
            self.gap("Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence.")
        mode = data.get("sandbox_mode")
        if isinstance(mode, str) and mode in SANDBOXES:
            self.add(["sandbox_mode"], "permission", [mode, "permission-profile selection is uninspected"] if profile else [mode],
                     {"unrestricted_filesystem": not profile and mode == "danger-full-access"})
        elif "sandbox_mode" in data:
            self.gap("sandbox_mode is unsupported or invalid; its value was withheld.")
        elif not profile:
            self.gap("sandbox_mode is absent; the reader does not infer its effective value.")
        if profile and "sandbox_mode" in data:
            self.gap("default_permissions and sandbox_mode conflict; effective sandbox selection is unknown.")
        if "sandbox_workspace_write" in data:
            table = self.table(data["sandbox_workspace_write"], "sandbox_workspace_write")
            self.unknown(table, {"network_access", "writable_roots", "exclude_tmpdir_env_var", "exclude_slash_tmp"}, "sandbox_workspace_write")
            active = mode == "workspace-write" and not profile
            if "writable_roots" in table:
                roots = table["writable_roots"]
                if not (isinstance(roots, list) and all(isinstance(r, str) for r in roots)):
                    self.gap("sandbox_workspace_write.writable_roots is invalid; its value was withheld.")
                elif roots and active:
                    self.writable_roots(roots, "profile" in data)
            if "network_access" in table:
                value = self.boolean(table, "network_access", False, "sandbox_workspace_write")
                if value is not None:
                    self.add(["sandbox_workspace_write", "network_access"], "permission",
                             [str(value).lower(), "workspace-write option" if active else "inactive or selection unknown"],
                             {"network_access": active and value})

    def shell_environment(self, data):
        label = "shell_environment_policy"
        policy = data.get(label, {})
        if not isinstance(policy, dict):
            self.gap(f"{label} must be a table.")
            return
        if self.unknown(policy, {"inherit", "ignore_default_excludes"}, label):
            return
        inherit = policy.get("inherit", "all")
        ignore = policy.get("ignore_default_excludes", True)
        inherit_valid = isinstance(inherit, str) and inherit in {"all", "core", "none"}
        ignore_valid = type(ignore) is bool
        if not inherit_valid:
            self.gap(f"{label}.inherit is unsupported or invalid; its value was withheld.")
        if not ignore_valid:
            self.gap(f"{label}.ignore_default_excludes has an invalid boolean; its behavior is unknown.")
        if not inherit_valid or not ignore_valid:
            return
        observations = [f"{key}: {value} ({'explicit' if key in policy else 'default'})"
                        for key, value in (("inherit", inherit), ("ignore_default_excludes", str(ignore).lower()))]
        self.add([label], "permission", observations,
                 {"environment_inheritance": inherit == "all"})

    def tool_approval(self, mode, applies, label, report_invalid=True):
        default = mode is None
        mode = "auto" if default else mode
        if isinstance(mode, str) and mode in APPROVALS:
            return ([f"tool approval: {mode}" + (" (default)" if default else "")],
                    {"automatic_tools": applies and mode == "approve",
                     "self_described_tools": applies and mode in {"auto", "writes"}}, True)
        if mode is not UNKNOWN and report_invalid:
            self.gap(f"A {label} approval mode is unsupported or invalid; its value was withheld.")
        return [], {}, False

    def tool(self, parts, name, override, mode, available, destructive, off_reason=None):
        own = override is not None
        obs = [off_reason or ("configured enabled" if available else "disabled or enablement unknown")]
        if destructive:
            obs.append("enabled even if destructive")
        effective = override if own else ("auto" if mode is None else mode)
        approval, facts, mode_valid = self.tool_approval(effective, own and available, "per-tool", report_invalid=own)
        self.add(parts + ["tools", name], "tool policy", obs + approval, facts | {"destructive_tools": destructive})
        return mode_valid

    def mcp_tools(self, server, parts, enabled):
        valid = True
        for key in ("enabled_tools", "disabled_tools"):
            values = server.get(key, [])
            if not (isinstance(values, list) and all(isinstance(v, str) for v in values)):
                valid = False
            elif key in server:
                names = [name for name in values if public_name(name, tool=True)]
                obs = ["configured names: " + ", ".join(names) if names else "no reportable configured names"]
                if len(names) != len(values):
                    obs.append("some names withheld")
                    self.gap("A tool allow/deny list contains a name that cannot be included in a shareable report.")
                self.add(parts + [key], "tool filter", obs)
        if not valid:
            self.gap("A tool allow/deny list is invalid; tool availability is unknown.")
        allow, deny = server.get("enabled_tools"), server.get("disabled_tools", [])
        def permitted(name):
            return valid and (allow is None or name in allow) and name not in deny
        mode, configs = server.get("default_tools_approval_mode"), tool_tables(server)
        applies = valid and (allow is None or any(permitted(n) and "approval_mode" not in configs.get(n, {}) for n in allow))
        observations, facts, mode_valid = self.tool_approval(mode, enabled is True and applies, "tool")
        policy_valid = valid and mode_valid
        if "tools" in server:
            policy_valid = policy_valid and isinstance(server["tools"], dict) and len(configs) == len(server["tools"])
            for name, config in self.named(self.table(server["tools"], "tools"), "tools"):
                self.unknown(config, {"approval_mode", "output_token_limit"}, "tools")
                override_valid = self.tool(parts, name, config.get("approval_mode"), mode, enabled is True and permitted(name), False)
                policy_valid = policy_valid and override_valid
        return observations, facts, policy_valid

    def mcp(self, data):
        servers = self.table(data.get("mcp_servers", {}), "mcp_servers")
        known = {"command", "args", "env", "env_vars", "cwd", "url", "http_headers", "env_http_headers",
                 "bearer_token_env_var", "oauth", "oauth_resource", "auth", "scopes", "name", "enabled",
                 "enabled_tools", "disabled_tools", "startup_timeout_sec", "startup_timeout_ms", "tool_timeout_sec",
                 "required", "startup_readiness", "default_tools_approval_mode", "tools", "http_headers_helper",
                 "environment_id", "supports_parallel_tool_calls", "tool_input_schema_max_bytes", "omit_tools_from"}
        for name, server in self.named(servers, "mcp_servers"):
            parts = ["mcp_servers", name]
            self.unknown(server, known, "mcp_servers")
            enabled = self.boolean(server, "enabled", True, "mcp_servers")
            obs = ["configured enabled" if enabled is True else "disabled" if enabled is False else "enablement unknown"]
            command, url = server.get("command"), server.get("url")
            stdio = isinstance(command, str) and url is None
            http = isinstance(url, str) and command is None
            helper = server.get("http_headers_helper")
            valid_helper = isinstance(helper, str) and bool(helper.strip())
            field = "env" if stdio else "http_headers"
            values = server.get(field, {})
            valid = (stdio and bool(command.strip())) or http
            if stdio and helper is not None:
                valid = False
                obs.append("Codex rejects this stdio configuration")
                self.gap(f"Codex cannot load this configuration because stdio MCP server {name} sets http_headers_helper.")
            elif valid and not (isinstance(values, dict) and all(isinstance(v, str) for v in values.values())):
                valid = False
                obs.append("Codex rejects this configuration")
                self.gap(INVALID_MCP_MAP.format(label=config_name(parts + [field])))
            elif valid:
                obs.append("stdio; command withheld" if stdio else "HTTP; endpoint withheld")
            else:
                obs.append("transport unknown")
                self.gap("An MCP transport is missing, conflicting or invalid.")
            policy, facts, policy_valid = self.mcp_tools(server, parts, enabled is True and valid)
            if (enabled is True and valid and policy_valid and values and MCP_OTHER_TRANSPORT[field].isdisjoint(server)
                    and (helper is None or valid_helper)):
                self.gap(INLINE_MCP_VALUES.format(label=config_name(parts + [field])))
            if helper is not None and not stdio and not valid_helper:
                self.gap("An MCP header-helper command is invalid; its value was withheld.")
            facts["configured_program"] = enabled is True and valid and (stdio or valid_helper)
            self.add(parts, "MCP server", obs + policy, facts)

    def app_tool_settings(self, app, path, tools_enabled, errors):
        for tool, config in self.named(self.table(app.get("tools", {}), "tools"), "tools", include_withheld=True):
            label = path + ".tools." + (config_name([tool]) if tool is not None else "*")
            enabled = app_tool_setting(config, label, "enabled", tools_enabled, errors)
            mode = app_tool_setting(config, label, "approval_mode", None, errors)
            known = {"approval_mode", "enabled"}
            reviewer = config.get("approvals_reviewer")
            if reviewer in ("user", *AUTO_REVIEW_VALUES):
                known.add("approvals_reviewer")
            if reviewer in AUTO_REVIEW_VALUES:
                self.gap(APP_TOOL_REVIEWER_GAP.format(label=f"{label}.approvals_reviewer"))
            if tool is not None:
                self.unknown(config, known, "tools")
            yield tool, enabled, mode, config.get("enabled") is True

    def apps(self, data, apps_off):
        apps = self.table(data.get("apps", {}), "apps")
        default = apps.get("_default", {})
        default_errors = []
        if not isinstance(default, dict):
            self.gap("apps._default must be a table.")
            apps = {k: v for k, v in apps.items() if k != "_default"}
            default = {"destructive_enabled": UNKNOWN}
            default_mode = UNKNOWN
        else:
            default_mode = app_tool_setting(default, "apps._default", "default_tools_approval_mode", None, default_errors)
        for name, app in self.named(apps, "apps"):
            before = set(self.gaps)
            settings = {**{k: v for k, v in default.items() if k != "enabled"}, **app}
            template = name == "_default"
            off_reason = "disabled by features.apps = false" if apps_off and not template else None
            allowed = {"enabled", "destructive_enabled", "open_world_enabled", "default_tools_approval_mode", "approvals_reviewer"}
            if not template:
                allowed |= {"default_tools_enabled", "tools", "links", "omit_tools_from"}
            self.unknown(app, allowed, "apps._default" if template else "apps")
            enabled = False if off_reason else self.boolean(settings, "enabled", True, "apps")
            path = config_name(["apps", name])
            load_errors = list(default_errors) if template else []
            for field in ("open_world_enabled", "destructive_enabled"):
                if field in app and type(app[field]) is not bool:
                    load_errors.append(INVALID_BOOLEAN.format(label=f"{path}.{field}"))
            mode = default_mode
            tools_enabled = True
            tools = []
            if not template:
                mode = app_tool_setting(app, path, "default_tools_approval_mode", default_mode, load_errors)
                tools_enabled = app_tool_setting(app, path, "default_tools_enabled", True, load_errors)
                tools = list(self.app_tool_settings(app, path, tools_enabled, load_errors))
            if load_errors and enabled is not False:
                enabled = None
                off_reason = "Codex cannot load this configuration file"
            obs = [off_reason or ("configured enabled" if enabled is True else "disabled" if enabled is False else "enablement unknown")]
            if tools_enabled is not True:
                obs.append("default tools disabled or unknown")
            applies = tools_enabled is True or any(own and override is None for _, _, override, own in tools)
            policy, facts, _ = self.tool_approval(mode, enabled is True and applies, "tool")
            for tool, tool_enabled, override, explicitly_enabled in tools:
                if tool is not None:
                    available = tool_enabled is True and enabled is True
                    self.tool(["apps", name], tool, override, mode, available, available and explicitly_enabled, off_reason)
            source = ("destructive_enabled" if "destructive_enabled" in app
                      else "apps._default.destructive_enabled" if "destructive_enabled" in settings else "Codex default")
            destructive = settings.get("destructive_enabled", True)
            if type(destructive) is not bool:
                destructive = None
            if not template and "default_tools_enabled" in app:
                destructive, source = (True, "default_tools_enabled") if tools_enabled is True else (None, None)
            if destructive is not None and enabled is True and not template:
                obs.append(f"destructive tools {'enabled' if destructive else 'disabled'} by {source}")
                facts["destructive_tools"] = destructive
            if "links" in app:
                self.gap("Per-account app policy is not evaluated; account identifiers were withheld.")
            if app.get("approvals_reviewer") in AUTO_REVIEW_VALUES:
                self.gap("App approvals_reviewer is not evaluated; Codex may let a reviewer decide an app's tool calls instead of asking you.")
            if enabled is False and not template:
                self.gaps = before
            for error in load_errors:
                self.gap(error)
            if template:
                facts = {k: v for k, v in facts.items() if k == "automatic_tools"} if enabled is True and not apps_off else {}
                explicit = default.get("destructive_enabled")
                if enabled is True and not apps_off and type(explicit) is bool:
                    obs.append(f"destructive tools {'enabled' if explicit else 'disabled'} by apps._default.destructive_enabled")
                    facts["destructive_tools"] = explicit
                if facts.get("automatic_tools") or facts.get("destructive_tools"):
                    obs.insert(1, "applies to apps not named in this file")
            self.add(["apps", name], "app policy", obs + policy, facts)

    @staticmethod
    def unnamed_apps(data):
        apps = data.get("apps", {})
        default = apps.get("_default", {}) if isinstance(apps, dict) else None
        if not isinstance(default, dict) or type(default.get("enabled", True)) is not bool:
            return "apps not named in this file: settings unknown"
        if default.get("enabled") is False:
            return "apps not named in this file: disabled by apps._default.enabled"
        if type(default.get("open_world_enabled", True)) is not bool:
            return "apps not named in this file: settings unknown"
        if "destructive_enabled" not in default:
            return "apps not named in this file: destructive tools enabled by Codex default"
        destructive = default["destructive_enabled"]
        if type(destructive) is not bool:
            return "apps not named in this file: destructive tools unknown"
        return (f"apps not named in this file: destructive tools {'enabled' if destructive else 'disabled'} "
                "by apps._default.destructive_enabled")

    def projects(self, projects):
        count = 0
        incomplete = not isinstance(projects, dict)
        if isinstance(projects, dict):
            for project in projects.values():
                if not isinstance(project, dict):
                    incomplete = True
                    continue
                trust = project.get("trust_level")
                count += trust == "trusted"
                if not isinstance(trust, str) or trust not in {"trusted", "untrusted"} or project.keys() - {"trust_level"}:
                    incomplete = True
            self.gap(f"projects contains {count} recognized trusted declarations; project settings were not inspected.")
        if incomplete:
            self.gap("projects contains malformed or unsupported data; its declarations could not be fully assessed.")

    def profiles(self, data):
        if "profile" in data:
            self.gap(LEGACY_PROFILE_SELECTOR if isinstance(data["profile"], str) else INVALID_PROFILE_SELECTOR)
            if "profiles" in data:
                self.table(data["profiles"], "profiles")
        elif "profiles" in data:
            profiles = data["profiles"]
            if profiles == {}:
                self.gap(EMPTY_PROFILES)
            for value in self.table(profiles, "profiles").values():
                self.gap(LEGACY_PROFILE_TABLES if isinstance(value, dict) else "profiles contains an entry that is not a table.")

    def read(self, data):
        unchecked = {"plugins", "marketplaces", "desktop"}
        for section in unchecked & data.keys():
            self.gap(f"Unchecked section {section}; its settings were not evaluated.")
        if "projects" in data:
            self.projects(data["projects"])
        self.profiles(data)
        self.approval(data)
        self.sandbox(data)
        approval = next((e for e in self.entries if e["name"] == "approval_policy"), None)
        full = (data.get("sandbox_mode") == "danger-full-access" and "default_permissions" not in data)
        self.shell_environment(data)
        self.mcp(data)
        if "model_providers" in data:
            for name, provider in self.named(self.table(data["model_providers"], "model_providers"), "model_providers"):
                self.add(["model_providers", name], "model provider", ["configured; endpoint and credentials withheld"])
                if "auth" in provider:
                    self.gap("Model-provider command-backed authentication is outside reader coverage.")
                aws = self.table(provider.get("aws", {}), "aws")
                for key in ("credential_export", "auth_refresh"):
                    if key in aws:
                        self.gap(f"Model-provider setting aws.{key} is for a credential command. Stay-safe did not check its value.")
                gateway = self.table(provider.get("gateway_oauth", {}), "gateway_oauth")
                if "credential_export" in gateway:
                    self.gap("Model-provider setting gateway_oauth.credential_export is for a credential command. Stay-safe did not check its value.")
        otel = data.get("otel")
        if isinstance(otel, dict) and "headers_helper" in otel:
            self.gap("otel.headers_helper is for a command that supplies telemetry headers. Stay-safe did not check its value.")
        if "notify" in data:
            notify = data["notify"]
            if (isinstance(notify, list) and notify and all(isinstance(p, str) for p in notify)
                    and notify[0]):
                self.add(["notify"], "automation", ["notification command configured; command withheld"], {"configured_program": True})
            else:
                self.gap("notify is not a command list with a nonempty program.")
        if "hooks" in data:
            hooks = self.table(data["hooks"], "hooks")
            self.unknown(hooks, HOOKS | {"state"}, "hooks")
            for name in HOOKS & hooks.keys():
                if not isinstance(hooks[name], list):
                    self.gap("hooks contains an invalid event configuration.")
                    continue
                program = False
                for group in hooks[name]:
                    if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                        self.gap("hooks contains an invalid handler group.")
                        continue
                    program = program or any(
                        isinstance(h, dict) and h.get("type") == "command" and isinstance(h.get("command"), str)
                        and any(isinstance(h.get(key), str) and bool(h[key].strip())
                                for key in ("command", "commandWindows", "command_windows"))
                        for h in group.get("hooks", []))
                self.add(["hooks", name], "automation", ["contents withheld"], {"configured_program": program})
            self.gap("Hook execution policy is outside reader coverage.")
        features = self.table(data.get("features", {}), "features")
        self.unknown(features, {"apps"}, "features")
        apps_enabled = self.boolean(features, "apps", True, "features.apps")
        if apps_enabled:
            self.add(["features", "apps"], "MCP server", ["ChatGPT Apps", "exists only if Codex is signed in with ChatGPT, "
                     "which is not checked", "features.apps = false turns it off", self.unnamed_apps(data)])
        self.apps(data, apps_enabled is False and features.get("connectors", False) is False)
        if "web_search" in data:
            value = data["web_search"]
            if isinstance(value, str) and value in {"disabled", "cached", "indexed", "live"}:
                self.add(["web_search"], "connection policy", [value])
            else:
                self.gap("web_search is unsupported or invalid; its value was withheld.")
        known = PREFERENCES | unchecked | {"projects", "approval_policy", "sandbox_mode", "sandbox_workspace_write", "mcp_servers", "apps",
                               "model_providers", "notify", "hooks", "web_search", "default_permissions", "permissions",
                               "shell_environment_policy", "profile", "profiles", "features"}
        self.unknown(data, known, "Configuration")
        if approval and full:
            self.full_access(approval)
        self.entries.sort(key=lambda e: e["name"])
        return self.entries, sorted(self.gaps)

    def full_access(self, approval):
        if approval["observations"] == ["on-request"]:
            approval["observations"].append("with danger-full-access, ordinary commands can run without asking")
            approval["facts"]["commands_without_prompts"] = True
        elif approval["observations"] == ["never"]:
            reachable = any(e["kind"] == "MCP server" and (e["name"] == "features.apps" or "configured enabled" in e["observations"])
                            or e["kind"] == "app policy" and e["name"] != "apps._default" and "configured enabled" in e["observations"]
                            for e in self.entries)
            if reachable:
                approval["observations"].append("with danger-full-access, MCP and app tool calls can run without asking")
                approval["facts"]["automatic_tools"] = True


EXCLUDED_ACCOUNT = "Claude Code account and credential files are excluded. Check which input file you selected."


def exclude_account_files(read_file):
    def checked(path, source, **options):
        if Path(path).name.casefold() in {".claude.json", ".credentials.json"}:
            return [], [f"{source}: {EXCLUDED_ACCOUNT}"]
        return read_file(path, source, **options)
    return checked


def open_input(path):
    return os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)


@exclude_account_files
def read_file(path: Path, source: str, *, discovered=False, workspace=None):
    reader = Reader(source, workspace)
    try:
        try:
            fd = open_input(path)
        except FileNotFoundError:
            if not discovered:
                raise
            reader.add(["config"], "configuration file", [
                "No default Codex configuration file was found. Assessed defaults: command environment and ChatGPT Apps.",
            ])
            return reader.read({})
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                reader.gap("Input is not a regular file.")
                return [], sorted(reader.gaps)
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            reader.gap("Input exceeds the 1 MiB size limit.")
            return [], sorted(reader.gaps)
        data = tomllib.loads(content.decode("utf-8"))
    except (OSError, RecursionError, ValueError) as error:
        if not discovered and isinstance(error, FileNotFoundError):
            reader.gap('Selected config file is missing. Check the path supplied to --config.')
        elif not discovered and isinstance(error, OSError) and error.errno == errno.ELOOP:
            reader.gap('Selected config file is a symlink and was not followed. Select its target file explicitly with --config.')
        elif not discovered and isinstance(error, OSError):
            reader.gap('Selected config file could not be read. Check its permissions and that it is a readable regular file.')
        elif not discovered and isinstance(error, UnicodeDecodeError):
            reader.gap('Selected config file is not valid UTF-8. Save a copy as UTF-8 and select it with --config.')
        elif not discovered and isinstance(error, tomllib.TOMLDecodeError):
            reader.gap('Selected config file is not valid TOML. Fix the TOML syntax locally, then run stay-safe again.')
        else:
            reader.gap("Input is missing, unreadable, a symlink, or invalid UTF-8 TOML; raw errors were withheld.")
        return [], sorted(reader.gaps)
    return reader.read(data)
