# Codex configuration meanings

This is the single interpretation table for the Codex reader. Setting interpretations
describe a selected configuration-file snapshot or the documented defaults assessed
under the [no-config-file contract](../contracts/claims.md#works_without_a_config_file-with-no-config-file-the-report-looks-where-codex-looks-and-tells-me-which-codex-defaults-apply). They do not
establish a session's effective policy, live access, or whether an incident will occur. CLI overrides,
selected profiles, trusted project layers, managed policies and runtime state are
uninspected. Missing approval or sandbox selectors are gaps; their defaults are not
inferred. The [tool-approval] and [shell-environment-input] sources define the
defaults below. The rules follow the selected file's policy,
not uninspected runtime layers or actual tool annotations. An open tool catalog can
retain a parent policy risk; a closed allowlist loses it when every allowed tool is
denied or has its own approval override. A tool without its own approval mode inherits
its server's or app's mode, and `apps._default` is a policy template for named apps;
[each_risk_shows_its_cause](../contracts/claims.md#each_risk_shows_its_cause-for-each-risk-i-see-which-of-my-settings-causes-it-and-real-incidents-where-that-setting-went-wrong)
says which entry carries each resulting risk.
Tool overrides belong to named apps. Tool allow and deny lists (`enabled_tools`,
`disabled_tools`) apply only to MCP servers: Codex's [app settings][app-config] have neither.
Unsupported `apps._default.tools` blocks are skipped with a gap; they create no child tool
entries or risk facts.

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

Codex source links are pinned to OpenAI Codex `rust-v0.167.0`
(`086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a`) and were re-checked there on 2026-11-09.
The configuration reference was read on 2026-11-02 for retired values.
The `auto` default is defined by [AppToolApproval][tool-default].

| Setting | Value | Meaning stay-safe uses | Source | Status |
| --- | --- | --- | --- | --- |
| `approval_policy` | `never` | Permitted commands do not ask for approval; the sandbox remains separate. Catalog: `never`. Rules: `commands_without_prompts`. Gap: no. | [approval] | documented |
| `approval_policy` | `on-request` | The model decides when to request approval; this is not blanket preapproval. Catalog: `on-request`. Rules: none. Gap: no. | [approval] | documented |
| `approval_policy` | `untrusted` | The configuration reference retires this unsupported value; the reader leaves it unhandled. Catalog: none. Rules: none. Gap: yes. | [configuration-reference] | documented: retired |
| `approval_policy` | `on-failure` | The configuration reference deprecates this value; the reader leaves it unhandled. Catalog: none. Rules: none. Gap: yes. | [configuration-reference] | documented: deprecated |
| `approval_policy` | `granular` | A category set to `false` rejects its approval requests automatically instead of asking, as `never` does; the reader leaves this policy unhandled. Catalog: none. Rules: none. Gap: yes. | [approval-granular] | open |
| `sandbox_mode` | `read-only` | The configured legacy sandbox is read-only. Catalog: `read-only`. Rules: none. Gap: no. | [sandbox] | documented |
| `sandbox_mode` | `workspace-write` | The configured legacy sandbox permits workspace writes. Catalog: `workspace-write`. Rules: none. Gap: no. | [sandbox] | documented |
| `sandbox_mode` | `danger-full-access` | The configured legacy policy removes sandbox restrictions. Catalog: `danger-full-access`. Rules: `unrestricted_filesystem`. Gap: no. | [sandbox] | documented |
| `default_permissions` | `selected with sandbox_mode` | Named-profile selection is unhandled and conflicts with the legacy selector; legacy risk facts are suppressed. Catalog: `danger-full-access`, `permission-profile selection is uninspected`. Rules: none. Gap: yes. | [schema] | open |
| `permissions` | `definitions without selection` | Unselected profile definitions remain unhandled without erasing the explicit legacy sandbox setting. Catalog: `danger-full-access`. Rules: `unrestricted_filesystem`. Gap: yes. | [schema] | open |
| `sandbox_workspace_write.network_access` | `true` | This workspace-write option controls outbound network access. Catalog: `true`, `workspace-write option`. Rules: `network_access`. Gap: no. | [sandbox] | documented |
| `sandbox_workspace_write.network_access` | `false` | This workspace-write option controls outbound network access. Catalog: `false`, `workspace-write option`. Rules: none. Gap: no. | [sandbox] | documented |
| `sandbox_workspace_write.*` | `under read-only` | Workspace-write options are not selected by read-only mode. Catalog: `true`, `inactive or selection unknown`. Rules: none. Gap: no. | [schema] | documented |
| `mcp_servers.*.enabled` | `false` | A disabled server supplies no enabled program or tool condition. Catalog: `disabled`, `stdio; command withheld`, `tool approval: auto (default)`. Rules: none. Gap: no. | [mcp] | documented |
| `mcp_servers.*.command` | `nonempty command, no url` | An enabled stdio server starts a configured command; contents are withheld. Catalog: `configured enabled`, `stdio; command withheld`, `tool approval: auto (default)`. Rules: `configured_program`, `self_described_tools`. Gap: no. | [mcp] | documented |
| `mcp_servers.*.url` | `string, no command` | Codex uses HTTP for any string `url` without `command` ([field][mcp-url], [transport][mcp-transport]); the reader does not check its form, and the endpoint is not evidence of reachability or authentication. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto (default)`. Rules: `self_described_tools`. Gap: no. | [mcp-transport] | documented in source |
| `mcp_servers.*.http_headers_helper` | `nonempty command` | An HTTP header helper is a configured program; contents are withheld. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto (default)`. Rules: `configured_program`, `self_described_tools`. Gap: no. | [mcp] | documented |
| `mcp_servers.*.enabled_tools` | `named allowlist` | Only listed names are allowed by this file, before the denylist; the list does not establish live availability. Catalog: `configured names: read, files/write`. Rules: none. Gap: no. | [mcp] | documented |
| `mcp_servers.*.disabled_tools` | `named denylist` | Listed names are removed after applying the allowlist. Catalog: `configured names: delete`. Rules: none. Gap: no. | [mcp] | documented |
| `mcp_servers.*.default_tools_approval_mode` | `approve` | Never asks before the tool call. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: approve`. Rules: `automatic_tools`. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.default_tools_approval_mode` | `auto` | The default mode asks when destructiveHint=true, or when readOnlyHint is absent/false and destructiveHint or openWorldHint is absent/true. Only auto remembers session approvals. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto`. Rules: `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.default_tools_approval_mode` | `prompt` | Always asks before a tool call; a session approval counts for one call. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: prompt`. Rules: none. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.default_tools_approval_mode` | `writes` | Asks when the tool does not declare readOnlyHint=true; session approval is not remembered. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: writes`. Rules: `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `mcp_servers.*.tools.*.approval_mode` | `approve` | A named tool override replaces the server default when the tool is permitted by its filters. Catalog: `configured enabled`, `tool approval: approve`. Rules: `automatic_tools`. Gap: no. | [mcp] | documented |
| `mcp_servers.*.tools.*.enabled` | `false` | This app-style field is unsupported for MCP tools and does not disable the configured tool. Catalog: `configured enabled`, `tool approval: approve`. Rules: `automatic_tools`. Gap: yes. | [schema] | open |
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
| `apps.*.links` | `per-account policy` | Account-specific policy is outside reader coverage and account identities are withheld. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: yes. | [apps] | open |
| `model_providers.*` | `definition` | The provider name is catalogued; endpoints and credentials are withheld and no provider selection is inferred. Catalog: `configured; endpoint and credentials withheld`. Rules: none. Gap: no. | [schema] | documented |
| `model_providers.*.auth` | `command-backed authentication` | Command-backed provider authentication is outside reader coverage. Catalog: `configured; endpoint and credentials withheld`. Rules: none. Gap: yes. | [schema] | open |
| `notify` | `command list with nonempty program` | Notifications may spawn a configured external command; its contents are withheld. Catalog: `notification command configured; command withheld`. Rules: `configured_program`. Gap: no. | [notify-program] | documented in source |
| `hooks.*` | `command handler with nonempty command` | Codex runs a `type = "command"` handler whose command is not empty, whatever its [matcher][hook-matcher] or [options][hook-handlers] such as `timeout`; trust and enablement in `hooks.state` are uninspected. Catalog: `contents withheld`. Rules: `configured_program`. Gap: yes. | [hooks] | documented in source |
| `hooks.*` | `no command handler with nonempty command` | Codex skips `prompt` and `agent` handlers ([source][hook-skipped]) and empty commands ([source][hook-empty]); an `mcp_tool` handler calls a tool on an MCP server ([source][hook-mcp-tool]). Catalog: `contents withheld`. Rules: none. Gap: yes. | [hooks] | documented in source |
| `hooks.state` | `trusts, distrusts or disables a hook` | Codex runs a hook from the user's `config.toml` only when this state enables and trusts it ([gate][hook-trust], [trust check][hook-trust-check], [state source][hook-state]); the reader does not inspect it, so a command handler keeps its risk. Catalog: `contents withheld`. Rules: `configured_program`. Gap: yes. | [hooks] | documented in source |
| `web_search` | `disabled` | The reader records this recognized configured mode without inferring live network availability. Catalog: `disabled`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `cached` | The reader records this recognized configured mode without inferring live network availability. Catalog: `cached`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `indexed` | The reader records this recognized configured mode without inferring live network availability. Catalog: `indexed`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `live` | The reader records this recognized configured mode without inferring live network availability. Catalog: `live`. Rules: none. Gap: no. | [schema] | documented |
| `web_search` | `unrecognized string` | An unrecognized mode is withheld and produces a coverage gap. Catalog: none. Rules: none. Gap: yes. | [schema] | open |
| `mcp_servers.*.default_tools_approval_mode` | `omitted` | The documented auto default applies to an enabled server when no tool override replaces it. Catalog: `configured enabled`, `HTTP; endpoint withheld`, `tool approval: auto (default)`. Rules: `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `apps.*.default_tools_approval_mode` | `omitted without _default mode` | The documented auto default applies to a named enabled app when no app or tool override replaces it. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: auto (default)`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [tool-approval] | documented in source |
| `apps.*.default_tools_approval_mode` | `writes inherited from _default` | The named app inherits the writes policy from its default; the hint-dependent meaning is defined in the mode rows above. Catalog: `configured enabled`, `destructive tools enabled by Codex default`, `tool approval: writes`. Rules: `destructive_tools`, `self_described_tools`. Gap: no. | [apps] | documented |
| `shell_environment_policy` | `omitted` | Catalog: `inherit: all (default)`, `ignore_default_excludes: true (default)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment-input] | documented in source |
| `shell_environment_policy.inherit` | `all` | Catalog: `inherit: all (explicit)`, `ignore_default_excludes: true (default)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.inherit` | `core` | Catalog: `inherit: core (explicit)`, `ignore_default_excludes: true (default)`. Rules: none. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.inherit` | `none` | Catalog: `inherit: none (explicit)`, `ignore_default_excludes: true (default)`. Rules: none. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.ignore_default_excludes` | `true` | Catalog: `inherit: all (default)`, `ignore_default_excludes: true (explicit)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy.ignore_default_excludes` | `false` | Catalog: `inherit: all (default)`, `ignore_default_excludes: false (explicit)`. Rules: `environment_inheritance`. Gap: no. | [shell-environment] | documented in source |
| `shell_environment_policy` | `additional fields` | Catalog: none. Rules: none. Gap: yes. | [shell-environment] | open |
| `features.apps` | `omitted` | Codex's apps feature is on by default ([default][apps-feature]). When Codex is signed in with ChatGPT, it adds an MCP connection to ChatGPT named `codex_apps` ([connection][apps-connection], [sign-in][apps-sign-in]); `false` removes it. The reader does not check sign-in. Catalog: `ChatGPT Apps`, `exists only if Codex is signed in with ChatGPT, which is not checked`, `features.apps = false turns it off`. Rules: none. Gap: no. | [apps-feature] | documented in source |

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

A record's words are withheld, except a first word on the program list in the
[saved-approval contract](../contracts/claims.md#lists_commands_codex_stops_asking_about-the-report-lists-the-commands-i-told-codex-to-stop-asking-about-and-tells-me-when-it-couldnt-read-or-check-a-rules-file), which is shown as
`program: <name>`. The list changes only by pull request.

The [saved-approval contract](../contracts/claims.md#lists_commands_codex_stops_asking_about-the-report-lists-the-commands-i-told-codex-to-stop-asking-about-and-tells-me-when-it-couldnt-read-or-check-a-rules-file) defines how the
report treats records inside and outside coverage; [share_without_exposing_secrets](../contracts/claims.md#share_without_exposing_secrets-i-can-share-the-report-without-exposing-my-commands-addresses-tokens-or-environment-values-names-appear-as-i-wrote-them-and-the-report-reminds-me-to-check-them-first)
covers disclosure. The broad label is stay-safe's inference, not a Codex score.
[Decision ordering][saved-decisions], [matching precedence][saved-precedence]
and [runtime sandbox handling][saved-runtime] establish the declared meaning.

[saved-writer]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/execpolicy/src/amend.rs
[saved-runtime]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/src/exec_policy.rs
[saved-match]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/execpolicy/src/rule.rs#L55-L72
[saved-precedence]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/execpolicy/src/policy.rs#L584-L595
[saved-decisions]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/execpolicy/src/decision.rs

[schema]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/config.schema.json
[approval]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/protocol.rs
[approval-granular]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/protocol.rs#L1158-L1168
[sandbox]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/protocol.rs
[mcp]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/mcp_types.rs
[tool-approval]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/src/mcp_tool_call.rs#L2597-L2627
[apps]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/types.rs
[app-tool-policy]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/connectors/src/app_tool_policy.rs#L279-L305
[app-config]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/types.rs#L534-L576
[app-default-destructive]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/types.rs#L471-L476
[app-enabled]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/connectors/src/app_tool_policy.rs#L174-L185
[app-enabled-field]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/types.rs#L537-L540
[apps-feature]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/features/src/lib.rs#L1658-L1663
[apps-connection]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/core/src/mcp.rs#L464-L479
[apps-sign-in]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/codex-mcp/src/mcp/mod.rs#L358-L360
[app-enabled-run]: https://github.com/chalkbadger/stay-safe-archive/issues/90#issuecomment-6726050010
[app-tool-policy-tests]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/connectors/src/app_tool_policy_tests.rs#L685-L770
[hooks]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/discovery.rs
[mcp-url]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/mcp_types.rs#L407
[mcp-transport]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/mcp_types.rs#L512-L566
[hook-matcher]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/matcher.rs#L32-L40
[hook-handlers]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/hooks.rs#L140-L188
[hook-skipped]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/discovery.rs#L782-L801
[hook-empty]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/discovery.rs#L665-L671
[hook-mcp-tool]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/discovery.rs#L729-L781
[hook-trust]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/discovery.rs#L917-L923
[hook-trust-check]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/engine/discovery.rs#L1000-L1027
[hook-state]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/config_rules.rs#L15-L45
[notify-program]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/hooks/src/registry.rs#L407-L421
[configuration-reference]: https://learn.chatgpt.com/docs/config-file/config-reference
[tool-default]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/mcp_types.rs#L26-L34
[shell-environment]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/protocol/src/config_types.rs#L205-L272
[shell-environment-input]: https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/config/src/shell_environment_policy.rs#L133-L169
