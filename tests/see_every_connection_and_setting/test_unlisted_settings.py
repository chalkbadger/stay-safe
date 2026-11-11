import unittest

from stay_safe.report import inspect
from tests.support import CHATGPT_APPS, ConfigCase

# Archived issues #81, #79 and #95: settings that no rule reads are not listed and give no gap of their own,
# whatever their value. Expected results come from those issues and these harnesses/codex.md rows:
# `approval_policy` `on-request`, `sandbox_mode` (`read-only`, `workspace-write`), the
# `default_permissions` row, `sandbox_workspace_write.network_access` `true`,
# `apps.*.destructive_enabled` `omitted`, `approval_policy` `granular` and
# `shell_environment_policy` `omitted`. `network_access` shows that the rest of its table is kept.
# Entries every case gives: harnesses/codex.md rows `shell_environment_policy` and `features.apps` `omitted`.
DEFAULTS = {"shell_environment_policy": ["inherit: all (default)", "ignore_default_excludes: true (default)"],
            "features.apps": CHATGPT_APPS}
SHELL_RISK = ("environment_inheritance", "config-1:shell_environment_policy")
ON_REQUEST = 'approval_policy="on-request"\n'

SANDBOX = (ON_REQUEST + 'sandbox_mode="workspace-write"\n[sandbox_workspace_write]\nnetwork_access=true\n')
SANDBOX_CATALOG = {"approval_policy": ["on-request"], "sandbox_mode": ["workspace-write"],
                   "sandbox_workspace_write.network_access": ["true", "workspace-write option"], **DEFAULTS}
SANDBOX_RISKS = {("network_access", "config-1:sandbox_workspace_write.network_access"), SHELL_RISK}

# An enabled app with nothing else set; an `apps._default` table is enabled with the auto default.
APP = ["configured enabled", "destructive tools enabled by Codex default", "tool approval: auto (default)"]
APP_CATALOG = {"approval_policy": ["on-request"], "sandbox_mode": ["read-only"], "apps.files": APP, **DEFAULTS}
APP_RISKS = {("destructive_tools", "config-1:apps.files"), ("self_described_tools", "config-1:apps.files"), SHELL_RISK}

PROFILES = "config-1: Named permission profiles are outside reader coverage; sandbox settings are not effective-permission evidence."
UNHANDLED = "config-1: approval_policy has a known but unhandled value; its behavior is not evaluated."
CATEGORIES = ("sandbox_approval", "rules", "mcp_elicitations", "request_permissions", "skill_approval")


def catalog(report):
    return {e["name"]: e["observations"] for e in report["catalog"]}


def risks(report):
    return {(r["rule"], r["entry"]) for r in report["risks"]}


class UnlistedSettingTests(ConfigCase):
    def test_sandbox_and_app_settings_no_rule_reads_give_no_entry_risk_or_gap(self):
        cases = [(SANDBOX + f"{key}={value}\n", SANDBOX_CATALOG, SANDBOX_RISKS)
                 for key, values in (("writable_roots", ('["/var/run/docker.sock"]', '"/var/run/docker.sock"', "7", "[7]")),
                                     ("exclude_slash_tmp", ("true", "false", '"yes"')),
                                     ("exclude_tmpdir_env_var", ("true", "false", '"yes"')))
                 for value in values]
        base = ON_REQUEST + 'sandbox_mode="read-only"\n'
        app_settings = [("open_world_enabled", value) for value in ("true", "false", '"yes"')]
        app_settings += [("approvals_reviewer", value) for value in ('"user"', '"auto_review"', '"guardian_subagent"', '"human"', "7")]
        for key, value in app_settings:
            cases.append((base + f"[apps.files]\n{key}={value}\n", APP_CATALOG, APP_RISKS))
            cases.append((base + f"[apps._default]\n{key}={value}\n[apps.files]\n",
                          {**APP_CATALOG, "apps._default": ["configured enabled", "tool approval: auto (default)"]}, APP_RISKS))
        for text, expected_catalog, expected_risks in cases:
            with self.subTest(config=text):
                report = inspect([self.config(text)])
                self.assertEqual(catalog(report), expected_catalog)
                self.assertEqual(risks(report), expected_risks)
                self.assertEqual(report["inspection_gaps"], [])

    def test_default_permissions_gives_no_entry_and_keeps_its_gaps(self):
        report = inspect([self.config(ON_REQUEST + 'default_permissions="team-profile"\n')])
        self.assertEqual(catalog(report), {"approval_policy": ["on-request"], **DEFAULTS})
        self.assertEqual(risks(report), {SHELL_RISK})
        self.assertEqual(report["inspection_gaps"], [PROFILES])

    def test_granular_approval_policy_gives_no_entry_and_only_the_unhandled_gap(self):
        for name, body in [
            ("complete, all false", "".join(f"{c}=false\n" for c in CATEGORIES)),
            ("complete, all true", "".join(f"{c}=true\n" for c in CATEGORIES)),
            ("partial", "sandbox_approval=false\n"),
            ("invalid category value", "".join(f"{c}=false\n" for c in CATEGORIES[:-1]) + 'skill_approval="yes"\n'),
        ]:
            with self.subTest(granular=name):
                report = inspect([self.config('sandbox_mode="read-only"\n[approval_policy.granular]\n' + body)])
                self.assertEqual(catalog(report), {"sandbox_mode": ["read-only"], **DEFAULTS})
                self.assertEqual(risks(report), {SHELL_RISK})
                self.assertEqual(report["inspection_gaps"], [UNHANDLED])


if __name__ == "__main__":
    unittest.main()
