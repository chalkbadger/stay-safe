# Stay safe

Check your Codex files for risky settings. See what each warning means and what you can do about it.

stay-safe reads settings and saved approvals from files. Only some settings are covered. The report names the defaults it uses and the checks it could not complete. It does not test live connections or what Codex will actually allow. See the [full scope](docs/report.md#full-scope).

Here is a finding from a run on a [test configuration](tests/runs_without_a_coding_agent/sample.toml):

> **Your config turns off Codex's sandbox.** Commands Codex runs aren't limited to your project, so a mistaken command could damage files elsewhere on your computer.
>
> *How it has gone wrong:* Agents have deleted a home directory and wiped a whole drive with one mistaken delete command. [I1](https://github.com/chalkbadger/stay-safe/blob/v0.2.2/incidents.md#i1-home-directory-deleted-by-rm--rf), [I3](https://github.com/chalkbadger/stay-safe/blob/v0.2.2/incidents.md#i3-windows-drive-wiped) (reported, not verified).
>
> *What to do:* Set `sandbox_mode = "workspace-write"` (commands can write only in your workspace). Stricter: `sandbox_mode = "read-only"` (commands can't write files).
>
> *Change it:* near the top of the file, before any `[section]`, or ask Codex: "Edit `<config-1>` to set `sandbox_mode = "workspace-write"`; show only what you change."
>
> *Rule `unrestricted_filesystem` · setting `config-1:sandbox_mode` = `danger-full-access`*

It runs on Unix with Python 3.11 or newer. No agent is needed:

```sh
git clone --branch v0.2.2 https://github.com/chalkbadger/stay-safe.git
cd stay-safe
python3 -m stay_safe
```

Without Git, [download the v0.2.2 ZIP](https://github.com/chalkbadger/stay-safe/archive/refs/tags/v0.2.2.zip) and extract it. Open a terminal in the folder containing the extracted `stay-safe-0.2.2` folder, then run:

```sh
cd stay-safe-0.2.2
python3 -m stay_safe
```

By default it reads `~/.codex/config.toml` (`$CODEX_HOME/config.toml` when `CODEX_HOME` is set). [Usage](docs/usage.md) covers the inspected files, options, `--save` and exit status.

## Run with uv

If you already use [uv](https://docs.astral.sh/uv/), run the
[published 0.2.3 package](https://pypi.org/project/stay-safe/0.2.3/):

```sh
uvx --python 3.11 stay-safe@0.2.3
```

The command asks uv for Python 3.11, downloading it if needed; your system Python
stays unchanged. Add `--save` to save the HTML report in your current directory.
The clone and ZIP routes above do not require uv.

## Ask Codex

Paste this into Codex in the ChatGPT app or the CLI:

```text
Download stay-safe at tag v0.2.2 from https://github.com/chalkbadger/stay-safe into
a new temporary folder and run `python3 -m stay_safe` there. Show the report exactly
as printed, with its exit status, then your notes under "Agent's own report". Don't
open auth files or change files outside that folder. If the download fails, stop and
tell me.
```

In "Ask for approval" mode, approve the one internet request; never choose "don't ask
again". If Codex can't download, see [Usage](docs/usage.md#if-codex-cant-download).

## What it checks and what it can't see

- It reads the files listed in [Usage](docs/usage.md) and changes nothing in your setup.
- Each warning names its rule and the setting behind it, and links to [incident reports](incidents.md). [Reading the report](docs/report.md) explains each part.
- The [Codex meanings table](harnesses/codex.md) lists the settings it checks and the sources it uses. The report says when it used a default or could not complete a check.
- The [full scope](docs/report.md#full-scope) explains what it does not inspect.
- It shows server, app and tool names as written. Check those names before sharing the report.

## Challenge a finding

Use the [challenge form](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml) to submit the finding, revision, disputed claim and evidence.

## Why stay-safe exists

stay-safe is part of [chalkbadger](https://github.com/chalkbadger), which works on AI safety through adversarial peer review: every claim a tool makes should be open to challenge, with the evidence to check it. Each finding names the rule and the reported incidents behind it, each claim in [`contracts/claims.md`](contracts/claims.md) names the test that proves it, and anyone can [challenge a finding](#challenge-a-finding). stay-safe is built with [Wirth](https://github.com/chalkbadger/wirth), which keeps those claims and their tests together and reviews every change against them.

## Develop

Git is required for the development tests. Run `python3 check_tests.py` in a
development virtual environment. Before the first run, install the build tools
with `python3 -m pip install build "setuptools>=77" wheel`.
This checks test-folder package markers before running unittest discovery.

## Contribute

Share feedback, challenge a finding or propose a change through [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

References to an *archived* issue or PR point to the private repository that holds this project's earlier working history.
