To refine an issue, follow https://github.com/chalkbadger/wirth/blob/main/skills/wirth-refinement/SKILL.md.

To implement an issue, follow https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md#claims-and-evidence and record results under https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md#record-execution-results; for this repository's own PRs, also follow CONTRIBUTING.md#development-and-review.

To review a PR or address its Wirth findings, follow https://github.com/chalkbadger/wirth/blob/main/skills/wirth-review/SKILL.md.

A diagnostic request follows the local diagnostic instructions and does not invoke or fetch Wirth development workflows.
When asked for a stay-safe diagnostic, run `python3 -m stay_safe` from this checkout.
Use `--config FILE` for explicitly selected configuration files; repeat it to inspect
more files as separate snapshots. Do not open auth files, print raw configuration,
start configured commands, or probe services. Show the code's report unchanged,
including inspection gaps and nonzero status. Only that code output is shareable.
Put your explanations and any observations beyond the files in the conversation
under `Agent's own report`; never append them to the shared report. Report configured
values as configured values, not confirmed live connections or effective permissions.
