# Rule evidence and challenges

## saved_approval

- Settings: [Saved approval records](../harnesses/codex.md#saved-approval-records)
- Incidents: [I26](../incidents.md#i26-saved-command-approval-persisted-across-sessions-and-workspaces)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+saved_approval+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+saved_approval)

## commands_without_prompts

- Settings: [Codex meanings](../harnesses/codex.md) rows `approval_policy`
- Incidents: [I2](../incidents.md#i2-home-directory-added-to-a-delete-command), [I3](../incidents.md#i3-windows-drive-wiped), [I24](../incidents.md#i24-driver-update-followed-by-boot-and-network-failures)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+commands_without_prompts+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+commands_without_prompts)

## unrestricted_filesystem

- Settings: [Codex meanings](../harnesses/codex.md) rows `sandbox_mode`, `permissions`
- Incidents: [I1](../incidents.md#i1-home-directory-deleted-by-rm--rf), [I3](../incidents.md#i3-windows-drive-wiped)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+unrestricted_filesystem+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+unrestricted_filesystem)

## configured_program

- Settings: [Codex meanings](../harnesses/codex.md) rows `mcp_servers.*.command`, `mcp_servers.*.http_headers_helper`, `notify`, `hooks.*`, `hooks.state`
- Incidents: [I13](../incidents.md#i13-repository-settings-run-commands-on-collaborators-machines), [I14](../incidents.md#i14-readme-injection-bypassed-a-command-allowlist), [I19](../incidents.md#i19-worm-persisted-through-agent-startup-hooks)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+configured_program+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+configured_program)

## automatic_tools

- Settings: [Codex meanings](../harnesses/codex.md) rows `mcp_servers.*.default_tools_approval_mode`, `mcp_servers.*.tools.*.approval_mode`, `mcp_servers.*.tools.*.enabled`, `apps._default.enabled`, `apps._default.default_tools_enabled`, `apps.*.default_tools_approval_mode`, `apps.*.enabled_tools`, `apps.*.disabled_tools`, `apps.*.tools.*.approval_mode`, `apps.*.tools.*.enabled`
- Incidents: [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I20](../incidents.md#i20-injected-text-turned-off-approvals)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+automatic_tools+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+automatic_tools)

## destructive_tools

- Settings: [Codex meanings](../harnesses/codex.md) rows `apps._default.enabled`, `apps.*.default_tools_enabled`, `apps._default.default_tools_enabled`, `apps.*.default_tools_approval_mode`, `apps.*.enabled_tools`, `apps.*.tools.*.enabled`, `apps.*.destructive_enabled`, `apps.*.links`
- Incidents: [I7](../incidents.md#i7-production-volumes-deleted-with-a-found-token), [I8](../incidents.md#i8-database-changes-after-an-order-to-stop)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+destructive_tools+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+destructive_tools)

## network_access

- Settings: [Codex meanings](../harnesses/codex.md) rows `sandbox_workspace_write.network_access`
- Incidents: [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I21](../incidents.md#i21-issue-content-steered-an-agent-toward-workflow-secrets)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+network_access+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+network_access)

## self_described_tools

- Settings: [Codex meanings](../harnesses/codex.md) rows `mcp_servers.*.command`, `mcp_servers.*.url`, `mcp_servers.*.http_headers_helper`, `mcp_servers.*.default_tools_approval_mode`, `apps.*.default_tools_enabled`, `apps.*.destructive_enabled`, `apps.*.links`, `apps.*.default_tools_approval_mode`
- Incidents: [I15](../incidents.md#i15-prompt-injection-through-github-issues), [I21](../incidents.md#i21-issue-content-steered-an-agent-toward-workflow-secrets)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+self_described_tools+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+self_described_tools)

## environment_inheritance

- Settings: [Codex meanings](../harnesses/codex.md) rows `shell_environment_policy`, `shell_environment_policy.inherit`, `shell_environment_policy.ignore_default_excludes`
- Incidents: [I23](../incidents.md#i23-production-tables-dropped-by-a-dev-only-migration-command)
- Challenges: [challenges citing this rule](https://github.com/chalkbadger/stay-safe/issues?q=is%3Aissue+label%3Achallenge+environment_inheritance+in%3Atitle%2Cbody)
- [Challenge this rule](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml&finding=Rule+environment_inheritance)
