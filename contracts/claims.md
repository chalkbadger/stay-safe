# stay-safe claims

## [test_folders_have_markers] When I forget a test folder's package marker, the development check names it and fails.
Issue: https://github.com/chalkbadger/stay-safe/issues/15
Tests: [tests/test_folders_have_markers/](../tests/test_folders_have_markers/)

- I omit a direct or intermediate test folder's marker, and the complete check names it and exits unsuccessfully before running the tests. `test_check.py::test_missing_direct_and_intermediate_markers_stop_the_complete_check`
- I restore the markers, and the complete check discovers my failing sentinel; correcting the sentinel makes the check pass. `test_check.py::test_restored_markers_run_the_failing_sentinel_then_allow_its_pass`
- I leave markers out of folders with no matching tests in them or their descendants, and the complete check passes. `test_check.py::test_folders_without_matching_tests_do_not_need_markers`

## [runs_without_a_coding_agent] I copy the README's first commands, with no coding agent, and they download a tagged release and run it; the README's sample finding is what it prints. If I run it the wrong way or with a Python that's too old, it either runs anyway or tells me the exact command to run.
Issue: https://github.com/chalkbadger/stay-safe/issues/3
Tests: [tests/runs_without_a_coding_agent/](../tests/runs_without_a_coding_agent/)

- I open the README and find its first three fenced commands are a clone of a `vX.Y.Z` tag, `cd stay-safe` and `python3 -m stay_safe`. `test_readme.py::test_first_commands_clone_a_release_tag_and_run_the_diagnostic_without_an_agent`
- I run stay-safe on the test configuration the README's sample finding links, and it prints that finding as the README shows it, apart from the commit in its links. `test_readme.py::test_sample_finding_is_what_stay_safe_prints_for_its_test_configuration`
- I run `python3 stay_safe` from the checkout, and I get the same report and exit status as with `-m`. `test_python_entry.py::test_running_the_folder_without_m_gives_the_same_report_and_exit_status`
- On a Python older than 3.11 with a newer Python on my `PATH`, I see that Python's command and a feedback link, and the exit status is 2. `test_python_entry.py::test_too_old_python_names_the_newest_python_on_the_path_and_exits_2`
- On a Python older than 3.11 with no newer Python found, I see instructions to install 3.11 or newer and a feedback link, and the exit status is 2. `test_python_entry.py::test_too_old_python_without_a_newer_one_says_to_install_it_and_exits_2`
- The version check runs before anything that needs 3.11 is imported, and stays parseable by Python 3.9. `test_python_entry.py::test_version_check_runs_before_any_module_needing_3_11_and_parses_as_python_3_9`

## [see_every_connection_and_setting] I can see what stay-safe found in my Codex files. The report tells me when it used a default or could not complete a check.
Issue: https://github.com/chalkbadger/stay-safe/issues/13
Tests: [tests/see_every_connection_and_setting/](../tests/see_every_connection_and_setting/)

- My `plugins`, `marketplaces` and `desktop` sections are named as unchecked; arbitrary top-level names stay withheld and ignored preferences stay ignored. `test_unchecked_sections.py::test_only_recognized_unchecked_sections_are_named_and_preferences_stay_ignored`
- My `projects` declarations give a literal trusted count, including zero; malformed or unsupported data gives a separate incomplete-assessment gap and preserves recognized counts in mixed tables. `test_unchecked_sections.py::test_project_counts_distinguish_zero_invalid_and_partial_declarations`
- In both report formats I see each selected file's named gaps and trusted count, with project settings unassessed; private paths, nested names and values stay withheld, existing findings remain and the command exits `2`. `test_unchecked_sections.py::test_both_formats_keep_file_counts_findings_and_private_identifiers_withheld`
- A project path in my config is never accessed while its trusted declaration is counted; a monitored directory access proves the test's detector works. `test_unchecked_sections.py::test_referenced_project_directories_are_not_accessed`

- I run stay-safe on a known config file and see exactly the expected named entries and risks; settings I turned off are not treated as on. `test_config.py::test_known_configuration_has_exact_named_catalog_and_risks`
- I read the Markdown report: it starts with a line counting its findings and the things it didn't check, then lists the findings, those gaps, my setup, the sources, then what the report can't see, each limit with why and what to do, with a link to the full scope, and ends with a footer naming the commit and report format. `test_report_order.py::test_summary_then_findings_and_gaps_then_setup_sources_limits_and_a_footer_last`
- I read Your setup in Markdown and see every entry once, under its file and a line on how Codex uses that file, each observation in plain words, with one note on why left-out values aren't shown and where to find them. `test_your_setup.py::test_a_real_run_lists_every_entry_once_under_its_file`
- My config doesn't set `features.apps = false`, and I see the ChatGPT Apps connection, with a note that it exists only if Codex is signed in with ChatGPT. `test_chatgpt_apps.py::test_configuration_without_apps_false_names_the_chatgpt_apps_connection`
- I set `features.apps = false` and see no ChatGPT Apps connection. `test_chatgpt_apps.py::test_apps_false_gives_no_chatgpt_apps_connection`
- I give an MCP server a `url` string and no `command`, and see the entry `HTTP; endpoint withheld`. `test_config.py::test_any_string_url_without_command_is_http_and_withheld`
- I set an allowlist or denylist on an MCP server, with no approval mode set for its tools, and still see the list under that server's name. `test_config.py::test_standalone_tool_filters_keep_names_and_report_withheld_names`
- Your setup (the catalog in JSON) tells me it has nothing to list exactly when it lists nothing, and a readable file of mine with no entries is not reported as one it couldn't read. `test_config.py::test_empty_catalog_does_not_claim_a_read_failure`
- I select a missing, symlinked (including dangling), unreadable, non-UTF-8 or malformed TOML config file, and both formats distinguish why it was skipped and give a next action. `test_selected_config_failures.py::test_each_failure_has_a_distinct_private_safe_reason_and_action_in_both_formats`
- A rejected selected config file does not expose its path, contents or raw errors in either report format. `test_selected_config_failures.py::test_each_failure_has_a_distinct_private_safe_reason_and_action_in_both_formats`
- I select a rejected config file and a readable snapshot together, and both formats preserve the readable snapshot's two expected findings while the exit status is 2. `test_selected_config_failures.py::test_each_failure_has_a_distinct_private_safe_reason_and_action_in_both_formats`
- I pass several files and each keeps its own source label and the setting names as I wrote them. `test_config.py::test_files_remain_independent_and_identity_preserves_dotted_name`
- I pass two files and both formats list each file's settings separately. `test_snapshots.py::test_two_files_are_separate_snapshots_without_tested_effective_permissions`
- I pass two files and see, in the JSON scope and in the Markdown section on what the report can't see, that the files are separate snapshots and that effective permissions are not tested. `test_snapshots.py::test_two_files_are_separate_snapshots_without_tested_effective_permissions`
- I pass several files and see, in both formats, each file's gaps under its own source label, numbered in the order I passed the files. `test_gaps.py::test_both_files_keep_distinct_gaps_and_argument_order_sources`
- I read the gaps in Markdown, under a line saying why things are skipped: each starts with a bold headline and plain sentences written for its kind, then what to do, then its file: where a file found automatically lives, or the label of a file I passed. `test_plain_gaps.py::test_each_gap_leads_with_what_was_not_checked_then_its_source`
- I have no Codex config file, and the gaps for settings it would hold say that no config file was found. `test_plain_gaps.py::test_absent_settings_say_there_is_no_config_file_when_none_was_found`
- I get one Markdown paragraph for each gap in the JSON report, including a gap with no plain wording of its own. `test_plain_gaps.py::test_every_gap_gets_its_own_paragraph_and_none_is_dropped`
- When a required field is missing, or a setting conflicts or isn't supported, I see a gap for it and still see every setting that could be read. `test_config.py::test_incomplete_unknown_and_malformed_inputs_are_reported`
- I give a validated field a wrong-typed or invalid value, or a `notify` command an empty first element, and see a gap and no observation or finding from that value, while unrelated valid findings in the same file remain. `test_invalid_values.py::test_each_invalid_value_is_a_gap_without_findings_and_keeps_unrelated_findings`
- I leave a tool to inherit an invalid setting, and both formats report the gap only at its parent. `test_inherited_gaps.py::test_inherited_invalid_values_report_only_the_parent_in_both_formats`
- I give a tool its own invalid override, and both formats keep its own gap. `test_inherited_gaps.py::test_invalid_tool_overrides_keep_their_own_gap`
- I give a tool a valid override of an invalid parent value, and both formats retain its findings. `test_inherited_gaps.py::test_valid_tool_overrides_keep_their_findings_with_an_invalid_parent`
- I inspect an invalid inherited setting through the command line, and both formats keep exit status 2. `test_inherited_gaps.py::test_inherited_gap_cli_remains_incomplete_without_private_values`
- I inspect an invalid inherited setting through the command line, and neither format reveals private input. `test_inherited_gaps.py::test_inherited_gap_cli_remains_incomplete_without_private_values`
- I turn a named app off with its own `enabled` and see no gap from any of its other settings. `test_invalid_values.py::test_a_disabled_app_gives_no_gap_from_its_other_settings`
- An app, MCP server, model provider, tool or `tools` block of mine that is not a table gives me a gap and no entry or risk of its own, and the rest of the report matches the file without it. `test_malformed_tables.py::test_a_value_that_must_be_a_table_is_a_gap_and_otherwise_absent`
- My `apps._default` is not a table: I see a gap for it, and no finding from an approval mode or `destructive_enabled` that a named app leaves to it; settings the app sets itself are reported as usual. `test_malformed_tables.py::test_a_template_that_is_not_a_table_leaves_inherited_app_settings_unknown`
- I set `enabled_tools` or `disabled_tools` on an app and see a gap, and the entries and risks match the file without it. `test_malformed_tables.py::test_app_tool_lists_are_a_gap_and_change_nothing_else`
- I set `writable_roots`, `exclude_slash_tmp`, `exclude_tmpdir_env_var`, `open_world_enabled` or `approvals_reviewer` to a valid or invalid value and see no mention of that setting and no gap from it. `test_unlisted_settings.py::test_sandbox_and_app_settings_no_rule_reads_give_no_entry_risk_or_gap`
- I set `default_permissions` and it gets no entry of its own. `test_unlisted_settings.py::test_default_permissions_gives_no_entry_and_keeps_its_gaps`
- I set a granular `approval_policy`, complete, partial or with an invalid category value, and see no entry for it and exactly one gap, `approval_policy has a known but unhandled value; its behavior is not evaluated.`, in the JSON report. `test_unlisted_settings.py::test_granular_approval_policy_gives_no_entry_and_only_the_unhandled_gap`
- I run each example in the Codex meanings table as its own config file and see the entries, rule conditions and gaps the table publishes for it. `test_meanings.py::test_reader_matches_every_published_meaning_example`
- I pass a config or rules file that is a symlink and get only the read gap for it. `test_symlinks.py::test_symlinked_explicit_inputs_are_gaps`
- A config or rules file that stay-safe finds in my Codex home and that is a symlink gives me only the read gap for it, and the other file is still read. `test_symlinks.py::test_symlinked_default_files_are_gaps`
- My regular config and rules files, whether I pass them or stay-safe finds them, are still read. `test_symlinks.py::test_regular_explicit_and_default_files_are_still_read`
- My config file of exactly 1 MiB is assessed in full. `test_size_limit.py::test_configuration_of_exactly_one_mebibyte_is_read`
- My config file one byte over 1 MiB gives me only the size gap, even when it starts with valid settings. `test_size_limit.py::test_configuration_one_byte_over_is_a_size_gap_without_partial_assessment`
- My rules file of exactly 1 MiB is assessed in full. `test_size_limit.py::test_rules_of_exactly_one_mebibyte_are_read`
- My rules file one byte over 1 MiB gives me only the size gap, even when it starts with a valid saved approval. `test_size_limit.py::test_rules_one_byte_over_are_a_size_gap_without_partial_assessment`
- I run stay-safe with no file arguments and a `hooks.json` file in my Codex home, and see a gap naming that file; the run exits `2`. `test_hooks_json.py::test_hooks_json_file_gives_a_gap_naming_it_and_exits_2`
- With no `hooks.json` file in my Codex home, I see no such gap. `test_hooks_json.py::test_codex_home_without_a_hooks_json_file_gives_no_such_gap`
- I run stay-safe with no file arguments, and a `config.toml`, `hooks.json`, `managed_config.toml` or `requirements.toml` file, or a `.rules` file in `rules/`, in the system config folder gives me one gap naming `/etc/codex`; the run exits `2`. `test_system_folder.py::test_each_codex_file_in_the_system_folder_gives_the_gap_and_exits_2`
- A system config folder that is missing or holds none of these files, including one whose `rules/` holds only other names such as `default.rules.bak`, gives me no such gap. `test_system_folder.py::test_system_folder_without_codex_files_gives_no_gap`
- A `rules/` folder in the system config folder that can't be listed gives me the same gap, and the run exits `2`. `test_system_folder.py::test_unlistable_rules_folder_gives_the_gap_and_exits_2`
- I run with `--config` or `--rules` and see no system config folder gap. `test_system_folder.py::test_runs_with_file_arguments_give_no_system_folder_gap`
- I run stay-safe with no file arguments, and a folder at `plugins/cache/<marketplace>/<plugin>/<version>` in my Codex home gives me one gap naming `plugins/cache`; the run exits `2`. `test_plugins_cache.py::test_version_folder_gives_the_gap_and_exits_2`
- A Codex home of mine with no `plugins/cache`, an empty one, or one holding only marketplace or plugin folders with no version folder gives me no such gap. `test_plugins_cache.py::test_cache_without_a_version_folder_gives_no_gap`
- A cache folder that cannot be listed gives me an inspection-failed gap and next step in both formats. `test_plugins_cache.py::test_unlistable_cache_reports_failure_without_private_details`
- A failed cache inspection keeps unrelated findings. `test_plugins_cache.py::test_unlistable_cache_reports_failure_without_private_details`
- A failed cache inspection exits `2`. `test_plugins_cache.py::test_unlistable_cache_reports_failure_without_private_details`
- A failed cache inspection reveals no private path or raw error. `test_plugins_cache.py::test_unlistable_cache_reports_failure_without_private_details`
- I run with `--config` or `--rules` and see no `plugins/cache` gap. `test_plugins_cache.py::test_runs_with_file_arguments_give_no_plugins_cache_gap`
- I open the full scope section of `docs/report.md` and find every scope line of the JSON report, including that local modifications are not checked. `test_report_order.py::test_the_full_scope_holds_every_scope_line`

## [each_risk_shows_its_cause] Each warning shows me the setting behind it and links to incident reports.
Issue: https://github.com/chalkbadger/stay-safe/issues/13
Tests: [tests/each_risk_shows_its_cause/](../tests/each_risk_shows_its_cause/)

- I run stay-safe on a known config file and see each risk tied to the config entry I'd expect for its rule. `test_report.py::test_cli_risks_have_expected_entries_incidents_and_status_in_both_formats`
- In both formats, I see the incident citations marked reported, not verified. `test_report.py::test_cli_risks_have_expected_entries_incidents_and_status_in_both_formats`
- I follow a risk's incident citations to committed incident entries, each with source links, coding agent, event and enabling condition, and the incident list tells me once that its entries are reported, not verified. `test_rules.py::test_every_rule_cites_complete_committed_reported_incidents`
- Each risk rule matches a plain fact, not a Codex setting name, and gives its pinned rule ID and incident citations. `test_rules.py::test_rules_accept_harness_neutral_observations`
- When an incident citation is missing, the run exits `2` with a gap, and I still see my setup, which setting causes each risk, and the remaining citation links. `test_report.py::test_cli_reports_missing_incident_citation_and_preserves_safe_data`
- When the settings that would cause a command, tool or sandbox risk don't apply in my config, I see no such risk. `test_conditions.py::test_command_prompt_and_filesystem_rules_have_independent_positive_and_negative_cases`
- A hook event with a `type = "command"` handler whose command is not empty gives me `configured_program`, whatever its matcher, options or `hooks.state` entry says. `test_hooks.py::test_command_handler_reports_program_whatever_matcher_options_or_state`
- A hook event whose handlers are only `prompt`, `agent` or `mcp_tool`, or have an empty command, gives me no `configured_program`. `test_hooks.py::test_prompt_agent_mcp_tool_or_empty_command_handlers_report_no_program`
- I see the risk from tools that describe themselves follow Codex's source-documented defaults, and approval overrides count only for connections and tools I configured and enabled. `test_self_described_tools.py::test_explicit_modes_and_omitted_auto_default_on_named_connections`
- A tool-approval risk that my server's or app's tools inherit appears once, on that server or app. `test_single_attribution.py::test_inherited_mode_is_reported_on_the_server_or_app_only`
- A tool-approval risk set by my tool's own mode appears once, on that tool. `test_single_attribution.py::test_tool_that_sets_its_own_mode_is_reported_on_the_tool_only`
- My `apps._default` settings give tool risks only on enabled named apps that inherit them, never on the template itself. `test_single_attribution.py::test_app_template_risks_appear_only_on_enabled_apps_that_inherit_them`
- An enabled app that sets neither `default_tools_enabled` nor `destructive_enabled`, with no `apps._default` or an `apps._default` without `destructive_enabled`, gives me `destructive_tools`, which says it comes from Codex's default. `test_destructive_tools.py::test_app_with_nothing_set_reports_codex_default`
- With `default_tools_enabled` unset, the `destructive_tools` risk tells me whether `destructive_enabled = true` comes from the app or from `apps._default`. `test_destructive_tools.py::test_risk_names_where_destructive_enabled_true_comes_from`
- An app with `default_tools_enabled = true` gives me `destructive_tools` naming that setting, whatever `destructive_enabled` says, and is not described as having destructive tools disabled. `test_destructive_tools.py::test_default_tools_enabled_true_decides_whatever_destructive_enabled_says`
- A tool with `enabled = true` under an enabled app gives me `destructive_tools` on that tool, whatever the app's settings say. `test_destructive_tools.py::test_tool_enabled_true_reports_on_the_tool_whatever_the_app_says`
- I see no `destructive_tools` for a disabled app, whatever its tools set, or, when none of its tools sets `enabled = true`, for an app whose `default_tools_enabled` is `false` or whose `destructive_enabled` is `false` with `default_tools_enabled` unset. `test_destructive_tools.py::test_no_risk_when_no_setting_lets_destructive_tools_run`

## [findings_say_what_to_do] Each finding tells me in plain words what is wrong and what to do, with a stricter option if I want one.
Issue: https://github.com/chalkbadger/stay-safe/issues/12
Tests: [tests/findings_say_what_to_do/](../tests/findings_say_what_to_do/)

- I read a finding in Markdown: it starts with a bold headline and plain sentences written for its rule and entry, including any source status; tool-approval findings describe the setting without predicting a live decision, and the JSON preapproval explanation names its mode. Then it says how it has gone wrong, with its incident labels marked reported, not verified, then what to do, and ends with one line giving its rule ID, entry ID and configured evidence; the rule and meanings source links appear once, in the Sources section. `test_plain_findings.py::test_each_finding_leads_with_its_meaning_then_incidents_next_step_and_trace_and_sources_close_the_report`
- I see one note before the findings. It explains that Codex reads the whole file when editing it. App settings, profiles and command-line options can override the file's settings. Codex can allow or block calls without asking me. The report does not test those decisions. The note explains file labels only when a finding uses one. `test_what_to_do.py::test_findings_open_with_one_shared_note`
- I see the same note when my files set an approval policy, leave it out, or use different policies. `test_what_to_do.py::test_shared_note_keeps_approval_outcomes_unassessed_for_each_policy`
- In Markdown, each finding's What to do is one line naming its lower-friction option, with its trade-off, where the Codex meanings table backs one, then its stricter option; Change it is one line telling me where the setting goes and giving a sentence that asks Codex to make the edit and show only what it changes. `test_what_to_do.py::test_each_finding_gives_lower_friction_then_stricter_option_then_how_to_change_it`
- Findings about my commands, programs, environment and saved approvals add a Check step that is a place to look or a command that prints names only. `test_what_to_do.py::test_each_finding_gives_lower_friction_then_stricter_option_then_how_to_change_it`
- The sentence for Codex and the Check step name a file found automatically where Codex keeps it, `~/.codex/...` or `$CODEX_HOME/...`, and a file I passed with `--config` or `--rules` by a placeholder with its label, such as `<config-1>`. `test_what_to_do.py::test_files_found_automatically_are_named_where_codex_keeps_them`
- The advice I get never suggests a sandbox looser than one a file I inspect sets: for `approval_policy = "never"` it keeps a `read-only` or `workspace-write` sandbox set in the same file, and it suggests `workspace-write` only when no file I inspect sets `read-only`. `test_what_to_do.py::test_advice_never_loosens_a_sandbox_another_inspected_file_sets`
- When my file selects a permission profile with `default_permissions`, its approval advice gives no `sandbox_mode` advice and tells me the profile decides what commands can write. `test_what_to_do.py::test_a_selected_permission_profile_gets_no_sandbox_mode_advice`
- Every setting the report's options tell me to change rests on a Codex meanings row whose status is documented or documented in source. `test_what_to_do.py::test_every_setting_an_option_names_rests_on_a_confirmed_meanings_row`


## [warns_when_codex_shares_my_environment] If Codex hands my whole shell environment to the commands it runs, the report tells me, whether I set that or it is Codex's default.
Issue: https://github.com/chalkbadger/stay-safe/issues/2
Tests: [tests/warns_when_codex_shares_my_environment/](../tests/warns_when_codex_shares_my_environment/)

- For each supported policy, I see each setting with whether I set it or it is the default, and `inherit = "all"`, set or default, is flagged whatever `ignore_default_excludes` says. `test_policy.py::test_absent_empty_partial_and_explicit_policies_identify_each_setting`
- I see the environment finding only for a supported `inherit = "all"`, whatever my name-filter setting says. `test_policy.py::test_only_full_inheritance_matches_regardless_of_name_filtering`
- In both the Markdown and JSON reports I see the cited environment finding, and the exit status reflects gaps only, not the finding. `test_policy.py::test_cli_formats_keep_evidence_citations_and_honest_status`
- I set a shell environment field other than `inherit` or `ignore_default_excludes`, or an invalid value, and I see a gap and no environment finding. `test_policy.py::test_invalid_or_extra_fields_are_gaps_without_fabricated_defaults`

## [lists_commands_codex_stops_asking_about] The report lists the commands I told Codex to stop asking about, and tells me when it couldn't read or check a rules file.
Issue: https://github.com/chalkbadger/stay-safe/issues/6
Tests: [tests/lists_commands_codex_stops_asking_about/](../tests/lists_commands_codex_stops_asking_about/)

- The report checks only the files I select, without combining their rules; when I select none, it checks `config.toml` and `rules/default.rules` in the Codex home. `test_rules.py::test_file_selection_keeps_configuration_and_rules_independent`
- When I have no default approvals file, the report says so without treating that as a problem, but marks the check incomplete when a file I selected is missing. `test_rules.py::test_missing_default_is_absent_but_missing_selected_file_is_a_gap`
- For each approval I saved in Codex's one-line format, I see its line number in the file and how many command parts it saves. `test_rules.py::test_saved_lines_keep_line_numbers_part_counts_and_broad_labels`
- For an approval whose first word is exactly one of `git gh npm npx pnpm yarn node python python3 pip pip3 uv cargo go make docker kubectl curl wget ssh bash sh rm mv cp chmod`, I see that name; for any other first word, such as `sudo`, `/usr/bin/git` or `Git`, I see no word. `test_rules.py::test_only_a_first_word_exactly_on_the_program_list_is_shown`
- An approval of mine with one saved command part, such as `curl`, is marked broad because it puts no limits on later arguments; approvals with more parts are not labelled broad. `test_rules.py::test_saved_lines_keep_line_numbers_part_counts_and_broad_labels`
- The report explains that I saved permission to run commands beginning with those parts outside Codex's restricted environment without being asked again. `test_rules.py::test_saved_lines_keep_line_numbers_part_counts_and_broad_labels`
- In a Git checkout, I see the incident references for each approval in both the readable report and the JSON version. `test_rules.py::test_both_formats_repeat_and_removing_a_rule_removes_its_finding`
- I remove a saved approval, run the report again, and its entry and explanation are gone. `test_rules.py::test_both_formats_repeat_and_removing_a_rule_removes_its_finding`
- A `prompt` or `forbidden` line of mine, alone or beside an `allow` line, counts as an unsupported line: I'm told the check is incomplete, and the `allow` line stays listed. `test_rules.py::test_prompt_and_forbidden_lines_are_unsupported_beside_listed_allow_lines`
- Apart from blank lines and comments, lines of mine outside the supported format make the check incomplete while readable approvals stay listed; the report doesn't check whether the whole rules file is valid. `test_rules.py::test_unsupported_lines_preserve_supported_records`
- When my rules file can't be read, I see an incomplete check and no approvals listed for that file. `test_rules.py::test_unreadable_nonregular_oversize_and_invalid_utf8_are_gaps`
- I run stay-safe with no file arguments and another `.rules` file beside `default.rules`, and see a gap that names no file; the run exits `2`. `test_other_rules_files.py::test_another_rules_file_adds_a_gap_naming_no_file_and_exits_2`
- That other file is not read: I don't see an approval saved in it. `test_other_rules_files.py::test_other_rules_file_is_not_read`
- A file of mine whose name doesn't end in `.rules`, such as `default.rules.bak`, adds no gap. `test_other_rules_files.py::test_files_codex_does_not_load_add_no_gap`
- A `rules/` folder that can't be listed gives me a gap and exit `2`. `test_other_rules_files.py::test_rules_directory_that_cannot_be_listed_is_a_gap`
- I read in the JSON report's scope, and in the full scope in `docs/report.md` that the Markdown report links at its commit, that listed entries are saved-format approval candidates whose syntax context and current effect (whether Codex would allow them now) are not checked. `test_rules.py::test_scope_calls_listed_entries_candidates_with_unchecked_context_and_effect`

## [works_without_a_config_file] With no config file, the report looks where Codex looks and tells me which Codex defaults apply.
Issue: https://github.com/chalkbadger/stay-safe/issues/7
Tests: [tests/works_without_a_config_file/](../tests/works_without_a_config_file/)

- I have no config file, and both formats tell me it is absent and show the cited default environment finding, with approval and sandbox gaps and exit status `2`. `test_report.py::test_both_formats_report_cited_defaults_and_retained_gaps`
- I have no config file, and the notice in both formats names the command environment and ChatGPT Apps as assessed defaults. `test_report.py::test_both_formats_report_cited_defaults_and_retained_gaps`
- I have no config file, and both formats say the ChatGPT Apps connection depends on sign-in, which was not checked. `test_report.py::test_both_formats_report_cited_defaults_and_retained_gaps`
- With `~/.codex` missing and `CODEX_HOME` unset, I still get the default assessment. `test_report.py::test_missing_home_dot_codex_with_unset_codex_home_uses_defaults`
- With `CODEX_HOME` empty or unset, stay-safe reads my `~/.codex`, not my working folder. `test_home.py::test_empty_or_unset_codex_home_reads_home_dot_codex_not_the_working_directory`
- When I set `CODEX_HOME`, it is read even when the home folder lookup fails. `test_home.py::test_set_codex_home_is_read_when_the_home_lookup_fails`
- A `CODEX_HOME` I set that is missing, a file or can't be checked gives me only a Codex home gap, no defaults and status `2`. `test_home.py::test_missing_or_file_codex_home_is_a_gap_without_defaults`
- With `CODEX_HOME` empty or unset and my home folder unknown, I get only a Codex home gap, no defaults and status `2`. `test_home.py::test_unknown_home_with_unset_codex_home_is_a_gap_without_defaults`
- When my default config file is readable, I see its own policy and no notice that the file is absent. `test_report.py::test_readable_default_file_keeps_its_policy_and_has_no_absence_notice`
- When my default config file is rejected, I see gaps and no default observations. `test_report.py::test_rejected_defaults_never_gain_default_observations`
- When I select config or rules files myself, a missing config file never gets defaults. `test_report.py::test_explicit_selection_never_assesses_the_absent_default`
- My saved rule findings and gaps stay visible alongside the assessment of the absent config file. `test_report.py::test_default_rules_findings_and_gaps_survive_config_absence`

## [share_without_exposing_secrets] I can share the report without exposing my commands, addresses, tokens or environment values. Names appear as I wrote them, and the report reminds me to check them first.
Issue: https://github.com/chalkbadger/stay-safe/issues/1
Tests: [tests/share_without_exposing_secrets/](../tests/share_without_exposing_secrets/)

- My private config values, such as commands, addresses, tokens and environment values, appear in neither format, nor in the saved page or the `--save` summary. `test_report.py::test_report_excludes_private_values`
- No word of my saved approvals appears in the Markdown or JSON report, the saved page or the `--save` summary, except a first word on the program list in the `lists_commands_codex_stops_asking_about` claim. `test_rules_file.py::test_no_saved_approval_word_other_than_a_listed_first_word_appears_in_any_output`
- A config name such as `acme-merger` is shown as I wrote it, in both formats. `test_report.py::test_names_are_shown_as_written_and_the_report_says_to_check_them`
- The JSON scope and the Markdown section on what the report can't see both tell me config names are shown as written and should be checked before I share. `test_report.py::test_names_are_shown_as_written_and_the_report_says_to_check_them`
- A name of mine containing HTML characters such as `<` or `&`, or shaped like a Markdown link to a `javascript:` or `data:` URL, is shown on the saved page as I wrote it, not as markup or a link. `test_page.py::test_names_with_html_characters_are_shown_as_written_not_as_markup`
- In Markdown, a file found automatically is named `~/.codex/...`, or `$CODEX_HOME/...` when `CODEX_HOME` is set, and never by my expanded folder; a file I pass keeps its `config-N` or `rules-N` label. `test_report.py::test_found_files_are_named_by_where_codex_keeps_them_without_the_users_folder`
- When no default config file is found, I don't see the expanded folder stay-safe looked in. `test_report.py::test_absent_default_report_is_repeatable_without_disclosing_its_path`
- When my input has a gap, the report shows neither its private text nor raw error messages. `test_report.py::test_malformed_and_private_identifiers_never_echo_raw_input`
- A rules line of mine with an invalid escape, such as `\q`, is reported as a gap without its text or the raw error. `test_rules_file.py::test_invalid_json_escape_does_not_disclose_private_source`

## [nothing_in_my_setup_changes] Running stay-safe changes nothing in my setup. With `--save`, it writes one report file in its own folder and nothing else.
Issue: https://github.com/chalkbadger/stay-safe/issues/1
Tests: [tests/nothing_in_my_setup_changes/](../tests/nothing_in_my_setup_changes/)

- The code I run has no way to start programs, open connections or run my input as code, and only its save step can write files. `test_read_only_source.py::test_package_source_uses_only_allowed_imports_calls_and_os_names`
- I run the report, with or without `--save`, and each file I select is unchanged, including its permissions and modification time. `test_inspected_setup.py::test_inspection_leaves_inspected_files_unchanged_and_adds_no_files`
- With the stay-safe checkout outside my home and working folders, I run the report, with or without `--save`, and no files are added to either. `test_inspected_setup.py::test_inspection_leaves_inspected_files_unchanged_and_adds_no_files`
- My run without `--save` adds or changes no file, in the checkout or elsewhere, apart from Python's own bytecode cache (`stay_safe/__pycache__`), which the check turns off; with `--save` it adds or replaces only `stay-safe-report.html` in the checkout, replacing a symlink there rather than writing through it. `test_save.py::test_without_save_nothing_is_written_and_with_save_only_the_report_is_added_or_replaced`
- With `--save`, I see the same Markdown report as without it, then one last line with a command that opens the saved page (`open` on macOS, `xdg-open` elsewhere) whose quoted path a shell reads back as the page's path, even with spaces, quotes, `$` or backticks in it, and the run exits as the Markdown report would. `test_save.py::test_save_prints_the_markdown_report_then_a_command_that_opens_the_saved_page`
- I open the saved page and see the Markdown report's words, links, bold, italic and code text, in the same order. `test_page.py::test_saved_page_shows_the_markdown_reports_words_links_bold_and_code_text`
- The saved page contains only document, text and https link elements, so it has no script and nothing that makes my browser load anything from outside the file. `test_page.py::test_saved_page_has_no_script_and_loads_nothing_from_outside_the_file`
- When the page can't be saved, I see one line saying so on standard error, then the Markdown report, and the run exits `2` exactly when there are gaps. `test_save.py::test_when_the_report_cannot_be_written_one_line_says_so_then_the_markdown_report_follows`
- `--save` with `--format json` gives me no report, writes nothing, says the two can't be combined, and exits `2`; `--help` says so too. `test_save.py::test_save_with_json_format_is_rejected_without_a_report_or_file`

## [anyone_can_recheck_a_report] Someone I share the report with sees the exact stay-safe version that made it, and gets the same report when they run that version on the same files.
Issue: https://github.com/chalkbadger/stay-safe/issues/4
Tests: [tests/anyone_can_recheck_a_report/](../tests/anyone_can_recheck_a_report/)

- I read the report and see the commit it ran from, with its rules and evidence linked at that commit. `test_revision.py::test_reports_show_expected_commit_hashes_and_evidence_in_both_formats`
- The JSON report and the full scope in `docs/report.md`, which the Markdown report links at its commit, tell me it checks neither local edits nor whether the commit is on GitHub. `test_revision.py::test_reports_show_expected_commit_hashes_and_evidence_in_both_formats`
- I run the report twice on the same files and get the same output in both formats (Markdown and JSON), and the same saved page with `--save`. `test_repeatable.py::test_report_is_deterministic`
- I run it from an unzipped `git archive` zip, and the report names the archived commit as a release archive and links its rules, meanings and incidents at that commit, with no revision gap. `test_release_archive.py::test_unzipped_archive_reports_archived_commit_and_links_in_both_formats`
- In every supported checkout layout I run from, the reported commit matches `git rev-parse HEAD`. `test_layouts.py::test_each_layout_reports_its_own_commit_as_git_does`
- When I run from a Git checkout, including a `git worktree` whose `.git` is a file, the commit comes from Git, never from the revision file. `test_release_archive.py::test_git_checkout_uses_git_and_ignores_revision_file`
- When I run from a checkout with Windows line endings, I still see its commit and links. `test_revision.py::test_clean_crlf_clone_retains_revision_and_cli_links`
- I edit a source file and its hash changes, but the reported commit doesn't. `test_revision.py::test_local_edits_change_hashes_but_never_claim_a_clean_checkout`
- If the commit can't be determined, the report tells me so, leaves out the links, keeps the findings and exits `2`. `test_revision.py::test_unknown_revision_cli_withholds_links_and_preserves_findings`
- When I run without Git metadata and the revision file still holds the placeholder, is missing or holds anything but one full commit hash, I see "revision unknown" and never the file's contents. `test_release_archive.py::test_placeholder_or_malformed_revision_file_gives_revision_unknown`
- When my Git metadata is malformed, I see "revision unknown" and exit `2`, and never the file's contents. `test_invalid_metadata.py::test_rejected_names_and_bad_values_report_revision_unknown_without_contents`
- My branch names are accepted or rejected exactly as `git check-ref-format` decides. `test_ref_names.py::test_ref_names_are_accepted_exactly_as_git_check_ref_format_decides`
- When one of stay-safe's source files is missing, I see a gap naming it; the findings stay and the run exits `2`. `test_fingerprints.py::test_missing_fingerprinted_file_is_a_named_gap_and_findings_remain`

## [challenge_a_wrong_finding] If I think a finding is wrong, the challenge form asks which finding and why; attaching the full report is optional.
Issue: https://github.com/chalkbadger/stay-safe/issues/5
Tests: [tests/challenge_a_wrong_finding/](../tests/challenge_a_wrong_finding/)

- I open the challenge form and find exactly five labeled multiline fields with valid ids, all required except the full report. `test_form.py::test_form_declares_the_challenge_record_as_required_and_the_report_as_optional`

## [explains_incomplete_inspection] When my report has gaps, I see why the run exits 2.
Issue: https://github.com/chalkbadger/stay-safe/issues/18
Tests: [tests/explains_incomplete_inspection/](../tests/explains_incomplete_inspection/)

- I get the fixed exit-2 explanation on stderr for Markdown, JSON and saved reports with gaps. `test_status.py::test_reports_with_gaps_explain_exit_two_on_stderr_only`
- The report stays on stdout without the explanation, and JSON output remains one parseable document. `test_status.py::test_reports_with_gaps_explain_exit_two_on_stderr_only`
- Neither output stream reveals the private input name or value. `test_status.py::test_reports_with_gaps_explain_exit_two_on_stderr_only`
- I get no incomplete-inspection explanation for a complete report or an invalid invocation that produces no report. `test_status.py::test_complete_reports_and_invalid_arguments_do_not_get_the_explanation`
- The report is flushed to stdout before the explanation is written to stderr. `test_status.py::test_report_is_flushed_before_the_explanation_is_written`

## [explains_save_path] I pass a path to `--save`, and the error tells me how to save the report.
Issue: https://github.com/chalkbadger/stay-safe/issues/19
Tests: [tests/explains_save_path/](../tests/explains_save_path/)

- I supply a destination after `--save`, and the command exits 2 with the fixed explanation and no report. `test_arguments.py::test_save_path_explains_the_supported_form_without_echoing_the_path`
- My supplied destination appears in neither output stream. `test_arguments.py::test_save_path_explains_the_supported_form_without_echoing_the_path`
- The mistaken invocation stops before discovery, inspection or saving. `test_arguments.py::test_save_path_stops_before_discovery_inspection_or_save`
- Other invalid invocations retain the generic error. `test_arguments.py::test_other_invalid_arguments_keep_the_generic_message`

## [find_feedback] After reading a report or encountering a command error, I can find a form to report a problem or suggest an idea without sharing private files.
Issue: https://github.com/chalkbadger/stay-safe/issues/53
Tests: [tests/find_feedback/](../tests/find_feedback/)

- Readable reports link to feedback once; JSON remains a report document and inspection gaps do not add another link. `test_feedback.py::test_reports_link_once_and_json_stays_a_document`
- Argument errors show the feedback destination without echoing private arguments; help exits normally. `test_feedback.py::test_argument_errors_link_once_without_echoing_private_arguments`
- Error and idea forms request relevant details, make reports optional and give sharing guidance. `test_feedback.py::test_error_and_idea_forms_collect_relevant_details_without_requiring_reports`
