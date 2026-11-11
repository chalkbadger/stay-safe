from tests.support import ReportRuns
from tests.support import ConfigCase


class SnapshotTests(ReportRuns, ConfigCase):
    def test_two_files_are_separate_snapshots_without_tested_effective_permissions(self):
        lines = {"json": ["Selected files are independent snapshots; other rules files are not read or merged.",
                          "Connection reachability, authentication, active tools and effective permissions are not tested."],
                 "markdown": ["These files are read as separate snapshots, not combined: Codex may apply several of "
                              "them together, so a setting in one can change what another allows.",
                              "Whether connections work, or what Codex actually allows when it runs: stay-safe only "
                              "reads files; it doesn't start Codex or contact any service. Watch what Codex asks "
                              "before it acts."]}
        approvals = {"json": (["config-1:approval_policy"], ["config-2:approval_policy"]),
                     "markdown": (["Approval: `never` (doesn't ask before commands; remaining tool human-review requests are denied)"],
                                  ["Approval: `on-request` (Codex can ask before commands; remaining tool human-review requests require a decision)"])}
        user = self.config('approval_policy="never"\nsandbox_mode="read-only"\n', "user.toml")
        project = self.config('approval_policy="on-request"\nsandbox_mode="workspace-write"\n', "project.toml")
        for format_name in ("markdown", "json"):
            with self.subTest(format=format_name):
                run = self.run_cli("--config", str(user), "--config", str(project), "--format", format_name)
                scope, groups = self.scope_and_setup(run, format_name)
                for line in lines[format_name]:
                    self.assertIn(line, scope)
                self.assertEqual(([i for i in groups["config-1"] if "pproval" in i], [i for i in groups["config-2"] if "pproval" in i]),
                                 approvals[format_name])
