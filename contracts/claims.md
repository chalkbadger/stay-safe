# stay-safe claims

## [see_every_connection_and_setting] I see supported settings and saved approvals from my files, with defaults identified.
Issue: https://github.com/chalkbadger/stay-safe/issues/13
Tests: [tests/see_every_connection_and_setting/](../tests/see_every_connection_and_setting/)

- I inspect known settings and see the expected entries and findings. `test_config.py::test_known_configuration_has_exact_named_catalog_and_risks`
- I turn Apps off in one file and see why its named apps give no warnings, while another file keeps its own warnings. `test_config.py::test_named_apps_respect_the_apps_switch_in_each_file`
- I inspect several files and each keeps its own settings and identities. `test_config.py::test_files_remain_independent_and_identity_preserves_dotted_name`
- I have no default config file and see the assessed defaults and remaining gaps. `test_defaults.py::test_both_formats_report_cited_defaults_and_retained_gaps`
- I inspect saved approvals and see each supported record identified separately. `test_saved_rules.py::test_saved_lines_keep_line_numbers_part_counts_and_broad_labels`

## [understand_inspection_limits] I can tell what the report establishes and what needs further checking.
Issue: https://github.com/chalkbadger/stay-safe/issues/97
Tests: [tests/understand_inspection_limits/](../tests/understand_inspection_limits/)

- I pass a cleared file to `--rules` and the introduction names it and confirms it contains no saved approvals. `test_scope.py::test_selected_rules_file_is_named_when_it_has_no_saved_approvals`
- I follow the report's scope link and see its limits on live connections, effective permissions and other unverified behavior. `test_scope.py::test_the_full_scope_holds_every_scope_line`
- I supply an unreadable file beside a readable one and see the failure without losing valid findings. `test_selected_config_failures.py::test_each_failure_has_a_distinct_private_safe_reason_and_action_in_both_formats`
- I get an incomplete report and an explanation of exit status 2. `test_status.py::test_reports_with_gaps_explain_exit_two_on_stderr_only`
- I see which AWS credential commands were left unchecked even when the provider is selected elsewhere. `test_status.py::test_aws_credentials_name_each_unchecked_command`

## [each_risk_shows_its_cause] Each warning identifies the setting and evidence behind it.
Issue: https://github.com/chalkbadger/stay-safe/issues/13
Tests: [tests/each_risk_shows_its_cause/](../tests/each_risk_shows_its_cause/)

- I see the expected warnings tied to their settings and reported incidents. `test_report.py::test_cli_risks_have_expected_entries_incidents_and_status_in_both_formats`
- I change command or sandbox settings and get warnings only when their conditions apply. `test_conditions.py::test_command_prompt_and_filesystem_rules_have_independent_positive_and_negative_cases`
- I lose an incident citation and see the gap while the findings remain. `test_report.py::test_cli_reports_missing_incident_citation_and_preserves_safe_data`

## [findings_say_what_to_do] Each finding explains what is wrong and what I can do.
Issue: https://github.com/chalkbadger/stay-safe/issues/12
Tests: [tests/findings_say_what_to_do/](../tests/findings_say_what_to_do/)

- I get advice for each finding, including the setting to change and stricter options where supported. `test_what_to_do.py::test_each_finding_gives_lower_friction_then_stricter_option_then_how_to_change_it`
- I inspect different sandbox settings and the advice never suggests a weaker sandbox. `test_what_to_do.py::test_commands_advice_never_loosens_the_configured_sandbox`
- I select a permission profile in one file and can follow the approval finding and sandbox gap advice without replacing it. `test_what_to_do.py::test_profile_in_either_file_preserves_approval_and_gap_advice`
- I see that configured approvals do not establish what Codex will allow. `test_what_to_do.py::test_shared_note_keeps_approval_outcomes_unassessed_for_each_policy`

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

- I see every finding once in the documented order, with matching details. `test_overview.py::test_every_finding_appears_once_in_policy_order_with_matching_details`
- I follow identical titles from different files and reach the correct details. `test_overview.py::test_two_files_with_the_same_title_keep_their_labels_and_each_link_reaches_its_own_finding`
- I get no findings and still see the incomplete checks and warning against assuming safety. `test_overview.py::test_no_findings_does_not_imply_safety_or_hide_incomplete_checks`
- I read the terminal report without Markdown markers, with source links available. `test_terminal.py::test_terminal_default_is_plain_with_links_and_private_values_withheld`

## [share_without_exposing_secrets] My report withholds commands, addresses, tokens and environment values; names need checking before sharing.
Issue: https://github.com/chalkbadger/stay-safe/issues/1
Tests: [tests/share_without_exposing_secrets/](../tests/share_without_exposing_secrets/)

- I inspect files containing private values and none appear in the report. `test_report.py::test_report_excludes_private_values`
- I see names as written, with a reminder to check them before sharing. `test_report.py::test_names_are_shown_as_written_and_the_report_says_to_check_them`
- I use names containing markup and the saved page shows text, not executable content or unintended links. `test_page.py::test_names_with_html_characters_are_shown_as_written_not_as_markup`

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

## [follow_rule_evidence] I can follow a finding to its rule's evidence and challenges.
Issue: https://github.com/chalkbadger/stay-safe/issues/100
Tests: [tests/follow_rule_evidence/](../tests/follow_rule_evidence/)

- I find each rule's section with matching setting rows and incident references and valid local targets and GitHub search and form URLs. `test_index.py::test_index_matches_rules_incidents_and_resolvable_links`
- I see each readable finding's rule linked at the report revision, or plain text when that revision is unknown. `test_index.py::test_readable_rule_links_follow_revision_and_unknown_stays_plain`
- I find the index's search label configured on the challenge form, with the rule ID directed to its required finding field. `test_index.py::test_index_matches_rules_incidents_and_resolvable_links`
