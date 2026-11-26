# What changed for the report in Codex 0.172.0?

The [release scan][inventory] found 24 added and two changed configuration paths since 0.171.0. When Apps and the named App are enabled, stay-safe names a tool’s request for AI review. It gives broader “Not checked” messages for plugins, profiles and feature settings. The new terminal shortcuts select groups of tasks and produce no warning.

| Setting in the scan | What Codex does and what stay-safe reports |
| --- | --- |
| `apps.*.tools.*.approvals_reviewer` | A tool can request human or AI review when it needs approval. A model policy can require AI review, and the configured reviewer must be allowed by policy. When Apps and the named App are enabled, either automatic value produces a named gap. A disabled App or an explicit `user` produces no reviewer gap. [Selection and policy][reviewer] · [Example reports](#app-tool-example) |
| `plugins.*.apps.*.tools.*.approvals_reviewer` | An enabled, allowed plugin can supply the same reviewer for a named App. Explicit top-level App fields take precedence. The report puts the whole `plugins` section under “Not checked.” It does not name a plugin tool’s reviewer. [Plugin overlays][overlays] · [Selection][reviewer] |
| `features.guardianv3.housekeeper`, `features.guardianv3.housekeeper.routing_instructions`, `features.guardianv3.housekeeper.batch_timeout_ms` | With Guardian V3 running, the housekeeper groups evidence for review. These settings control its guidance and time per batch. Stay-safe gives the general `features` gap. [Fields][guardian-fields] · [Housekeeper][housekeeper] |
| `features.guardianv3.reviewer`, `features.guardianv3.reviewer.retrieval_instructions`, `features.guardianv3.max_instruction_tokens` | The instructions guide how the reviewer finds evidence. The limit applies separately to each custom routing or retrieval prompt. Exceeding it can stop config loading. Codex strips both prompts and the limit from project configuration. Stay-safe gives the general `features` gap. [Reviewer’s board][board] · [Limit][limit] · [Project loader][project] |
| `features.guardianv3.message_board_in_memory` | Guardian can keep a fresh thread’s evidence in memory. On resume that board cannot supply earlier evidence, so its attached reviewer is unavailable. This changes what evidence the reviewer can use. Stay-safe gives the general `features` gap. [Board storage][board] · [Resume][resume] |
| `features.connector_tool_result_passthrough` | When enabled, Codex can include an eligible App tool’s result in a model request. This depends on the call, sign-in and request destination. Stay-safe gives the general `features` gap. The file cannot establish that Codex sent a result. [Feature check][capture] · [Eligible call][eligible] · [Destination][destination] · [Request][request] |
| `features.realtime_frames_local` | The flag enables local realtime history for threads with a state database and paginated history. A thread with an existing canonical realtime session may still qualify with the flag off. Stay-safe gives the general `features` gap. It does not inspect stored conversations. [Flag to store][store] · [Enrollment][enrollment] · [Persistence][persistence] |
| The nine feature paths above under `profiles.*.` | The schema repeats all nine inside legacy profile tables. Codex 0.172.0 uses a separate file for an active profile. An unrelated legacy table can coexist with it. Stay-safe gives a conditional warning for a table alone and a load-error message for a file with the old selector. [Profile loading][profile-layer] · [Unrelated table][unrelated] · [Profile example](#profile-example) |
| `tui.keymap`, `tui.keymap.agents`, `tui.keymap.agents.next_group`, `tui.keymap.agents.next_group[]`, `tui.keymap.agents.previous_group`, `tui.keymap.agents.previous_group[]` | The two changed parent objects include the new bindings. The added arrays and their items set shortcuts for moving to the next or previous task group. Stay-safe treats terminal preferences as outside its permissions report and gives no gap. [Binding definitions][bindings] · [Navigation][navigation] |

Guardian V3 is off by default. The new Guardian fields configure its evidence and how its reviewer uses that evidence. Setting one of those fields does not select AI review for an App tool. [Default][guardian-default] · [Extension activation][activation] · [App reviewer selection][reviewer]

## Profile example

Codex 0.172.0 stops when it finds `profile = "work"` in the effective config. To select that profile, move its settings into `work.config.toml`, remove the old selector and matching `[profiles.work]` table from the base file, and start Codex with `--profile work`. The profile file can override the base user settings. From the folder containing it, run `python -m stay_safe --config work.config.toml` to check its settings separately. Stay-safe reports the selector error once when it finds both forms in the file. [Selector rejection][selector] · [File loading][profile-layer] · [Reader follow-up #21][profile-issue]

Save this complete example as `profile.toml`. Run `python -m stay_safe --config profile.toml --format markdown` or use `--format json`. Both exit 2.

```toml
approval_policy = "on-request"
sandbox_mode = "read-only"
shell_environment_policy.inherit = "none"
profile = "work"

[profiles.work.features]
realtime_frames_local = true
```

**Markdown**

> **This file uses an old way to select a profile.** Codex 0.172.0 stops if `profile` is in the configuration it uses at startup. It ignores this setting in project configuration. On versions that support inline profiles, settings in the selected table can override your top-level settings.

**JSON** (`inspection_gaps`)

```json
["config-1: Codex 0.172.0 rejects a top-level profile selector in the configuration it uses at startup. It ignores this setting in project configuration. On versions that support inline profiles, settings in the selected table can override your top-level settings."]
```

## App tool example

Save this synthetic file as `example.toml` and run `python -m stay_safe --config example.toml --format markdown` or use `--format json`. Both exit 2. These are the portions that identify the reviewer. [App tool change #231][app-issue]

```toml
approval_policy = "on-request"
sandbox_mode = "read-only"
shell_environment_policy.inherit = "none"
[apps.calendar.tools.read]
approvals_reviewer = "auto_review"
```

**Markdown**

> **Not checked: `apps.calendar.tools.read.approvals_reviewer`.** If this tool needs approval, your file asks Codex to have an AI reviewer approve or deny the request. Your organization can limit who may review requests. For example, if its policy allows only human review, Codex may ask you to decide. Stay-safe can’t tell from this file which policy applies to your run.

**JSON** (`inspection_gaps`)

```json
["config-1: apps.calendar.tools.read.approvals_reviewer requests AI review if this tool needs approval. A policy can require human review. The effective reviewer was not checked."]
```

[inventory]: https://github.com/chalkbadger/stay-safe/blob/26fedaf3fa199b5e582fa9f87aa2645d29aeda11/codex-release-scan.md#L6168-L6197
[app-issue]: https://github.com/chalkbadger/stay-safe/issues/231
[profile-issue]: https://github.com/chalkbadger/stay-safe/issues/21
[reviewer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/connectors.rs#L522-L561
[overlays]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/connectors/src/app_tool_policy.rs#L139-L172
[guardian-fields]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/features/src/feature_configs.rs#L314-L349
[housekeeper]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/guardian-v3/src/housekeeper.rs#L89-L106
[board]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/guardian-v3/src/host.rs#L44-L68
[limit]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/config/mod.rs#L3192-L3227
[project]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L1374-L1391
[resume]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/ext/guardian-v3/src/host.rs#L90-L105
[capture]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/tools/executed_tool_calls.rs#L468-L489
[eligible]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/codex-mcp/src/binding.rs#L360-L390
[destination]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/client.rs#L285-L331
[request]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/client.rs#L2245-L2257
[store]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/thread_store_builder.rs#L60-L83
[enrollment]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/thread-store/src/local/mod.rs#L851-L866
[persistence]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/session/realtime_history.rs#L105-L119
[profile-layer]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/mod.rs#L295-L343
[unrelated]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/config/src/loader/tests.rs#L1030-L1064
[selector]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/src/config/mod.rs#L3664-L3671
[bindings]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/core/config.schema.json#L6004-L6019
[navigation]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/tui/src/app/agents_overview_view.rs#L726-L733
[guardian-default]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/features/src/lib.rs#L2305-L2310
[activation]: https://github.com/openai/codex/blob/3d86e43b075adeba2193ec5c22ac92f55afd82e6/codex-rs/app-server/src/extensions.rs#L107-L112
