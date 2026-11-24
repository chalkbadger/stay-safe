# stay-safe claims

## [see_every_connection_and_setting] I see supported settings and saved approvals from my files, with defaults identified.
Issue: https://github.com/chalkbadger/stay-safe/issues/13
Tests: [tests/see_every_connection_and_setting/](../tests/see_every_connection_and_setting/)

- I inspect known settings and see the expected entries and findings. `test_config.py::test_known_configuration_has_exact_named_catalog_and_risks`
- I turn Apps off in one file and see why its named apps give no warnings, while another file keeps its own warnings. `test_config.py::test_named_apps_respect_the_apps_switch_in_each_file`
- I inspect several files and each keeps its own settings and identities. `test_config.py::test_files_remain_independent_and_identity_preserves_dotted_name`
- I have no default config file and see the assessed defaults and remaining gaps. `test_defaults.py::test_both_formats_report_cited_defaults_and_retained_gaps`
- I inspect saved approvals and see each supported record identified separately. `test_saved_rules.py::test_saved_lines_keep_line_numbers_part_counts_and_broad_labels`
- I let commands in `workspace-write` mode write to extra folders and see that setting under "Not checked", without the folders' paths. `test_unlisted_settings.py::test_active_writable_roots_give_a_gap_and_no_entry_or_risk`
- I see on the ChatGPT Apps connection whether apps my file doesn't name are off and where their `destructive_enabled` comes from. `test_chatgpt_apps.py::test_chatgpt_apps_connection_says_whether_apps_not_named_can_change_data`
- My Codex folder has skills in `skills` and an `environments.toml` file, and I see each under "Not checked" without their contents. `test_skills_and_environments.py::test_skills_and_environments_toml_each_give_their_own_gap`
- My Codex folder reaches a skill folder by a short route and by a longer link, and I still see the skills under "Not checked". `test_skills_and_environments.py::test_a_skill_in_the_skills_folder_gives_the_gap_and_exits_2`
- My Codex folder has an `environments.toml` that is a folder, and I see that under "Not checked". `test_skills_and_environments.py::test_environments_toml_that_is_not_a_file_gives_its_own_gap`
- My skills folder is reached through a link I can't open, and I see that stay-safe could not check it. `test_skills_and_environments.py::test_permission_error_on_a_linked_skills_folder_reports_failure`
- I see which named App has an invalid `open_world_enabled` boolean, and I can still review the other App's configured tools. `test_named_app_validation.py::test_invalid_open_world_flag_names_the_app_and_preserves_its_sibling`
- When I quote an App boolean, both the load error and the fix tell me to write the boolean without quotes. `test_named_app_validation.py::test_markdown_explains_how_to_correct_a_quoted_boolean`
- A malformed tool flag in a named App or its default template tells me Codex cannot load the file, and I can still review another App's configured settings. `test_named_app_validation.py::test_both_flags_reject_the_file_and_preserve_independent_app_settings`
- I see why a named App is off alongside its App flag validation error. `test_named_app_validation.py::test_invalid_flag_on_a_disabled_app_keeps_the_off_reason_and_only_the_validation_gap`
- I give a named App an invalid tool setting, and both reports name the field and drop the affected App's tool risks while preserving a valid sibling App's configured findings. `test_named_app_validation.py::test_app_tool_load_errors_name_the_field_in_both_formats`
- I set a tool flag to an integer on an App or its tool and see a boolean load error. `test_named_app_validation.py::test_app_and_tool_flags_reject_integer_zero_and_one`
- I set any supported approval mode on an App or its tool and see the selected mode in the catalog. `test_named_app_validation.py::test_app_and_tool_accept_each_codex_approval_mode`
- I give a tool with a withheld name an invalid setting and see the load error or the configured off reason on the other tools in its App. `test_named_app_validation.py::test_withheld_invalid_tool_marks_all_public_tools_unloadable_unless_apps_are_off`
- I give the default template an invalid approval mode and see the error on the template alongside a named App's explicit override. `test_named_app_validation.py::test_invalid_default_mode_is_attributed_to_its_declaration_and_an_independent_app_can_override_it`
- I see a disabled App's malformed tool setting even when the report withholds the tool's name. `test_named_app_validation.py::test_disabled_app_reports_a_malformed_setting_when_its_tool_name_is_withheld`
- I give `apps._default` an invalid value and see that the ChatGPT Apps connection says unknown for apps my file doesn't name, next to the invalid-value gap. `test_chatgpt_apps.py::test_invalid_template_leaves_apps_not_named_unknown_and_keeps_its_gap`
- I set each Claude Code permission mode and see it listed, with `auto` under "Not checked". `test_claude_settings.py::test_each_permission_mode_is_listed_and_only_bypass_runs_without_asking`
- I leave Claude Code's permission mode out or give it an invalid value and see that under "Not checked", not a guessed mode. `test_claude_settings.py::test_absent_and_invalid_modes_are_gaps_not_guesses`
- I allow shell commands and web fetches in Claude Code and see each rule and the sandbox setting, without the rules' contents. `test_claude_settings.py::test_allow_rules_for_shell_commands_and_web_fetches`
- I add Claude Code ask or deny rules and settings stay-safe doesn't read, and see them under "Not checked" without their values. `test_claude_settings.py::test_ask_and_deny_rules_and_uncovered_settings_are_gaps`
- My Claude Code settings file is invalid, a symlink or missing, and I see that under "Not checked". `test_claude_settings.py::test_unreadable_files_give_a_gap_and_no_entries`
- I see which Claude Code files were read even when every field in a parsed file is invalid. `test_claude_settings.py::test_read_summary_counts_parsed_files_even_when_all_fields_are_invalid`
- I supply a malformed Claude permission or sandbox field and see the field named as a gap. `test_claude_settings.py::test_malformed_permission_lists_and_sandbox_fields_name_the_field`
- I turn on sandboxing and see whether the file sets automatic Bash approval or leaves it to a version-dependent default. `test_claude_settings.py::test_sandbox_approval_is_version_dependent_only_when_enabled_and_unset`
- I configure only an ask rule and see that its matches were not checked. `test_claude_settings.py::test_ask_only_rules_name_the_unchecked_list_without_a_finding`

## [understand_inspection_limits] I can tell what the report establishes and what needs further checking.
Issue: https://github.com/chalkbadger/stay-safe/issues/97
Tests: [tests/understand_inspection_limits/](../tests/understand_inspection_limits/)

- I pass a cleared file to `--rules` and the introduction names it and confirms it contains no saved approvals. `test_scope.py::test_selected_rules_file_is_named_when_it_has_no_saved_approvals`
- I follow the report's scope link and see its limits on live connections, effective permissions and other unverified behavior. `test_scope.py::test_the_full_scope_holds_every_scope_line`
- I supply an unreadable file beside a readable one and see the failure without losing valid findings. `test_selected_config_failures.py::test_each_failure_has_a_distinct_private_safe_reason_and_action_in_both_formats`
- I get an incomplete report and an explanation of exit status 2. `test_status.py::test_reports_with_gaps_explain_exit_two_on_stderr_only`
- I give a stdio server an HTTP header helper and see why Codex rejects the setting and how to fix it. `test_status.py::test_stdio_header_helper_names_the_rejected_setting`
- I see which AWS credential commands were left unchecked even when the provider is selected elsewhere. `test_status.py::test_aws_credentials_name_each_unchecked_command`

## [each_risk_shows_its_cause] Each warning identifies the setting and evidence behind it.
Issue: https://github.com/chalkbadger/stay-safe/issues/13
Tests: [tests/each_risk_shows_its_cause/](../tests/each_risk_shows_its_cause/)

- I see the expected warnings tied to their settings and reported incidents. `test_report.py::test_cli_risks_have_expected_entries_incidents_and_status_in_both_formats`
- I change command or sandbox settings and get warnings only when their conditions apply. `test_conditions.py::test_command_prompt_and_filesystem_rules_have_independent_positive_and_negative_cases`
- I set a hook whose only command is its Windows command and see that it can start a program. `test_hooks.py::test_windows_command_alone_reports_program`
- I combine `danger-full-access` with `on-request` or `never` and see that ordinary commands, or MCP and app tool calls, can run without asking. `test_conditions.py::test_full_access_lets_on_request_commands_and_never_tool_calls_run_without_asking`
- I lose an incident citation and see the gap while the findings remain. `test_report.py::test_cli_reports_missing_incident_citation_and_preserves_safe_data`
- I set an approval mode or `destructive_enabled = true` in `apps._default` and see its risk once, on the template, for apps my file doesn't name. `test_single_attribution.py::test_app_template_approval_applies_to_unnamed_apps_and_inherited_risks_to_enabled_named_apps`
- I set Claude Code's `bypassPermissions`, or allow every shell command or web fetch, and see each warning tied to its setting and incidents. `test_claude_risks.py::test_each_claude_code_warning_names_its_rule_setting_and_incidents`
- I see which Claude Code versions and file scopes limit the bypass setting in both JSON and Markdown. `test_claude_risks.py::test_bypass_finding_explains_file_scope_and_version_in_json_and_markdown`
- I see competing ask or deny rules beside the allowance in the overview, details and JSON. `test_claude_risks.py::test_competing_permission_rules_are_visible_on_each_affected_finding`

## [findings_say_what_to_do] Each finding explains what is wrong and what I can do.
Issue: https://github.com/chalkbadger/stay-safe/issues/12
Tests: [tests/findings_say_what_to_do/](../tests/findings_say_what_to_do/)

- I get advice for each finding, including the setting to change and stricter options where supported. `test_what_to_do.py::test_each_finding_gives_lower_friction_then_stricter_option_then_how_to_change_it`
- I inspect different sandbox settings with `never` and the advice never suggests a weaker sandbox, and says what `on-request` adds and that ordinary commands can still run without asking. `test_what_to_do.py::test_commands_advice_never_loosens_the_configured_sandbox`
- I select a permission profile in one file and can follow the approval finding and sandbox gap advice without replacing it. `test_what_to_do.py::test_profile_in_either_file_preserves_approval_and_gap_advice`
- I see that configured approvals do not establish what Codex will allow. `test_what_to_do.py::test_shared_note_keeps_approval_outcomes_unassessed_for_each_policy`
- I use `danger-full-access` with `on-request` or `never` and the advice tells me to change the sandbox. `test_what_to_do.py::test_full_access_findings_on_the_approval_policy_say_to_change_the_sandbox`
- I follow the sandbox advice in a file with extra writable folders and see that the advice and the new report both tell me to review `writable_roots`. `test_what_to_do.py::test_following_the_sandbox_advice_with_writable_roots_leaves_them_to_review`
- I combine a `danger-full-access` file with another file that sets `read-only`, and every finding on the first file suggests `read-only`; with `on-request`, it says ordinary commands can still run without asking. `test_what_to_do.py::test_full_access_advice_matches_the_read_only_edit_when_another_file_sets_read_only`
- I get a finding from `apps._default` and its advice says it covers apps my file doesn't name. `test_what_to_do.py::test_app_template_findings_cover_apps_the_file_does_not_name`
- I get advice for each Claude Code finding, naming the setting to change and how to check it. `test_claude_advice.py::test_each_claude_code_finding_says_what_to_change_where_and_how_to_check`
- I see how to remove broad WebFetch access without adding sandbox hosts, with the versions that honor a domain wildcard. `test_claude_advice.py::test_all_domain_rule_gets_broad_advice_and_distinct_evidence`
- I leave bypass mode in one Claude file and see which sandboxed Bash approvals can survive the edit. `test_claude_advice.py::test_switching_mode_explains_the_sandbox_approval_left_in_each_file`
- I read the advice for leaving auto mode and see which sandboxed Bash commands can still run without a prompt. `test_claude_advice.py::test_auto_mode_advice_identifies_bash_auto_approval_that_survives_the_edit`
- I see that the auto-mode edit applies to user settings when I select a Claude Code settings file. `test_claude_advice.py::test_auto_mode_edit_is_conditional_on_user_settings`
- I run the environment Check with a variable whose value spans several lines and see only variable names. `test_what_to_do.py::test_environment_check_lists_variable_names_without_values`

## [runs_without_a_coding_agent] I can run stay-safe without an agent and get guidance if my Python is too old.
Issue: https://github.com/chalkbadger/stay-safe/issues/3
Tests: [tests/runs_without_a_coding_agent/](../tests/runs_without_a_coding_agent/)

- I run the README's documented command and get the expected report. `test_readme.py::test_documented_clone_commands_run_the_diagnostic`
- I use an older Python and see an available supported command. `test_python_entry.py::test_too_old_python_names_the_newest_python_on_the_path_and_exits_2`
- I have no supported Python command and get setup guidance. `test_python_entry.py::test_too_old_python_without_a_recognized_command_links_setup_and_exits_2`
- I run the installed package and get the checkout's report, with saving in my working directory. `test_package.py::test_wheel_and_sdist_keep_report_resources_revision_and_safe_current_directory_save`

## [overview_lists_findings_first] I can scan the report and reach each finding's details.
Issue: https://github.com/chalkbadger/stay-safe/issues/82
Tests: [tests/overview_lists_findings_first/](../tests/overview_lists_findings_first/)

- I see the same two numbered lists in the Claude Markdown overview and saved page. `test_overview.py::test_claude_finding_groups_keep_numbered_lists_in_markdown_and_html`
- I see every finding once in the documented order, with matching details. `test_overview.py::test_every_finding_appears_once_in_policy_order_with_matching_details`
- I see how many findings concern network access, credentials, or connected tools when that group appears. `test_overview.py::test_network_credentials_and_tools_group_uses_topic_and_count`
- I follow identical titles from different files and reach the correct details. `test_overview.py::test_two_files_with_the_same_title_keep_their_labels_and_each_link_reaches_its_own_finding`
- I get no findings and still see the incomplete checks and warning against assuming safety. `test_overview.py::test_no_findings_does_not_imply_safety_or_hide_incomplete_checks`
- I read the terminal report without Markdown markers, with source links available. `test_terminal.py::test_terminal_default_is_plain_with_links_and_private_values_withheld`

## [share_without_exposing_secrets] My report withholds commands, addresses, tokens and environment values; names need checking before sharing.
Issue: https://github.com/chalkbadger/stay-safe/issues/1
Tests: [tests/share_without_exposing_secrets/](../tests/share_without_exposing_secrets/)

- I inspect files containing private values and none appear in the report. `test_report.py::test_report_excludes_private_values`
- I see names as written, with a reminder to check them before sharing. `test_report.py::test_names_are_shown_as_written_and_the_report_says_to_check_them`
- I use names containing markup and the saved page shows text, not executable content or unintended links. `test_page.py::test_names_with_html_characters_are_shown_as_written_not_as_markup`
- I inspect Claude Code settings containing commands, domains and environment values, and none appear in the report. `test_claude_report.py::test_claude_code_report_excludes_private_values`
- The program names my report may show from a saved approval are exactly the list in the Codex meanings document. `test_rules_file.py::test_shown_program_names_are_the_list_in_the_meanings_document`

## [nothing_in_my_setup_changes] Running stay-safe leaves my setup unchanged; saving writes only the report.
Issue: https://github.com/chalkbadger/stay-safe/issues/1
Tests: [tests/nothing_in_my_setup_changes/](../tests/nothing_in_my_setup_changes/)

- I run the diagnostic and my inspected files remain unchanged. `test_inspected_setup.py::test_inspection_leaves_inspected_files_unchanged_and_adds_no_files`
- I save a report and only its destination is added or replaced, without following a destination symlink. `test_save.py::test_without_save_nothing_is_written_and_with_save_only_the_report_is_added_or_replaced`
- I get a save failure and still receive the report, without a false success message. `test_save.py::test_when_the_report_cannot_be_written_one_line_says_so_then_the_markdown_report_follows`
- I open the saved page and it executes no script or external resource request. `test_page.py::test_saved_page_has_no_script_and_loads_nothing_from_outside_the_file`

## [anyone_can_recheck_a_report] I can identify the code that made a report and reproduce it from the same files.
Issue: https://github.com/chalkbadger/stay-safe/issues/4
Tests: [tests/anyone_can_recheck_a_report/](../tests/anyone_can_recheck_a_report/)

- I see the source revision, with evidence links fixed to that revision. `test_revision.py::test_reports_show_expected_commit_hashes_and_evidence_in_both_formats`
- I rerun the same code on the same files and get the same report. `test_repeatable.py::test_report_is_deterministic`
- I edit source files and their fingerprints change without claiming a new commit. `test_revision.py::test_local_edits_change_hashes_but_never_claim_a_clean_checkout`
- I run without an identifiable revision and see that gap instead of unverified source links. `test_revision.py::test_unknown_revision_cli_withholds_links_and_preserves_findings`

## [find_feedback] I can report a problem, suggest an idea or challenge a finding without sharing private files.
Issue: https://github.com/chalkbadger/stay-safe/issues/53
Tests: [tests/find_feedback/](../tests/find_feedback/)

- I find feedback links in readable reports while JSON stays machine-readable. `test_feedback.py::test_reports_link_once_and_json_stays_a_document`
- I get an argument error and can find feedback without exposing private arguments. `test_feedback.py::test_argument_errors_link_once_without_echoing_private_arguments`
- I can provide the context for a problem, idea or challenge without attaching a report. `test_forms.py::test_forms_collect_context_without_requiring_a_report`
- I see how to share a warning containing a private name in the field that asks for the finding. `test_forms.py::test_finding_field_explains_how_to_share_a_warning_with_private_names`

## [follow_rule_evidence] I can follow a finding to its rule's evidence and challenges.
Issue: https://github.com/chalkbadger/stay-safe/issues/100
Tests: [tests/follow_rule_evidence/](../tests/follow_rule_evidence/)

- I find each rule's section with matching setting rows and incident references and valid local targets and GitHub search and form URLs. `test_index.py::test_index_matches_rules_incidents_and_resolvable_links`
- I follow the saved-approval finding and its rule index to the Codex approval and Claude Code credential reports. `test_index.py::test_saved_approval_links_to_both_incident_entries_in_the_report_and_index`
- I see each readable finding's rule linked at the report revision, or plain text when that revision is unknown. `test_index.py::test_readable_rule_links_follow_revision_and_unknown_stays_plain`
- I find the index's search label configured on the challenge form, with the rule ID directed to its required finding field. `test_index.py::test_index_matches_rules_incidents_and_resolvable_links`
- I read what the `network_access` and `commands_without_prompts` citations support, with links to the incidents, rule, and sources the note names. `test_index.py::test_index_matches_rules_incidents_and_resolvable_links`

## [check_every_installed_agent] I run one command and see a report for each coding agent I have installed, or choose one with `--agent`.
Issue: https://github.com/chalkbadger/stay-safe/issues/163
Tests: [tests/check_every_installed_agent/](../tests/check_every_installed_agent/)

- I have Codex and Claude Code folders and one run reports both. `test_agents.py::test_default_run_reports_every_installed_agent`
- I have only a Claude Code home and get only its report, even with account and extension files present. `test_agents.py::test_claude_only_home_keeps_just_its_report_even_with_account_and_extensions`
- I configure a missing or invalid Claude folder and still see my Codex findings beside the Claude gap. `test_agents.py::test_bad_configured_claude_home_keeps_codex_findings_and_reports_gap`
- I have an inaccessible Claude folder and see its gap alongside my Codex findings. `test_agents.py::test_inaccessible_claude_directory_keeps_the_other_report`
- I have neither agent folder and see the Codex default assessment. `test_agents.py::test_neither_home_keeps_codex_defaults_and_any_explicit_claude_gap`
- I select a Claude account or credential file as settings or saved rules and see it excluded before it is opened. `test_agents.py::test_selected_account_file_never_reaches_the_opener`
- I have no Claude Code folder and see the same report as `--agent codex`. `test_agents.py::test_without_a_claude_folder_the_default_run_is_the_codex_report`
- I choose `--agent claude` and see only the Claude Code report. `test_agents.py::test_agent_claude_reports_only_claude_code`
- I set `CLAUDE_CONFIG_DIR` and see the settings in that folder. `test_agents.py::test_claude_config_dir_selects_the_claude_folder`
- I choose `--agent claude` without a Claude Code folder and see that nothing was inspected. `test_agents.py::test_agent_claude_without_its_folder_says_nothing_was_inspected`
- I pass a file with both agents chosen, or a rules file for Claude Code, and am told what to choose. `test_agents.py::test_selected_files_need_exactly_one_agent_and_rules_need_codex`

## [export_private_sarif] I can send findings and unchecked items to a SARIF consumer while keeping my input files private.
Issue: https://github.com/chalkbadger/stay-safe/issues/204
Tests: [tests/export_private_sarif/](../tests/export_private_sarif/)

- An empty complete inspection and an incomplete one with only a gap produce distinguishable SARIF 2.1.0 reports and exit statuses. `test_sarif.py::test_complete_and_gaps_only_reports_distinguish_an_empty_result_from_incomplete_inspection`
- The report preserves findings, rule explanations, logical entry IDs and available pinned rule links, including when the revision is unknown. `test_sarif.py::test_each_risk_keeps_its_rule_explanation_and_logical_entry_and_each_gap_is_a_warning`
- Each agent's run contains only its own findings and unchecked items. `test_sarif.py::test_two_agents_keep_their_own_results_and_notifications`
- The export withholds private input paths, commands, arguments, addresses and environment and header values. `test_sarif.py::test_private_inputs_stay_withheld_throughout_the_document`
- Combining SARIF with saving exits 2 before emitting a report or creating a file. `test_sarif.py::test_save_rejects_sarif_before_writing_any_report`
