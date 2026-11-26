# Codex configuration meanings

This is the single interpretation table for the Codex reader. Setting interpretations
describe a selected configuration-file snapshot or the documented defaults assessed
under the [inspection contract](../contracts/claims.md#see_every_connection_and_setting-i-see-supported-settings-and-saved-approvals-from-my-files-with-defaults-identified). They do not
establish a session's effective policy, live access, or whether an incident will occur. CLI overrides,
selected profiles, trusted project layers, managed policies and runtime state are
uninspected. Missing approval or sandbox selectors are gaps; their defaults are not
inferred. The [tool-approval] and [shell-environment-input] sources define the
defaults below. The rules follow the selected file's policy,
not uninspected runtime layers or actual tool annotations. An open tool catalog can
retain a parent policy risk; a closed allowlist loses it when every allowed tool is
denied or has its own approval override. Without a tool override, the reader uses the
server or app default. Codex can also apply an account-specific or managed App policy
([order][app-unnamed-approval]). `apps._default` is a policy template for named apps;
[each_risk_shows_its_cause](../contracts/claims.md#each_risk_shows_its_cause-each-warning-identifies-the-setting-and-evidence-behind-it)
says which entry carries each resulting risk. An approval mode alone does not determine a live call’s outcome.
Tool overrides belong to named apps. Tool allow and deny lists (`enabled_tools`,
`disabled_tools`) apply only to MCP servers: Codex's [app settings][app-config] have neither.
Unsupported `apps._default.tools` blocks are skipped with a gap; they create no child tool
entries or risk facts.

Codex [requires typed App and tool settings][app-config]. A named App's `default_tools_enabled` and
each tool's `enabled` take unquoted booleans. The App's `default_tools_approval_mode` and each tool's
`approval_mode` take a supported approval mode. See the [inspection contract](../contracts/claims.md#see_every_connection_and_setting-i-see-supported-settings-and-saved-approvals-from-my-files-with-defaults-identified) for how the report handles a rejected value.

For a tool of an enabled app, Codex uses the first that is set: the tool's `enabled`,
the app's `default_tools_enabled`, then `destructive_enabled` from the app, then
`_default`, then `true` ([order][app-tool-policy], [tests][app-tool-policy-tests]).
When `destructive_enabled` decides and is `false`, tools marked destructive, or without a mark, are left out;
the report names where the value comes from. The rows below call this Codex's order.

`documented` means the interpretation is supported by the linked official source;
`documented in source` identifies behavior read at the cited implementation revision,
not observed in a live tool call. `documented: retired` and `documented: deprecated`
identify values the official reference retires or deprecates; both remain unhandled.
`inferred` identifies stay-safe's stated inference. `open` means the reader does not
handle that meaning. `confirmed by the maintainer` and `disputed` are available for
future review; no row currently claims either status.

The literal Catalog and Rules clauses are the expected observations and risk IDs
for the named entry in each independent fixture in
[meanings.json](../tests/see_every_connection_and_setting/meanings.json). `none` means no entry or no risk,
respectively. Gap says whether that fixture needs an inspection gap. The
[table test](../tests/see_every_connection_and_setting/test_meanings.py) compares the reader's result to these
authored expectations; it does not derive expectations from the reader or its rules.
Additional positive and negative cases live under
[each_risk_shows_its_cause](../tests/each_risk_shows_its_cause/test_conditions.py).

Unless a row or section names another release,
Codex source links are pinned to OpenAI Codex `rust-v0.172.0`
(`3d86e43b075adeba2193ec5c22ac92f55afd82e6`). On 2026-11-25 we rechecked the cited
passages for the meanings below. The [release scan](https://github.com/chalkbadger/stay-safe/pull/131#issuecomment-7176657473)
lists new and changed configuration fields. The [0.172.0 field review](../docs/codex-0.172.0-fields.md)
explains how the report handles each change since 0.171.0.
The configuration reference was read on 2026-11-02 for retired values.
The `auto` default is defined by [AppToolApproval][tool-default].

| Setting | Value | Meaning stay-safe uses | Source | Status |
| --- | --- | --- | --- | --- |
| `approval_policy` | `never` | Permitted commands do not ask for approval; the sandbox remains separate. Catalog: `never`. Rules: `commands_without_prompts`. Gap: no. | [approval] | documented |
| `approval_policy` | `on-request` | The model decides when to request approval; this is not blanket preapproval. In a restricted sandbox, a command that no execution rule matches runs inside the sandbox without asking unless Codex flags it as dangerous, which `never` refuses and `on-request` can ask about ([fallback][restricted-commands]); a matching rule can still require a prompt, even for an ordinary command ([rules][rule-prompts]). Catalog: `on-request`. Rules: none. Gap: no. | [approval] | documented |
| `approval_policy` | `on-request with danger-full-access` | With no sandbox, a command that no execution rule matches runs without asking unless Codex flags it as dangerous ([decision][full-access-commands]); the flag covers forced deletes ([flag][dangerous-commands]). A matching rule can still ask; the reader does not read rules for this row. Catalog: `on-request`, `with danger-full-access, ordinary commands can run without asking`. Rules: `commands_without_prompts`. Gap: no. | [full-access-commands] | documented in source |
| `approval_policy` | `never with danger-full-access` | With `never`, Codex can skip an MCP or App tool prompt even when the tool requests one. This path requires strict automatic review to be off and uses the server’s effective permission profile ([approval][full-access-tools], [call][full-access-tool-call]). The reader flags the configured combination when an enabled MCP server or the ChatGPT Apps connection is present. Catalog: `never`, `with danger-full-access, MCP and app tool calls can run without asking`. Rules: `commands_without_prompts`, `automatic_tools`. Gap: no. | [full-access-tools] | documented in source |
| `approval_policy` | `untrusted` | The configuration reference retires this unsupported value; the reader leaves it unhandled. Catalog: none. Rules: none. Gap: yes. | [configuration-reference] | documented: retired |
| `approval_policy` | `on-failure` | The configuration reference deprecates this spelling. Codex parses it as `on-request` ([alias][approval-alias]) and the reader leaves it unhandled. Catalog: none. Rules: none. Gap: yes. | [configuration-reference] | documented: deprecated |
| `approval_policy` | `granular` | A disabled category rejects requests in that category. Turning off sandbox-escalation prompts still permits certain dangerous commands to request approval within existing permissions ([decision][rule-prompts]). The reader leaves this policy unhandled. Catalog: none. Rules: none. Gap: yes. | [approval-granular] | open |
| `sandbox_mode` | `read-only` | The configured legacy sandbox is read-only. Catalog: `read-only`. Rules: none. Gap: no. | [sandbox] | documented |
| `sandbox_mode` | `workspace-write` | The configured legacy sandbox permits workspace writes. Catalog: `workspace-write`. Rules: none. Gap: no. | [sandbox] | documented |
| `sandbox_mode` | `danger-full-access` | The configured legacy policy [removes sandbox restrictions][unrestricted-policy]. `workspace-write` [protects the project’s top-level `.codex` directory by default][project-metadata-protection], even before it exists. `danger-full-access` removes that sandbox protection. Catalog: `danger-full-access`. Rules: `unrestricted_filesystem`. Gap: no. | [full-access-selection] | documented in source |
| `profile` | `top-level string` | Codex 0.172.0 rejects the old selector in the effective configuration. Its project loader [lists both legacy keys][project-profile-keys] and [removes them][project-profile-filter]. Stay-safe explains how to move the profile settings to a separate file. A selector alongside profile definitions produces one profile message. Codex 0.100.0 [selected an inline profile][historical-inline-selector] and could [use its sandbox setting ahead of the top-level setting][historical-inline-sandbox]. Catalog: none. Rules: none. Gap: yes. | [old-config-selector] | documented in source |
| `profiles.*` | `named tables without a selector` | In Codex 0.172.0 a matching `--profile` name conflicts with a table in the base user config. An [unrelated table can coexist with the selected file][unrelated-config-profile]. Stay-safe reports the condition without reading the startup flag or applying profile values. Catalog: none. Rules: none. Gap: yes. | [config-profile-loader] | documented in source |
| `default_permissions` | `selected with sandbox_mode` | Named-profile selection is unhandled and conflicts with the legacy selector; legacy risk facts are suppressed. Catalog: `danger-full-access`, `permission-profile selection is uninspected`. Rules: none. Gap: yes. | [schema] | open |
| `permissions` | `definitions without selection` | Unselected profile definitions remain unhandled without erasing the explicit legacy sandbox setting. Catalog: `danger-full-access`. Rules: `unrestricted_filesystem`. Gap: yes. | [schema] | open |
| `sandbox_workspace_write.network_access` | `true` | This workspace-write option controls outbound network access. Catalog: `true`, `workspace-write option`. Rules: `network_access`. Gap: no. | [sandbox] | documented |
| `sandbox_workspace_write.network_access` | `false` | This workspace-write option controls outbound network access. Catalog: `false`, `workspace-write option`. Rules: none. Gap: no. | [sandbox] | documented |
| `sandbox_workspace_write.*` | `under read-only` | Workspace-write options are not selected by read-only mode. Catalog: `true`, `inactive or selection unknown`. Rules: none. Gap: no. | [schema] | documented |
| `sandbox_workspace_write.writable_roots` | `paths under workspace-write` | Codex adds the listed folders to its workspace roots. Without a selected workspace the reader withholds the paths and leaves their effect unchecked. Catalog: none. Rules: none. Gap: yes. | [writable-roots] | documented in source |
| `sandbox_workspace_write.writable_roots` | `direct grant to project .codex` | Legacy workspace-write [passes the roots to its permission profile][legacy-profile]. Codex reads [typed root paths][roots-type] in their [configuration layer][roots-layer], [expands `~` and `~/` against the user's home][roots-home], and [folds `..` lexically][roots-parents]. The writable workspace alone protects its top-level `.codex`; a direct write grant to that directory permits writes to its project configuration. Codex [distinguishes this project layer from user Codex home and checks project trust][project-layer]. An [explicitly selected built-in :workspace ignores the legacy list][explicit-workspace]. Catalog: `selected workspace's .codex directory explicitly listed`. Rules: `writable_project_settings`. Gap: yes. | [project-settings-write] | documented in source |
| `mcp_servers.*.enabled` | `false` | A disabled server supplies no enabled program or tool condition. Catalog: `disabled`, `stdio; command withheld`, `tool approval: auto (default)`. Rules: none. Gap: no. | [mcp] | documented |
| `mcp_servers.*.command` | `nonempty command, no url` | An enabled stdio server starts a configured command; contents are withheld. Catalog: `configured enabled`, `stdio; command withheld`, `tool approval: auto (default)`. Rules: `configured_program`, `self_described_tools`. Gap: no. | [mcp] | documented |
| `mcp_servers.*.url` | `string, no command` | Codex uses HTTP for any string `url` without `command` ([field][mcp-url], [transport][mcp-transport]); the reader does not check its form, and the endpoint is not evidence of reachability or authentication. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto (default)`. Rules: `self_described_tools`. Gap: no. | [mcp-transport] | documented in source |
| `mcp_servers.*.env` | `nonempty stdio table` | Codex passes literal environment values to the command. Check the values locally for credentials. Catalog: none. Rules: none. Gap: yes. | [mcp-inline-fields] | documented in source |
| `mcp_servers.*.http_headers` | `nonempty HTTP table` | Codex takes literal HTTP header values from the table. Check the values locally for credentials. Catalog: none. Rules: none. Gap: yes. | [mcp-inline-fields] | documented in source |
| `mcp_servers.*.env_vars` | `stdio references` | Codex looks up values for the referenced variables. Catalog: none. Rules: none. Gap: no. | [mcp-inline-fields] | documented in source |
| `mcp_servers.*.env_http_headers` | `HTTP references` | Codex looks up header values by environment variable name. Catalog: none. Rules: none. Gap: no. | [mcp-inline-fields] | documented in source |
| `mcp_servers.*.bearer_token_env_var` | `HTTP reference` | Codex looks up the bearer token by environment variable name. Catalog: none. Rules: none. Gap: no. | [mcp-inline-fields] | documented in source |
| `mcp_servers.*.http_headers_helper` | `nonempty command` | An HTTP header helper is a configured program; contents are withheld. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto (default)`. Rules: `configured_program`, `self_described_tools`. Gap: no. | [mcp] | documented |
| `mcp_servers.*.http_headers_helper` | `on a stdio server` | Codex rejects the configuration when a stdio server sets this field. Catalog: `configured enabled`, `Codex rejects this stdio configuration`, `tool approval: auto (default)`. Rules: none. Gap: yes. | [mcp-transport] | documented in source |
| `mcp_servers.*.enabled_tools` | `named allowlist` | Only listed names are allowed by this file, before the denylist; an empty list allows none ([allowlist][mcp-allowlist]); the list does not establish live availability. Catalog: `configured names: read, files/write`. Rules: none. Gap: no. | [mcp] | documented |
| `mcp_servers.*.disabled_tools` | `named denylist` | Listed names are removed after applying the allowlist. Catalog: `configured names: delete`. Rules: none. Gap: no. | [mcp] | documented |
| `mcp_servers.*.default_tools_approval_mode` | `approve` | Preapproval mode. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: approve`. Rules: `automatic_tools`. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.default_tools_approval_mode` | `auto` | Uses server-declared hints in the [order for the checked version](#tool-approval-by-version). Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto`. Rules: `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.default_tools_approval_mode` | `prompt` | Requests approval. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: prompt`. Rules: none. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.default_tools_approval_mode` | `writes` | Uses the server’s read-only hint for tool approval. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: writes`. Rules: `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.tools.*.approval_mode` | `approve` | A named tool override replaces the server default when the tool is permitted by its filters. Catalog: `configured enabled`, `tool approval: approve`. Rules: `automatic_tools`. Gap: no. | [mcp] | documented |
| `mcp_servers.*.tools.*.enabled` | `false` | This app-style field is unsupported for MCP tools and does not disable the configured tool. Catalog: `configured enabled`, `tool approval: approve`. Rules: `automatic_tools`. Gap: yes. | [schema] | open |
| `apps._default.default_tools_approval_mode` | `approve` | An app the file does not name takes this mode ([approval][app-unnamed-approval]) while `apps._default.enabled` is not `false` ([enabled][app-enabled]), so the template carries the risk once. Catalog: `configured enabled`, `applies to apps not named in this file`, `tool approval: approve`. Rules: `automatic_tools`. Gap: no. | [app-unnamed-approval] | documented in source |
| `apps._default.destructive_enabled` | `true` | An app the file does not name takes this value when its tools have no `enabled` of their own ([order][app-tool-policy]), so the template carries the risk once. Without the field Codex also uses `true` ([default][app-default-destructive]); that gives no finding. Catalog: `configured enabled`, `applies to apps not named in this file`, `destructive tools enabled by apps._default.destructive_enabled`, `tool approval: auto (default)`. Rules: `destructive_tools`. Gap: no. | [app-tool-policy] | documented in source |
| `apps._default.enabled` | `false, named app without enabled` | Disables no named app: a named app's enablement comes from its own `enabled`, which defaults to `true` ([field][app-enabled-field]), so an app without it stays enabled, as a [recorded Codex 0.167.0 run][app-enabled-run] shows. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: approve`. Rules: `automatic_tools`, `destructive_tools`. Gap: no. | [app-enabled] | documented in source |
| `apps.*.enabled` | `false` | An explicitly disabled app supplies no enabled tool conditions. Catalog: `disabled`, `tool approval: approve`. Rules: none. Gap: no. | [apps] | documented |
| `apps.*.default_tools_enabled` | `false` | Codex follows [the order above](#codex-configuration-meanings). This value disables the app's tools without their own `enabled`, whatever `destructive_enabled` says. Catalog: `configured enabled`, `default tools disabled or unknown`, `tool approval: approve`. Rules: none. Gap: no. | [app-tool-policy] | documented in source |
| `apps.*.default_tools_enabled` | `true` | Codex follows [the order above](#codex-configuration-meanings). This value enables the app's tools without their own `enabled`, destructive or not, whatever `destructive_enabled` says. Catalog: `configured enabled`, `destructive tools enabled by default_tools_enabled`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [app-tool-policy] | documented in source |
| `apps._default.default_tools_enabled` | `false` | The global default schema has no such field; the reader reports it without inventing inheritance. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: approve`. Rules: `automatic_tools`, `destructive_tools`. Gap: yes. | [schema] | open |
| `apps.*.default_tools_approval_mode` | `approve inherited from _default` | An app inherits its default tool approval mode unless it overrides it. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: approve`. Rules: `automatic_tools`, `destructive_tools`. Gap: no. | [apps] | documented |
| `apps.*.enabled_tools` | `on an app` | Codex's app settings have no tool allowlist; the list is a gap and the app keeps its findings. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: approve`. Rules: `automatic_tools`, `destructive_tools`. Gap: yes. | [app-config] | open |
| `apps.*.disabled_tools` | `on an app` | Codex's app settings have no tool denylist; the list is a gap and a listed tool keeps its findings. Catalog: `configured enabled`, `tool approval: approve`. Rules: `automatic_tools`. Gap: yes. | [app-config] | open |
| `apps.*.tools.*.approval_mode` | `approve` | A named app tool override replaces its app default. Catalog: `configured enabled`, `tool approval: approve`. Rules: `automatic_tools`. Gap: no. | [apps] | documented |
| `apps.*.tools.*.enabled` | `false` | A disabled app tool supplies no preapproved-tool condition. Catalog: `disabled or enablement unknown`, `tool approval: approve`. Rules: none. Gap: no. | [apps] | documented |
| `apps.*.tools.*.enabled` | `true overrides default_tools_enabled` | A tool's own `enabled` comes first in [Codex's order](#codex-configuration-meanings), so this value enables the tool even if it is destructive. Catalog: `configured enabled`, `enabled even if destructive`, `tool approval: approve`. Rules: `automatic_tools`, `destructive_tools`. Gap: no. | [app-tool-policy] | documented in source |
| `apps.*.destructive_enabled` | `omitted` | Codex follows [the order above](#codex-configuration-meanings). An `_default` table without this field also gives `true` ([default][app-default-destructive]). Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [app-tool-policy] | documented in source |
| `apps.*.destructive_enabled` | `true inherited from _default` | Codex follows [the order above](#codex-configuration-meanings). Catalog: `configured enabled`, `destructive tools enabled by apps._default.destructive_enabled`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [app-tool-policy] | documented in source |
| `apps.*.destructive_enabled` | `false inherited from _default` | Codex follows [the order above](#codex-configuration-meanings). Catalog: `configured enabled`, `destructive tools disabled by apps._default.destructive_enabled`, `tool approval: auto (default)`. Rules: `self_described_tools`. Gap: no. | [app-tool-policy] | documented in source |
| `apps.*` | `non-boolean open_world_enabled or destructive_enabled on a named App or _default` | A malformed `open_world_enabled` or `destructive_enabled` on a named App or its [default template][app-default-destructive] prevents Codex from loading the file. Other entries describe settings written in that file. Catalog: `Codex cannot load this configuration file`, `tool approval: auto (default)`. Rules: none. Gap: yes. | [app-config] | documented in source |
| `apps.*.links` | `per-account policy` | Account-specific policy is outside reader coverage and account identities are withheld. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: yes. | [apps] | open |
| `apps.*.approvals_reviewer` | `per-app reviewer` | In [0.171.0][app-reviewer-0-171], Codex checked the linked account, the app and then `apps._default` for an Apps approval prompt. In 0.172.0 it checks the matching tool’s reviewer first, using the [raw tool name before its title][app-tool-match], then follows the same order. Model and managed requirements can constrain the choice. `user` routes to the user and `auto_review` (alias `guardian_subagent`) routes to automatic review ([values][reviewer-values], [routing][reviewer-routing]). An app or Apps default set to automatic review gets the named gap. Linked-account reviewer settings remain unchecked. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: yes. | [app-reviewer] | documented in source |
| `apps.*.tools.*.approvals_reviewer` | `auto_review or guardian_subagent` | Codex 0.172.0 added the [tool reviewer setting][app-tool-reviewer-field]. In [0.171.0][app-reviewer-0-171], reviewer selection started with the linked account. Either value requests AI review when the tool needs approval. A policy can require AI review for the selected model. Otherwise, Codex accepts the configured reviewer only if it is [allowed by policy][allowed-reviewers]. The report names the setting under “Not checked” because it cannot establish the effective reviewer. Catalog: `configured enabled`, `tool approval: auto`. Rules: none. Gap: yes. | [app-reviewer] | documented in source |
| `apps.*.tools.*.approvals_reviewer` | `user` | From 0.172.0, this requests human review for the tool. The reader recognizes the setting and adds no reviewer gap. A model-specific policy can still require AI review. Catalog: `configured enabled`, `tool approval: auto`. Rules: none. Gap: no. | [app-reviewer] | documented in source |
| `model_providers.*` | `definition` | The provider name is catalogued; endpoints and credentials are withheld and no provider selection is inferred. See the rows below for credential commands. Catalog: `configured; endpoint and credentials withheld`. Rules: none. Gap: no. | [schema] | documented |
| `model_providers.*.auth` | `command-backed authentication` | Command-backed provider authentication is outside reader coverage. This row covers the provider’s `auth` command. Catalog: `configured; endpoint and credentials withheld`. Rules: none. Gap: yes. | [schema] | open |
| `model_providers.*.aws` | `credential commands` | Each `credential_export` or `auth_refresh` setting present is named as unchecked, whether or not the file selects the provider. Catalog: `configured; endpoint and credentials withheld`. Rules: none. Gap: yes. | [provider-auth] | documented in source |
| `model_providers.*.gateway_oauth.credential_export` | `present` | Added in Codex 0.169.0 and checked at 0.172.0. Stay-safe lists the setting under "Not checked" whenever it is present, even with a malformed value. It does not work out whether this provider is selected. Catalog: `configured; endpoint and credentials withheld`. Rules: none. Gap: yes. | [gateway-export] | documented in source |
| `otel.headers_helper` | `present` | Added in Codex 0.170.0 and checked at 0.172.0. Stay-safe lists the helper under "Not checked" whenever it is present, even with a malformed value. It does not check [whether the exporter is active][otel-helper-start] or read the rest of `[otel]`. Catalog: none. Rules: none. Gap: yes. | [otel-helper] | documented in source |
| `notify` | `command list with nonempty program` | Notifications may spawn a configured external command; its contents are withheld. Catalog: `notification command configured; command withheld`. Rules: `configured_program`. Gap: no. | [notify-program] | documented in source |
| `hooks.*` | `command handler with nonempty command` | Codex runs a `type = "command"` handler whose command is not empty, in each matcher group of each [event][hook-events] whose matcher is a valid pattern ([groups][hook-groups]), whatever events the [matcher][hook-matcher] selects and whatever its [options][hook-handlers] such as `timeout`; the reader does not check matcher patterns, and trust and enablement in `hooks.state` are uninspected. Catalog: `contents withheld`. Rules: `configured_program`. Gap: yes. | [hooks] | documented in source |
| `hooks.*` | `command handler with empty command and nonempty Windows command` | On Windows, Codex runs the handler's `commandWindows` (alias `command_windows`) in place of `command` when it is set ([field][hook-command-windows], [choice][hook-windows-choice]); on other platforms it skips the empty `command`. The file may be used on either platform, so the handler counts. Catalog: `contents withheld`. Rules: `configured_program`. Gap: yes. | [hooks] | documented in source |
| `hooks.*` | `no command handler with nonempty command` | Codex skips `prompt` and `agent` handlers ([source][hook-skipped]) and empty commands ([source][hook-empty]); an `mcp_tool` handler calls a tool on an MCP server ([source][hook-mcp-tool]). Catalog: `contents withheld`. Rules: none. Gap: yes. | [hooks] | documented in source |
| `hooks.state` | `trusts, distrusts or disables a hook` | Codex runs a hook from the user's `config.toml` only when this state enables and trusts it ([gate][hook-trust], [trust check][hook-trust-check], [state source][hook-state]); the reader does not inspect it, so a command handler keeps its risk. Catalog: `contents withheld`. Rules: `configured_program`. Gap: yes. | [hooks] | documented in source |
| `web_search` | `disabled` | The reader records this recognized configured mode without inferring live network availability. Catalog: `disabled`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `cached` | The reader records this recognized configured mode without inferring live network availability. Catalog: `cached`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `indexed` | The reader records this recognized configured mode without inferring live network availability. Catalog: `indexed`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `live` | The reader records this recognized configured mode without inferring live network availability. Catalog: `live`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `unrecognized string` | An unrecognized mode is withheld and produces a coverage gap. Catalog: none. Rules: none. Gap: yes. | [schema] | open |
| `mcp_servers.*.default_tools_approval_mode` | `omitted` | The documented [auto default](#tool-approval-by-version) applies to an enabled server when no tool override replaces it. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto (default)`. Rules: `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `apps.*.default_tools_approval_mode` | `omitted without _default mode` | The documented [auto default](#tool-approval-by-version) applies to a named enabled app when no managed, tool, linked-account or app mode replaces it. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `apps.*.default_tools_approval_mode` | `writes inherited from _default` | The named app inherits the writes policy from its default; the hint-dependent meaning is defined in the mode rows above. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: writes`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [apps] | documented |
| `shell_environment_policy` | `omitted` | Catalog: `inherit: all (default)`, `ignore_default_excludes: true (default)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment-input] | documented in source |
| `shell_environment_policy.inherit` | `all` | Codex still withholds its own non-inheritable launch variables ([list][shell-launch], [use][shell-launch-use]). Catalog: `inherit: all (explicit)`, `ignore_default_excludes: true (default)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.inherit` | `core` | Core variables on Unix include `HOME` and `PATH` ([core][shell-core]), and Codex adds `set` entries after `inherit` ([set][shell-set]). Catalog: `inherit: core (explicit)`, `ignore_default_excludes: true (default)`. Rules: none. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.inherit` | `none` | Catalog: `inherit: none (explicit)`, `ignore_default_excludes: true (default)`. Rules: none. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.ignore_default_excludes` | `true` | Catalog: `inherit: all (default)`, `ignore_default_excludes: true (explicit)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.ignore_default_excludes` | `false` | Catalog: `inherit: all (default)`, `ignore_default_excludes: false (explicit)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy` | `additional fields` | Catalog: none. Rules: none. Gap: yes. | [shell-environment] | open |
| `features.apps` | `omitted` | Codex's apps feature is on by default ([default][apps-feature]). A non-isolated session can add the implicit `codex_apps` connection. Host-owned Apps also requires a suitable ChatGPT sign-in ([connection][apps-connection], [sign-in][apps-sign-in]). The reader checks neither session isolation nor sign-in. An app the file does not name takes `apps._default`, then Codex's defaults ([enabled][app-enabled], [order][app-tool-policy]), so this entry says whether such apps are off and where their `destructive_enabled` comes from; Codex's own default gives no finding. A missing value takes Codex's default; an invalid `apps`, `apps._default` or `enabled` makes the entry say `settings unknown`, as does an invalid `open_world_enabled` on an enabled template. An invalid `destructive_enabled` says `destructive tools unknown`. Catalog: `ChatGPT Apps`, `exists only if Codex is signed in with ChatGPT, which is not checked`, `features.apps = false turns it off`, `apps not named in this file: destructive tools enabled by Codex default`. Rules: none. Gap: no. | [apps-feature] | documented in source |
| `features.apps` | `false` | Reported apps and tools show as off and produce no findings, unless the legacy `connectors` flag can turn Apps back on ([alias][apps-alias], [application order][apps-feature-order]). Catalog: `disabled by features.apps = false`, `tool approval: auto (default)`. Rules: none. Gap: no. | [apps-connection] | documented in source |

## Tool approval by version

In `auto` mode, a tool can describe itself as both read-only and destructive.
Codex changed how it handles that conflict in 0.169.0. Earlier checked versions
gave priority to the destructive hint and required approval at this step. From
0.169.0 through 0.172.0, the read-only hint takes priority and this step can
allow the call without asking. Strict auto review disables that exemption.
Permission policy and saved approvals also affect whether the user is asked.

| Checked stable releases | Hint used when both are true | Codex source |
| --- | --- | --- |
| 0.167.0–0.168.0 | Destructive (`destructiveHint`) | [0.167.0][tool-approval-0-167], [0.168.0][tool-approval-0-168] |
| 0.169.0–0.172.0 | Read-only (`readOnlyHint`) | [0.169.0][tool-approval-0-169], [0.172.0][tool-approval] |

For MCP and App tools, both `auto` and `writes` use hints supplied by the server.
When a tool omits the read-only hint or sets it to `false`, `auto` requires approval
at this step unless both the destructive and open-world hints are explicitly `false`.
The `writes` check requires approval unless the read-only hint is `true`.

The source review through 2026-11-25 covered this check and the code that uses it
at every stable release in the table ([first release][tool-approval-caller-0-167],
[last release][tool-approval-caller-0-172]). Stay-safe does not detect the
installed Codex version. Actual tool calls were outside this review.

## Saved approval records

The [Codex writer][saved-writer] appends records such as
`prefix_rule(pattern=["curl"], decision="allow")` to the
[default rules file][saved-runtime]. This reader covers that one-line layout,
with a nonempty JSON string array and an explicit `allow` decision. Other
layouts and `network_rule` records remain outside coverage, as do `prompt` and
`forbidden` records, whose stricter decision could override a listed `allow`.
It inventories matching lines, not the structure of a Starlark program. A record covers every command whose
first words equal its pattern ([matching][saved-match]), so a pattern with more words covers
fewer commands.

A record's words are withheld, except an exact first-word match from this fixed
list, shown as `program: <name>`:

`git gh npm npx pnpm yarn node python python3 pip pip3 uv cargo go make docker kubectl curl wget ssh bash sh rm mv cp chmod`

The list changes only by pull request. A one-word pattern is marked broad because
it puts no limits on later arguments. This is stay-safe's inference, not a Codex score.
Unreadable files and unsupported records leave the inspection incomplete;
supported records remain listed. The [inspection contract](../contracts/claims.md#see_every_connection_and_setting-i-see-supported-settings-and-saved-approvals-from-my-files-with-defaults-identified)
and [privacy contract](../contracts/claims.md#share_without_exposing_secrets-my-report-withholds-commands-addresses-tokens-and-environment-values-names-need-checking-before-sharing)
state the user promises.
[Decision ordering][saved-decisions], [matching precedence][saved-precedence]
and [runtime sandbox handling][saved-runtime] establish the declared meaning.

## Files in the Codex home and system folder

A run with no file arguments finds the Codex home as Codex does ([home][codex-home]): `$CODEX_HOME`, or
`~/.codex` when it is unset or empty. A set `CODEX_HOME` must be an existing folder, or Codex refuses to start.
Codex also reads the files below, there and in its system folder `/etc/codex`. Apart from the default rules
file (see [Saved approval records](#saved-approval-records)), the reader does not read their contents; each one
it finds is an inspection gap.

- `hooks.json`: Codex loads hooks from `hooks.json` in each layer's config folder ([load][hooks-json],
  [folder][config-folder]): the folder holding the Codex home's `config.toml` for the User layer, and
  `/etc/codex` for the System layer. The User layer is added even without a `config.toml`
  ([missing file][user-layer-missing], [layer][user-layer]). Codex loads the file only when Rust's
  `Path::is_file` is true ([check][hooks-json-is-file]), which follows links and is true only for a regular
  file ([Rust 1.99.1][rust-is-file], [toolchain][rust-toolchain]).
- `rules/`: Codex looks for `rules` in each layer's config folder ([folders][policy-files]) and loads every
  regular file whose extension is exactly `rules`. A missing folder gives none; any other listing error
  fails ([collect][collect-policy-files]).
- `plugins/cache`: the plugin cache ([cache][plugin-cache], [store][plugin-store]). A plugin installs to
  `<marketplace>/<plugin>/<version>` ([install][plugin-install]); its active version is a folder inside
  `<marketplace>/<plugin>`, and with none no plugin loads ([active][plugin-active]).
- `skills`: Codex loads skills from `skills` in the Codex home ([roots][skills-root]). A skill is a file named
  exactly `SKILL.md` anywhere in the search ([name][skill-name], [discovery][skill-discovery],
  [recursive][skill-recursive]). The search starts at `skills` (depth 0) and enters folders below depth 6
  ([depth][skill-depth], [walk][skill-walk], [listing][skill-listing]), so `SKILL.md` six folders down is
  found and seven down is not. It follows folder links ([links][skill-links]), skips file links
  ([file links][skill-file-links]) and hidden folders ([hidden][skill-hidden]), among them `skills/.system`,
  where Codex writes its bundled skills ([bundled][skill-system], [startup][skill-system-startup]). A `skills`
  path that is not a folder, or is missing, holds no skills ([not a folder][skill-not-folder],
  [missing][skill-missing]). A skill can name an MCP server that Codex installs and starts
  ([dependencies][skill-mcp]).
- `environments.toml`: Codex reads it from the Codex home ([path][environments-path],
  [load][environments-load]), and an entry can name a `program` with `args` that Codex runs
  ([program][environments-program]). Codex reads it with `read_to_string`: a missing file or broken link is
  skipped, and any other failure is an error, so a folder by that name is an error ([read][environments-read]).
- `/etc/codex`: the System layer reads `config.toml` ([config][system-config]), `managed_config.toml`
  ([managed][system-managed]) and `requirements.toml` ([requirements][system-requirements]) there, and
  `hooks.json` and `rules/` as above.

## Facts behind the advice

The report's advice rests on these:

- Codex writes each hook matcher group's handlers as `[[hooks.<Event>.hooks]]` sections
  ([group][hook-group], [written layout][hook-group-written]). Deleting only the `[[hooks.<Event>]]` lines
  leaves those sections, and Codex 0.167.0 refused to load the result.
- A `notify` list can continue over several lines. Codex 0.167.0 refused a file with only its first line
  deleted.
- A stdio MCP server runs `command` with `args` ([command][mcp-command]), so with a launcher or interpreter
  what runs is in `args`; `http_headers_helper` is a program too ([helper][mcp-headers-helper]).
- `codex --help` (0.167.0) lists `-a, --ask-for-approval`, `-s, --sandbox`, `-p, --profile` and
  `-c, --config`, which override a file.
- A later layer's `sandbox_mode` replaces a permission profile, and with `default_permissions` the profile, not
  `sandbox_mode`, decides what commands can write ([profile][sandbox-profile]).
- With a sandbox, each tool's approval mode applies again, and `never` refuses a call that needs approval
  ([never][never-refuses]).

The two refusals were observed with Codex 0.167.0 when the advice was reviewed, and are recorded here as
observations, not source readings. The environment Check lists variable names with awk's `ENVIRON`:
`env | cut -d= -f1` would print each line of a multi-line value that has no `=`.

[saved-writer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/execpolicy/src/amend.rs
[saved-runtime]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/exec_policy.rs
[saved-match]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/execpolicy/src/rule.rs#L55-L72
[saved-precedence]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/execpolicy/src/policy.rs#L584-L595
[saved-decisions]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/execpolicy/src/decision.rs

[project-profile-keys]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L92-L105
[project-profile-filter]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L1351-L1367
[old-config-selector]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/config/mod.rs#L3664-L3671
[historical-inline-selector]: https://github.com/openai/codex/blob/8272f9a71ee7364d8de992418103628f8a17eb6f/codex-rs/core/src/config/mod.rs#L1432-L1448
[historical-inline-sandbox]: https://github.com/openai/codex/blob/8272f9a71ee7364d8de992418103628f8a17eb6f/codex-rs/core/src/config/mod.rs#L1158-L1172
[config-profile-loader]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L295-L343
[unrelated-config-profile]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/tests.rs#L1030-L1064
[schema]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/config.schema.json
[approval]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/protocol.rs
[approval-alias]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/protocol.rs#L1204-L1215
[approval-granular]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/protocol.rs#L1217-L1227
[sandbox]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/protocol.rs
[mcp]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs
[tool-approval]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/mcp_tool_call.rs#L2893-L2920
[tool-approval-0-168]: https://github.com/openai/codex/blob/9480ec100c3edee9fc69172e8e80a4730444094d/codex-rs/core/src/mcp_tool_call.rs#L2744-L2775
[tool-approval-0-169]: https://github.com/openai/codex/blob/d32063f96c2dff1dc96af839b3952abb6acfeda4/codex-rs/core/src/mcp_tool_call.rs#L2757-L2784
[tool-approval-0-167]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/src/mcp_tool_call.rs#L2595-L2626
[tool-approval-caller-0-167]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/src/mcp_tool_call.rs#L1564-L1610
[tool-approval-caller-0-172]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/mcp_tool_call.rs#L1731-L1778
[apps]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs
[provider-auth]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/model-provider-info/src/lib.rs#L241-L253
[gateway-export]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/model-provider-info/src/gateway_oauth.rs#L31-L45
[otel-helper]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L650-L658
[otel-helper-start]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/otel/src/provider.rs#L202-L252
[app-tool-reviewer-field]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L491-L506
[allowed-reviewers]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/config_requirements.rs#L2425-L2447
[app-tool-match]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L517-L524
[app-reviewer-0-171]: https://github.com/openai/codex/blob/ccf9be8cc458bd6b8336fe84d68d8893f2691a5e/codex-rs/core/src/connectors.rs#L523-L535
[app-reviewer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/connectors.rs#L511-L561
[reviewer-values]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/config_types.rs#L183-L190
[reviewer-routing]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/guardian-reviewer/src/routing.rs#L59-L67
[app-tool-policy]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/connectors/src/app_tool_policy.rs#L274-L300
[app-config]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L548-L590
[app-default-destructive]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L472-L477
[app-enabled]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/connectors/src/app_tool_policy.rs#L174-L185
[app-unnamed-approval]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/connectors/src/app_tool_policy.rs#L249-L265
[app-enabled-field]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L551-L554
[apps-alias]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/features/src/legacy.rs#L11-L15
[apps-feature-order]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/features/src/lib.rs#L751-L852
[apps-feature]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/features/src/lib.rs#L1783-L1788
[apps-connection]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/mcp.rs#L503-L525
[apps-sign-in]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/codex-mcp/src/mcp/mod.rs#L404-L406
[app-enabled-run]: https://github.com/chalkbadger/stay-safe-archive/issues/90#issuecomment-6726050010
[app-tool-policy-tests]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/connectors/src/app_tool_policy_tests.rs#L687-L773
[roots-type]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/types.rs#L1324-L1330
[roots-layer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L1661-L1698
[roots-home]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/utils/absolute-path/src/lib.rs#L27-L56
[roots-parents]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/utils/absolute-path/src/absolutize.rs#L22-L44
[legacy-profile]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/permission_config.rs#L80-L103
[project-metadata-protection]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/permissions.rs#L2422-L2429
[full-access-selection]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/permissions.rs#L2096-L2102
[unrestricted-policy]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/permissions.rs#L630-L636
[project-settings-write]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/permissions_tests.rs#L774-L861
[project-layer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L1909-L1939
[explicit-workspace]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/config/config_tests.rs#L3750-L3790
[writable-roots]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/config/mod.rs#L3918-L3939
[restricted-commands]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/exec_policy.rs#L897-L936
[rule-prompts]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/exec_policy.rs#L436-L494
[full-access-commands]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/exec_policy.rs#L897-L925
[dangerous-commands]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/shell-command/src/command_safety/is_dangerous_command.rs#L132-L160
[full-access-tools]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/codex-mcp/src/mcp/mod.rs#L96-L115
[full-access-tool-call]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/mcp_tool_call.rs#L1747-L1758
[hooks]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs
[mcp-url]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs#L413
[mcp-inline-fields]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs#L395-L417
[mcp-transport]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs#L518-L572
[hook-matcher]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/matcher.rs#L32-L40
[hook-handlers]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/hooks.rs#L140-L188
[hook-skipped]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L792-L811
[hook-empty]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L674-L680
[hook-command-windows]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/hooks.rs#L150-L155
[hook-windows-choice]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L669-L680
[hook-mcp-tool]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L738-L790
[hook-trust]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L928-L934
[hook-trust-check]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L1011-L1038
[hook-state]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/config_rules.rs#L15-L45
[notify-program]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/registry.rs#L412-L426
[configuration-reference]: https://learn.chatgpt.com/docs/config-file/config-reference
[tool-default]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs#L26-L34
[shell-environment]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/config_types.rs#L205-L272
[shell-environment-input]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/shell_environment_policy.rs#L133-L169
[mcp-allowlist]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/codex-mcp/src/tools.rs#L84-L116
[shell-launch]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/shell_environment.rs#L18-L29
[shell-launch-use]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/shell_environment.rs#L177-L179
[shell-core]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/shell_environment.rs#L185-L188
[shell-set]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/shell_environment.rs#L160-L165
[hook-groups]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L633-L651
[hook-events]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/hooks.rs#L113-L137
[hook-group]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/protocol/src/hooks.rs#L140-L145
[hook-group-written]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/app-server/tests/suite/v2/hooks_list.rs#L80-L87
[mcp-command]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs#L399-L403
[mcp-headers-helper]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/mcp_types.rs#L417
[sandbox-profile]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/permission_config.rs#L62-L74
[never-refuses]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/mcp_tool_call.rs#L1923-L1931
[codex-home]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/utils/home-dir/src/lib.rs#L13-L62
[hooks-json]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L177-L182
[config-folder]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/state.rs#L225-L250
[user-layer-missing]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L657-L659
[user-layer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L295-L330
[hooks-json-is-file]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/hooks/src/engine/discovery.rs#L391-L398
[rust-toolchain]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/rust-toolchain.toml#L2
[policy-files]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/exec_policy.rs#L749-L773
[collect-policy-files]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/exec_policy.rs#L1238-L1288
[plugin-cache]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core-plugin-common/src/installed.rs#L11
[plugin-store]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core-plugins/src/store.rs#L87-L88
[plugin-install]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core-plugins/src/store.rs#L112-L120
[plugin-active]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core-plugin-common/src/installed.rs#L47-L68
[skills-root]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/host_roots.rs#L151-L158
[skill-name]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/mod.rs#L21
[skill-discovery]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/discovery.rs#L147-L159
[skill-recursive]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/host.rs#L105-L111
[skill-depth]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/mod.rs#L26
[skill-walk]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/discovery.rs#L71-L74
[skill-listing]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/local_file_system.rs#L872-L875
[skill-links]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/host.rs#L161-L164
[skill-file-links]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/local_file_system.rs#L849-L851
[skill-hidden]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/host.rs#L174-L178
[skill-system]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/skills/src/lib.rs#L66-L104
[skill-system-startup]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/host_service.rs#L503
[skill-not-folder]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/local_file_system.rs#L777-L779
[skill-missing]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/skills/src/loader/discovery.rs#L90
[skill-mcp]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/mcp_skill_dependencies.rs#L40-L83
[environments-path]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/environment_toml.rs#L234-L246
[environments-load]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/environment.rs#L194-L209
[environments-program]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/environment_toml.rs#L183-L198
[environments-read]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/exec-server/src/environment_toml.rs#L330-L341
[system-config]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L277-L292
[system-managed]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/layer_io.rs#L223-L233
[system-requirements]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L774-L777
[rust-is-file]: https://github.com/rust-lang/rust/blob/58cf8f9c35b355199727627d07ae34a4e2846d67/library/std/src/path.rs#L3584-L3615
