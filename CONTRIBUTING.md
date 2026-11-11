# Contributing to stay-safe

Follow the [shared participation policy](https://github.com/chalkbadger/wirth/blob/main/docs/participation.md)
for use, feedback, and upstream changes.

## Share feedback

Use the [challenge form](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml)
to dispute a finding or show a risk the report missed; you need no code to do it.
Open a [stay-safe issue](https://github.com/chalkbadger/stay-safe/issues/new/choose)
for a bug, question, or review. You can also use an issue to link findings or
records published elsewhere.

For evidence, start from the [contracts](contracts/), the
[Codex meanings table](harnesses/codex.md) with its sources, and the
[reported incidents](incidents.md). [The report shows configured values, not live
connections or effective permissions](docs/report.md#full-scope), so say whether
your evidence comes from a configuration file or from what Codex did.

## Propose a change

Open or identify the originating issue before implementing a change to stay-safe.
Use the [implementation workflow](https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md#claims-and-evidence)
for scope readiness, claims, and evidence, and
[development and review](#development-and-review) for the check commands and
published-revision verification record.

An addition stay-safe would maintain, such as a diagnostic for another coding agent,
[names its supported scope, how it was checked, and who maintains it](https://github.com/chalkbadger/wirth/blob/main/docs/participation.md#propose-bounded-changes).

The [review passes](https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md#review-passes)
guide review. The [publication rules](https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md#5-process)
govern attribution and corrections. [@weiks](https://github.com/weiks) is
stay-safe's accepting owner; [acceptance](https://github.com/chalkbadger/wirth/blob/main/docs/product.md#acceptance)
defines what the merge accepts.

## Development and review

Follow [the workflow](https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md).
Run the [development tests](README.md#develop) and
[`wirth validate`](https://github.com/chalkbadger/wirth/blob/main/docs/usage.md#local-contract-validation)
from the repository root.

For stay-safe's own PRs, a passing [check](.github/workflows/checks.yml) on the PR's
latest push replaces the
[verification procedure](https://github.com/chalkbadger/wirth/blob/main/docs/workflow.md#record-execution-results);
link that run in the PR. Follow the procedure when no check ran on the latest push,
for example while a fork PR waits for approval. In stay-safe's checkout, the
procedure's commands are the development tests and `wirth validate`.
