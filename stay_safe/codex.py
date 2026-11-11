"""Read selected Codex TOML files without executing their configuration."""

import errno
import json
import os
from pathlib import Path
import re
import stat
import tomllib

MAX_BYTES = 1024 * 1024
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}\Z")
APPROVALS = {"auto", "prompt", "writes", "approve"}
SANDBOXES = {"read-only", "workspace-write", "danger-full-access"}
HOOKS = {"SessionStart", "SessionEnd", "PreToolUse", "PostToolUse", "UserPromptSubmit",
         "Stop", "SubagentStart", "SubagentStop", "PreCompact", "PostCompact",
         "PreModelRequest", "PostModelRequest", "PermissionRequest", "Interrupt"}
UNKNOWN = object()  # A value left to an apps._default that is not a table.
# Non-security preferences are deliberately ignored; unknown surfaces become gaps.
PREFERENCES = {"model", "review_model", "model_reasoning_effort", "model_reasoning_summary",
               "model_verbosity", "service_tier", "personality", "tui", "notice", "history",
               "check_for_update_on_startup", "disable_paste_burst", "hide_agent_reasoning",
               "show_raw_agent_reasoning", "suppress_unstable_features_warning"}


def config_name(parts):
    return ".".join(p if re.fullmatch(r"[A-Za-z0-9_-]+", p) else json.dumps(p) for p in parts)


def tool_tables(table):
    # A tools block or tool that is not a table is read as absent.
    tools = table.get("tools", {})
    return {n: c for n, c in tools.items() if isinstance(c, dict)} if isinstance(tools, dict) else {}


def public_name(value, tool=False):
    # Account IDs, URLs, paths, control text and credential-shaped identifiers are not report names.
    pieces = value.split("/") if tool else [value]
    return all(bool(NAME.fullmatch(p)) and p not in {".", ".."}
               and not p.lower().startswith(("sk-", "ghp_", "github_pat_")) for p in pieces)


class Reader:
    def __init__(self, source):
        self.source = source
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

    def named(self, table, label):
        for name, value in table.items():
            if not public_name(name, tool=label == "tools"):
                self.gap(f"{label} contains a name that cannot be included in a shareable report.")
                continue
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

    def sandbox(self, data):
        # A selected permission profile may supersede the sandbox settings, so they give no risk.
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
        # Source and coverage boundary: harnesses/codex.md [shell-environment].
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

    def tool_approval(self, mode, applies, label):
        """Observations and facts of an approval mode that tools take when applies is true."""
        default = mode is None
        mode = "auto" if default else mode
        if isinstance(mode, str) and mode in APPROVALS:
            return ([f"tool approval: {mode}" + (" (default)" if default else "")],
                    {"automatic_tools": applies and mode == "approve",
                     "self_described_tools": applies and mode in {"auto", "writes"}})
        if mode is not UNKNOWN:
            self.gap(f"A {label} approval mode is unsupported or invalid; its value was withheld.")
        return [], {}

    def tool(self, parts, name, config, mode, available, destructive):
        # A tool without its own mode takes its connection's; that risk stays on the connection.
        own = "approval_mode" in config
        obs = ["configured enabled" if available else "disabled or enablement unknown"]
        if destructive:
            obs.append("enabled even if destructive")
        approval, facts = self.tool_approval(config.get("approval_mode", "auto" if mode is None else mode), own and available, "per-tool")
        self.add(parts + ["tools", name], "tool policy", obs + approval, facts | {"destructive_tools": destructive})

    def mcp_tools(self, server, parts, enabled):
        # Tool allow and deny lists exist only on MCP servers: harnesses/codex.md [app-config].
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
        observations, facts = self.tool_approval(mode, enabled is True and applies, "tool")
        if "tools" in server:
            for name, config in self.named(self.table(server["tools"], "tools"), "tools"):
                self.unknown(config, {"approval_mode", "output_token_limit"}, "tools")
                self.tool(parts, name, config, mode, enabled is True and permitted(name), False)
        return observations, facts

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
            valid_command = isinstance(command, str) and bool(command.strip())
            # Codex uses HTTP for any string url without command: harnesses/codex.md [mcp-transport].
            valid_url = isinstance(url, str)
            valid = (valid_command and url is None) or (valid_url and command is None)
            if valid:
                obs.append("stdio; command withheld" if valid_command else "HTTP; endpoint withheld")
            else:
                obs.append("transport unknown")
                self.gap("An MCP transport is missing, conflicting or invalid.")
            policy, facts = self.mcp_tools(server, parts, enabled is True and valid)
            helper = server.get("http_headers_helper")
            valid_helper = isinstance(helper, str) and bool(helper.strip())
            if helper is not None and not valid_helper:
                self.gap("An MCP header-helper command is invalid; its value was withheld.")
            facts["configured_program"] = enabled is True and valid and (valid_command or valid_helper)
            self.add(parts, "MCP server", obs + policy, facts)

    def app_tools(self, app, name, enabled, mode, tools_enabled):
        # Without default_tools_enabled = true, only tools enabled by name take the app's mode.
        applies = tools_enabled is True or any("approval_mode" not in config and config.get("enabled") is True
                                               for config in tool_tables(app).values())
        observations, facts = self.tool_approval(mode, enabled is True and applies, "tool")
        if "tools" in app and name != "_default":
            for tool, config in self.named(self.table(app["tools"], "tools"), "tools"):
                self.unknown(config, {"approval_mode", "enabled"}, "tools")
                available = self.boolean(config, "enabled", tools_enabled, "tools") is True and enabled is True
                self.tool(["apps", name], tool, config, mode, available, available and config.get("enabled") is True)
        return observations, facts

    def apps(self, data):
        apps = self.table(data.get("apps", {}), "apps")
        default = apps.get("_default", {})
        if not isinstance(default, dict):
            self.gap("apps._default must be a table.")
            apps = {k: v for k, v in apps.items() if k != "_default"}
            # A template that is not a table leaves every setting an app takes from it unknown.
            default = dict.fromkeys(("default_tools_approval_mode", "destructive_enabled"), UNKNOWN)
        for name, app in self.named(apps, "apps"):
            before = set(self.gaps)
            # What the app takes from apps._default; the code below reads only this and the app's own fields.
            # Not enabled: apps._default.enabled disables no named app (harnesses/codex.md [app-enabled]).
            settings = {**{k: v for k, v in default.items() if k != "enabled"}, **app}
            template = name == "_default"
            allowed = {"enabled", "destructive_enabled", "open_world_enabled", "default_tools_approval_mode", "approvals_reviewer"}
            if not template:
                allowed |= {"default_tools_enabled", "tools", "links", "omit_tools_from"}
            self.unknown(app, allowed, "apps._default" if template else "apps")
            enabled = self.boolean(settings, "enabled", True, "apps")
            tools_enabled = True if template else self.boolean(app, "default_tools_enabled", True, "apps")
            obs = ["configured enabled" if enabled is True else "disabled" if enabled is False else "enablement unknown"]
            if tools_enabled is not True:
                obs.append("default tools disabled or unknown")
            policy, facts = self.app_tools(app, name, enabled, settings.get("default_tools_approval_mode"), tools_enabled)
            # Codex decides by default_tools_enabled, then destructive_enabled: harnesses/codex.md [app-tool-policy].
            source = ("destructive_enabled" if "destructive_enabled" in app
                      else "apps._default.destructive_enabled" if "destructive_enabled" in settings else "Codex default")
            destructive = settings.get("destructive_enabled", True)
            if destructive is UNKNOWN:
                destructive = None
            elif type(destructive) is not bool:
                self.gap("apps has an invalid destructive_enabled flag.")
                destructive = None
            if not template and "default_tools_enabled" in app:
                destructive, source = (True, "default_tools_enabled") if tools_enabled is True else (None, None)
            # A disabled app is decided before destructive_enabled is read; _default is only a template.
            if destructive is not None and enabled is True and not template:
                obs.append(f"destructive tools {'enabled' if destructive else 'disabled'} by {source}")
                facts["destructive_tools"] = destructive
            if "links" in app:
                self.gap("Per-account app policy is not evaluated; account identifiers were withheld.")
            if enabled is False and not template:
                # Codex disables every tool of a disabled app whatever else it sets (app_tool_policy.rs
                # L272-L277 at 086ccc8), so its other settings can't change a finding and give no gap.
                self.gaps = before
            self.add(["apps", name], "app policy", obs + policy, {} if template else facts)

    def projects(self, projects):
        """Count literal declarations only; never use project keys as filesystem paths."""
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

    def read(self, data):
        unchecked = {"plugins", "marketplaces", "desktop"}
        for section in unchecked & data.keys():
            self.gap(f"Unchecked section {section}; its settings were not evaluated.")
        if "projects" in data:
            self.projects(data["projects"])
        if "profile" in data or "profiles" in data:
            self.gap("Profiles are outside reader coverage; a selected profile can override the reported settings.")
        self.approval(data)
        self.sandbox(data)
        self.shell_environment(data)
        self.mcp(data)
        self.apps(data)
        if "model_providers" in data:
            for name, provider in self.named(self.table(data["model_providers"], "model_providers"), "model_providers"):
                self.add(["model_providers", name], "model provider", ["configured; endpoint and credentials withheld"])
                if "auth" in provider:
                    self.gap("Model-provider command-backed authentication is outside reader coverage.")
        if "notify" in data:
            notify = data["notify"]
            # The first element is the program; later arguments may be empty.
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
                    # Matchers, options and hooks.state do not stop a command: harnesses/codex.md [hooks].
                    program = program or any(
                        isinstance(h, dict) and h.get("type") == "command"
                        and isinstance(h.get("command"), str) and bool(h["command"].strip())
                        for h in group.get("hooks", []))
                self.add(["hooks", name], "automation", ["contents withheld"], {"configured_program": program})
            self.gap("Hook execution policy is outside reader coverage.")
        features = self.table(data.get("features", {}), "features")
        self.unknown(features, {"apps"}, "features")
        # Codex adds the ChatGPT Apps connection at ChatGPT sign-in unless this is false: harnesses/codex.md [apps-feature].
        if self.boolean(features, "apps", True, "features.apps"):
            self.add(["features", "apps"], "MCP server", ["ChatGPT Apps", "exists only if Codex is signed in with ChatGPT, "
                     "which is not checked", "features.apps = false turns it off"])
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
        self.entries.sort(key=lambda e: e["name"])
        return self.entries, sorted(self.gaps)


def open_input(path):
    """Open a file read-only; O_NOFOLLOW refuses a symlink as the final component."""
    return os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)


def read_file(path: Path, source: str, *, discovered=False):
    reader = Reader(source)
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
