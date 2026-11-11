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
                obs = …33826 tokens truncated…proval_policy', 'config-1:features.apps', 'config-1:sandbox_mode', 'config-1:shell_environment_policy']
RULES_GAP = 'rules-1: Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.'
RULES_IDS = ['rules-1:prefix_rule.1']


class SymlinkPolicyTests(ConfigCase):
    def setUp(self):
        super().setUp()
        self.home = self.root / 'home'
        (self.home / 'rules').mkdir(parents=True)
        self.targets = self.root / 'targets'
        self.targets.mkdir()
        (self.targets / 'config.toml').write_text(CONFIG)
        (self.targets / 'default.rules').write_text(ALLOW)

    def report(self, *args):
        output = io.StringIO()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.home)}, clear=True), redirect_stdout(output):
            status = main([*args, '--format', 'json'])
        report = json.loads(output.getvalue())
        return status, report['inspection_gaps'], sorted(e['id'] for e in report['catalog'])

    def test_symlinked_explicit_inputs_are_gaps(self):
        config = self.root / 'link.toml'
        config.symlink_to(self.targets / 'config.toml')
        rules = self.root / 'link.rules'
        rules.symlink_to(self.targets / 'default.rules')
        for option, path, gap in [('--config', config, 'config-1: Selected config file is a symlink and was not followed. Select its target file explicitly with --config.'), ('--rules', rules, RULES_GAP)]:
            with self.subTest(option=option):
                self.assertEqual(self.report(option, str(path)), (2, [gap], []))

    def test_symlinked_default_files_are_gaps(self):
        config, rules = self.home / 'config.toml', self.home / 'rules' / 'default.rules'
        for link, regular, text, gap, ids in [(config, rules, ALLOW, CONFIG_GAP, RULES_IDS),
                                              (rules, config, CONFIG, RULES_GAP, CONFIG_IDS)]:
            with self.subTest(link=link.name):
                link.unlink(missing_ok=True)
                link.symlink_to(self.targets / link.name)
                regular.unlink(missing_ok=True)
                regular.write_text(text)
                self.assertEqual(self.report(), (2, [gap], ids))

    def test_regular_explicit_and_default_files_are_still_read(self):
        read = (0, [], [*CONFIG_IDS, *RULES_IDS])
        explicit = ('--config', str(self.targets / 'config.toml'), '--rules', str(self.targets / 'default.rules'))
        self.assertEqual(self.report(*explicit), read)
        (self.home / 'config.toml').write_text(CONFIG)
        (self.home / 'rules' / 'default.rules').write_text(ALLOW)
        self.assertEqual(self.report(), read)
